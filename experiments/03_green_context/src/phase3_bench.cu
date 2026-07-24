// Phase 3 v2 — green context (SM partitioning) on the two-kernel roofline,
// with IN-CONTEXT block-count saturation search and a widened size sweep
// (see prompts/03_green_context_v2.md). Measures ONE cell per invocation
// (test point x config x sm split); the outer sweep over test points /
// partition ratios / sizes lives in scripts/sweep.py, which reads Phase 1/2
// findings.json at run time (00_conventions.md: never fabricate numbers).
//
// Build: nvcc -O3 -arch=sm_87 -o phase3_bench phase3_bench.cu -lcuda
//
// Modes:
//   (default)          saturate blocks_k0/blocks_k1 in context for this cell
//                       (see "in-context block saturation search" below), then
//                       measure and print one CSV row (no header) to stdout
//   --verify           create the requested SM split, run the %smid probe kernel
//                       on each partition, report whether the observed SM id sets
//                       are disjoint (evidence partitioning took effect)
//   --check-api        print whether the green-context driver API is usable on
//                       this device/driver and exit (no measurement)
//
// In-context block saturation search (v2 Change 1 — prompts/03_green_context_v2.md):
// Phase 1's saturation_blocks_by_size (nearest-neighbor by size, single-kernel,
// 16-SM) is NEVER used as the final block count. It is only a SEED / lower bound
// for a local search run independently for THIS cell's config and SM split:
//   - lower_bound = max(seed_from_phase1, kBlocksPerSmMin * assigned_sm_count)
//     so the search range scales with how many SMs this partition actually has
//     (a green 8-SM partition and the 16-SM shared config get different bounds).
//   - candidates = {1,2,4,8} x lower_bound, each clamped to kBlocksCap (1024).
//   - phase2_bench-style local search: sweep K0's candidates with K1 held at its
//     own lower bound, pick the best (lowest wall time == highest agg GB/s);
//     then sweep K1's candidates with K0 held at the chosen best; pick the best.
//   - plateau_reached = true iff, on EACH axis, the top candidate's agg-GB/s gain
//     over the previous candidate was < kPlateauGainFrac (~2%) -- i.e. the search
//     actually flattened rather than still climbing at the kBlocksCap ceiling.
// The chosen blocks_k0/blocks_k1 and plateau_reached are the ones printed in the
// CSV row (00_conventions.md #4: block count is a knob, its saturated value is
// what gets reported).
//
// Green context requires the CUDA *driver* API (cuda.h), CUDA >= 12.4
// (prompts/03_green_context.md). Code is guarded by CUDA_VERSION so it still
// compiles against older toolkits (green config then reports unsupported
// instead of faking a partition).
//
// IMPORTANT (found on-device): both partitions of a two-way SM split MUST come
// from the SAME cuDevSmResourceSplitByCount call (result[0] + its `remaining`
// output). Creating them from two separate split calls fails with
// CUDA_ERROR_INVALID_RESOURCE_CONFIGURATION even for a symmetric 8:8 ratio.
//
// Exit codes: 0 success; 1 fatal CUDA/correctness failure; 2 bad CLI usage;
// 3 green context API unavailable (see --check-api); 4 this SM ratio was
// invalid or rejected by the driver -- skip this cell, not fatal to the sweep
// (scripts/sweep.py catches 4, warns, and continues with the next cell).
#include <cuda_runtime.h>
#include <cuda.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>
#include <vector>
#include <set>

#define CUDA_CHECK(call)                                                          \
    do {                                                                          \
        cudaError_t _err = (call);                                                \
        if (_err != cudaSuccess) {                                                \
            fprintf(stderr, "CUDA error %s:%d: %s\n", __FILE__, __LINE__,          \
                    cudaGetErrorString(_err));                                     \
            exit(1);                                                              \
        }                                                                          \
    } while (0)

#define CU_CHECK(call)                                                            \
    do {                                                                          \
        CUresult _res = (call);                                                   \
        if (_res != CUDA_SUCCESS) {                                               \
            const char* _name = nullptr;                                         \
            cuGetErrorName(_res, &_name);                                         \
            fprintf(stderr, "CUDA driver error %s:%d: %s\n", __FILE__, __LINE__,   \
                    _name ? _name : "unknown");                                   \
            exit(1);                                                              \
        }                                                                          \
    } while (0)

#define PHASE3_MIN_CUDA_VERSION 12040  // CUDA 12.4: green context driver API

#if defined(CUDA_VERSION) && CUDA_VERSION >= PHASE3_MIN_CUDA_VERSION
#define GREEN_CTX_COMPILED 1
#else
#define GREEN_CTX_COMPILED 0
#endif

__global__ void addKernel(const float* __restrict__ A, const float* __restrict__ B,
                           float* __restrict__ C, size_t n) {
    size_t stride = (size_t)gridDim.x * blockDim.x;
    for (size_t i = (size_t)blockIdx.x * blockDim.x + threadIdx.x; i < n; i += stride) {
        C[i] = A[i] + B[i];
    }
}

__global__ void fillKernel(float* __restrict__ A, float* __restrict__ B, size_t n) {
    size_t stride = (size_t)gridDim.x * blockDim.x;
    for (size_t i = (size_t)blockIdx.x * blockDim.x + threadIdx.x; i < n; i += stride) {
        A[i] = 1.0f;
        B[i] = 2.0f;
    }
}

// Verification kernel: each thread records which SM it executed on
// (00_conventions verification requirement / prompt "Verification" section).
__global__ void smidProbeKernel(unsigned int* __restrict__ out) {
    unsigned int smid;
    asm volatile("mov.u32 %0, %%smid;" : "=r"(smid));
    out[(size_t)blockIdx.x * blockDim.x + threadIdx.x] = smid;
}

// ---- env / device info (same approach as Phase 1) ----

static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    size_t b = s.find_last_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    return s.substr(a, b - a + 1);
}

static std::string queryPowerMode() {
    FILE* pipe = popen("nvpmodel -q 2>/dev/null", "r");
    if (!pipe) return "unknown";
    std::string result = "unknown";
    char buf[256];
    while (fgets(buf, sizeof(buf), pipe)) {
        std::string line(buf);
        auto pos = line.find("NV Power Mode");
        if (pos != std::string::npos) {
            auto colon = line.find(':', pos);
            if (colon != std::string::npos) result = trim(line.substr(colon + 1));
        }
    }
    pclose(pipe);
    return result;
}

static double querySocTempC() {
    static const char* candidates[] = {
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone0/temp",
    };
    for (const char* path : candidates) {
        FILE* f = fopen(path, "r");
        if (!f) continue;
        long milli = 0;
        int got = fscanf(f, "%ld", &milli);
        fclose(f);
        if (got == 1) return milli / 1000.0;
    }
    return -1.0;
}

static std::string versionStr(int v) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%d.%d", v / 1000, (v % 100) / 10);
    return buf;
}

struct EnvInfo {
    int gpu_clock_mhz;
    std::string power_mode;
    double soc_temp_c;
    std::string cuda_version;
    std::string driver_version;
};

static EnvInfo queryEnv() {
    EnvInfo e;
    int runtimeVer = 0, driverVer = 0, clockKhz = 0;
    CUDA_CHECK(cudaRuntimeGetVersion(&runtimeVer));
    CUDA_CHECK(cudaDriverGetVersion(&driverVer));
    CUDA_CHECK(cudaDeviceGetAttribute(&clockKhz, cudaDevAttrClockRate, 0));
    e.gpu_clock_mhz = clockKhz / 1000;
    e.cuda_version = versionStr(runtimeVer);
    e.driver_version = versionStr(driverVer);
    e.power_mode = queryPowerMode();
    e.soc_temp_c = querySocTempC();
    return e;
}

// ---- stats ----

struct Stats {
    double median, min, max, stddev;
};

static Stats computeStats(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    Stats s;
    size_t n = v.size();
    s.min = v.front();
    s.max = v.back();
    s.median = (n % 2 == 0) ? (v[n / 2 - 1] + v[n / 2]) / 2.0 : v[n / 2];
    double mean = 0;
    for (double x : v) mean += x;
    mean /= n;
    double var = 0;
    for (double x : v) var += (x - mean) * (x - mean);
    var /= n;
    s.stddev = std::sqrt(var);
    return s;
}

// ---- in-context block saturation search (v2 Change 1) ----

// Minimum blocks/SM used to build the search's lower bound (matches Phase 1's
// own ~4 blocks/SM at its saturation point, e.g. 64 blocks / 16 SMs); the actual
// plateau is still found by the search below, this only seeds where it starts.
static const int kBlocksPerSmMin = 4;
static const int kSearchMultipliers[] = {1, 2, 4, 8};
static const int kBlocksCap = 1024;
static const double kPlateauGainFrac = 0.02;  // <2% gain over previous candidate = plateaued
static const int kSearchTrials = 3;           // cheap timing during the search; final cell uses a.trials

static int clampBlocksCount(long long b) { return (int)std::min<long long>(b, kBlocksCap); }

// Geometric candidate ladder for one axis, seeded by the Phase 1 nearest-size
// lookup but floored by kBlocksPerSmMin * assignedSmCount so a smaller SM
// partition still gets a search range scaled to ITS SM count, not the
// single-kernel/16-SM value (prompts/03_green_context_v2.md Change 1).
static std::vector<int> buildBlockCandidates(int seedBlocks, int assignedSmCount) {
    long long lowerBound = std::max<long long>((long long)seedBlocks,
                                                 (long long)kBlocksPerSmMin * assignedSmCount);
    std::vector<int> cands;
    for (int m : kSearchMultipliers) {
        int c = clampBlocksCount(lowerBound * m);
        if (cands.empty() || cands.back() != c) cands.push_back(c);
    }
    return cands;
}

struct SearchAxisResult {
    int chosenBlocks;
    bool plateauReached;
};

// Sweep `candidates` for one axis via `aggGBpsForCandidate`, picking the one with
// highest aggregate GB/s. plateauReached reflects whether the top candidate's
// gain over the previous one is below kPlateauGainFrac (see file header comment).
static SearchAxisResult sweepBlockAxis(const std::function<double(int)>& aggGBpsForCandidate,
                                        const std::vector<int>& candidates) {
    SearchAxisResult r{candidates.front(), true};
    double bestAgg = -1.0;
    std::vector<double> aggs;
    aggs.reserve(candidates.size());
    for (int c : candidates) {
        double agg = aggGBpsForCandidate(c);
        aggs.push_back(agg);
        if (agg > bestAgg) { bestAgg = agg; r.chosenBlocks = c; }
    }
    if (aggs.size() >= 2) {
        double prev = aggs[aggs.size() - 2];
        double last = aggs.back();
        double gain = (prev > 0) ? (last - prev) / prev : 0.0;
        r.plateauReached = gain < kPlateauGainFrac;
    }
    return r;
}

// ---- green context availability (00_conventions: verify before use, never fake) ----

static bool greenContextApiAvailable(std::string& reason) {
#if !GREEN_CTX_COMPILED
    reason = "compiled against CUDA_VERSION < " + std::to_string(PHASE3_MIN_CUDA_VERSION) +
              " (green context driver API not declared in this cuda.h)";
    return false;
#else
    CUresult initRes = cuInit(0);
    if (initRes != CUDA_SUCCESS) {
        reason = "cuInit failed";
        return false;
    }
    int driverVer = 0;
    CU_CHECK(cuDriverGetVersion(&driverVer));
    if (driverVer < PHASE3_MIN_CUDA_VERSION) {
        reason = "driver reports CUDA " + versionStr(driverVer) + ", need >= 12.4";
        return false;
    }
    reason = "driver CUDA " + versionStr(driverVer) + " >= 12.4, green context API present";
    return true;
#endif
}

#if GREEN_CTX_COMPILED
// Total SM count on this device (OVERVIEW.md: 16 SMs on the Orin AGX iGPU).
static const unsigned int kNumSMs = 16;

// Caller launches kernels on the returned streams (cast to cudaStream_t) using
// ordinary <<<>>> syntax with the corresponding green context current on the
// launching thread (cuCtxPushCurrent(ctxView) before, cuCtxPopCurrent after).
struct GreenPartition {
    CUgreenCtx gctx;
    CUcontext ctxView;   // cuCtxFromGreenCtx: lets runtime-API launches target this partition
    CUstream stream;
};

// Build a green context + stream from an already-carved-out SM resource. Checks
// every driver call's return code; returns false (with *errOut / *stageOut set)
// instead of aborting, so the caller can skip an invalid configuration with a
// warning rather than crashing the whole sweep.
static bool tryMakeGreenPartitionFromResource(CUdevice dev, CUdevResource* resource,
                                               GreenPartition* out, CUresult* errOut,
                                               const char** stageOut) {
    CUdevResourceDesc desc;
    *errOut = cuDevResourceGenerateDesc(&desc, resource, 1);
    if (*errOut != CUDA_SUCCESS) { *stageOut = "cuDevResourceGenerateDesc"; return false; }

    *errOut = cuGreenCtxCreate(&out->gctx, desc, dev, CU_GREEN_CTX_DEFAULT_STREAM);
    if (*errOut != CUDA_SUCCESS) { *stageOut = "cuGreenCtxCreate"; return false; }

    *errOut = cuCtxFromGreenCtx(&out->ctxView, out->gctx);
    if (*errOut != CUDA_SUCCESS) {
        *stageOut = "cuCtxFromGreenCtx";
        cuGreenCtxDestroy(out->gctx);
        return false;
    }

    *errOut = cuGreenCtxStreamCreate(&out->stream, out->gctx, CU_STREAM_NON_BLOCKING, /*priority=*/0);
    if (*errOut != CUDA_SUCCESS) {
        *stageOut = "cuGreenCtxStreamCreate";
        cuGreenCtxDestroy(out->gctx);
        return false;
    }
    return true;
}

// Partition the device's SMs into exactly two disjoint groups with a SINGLE
// cuDevSmResourceSplitByCount call: result[0] gets minCount SMs, `remaining` gets
// the rest. Both green contexts are built from THIS call's outputs (never from
// two separate split calls -- see the file header comment on why). `minCount`
// must be a multiple of 2 (Tegra requirement); the ratio being swept is
// minCount:(kNumSMs - minCount).
static bool trySplitAndMakeTwoPartitions(CUdevice dev, unsigned int minCount,
                                          GreenPartition* p0, GreenPartition* p1,
                                          CUresult* errOut, const char** stageOut) {
    if (minCount == 0 || minCount >= kNumSMs || minCount % 2 != 0) {
        *errOut = CUDA_ERROR_INVALID_VALUE;
        *stageOut = "minCount must be even and in (0, 16) (Tegra requirement)";
        return false;
    }

    CUdevResource smPool;
    *errOut = cuDeviceGetDevResource(dev, &smPool, CU_DEV_RESOURCE_TYPE_SM);
    if (*errOut != CUDA_SUCCESS) { *stageOut = "cuDeviceGetDevResource"; return false; }

    CUdevResource result[1];
    CUdevResource remaining;
    unsigned int nbGroups = 1;
    *errOut = cuDevSmResourceSplitByCount(result, &nbGroups, &smPool, &remaining,
                                           /*useFlags=*/0, minCount);
    if (*errOut != CUDA_SUCCESS) { *stageOut = "cuDevSmResourceSplitByCount"; return false; }

    if (!tryMakeGreenPartitionFromResource(dev, &result[0], p0, errOut, stageOut)) {
        return false;
    }
    if (!tryMakeGreenPartitionFromResource(dev, &remaining, p1, errOut, stageOut)) {
        cuStreamDestroy(p0->stream);
        cuGreenCtxDestroy(p0->gctx);
        return false;
    }
    return true;
}

static void destroyGreenPartition(GreenPartition& p) {
    cuStreamDestroy(p.stream);
    cuGreenCtxDestroy(p.gctx);
}
#endif

// ---- CLI ----

struct Args {
    std::string testPointId = "unspecified";
    std::string mode = "symmetric";      // symmetric|asymmetric
    std::string config = "shared";       // shared|green
    size_t k0Bytes = 1ull * 1024 * 1024;
    size_t k1Bytes = 1ull * 1024 * 1024;
    int sm0 = 8;                          // SM count for K0 partition (green only)
    int sm1 = 8;                          // SM count for K1 partition (green only)
    int blocks0 = 256;                    // --verify only: probe kernel block count, used as-is
    int blocks1 = 256;                    // --verify only: probe kernel block count, used as-is
    int blocks0Seed = 64;                 // measurement mode: seed/lower bound for the in-context search
    int blocks1Seed = 64;                 // measurement mode: seed/lower bound for the in-context search
    int tpb = 256;
    int trials = 10;
    bool verify = false;
    bool checkApiOnly = false;
};

static size_t parseBytes(const std::string& s) { return (size_t)std::strtoull(s.c_str(), nullptr, 10); }

static Args parseArgs(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&](void) -> std::string { return (i + 1 < argc) ? argv[++i] : ""; };
        if (arg == "--test-point-id") a.testPointId = next();
        else if (arg == "--mode") a.mode = next();
        else if (arg == "--config") a.config = next();
        else if (arg == "--k0-bytes") a.k0Bytes = parseBytes(next());
        else if (arg == "--k1-bytes") a.k1Bytes = parseBytes(next());
        else if (arg == "--sm0") a.sm0 = std::atoi(next().c_str());
        else if (arg == "--sm1") a.sm1 = std::atoi(next().c_str());
        else if (arg == "--blocks0") a.blocks0 = std::atoi(next().c_str());
        else if (arg == "--blocks1") a.blocks1 = std::atoi(next().c_str());
        else if (arg == "--blocks0-seed") a.blocks0Seed = std::atoi(next().c_str());
        else if (arg == "--blocks1-seed") a.blocks1Seed = std::atoi(next().c_str());
        else if (arg == "--tpb") a.tpb = std::atoi(next().c_str());
        else if (arg == "--trials") a.trials = std::atoi(next().c_str());
        else if (arg == "--verify") a.verify = true;
        else if (arg == "--check-api") a.checkApiOnly = true;
        else {
            fprintf(stderr, "Unknown arg: %s\n", arg.c_str());
            exit(2);
        }
    }
    return a;
}

// ---- measurement: shared (no green context) ----
// Both kernels launched on two ordinary streams, all 16 SMs, block scheduler
// interleaves both (the Phase 2 baseline). Wall time = both streams complete.

static double measureSharedWallMs(float* dA0, float* dB0, float* dC0, size_t n0, int blocks0,
                                   float* dA1, float* dB1, float* dC1, size_t n1, int blocks1,
                                   int tpb, int trials, double* k0MsOut, double* k1MsOut) {
    cudaStream_t s0, s1;
    CUDA_CHECK(cudaStreamCreate(&s0));
    CUDA_CHECK(cudaStreamCreate(&s1));

    for (int w = 0; w < 3; ++w) {
        addKernel<<<blocks0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        addKernel<<<blocks1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
    }
    CUDA_CHECK(cudaDeviceSynchronize());

    cudaEvent_t start, stop0, stop1;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop0));
    CUDA_CHECK(cudaEventCreate(&stop1));

    std::vector<double> wallMs, k0Ms, k1Ms;
    for (int t = 0; t < trials; ++t) {
        // barrier: both streams wait on the same start event so timing starts together
        CUDA_CHECK(cudaEventRecord(start, s0));
        CUDA_CHECK(cudaStreamWaitEvent(s1, start, 0));

        addKernel<<<blocks0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        CUDA_CHECK(cudaEventRecord(stop0, s0));
        addKernel<<<blocks1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
        CUDA_CHECK(cudaEventRecord(stop1, s1));

        CUDA_CHECK(cudaEventSynchronize(stop0));
        CUDA_CHECK(cudaEventSynchronize(stop1));
        float ms0 = 0, ms1 = 0;
        CUDA_CHECK(cudaEventElapsedTime(&ms0, start, stop0));
        CUDA_CHECK(cudaEventElapsedTime(&ms1, start, stop1));
        k0Ms.push_back(ms0);
        k1Ms.push_back(ms1);
        wallMs.push_back(std::max(ms0, ms1));
    }

    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop0));
    CUDA_CHECK(cudaEventDestroy(stop1));
    CUDA_CHECK(cudaStreamDestroy(s0));
    CUDA_CHECK(cudaStreamDestroy(s1));

    *k0MsOut = computeStats(k0Ms).median;
    *k1MsOut = computeStats(k1Ms).median;
    return computeStats(wallMs).median;
}

#if GREEN_CTX_COMPILED
// ---- measurement: green context (partitioned SMs) ----

// Returns false (without measuring) if the driver rejected this SM ratio; the
// caller warns and skips the cell instead of failing the whole sweep.
static bool measureGreenWallMs(CUdevice dev, int sm0Count,
                                float* dA0, float* dB0, float* dC0, size_t n0, int blocks0,
                                float* dA1, float* dB1, float* dC1, size_t n1, int blocks1,
                                int tpb, int trials,
                                double* wallMsOut, double* k0MsOut, double* k1MsOut) {
    GreenPartition p0{}, p1{};
    CUresult err = CUDA_SUCCESS;
    const char* stage = "";
    if (!trySplitAndMakeTwoPartitions(dev, (unsigned int)sm0Count, &p0, &p1, &err, &stage)) {
        const char* name = nullptr;
        cuGetErrorName(err, &name);
        fprintf(stderr, "WARNING: SM split %d:%d rejected at %s (%s) -- skipping this ratio\n",
                sm0Count, (int)kNumSMs - sm0Count, stage, name ? name : "unknown");
        return false;
    }

    cudaStream_t s0 = (cudaStream_t)p0.stream;
    cudaStream_t s1 = (cudaStream_t)p1.stream;

    for (int w = 0; w < 3; ++w) {
        CU_CHECK(cuCtxPushCurrent(p0.ctxView));
        addKernel<<<blocks0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        CU_CHECK(cuCtxPopCurrent(nullptr));

        CU_CHECK(cuCtxPushCurrent(p1.ctxView));
        addKernel<<<blocks1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
        CU_CHECK(cuCtxPopCurrent(nullptr));
    }
    CUDA_CHECK(cudaDeviceSynchronize());

    cudaEvent_t start, stop0, stop1;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop0));
    CUDA_CHECK(cudaEventCreate(&stop1));

    std::vector<double> wallMs, k0Ms, k1Ms;
    for (int t = 0; t < trials; ++t) {
        CUDA_CHECK(cudaEventRecord(start, s0));
        CUDA_CHECK(cudaStreamWaitEvent(s1, start, 0));

        CU_CHECK(cuCtxPushCurrent(p0.ctxView));
        addKernel<<<blocks0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        CUDA_CHECK(cudaEventRecord(stop0, s0));
        CU_CHECK(cuCtxPopCurrent(nullptr));

        CU_CHECK(cuCtxPushCurrent(p1.ctxView));
        addKernel<<<blocks1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
        CUDA_CHECK(cudaEventRecord(stop1, s1));
        CU_CHECK(cuCtxPopCurrent(nullptr));

        CUDA_CHECK(cudaEventSynchronize(stop0));
        CUDA_CHECK(cudaEventSynchronize(stop1));
        float ms0 = 0, ms1 = 0;
        CUDA_CHECK(cudaEventElapsedTime(&ms0, start, stop0));
        CUDA_CHECK(cudaEventElapsedTime(&ms1, start, stop1));
        k0Ms.push_back(ms0);
        k1Ms.push_back(ms1);
        wallMs.push_back(std::max(ms0, ms1));
    }

    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop0));
    CUDA_CHECK(cudaEventDestroy(stop1));
    destroyGreenPartition(p0);
    destroyGreenPartition(p1);

    *k0MsOut = computeStats(k0Ms).median;
    *k1MsOut = computeStats(k1Ms).median;
    *wallMsOut = computeStats(wallMs).median;
    return true;
}

// ---- verification: confirm each partition's blocks only ran on its assigned SMs ----

static bool runVerify(CUdevice dev, int sm0Count, int blocks0, int blocks1, int tpb) {
    GreenPartition p0{}, p1{};
    CUresult err = CUDA_SUCCESS;
    const char* stage = "";
    if (!trySplitAndMakeTwoPartitions(dev, (unsigned int)sm0Count, &p0, &p1, &err, &stage)) {
        const char* name = nullptr;
        cuGetErrorName(err, &name);
        fprintf(stderr, "WARNING: SM split %d:%d rejected at %s (%s) -- cannot verify this ratio\n",
                sm0Count, (int)kNumSMs - sm0Count, stage, name ? name : "unknown");
        return false;
    }

    size_t n0Threads = (size_t)blocks0 * tpb;
    size_t n1Threads = (size_t)blocks1 * tpb;
    unsigned int *dOut0, *dOut1;
    CUDA_CHECK(cudaMalloc(&dOut0, n0Threads * sizeof(unsigned int)));
    CUDA_CHECK(cudaMalloc(&dOut1, n1Threads * sizeof(unsigned int)));

    CU_CHECK(cuCtxPushCurrent(p0.ctxView));
    smidProbeKernel<<<blocks0, tpb, 0, (cudaStream_t)p0.stream>>>(dOut0);
    CU_CHECK(cuCtxPopCurrent(nullptr));

    CU_CHECK(cuCtxPushCurrent(p1.ctxView));
    smidProbeKernel<<<blocks1, tpb, 0, (cudaStream_t)p1.stream>>>(dOut1);
    CU_CHECK(cuCtxPopCurrent(nullptr));

    CUDA_CHECK(cudaDeviceSynchronize());

    std::vector<unsigned int> h0(n0Threads), h1(n1Threads);
    CUDA_CHECK(cudaMemcpy(h0.data(), dOut0, n0Threads * sizeof(unsigned int), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(h1.data(), dOut1, n1Threads * sizeof(unsigned int), cudaMemcpyDeviceToHost));

    std::set<unsigned int> smids0(h0.begin(), h0.end());
    std::set<unsigned int> smids1(h1.begin(), h1.end());
    std::vector<unsigned int> overlap;
    std::set_intersection(smids0.begin(), smids0.end(), smids1.begin(), smids1.end(),
                           std::back_inserter(overlap));

    printf("partition0 (%d SMs requested) observed smids:", sm0Count);
    for (auto id : smids0) printf(" %u", id);
    printf("\npartition1 (%d SMs requested) observed smids:", (int)kNumSMs - sm0Count);
    for (auto id : smids1) printf(" %u", id);
    printf("\noverlap: %zu smid(s) %s\n", overlap.size(),
           overlap.empty() ? "(disjoint -- partitioning confirmed)"
                            : "(NOT disjoint -- partitioning did NOT take effect, investigate)");

    cudaFree(dOut0);
    cudaFree(dOut1);
    destroyGreenPartition(p0);
    destroyGreenPartition(p1);
    return true;
}
#endif  // GREEN_CTX_COMPILED

int main(int argc, char** argv) {
    Args a = parseArgs(argc, argv);

    if (a.checkApiOnly) {
        std::string reason;
        bool ok = greenContextApiAvailable(reason);
        printf("green_context_available=%d reason=\"%s\"\n", ok ? 1 : 0, reason.c_str());
        return ok ? 0 : 3;
    }

    if (a.config == "green") {
        std::string reason;
        if (!greenContextApiAvailable(reason)) {
            fprintf(stderr, "ERROR: green context requested but unavailable: %s\n", reason.c_str());
            fprintf(stderr, "STOP (00_conventions.md / prompt: do not fake partitioning). "
                             "Report this in the worklog.\n");
            return 3;
        }
        // The split is a single cuDevSmResourceSplitByCount(minCount=sm0) call;
        // partition 1 automatically gets the remaining 16 - sm0 SMs, so sm1 is
        // only accepted as a consistency check. Tegra requires minCount % 2 == 0.
        if (a.sm0 + a.sm1 != 16) {
            fprintf(stderr, "ERROR: sm0(%d)+sm1(%d) must sum to 16 (partition 1 = remainder)\n",
                    a.sm0, a.sm1);
            return 2;
        }
        if (a.sm0 <= 0 || a.sm0 >= 16 || a.sm0 % 2 != 0) {
            fprintf(stderr, "WARNING: sm0=%d invalid on Tegra (must be even, 0 < sm0 < 16) "
                             "-- skipping this ratio\n", a.sm0);
            return 4;
        }
    }

#if GREEN_CTX_COMPILED
    CUdevice dev = 0;
    if (a.config == "green" || a.verify) {
        CU_CHECK(cuInit(0));
        CU_CHECK(cuDeviceGet(&dev, 0));
    }
#endif

    size_t n0 = a.k0Bytes / sizeof(float);
    size_t n1 = a.k1Bytes / sizeof(float);

    float *dA0, *dB0, *dC0, *dA1, *dB1, *dC1;
    CUDA_CHECK(cudaMalloc(&dA0, n0 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dB0, n0 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dC0, n0 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dA1, n1 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dB1, n1 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dC1, n1 * sizeof(float)));
    fillKernel<<<256, a.tpb>>>(dA0, dB0, n0);
    fillKernel<<<256, a.tpb>>>(dA1, dB1, n1);
    CUDA_CHECK(cudaDeviceSynchronize());

    if (a.verify) {
        int rc = 0;
#if GREEN_CTX_COMPILED
        if (!runVerify(dev, a.sm0, a.blocks0, a.blocks1, a.tpb)) rc = 4;
#else
        fprintf(stderr, "ERROR: --verify requires green context support; not compiled in "
                         "(CUDA_VERSION < %d)\n", PHASE3_MIN_CUDA_VERSION);
        rc = 3;
#endif
        cudaFree(dA0); cudaFree(dB0); cudaFree(dC0);
        cudaFree(dA1); cudaFree(dB1); cudaFree(dC1);
        return rc;
    }

    EnvInfo env = queryEnv();

    // ---- in-context block saturation search (v2 Change 1) ----
    // assigned SM count per axis: 16/16 for shared (both kernels see all SMs),
    // a.sm0/a.sm1 for green (each kernel confined to its own partition).
    int assignedSm0 = (a.config == "shared") ? 16 : a.sm0;
    int assignedSm1 = (a.config == "shared") ? 16 : a.sm1;
    double totalBytesForSearch = 3.0 * (double)n0 * 4.0 + 3.0 * (double)n1 * 4.0;  // A+B+C both kernels

    bool ratioRejected = false;
    // aggGBpsForPair: single point of contact with the device for the search --
    // routes to the shared or green measurement path, kSearchTrials only (cheap).
    // Sets ratioRejected and returns -1 if the green split was rejected by the
    // driver (mirrors the pre-v2 behavior: skip this cell with a warning).
    auto aggGBpsForPair = [&](int b0, int b1) -> double {
        double wMs = 0, m0 = 0, m1 = 0;
        bool ok;
        if (a.config == "shared") {
            wMs = measureSharedWallMs(dA0, dB0, dC0, n0, b0, dA1, dB1, dC1, n1, b1,
                                       a.tpb, kSearchTrials, &m0, &m1);
            ok = true;
        } else {
#if GREEN_CTX_COMPILED
            ok = measureGreenWallMs(dev, a.sm0, dA0, dB0, dC0, n0, b0, dA1, dB1, dC1, n1, b1,
                                     a.tpb, kSearchTrials, &wMs, &m0, &m1);
#else
            ok = false;
#endif
        }
        if (!ok) { ratioRejected = true; return -1.0; }
        return totalBytesForSearch / (wMs / 1000.0) / 1e9;
    };

    std::vector<int> cand0 = buildBlockCandidates(a.blocks0Seed, assignedSm0);
    std::vector<int> cand1 = buildBlockCandidates(a.blocks1Seed, assignedSm1);

    // pass 1: sweep K0 candidates with K1 held at its own lower bound
    SearchAxisResult r0 = sweepBlockAxis(
        [&](int c) { return aggGBpsForPair(c, cand1.front()); }, cand0);
    if (ratioRejected) {
        fprintf(stderr, "WARNING: SM split %d:%d rejected during block search -- skipping cell\n",
                a.sm0, a.sm1);
        cudaFree(dA0); cudaFree(dB0); cudaFree(dC0);
        cudaFree(dA1); cudaFree(dB1); cudaFree(dC1);
        return 4;
    }
    int bestBlocks0 = r0.chosenBlocks;

    // pass 2: sweep K1 candidates with K0 held at the pass-1 winner
    SearchAxisResult r1 = sweepBlockAxis(
        [&](int c) { return aggGBpsForPair(bestBlocks0, c); }, cand1);
    if (ratioRejected) {
        fprintf(stderr, "WARNING: SM split %d:%d rejected during block search -- skipping cell\n",
                a.sm0, a.sm1);
        cudaFree(dA0); cudaFree(dB0); cudaFree(dC0);
        cudaFree(dA1); cudaFree(dB1); cudaFree(dC1);
        return 4;
    }
    int bestBlocks1 = r1.chosenBlocks;
    bool plateauReached = r0.plateauReached && r1.plateauReached;
    if (!plateauReached) {
        fprintf(stderr, "WARNING: block search did not plateau within cap=%d for test_point=%s "
                         "config=%s sm=%d:%d (blocks_k0=%d plateau0=%d, blocks_k1=%d plateau1=%d)\n",
                kBlocksCap, a.testPointId.c_str(), a.config.c_str(), a.sm0, a.sm1,
                bestBlocks0, r0.plateauReached, bestBlocks1, r1.plateauReached);
    }

    // ---- final measured cell at the chosen (bestBlocks0, bestBlocks1), full trial count ----
    double k0Ms = 0, k1Ms = 0, wallMs = 0;
    int smSplit0 = 0, smSplit1 = 0;
    if (a.config == "shared") {
        wallMs = measureSharedWallMs(dA0, dB0, dC0, n0, bestBlocks0, dA1, dB1, dC1, n1, bestBlocks1,
                                      a.tpb, a.trials, &k0Ms, &k1Ms);
        smSplit0 = 16;  // shared: both kernels see all 16 SMs
        smSplit1 = 16;
    } else {
#if GREEN_CTX_COMPILED
        if (!measureGreenWallMs(dev, a.sm0, dA0, dB0, dC0, n0, bestBlocks0,
                                 dA1, dB1, dC1, n1, bestBlocks1, a.tpb, a.trials,
                                 &wallMs, &k0Ms, &k1Ms)) {
            cudaFree(dA0); cudaFree(dB0); cudaFree(dC0);
            cudaFree(dA1); cudaFree(dB1); cudaFree(dC1);
            return 4;  // ratio rejected by driver: sweep.py warns and skips this cell
        }
        smSplit0 = a.sm0;
        smSplit1 = a.sm1;
#endif
    }

    // correctness check on both outputs after the measured run
    {
        size_t nsample0 = std::min<size_t>(n0, 4096);
        size_t nsample1 = std::min<size_t>(n1, 4096);
        std::vector<float> h0(nsample0), h1(nsample1);
        CUDA_CHECK(cudaMemcpy(h0.data(), dC0, nsample0 * sizeof(float), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpy(h1.data(), dC1, nsample1 * sizeof(float), cudaMemcpyDeviceToHost));
        for (float v : h0) if (std::fabs(v - 3.0f) > 1e-5f) {
            fprintf(stderr, "CORRECTNESS FAILURE in K0 (test_point=%s config=%s)\n",
                    a.testPointId.c_str(), a.config.c_str());
            return 1;
        }
        for (float v : h1) if (std::fabs(v - 3.0f) > 1e-5f) {
            fprintf(stderr, "CORRECTNESS FAILURE in K1 (test_point=%s config=%s)\n",
                    a.testPointId.c_str(), a.config.c_str());
            return 1;
        }
    }

    cudaFree(dA0); cudaFree(dB0); cudaFree(dC0);
    cudaFree(dA1); cudaFree(dB1); cudaFree(dC1);

    double k0Bytes = 3.0 * (double)n0 * 4.0;  // A read + B read + C write
    double k1Bytes = 3.0 * (double)n1 * 4.0;
    double k0GBps = k0Bytes / (k0Ms / 1000.0) / 1e9;
    double k1GBps = k1Bytes / (k1Ms / 1000.0) / 1e9;
    double aggGBps = (k0Bytes + k1Bytes) / (wallMs / 1000.0) / 1e9;

    // delta_vs_shared_pct is filled in by scripts/sweep.py after collecting the
    // matching shared-baseline row for this test_point_id (needs cross-row join).
    printf("%s,%s,%zu,%zu,%s,%d,%d,%d,%d,%d,%d,%d,%.6f,%.3f,%.3f,%.3f,%.3f,%d,%s,%.1f,%s,%s\n",
           a.testPointId.c_str(), a.mode.c_str(), a.k0Bytes, a.k1Bytes, a.config.c_str(),
           smSplit0, smSplit1, bestBlocks0, bestBlocks1, a.tpb, a.trials, plateauReached ? 1 : 0,
           wallMs, aggGBps, k0GBps, k1GBps, 0.0, env.gpu_clock_mhz, env.power_mode.c_str(),
           env.soc_temp_c, env.cuda_version.c_str(), env.driver_version.c_str());

    return 0;
}
