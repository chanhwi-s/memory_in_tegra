// Phase 2 -- two concurrent kernels, size sweep (green context OFF, zero copy OFF)
// See prompts/02_two_kernel_size.md. Build: nvcc -O3 -arch=sm_87 -o phase2_bench phase2_bench.cu
//
// Each measured cell runs K0 and K1 (both the Phase-1 `C = A + B` kernel, own buffers) on two
// CUDA streams concurrently. The cell's config (sizes, block-count hints, single-kernel reference
// throughput from Phase 1) is supplied by scripts/gen_config.py via a small CSV config file --
// this binary does no JSON parsing and never invents Phase-1 numbers itself.
//
// v2 add-on (prompts/02_two_kernel_size_v2.md): an optional `--reuse-out <path>` flag switches
// to a separate reuse-sweep overlay mode (reuse_N in {1,2,4,8,16,32}, same size grid, config
// stays shared/zero-copy-off) that writes results/phase2_reuse_results.csv and never touches
// results/phase2_results.csv or findings.json -- see runReuseSweep() below. Default behavior
// (no --reuse-out) is completely unchanged from the original reuse=1 sweep.
#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CUDA_CHECK(call)                                                          \
    do {                                                                          \
        cudaError_t _err = (call);                                                \
        if (_err != cudaSuccess) {                                                \
            fprintf(stderr, "CUDA error %s:%d: %s\n", __FILE__, __LINE__,          \
                    cudaGetErrorString(_err));                                     \
            exit(1);                                                              \
        }                                                                          \
    } while (0)

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

// ---- env / device info (best-effort; Jetson-specific probes fall back gracefully) ----
// Identical to Phase 1's probes (experiments/01_single_kernel_size/src/phase1_bench.cu);
// duplicated rather than shared per the phase-isolation rule in prompts/00_conventions.md #1.

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

// ---- one requested cell, read from the config CSV ----

struct CellConfig {
    std::string mode;         // "symmetric" | "asymmetric"
    size_t k0_bytes;
    size_t k1_bytes;
    int blocks_k0_hint;
    int blocks_k1_hint;
    int threads_per_block;
    double single_k0_GBps_ref;  // -1 => missing upstream (Phase 1 not run yet)
    double single_k1_GBps_ref;
};

static std::vector<CellConfig> readConfig(const std::string& path) {
    std::vector<CellConfig> cells;
    FILE* f = fopen(path.c_str(), "r");
    if (!f) {
        fprintf(stderr, "Cannot open config %s\n", path.c_str());
        exit(1);
    }
    char line[512];
    bool first = true;
    while (fgets(line, sizeof(line), f)) {
        if (first) { first = false; continue; }  // header
        std::string s(line);
        if (trim(s).empty()) continue;
        CellConfig c;
        char modeBuf[32];
        unsigned long long k0, k1;
        int bk0, bk1, tpb;
        double r0, r1;
        int got = sscanf(line, "%31[^,],%llu,%llu,%d,%d,%d,%lf,%lf", modeBuf, &k0, &k1, &bk0,
                          &bk1, &tpb, &r0, &r1);
        if (got != 8) {
            fprintf(stderr, "Malformed config line, skipping: %s", line);
            continue;
        }
        c.mode = modeBuf;
        c.k0_bytes = (size_t)k0;
        c.k1_bytes = (size_t)k1;
        c.blocks_k0_hint = bk0;
        c.blocks_k1_hint = bk1;
        c.threads_per_block = tpb;
        c.single_k0_GBps_ref = r0;
        c.single_k1_GBps_ref = r1;
        cells.push_back(c);
    }
    fclose(f);
    return cells;
}

// ---- concurrent measurement ----

struct ConcurrentResult {
    Stats wall_ms;
    double k0_GBps_median;
    double k1_GBps_median;
    double agg_GBps_median;
};

// Runs `trials` timed launches of K0 (stream0) and K1 (stream1) concurrently, each launch
// re-reading the identical buffers `reuseN` times (inter-launch, full-buffer reuse; same
// definition as Phase 1 and Phase 4 -- prompts/02_two_kernel_size_v2.md). The original
// (non-v2) call sites all pass reuseN=1, which reproduces the exact prior behavior/values. A
// shared "join" event recorded on stream0 and waited-on by stream1 keeps both loops starting
// from the same reference point so wall time genuinely reflects the overlapped run.
static ConcurrentResult measureConcurrent(const float* dA0, const float* dB0, float* dC0,
                                           size_t n0, int blocksK0,
                                           const float* dA1, const float* dB1, float* dC1,
                                           size_t n1, int blocksK1, int tpb, int reuseN,
                                           int trials, cudaStream_t s0, cudaStream_t s1) {
    // warm-up (untimed), both streams
    for (int w = 0; w < 3; ++w) {
        addKernel<<<blocksK0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        addKernel<<<blocksK1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
    }
    CUDA_CHECK(cudaStreamSynchronize(s0));
    CUDA_CHECK(cudaStreamSynchronize(s1));

    cudaEvent_t join, stop0, stop1;
    CUDA_CHECK(cudaEventCreate(&join));
    CUDA_CHECK(cudaEventCreate(&stop0));
    CUDA_CHECK(cudaEventCreate(&stop1));

    std::vector<double> wall_ms(trials), k0_ms(trials), k1_ms(trials);
    for (int t = 0; t < trials; ++t) {
        CUDA_CHECK(cudaEventRecord(join, s0));
        CUDA_CHECK(cudaStreamWaitEvent(s1, join, 0));

        for (int j = 0; j < reuseN; ++j) addKernel<<<blocksK0, tpb, 0, s0>>>(dA0, dB0, dC0, n0);
        CUDA_CHECK(cudaEventRecord(stop0, s0));

        for (int j = 0; j < reuseN; ++j) addKernel<<<blocksK1, tpb, 0, s1>>>(dA1, dB1, dC1, n1);
        CUDA_CHECK(cudaEventRecord(stop1, s1));

        CUDA_CHECK(cudaEventSynchronize(stop0));
        CUDA_CHECK(cudaEventSynchronize(stop1));

        float ms0 = 0, ms1 = 0;
        CUDA_CHECK(cudaEventElapsedTime(&ms0, join, stop0));
        CUDA_CHECK(cudaEventElapsedTime(&ms1, join, stop1));
        k0_ms[t] = ms0;
        k1_ms[t] = ms1;
        wall_ms[t] = std::max(ms0, ms1);
    }
    CUDA_CHECK(cudaEventDestroy(join));
    CUDA_CHECK(cudaEventDestroy(stop0));
    CUDA_CHECK(cudaEventDestroy(stop1));

    ConcurrentResult r;
    r.wall_ms = computeStats(wall_ms);
    Stats k0stat = computeStats(k0_ms);
    Stats k1stat = computeStats(k1_ms);
    double bytes0 = 3.0 * (double)n0 * 4.0 * (double)reuseN;  // A read + B read + C write, x reuseN
    double bytes1 = 3.0 * (double)n1 * 4.0 * (double)reuseN;
    r.k0_GBps_median = bytes0 / (k0stat.median / 1000.0) / 1e9;
    r.k1_GBps_median = bytes1 / (k1stat.median / 1000.0) / 1e9;
    r.agg_GBps_median = (bytes0 + bytes1) / (r.wall_ms.median / 1000.0) / 1e9;
    return r;
}

// Isolated (serial) reference used only for the overlap sanity check (00_conventions.md /
// prompt Verification: "wall < serial sum"). Not written to the CSV -- the CSV's
// single_k*_GBps_ref columns come from Phase 1, not this in-process re-measurement.
static double measureIsolatedMs(const float* dA, const float* dB, float* dC, size_t n,
                                 int blocks, int tpb, cudaStream_t s, int trials) {
    for (int w = 0; w < 3; ++w) addKernel<<<blocks, tpb, 0, s>>>(dA, dB, dC, n);
    CUDA_CHECK(cudaStreamSynchronize(s));

    cudaEvent_t start, stop;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));
    std::vector<double> ms(trials);
    for (int t = 0; t < trials; ++t) {
        CUDA_CHECK(cudaEventRecord(start, s));
        addKernel<<<blocks, tpb, 0, s>>>(dA, dB, dC, n);
        CUDA_CHECK(cudaEventRecord(stop, s));
        CUDA_CHECK(cudaEventSynchronize(stop));
        float e = 0;
        CUDA_CHECK(cudaEventElapsedTime(&e, start, stop));
        ms[t] = e;
    }
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    return computeStats(ms).median;
}

static bool checkCorrectness(const float* dC, size_t n) {
    size_t nsample = std::min<size_t>(n, 4096);
    std::vector<float> host(nsample);
    CUDA_CHECK(cudaMemcpy(host.data(), dC, nsample * sizeof(float), cudaMemcpyDeviceToHost));
    for (size_t i = 0; i < nsample; ++i) {
        if (std::fabs(host[i] - 3.0f) > 1e-5f) return false;
    }
    return true;
}

// Small local block-count search around the hinted value: two 1D passes (K0 then K1) rather
// than a full 2D grid search, to confirm the aggregate plateau without an expensive sweep.
// Documented simplification -- see README.md "Design notes".
static const std::vector<int> kCandidateMultipliers = {1, 2, 4};  // x hint, capped at 1024

static int clampBlocks(int b) { return std::min(b, 1024); }

// Factored out of main()'s original inline search so the v2 reuse-overlay sweep (below) can
// reuse the identical two-1D-pass search at an arbitrary reuse_N (needed to verify the
// saturated block count is stable across reuse_N before holding it fixed). 3 trials per
// candidate, same as the original inline version.
static void searchBlocks(const float* dA0, const float* dB0, float* dC0, size_t n0,
                          const float* dA1, const float* dB1, float* dC1, size_t n1, int hintK0,
                          int hintK1, int tpb, int reuseN, cudaStream_t s0, cudaStream_t s1,
                          int& outK0, int& outK1) {
    const int kSearchTrials = 3;
    int bestK0 = clampBlocks(hintK0);
    int bestK1 = clampBlocks(hintK1);

    double bestAgg = -1;
    for (int mult : kCandidateMultipliers) {
        int cand = clampBlocks(hintK0 * mult);
        ConcurrentResult r = measureConcurrent(dA0, dB0, dC0, n0, cand, dA1, dB1, dC1, n1, bestK1,
                                                tpb, reuseN, kSearchTrials, s0, s1);
        if (r.agg_GBps_median > bestAgg) { bestAgg = r.agg_GBps_median; bestK0 = cand; }
    }
    bestAgg = -1;
    for (int mult : kCandidateMultipliers) {
        int cand = clampBlocks(hintK1 * mult);
        ConcurrentResult r = measureConcurrent(dA0, dB0, dC0, n0, bestK0, dA1, dB1, dC1, n1, cand,
                                                tpb, reuseN, kSearchTrials, s0, s1);
        if (r.agg_GBps_median > bestAgg) { bestAgg = r.agg_GBps_median; bestK1 = cand; }
    }

    outK0 = bestK0;
    outK1 = bestK1;
}

// ---- v2 add-on: reuse-sweep overlay (prompts/02_two_kernel_size_v2.md) ----
// Writes results/phase2_reuse_results.csv, reuse_N in {1,2,4,8,16,32}, same size grid and
// per-cell config as the main sweep (config stays shared -- no green context, zero copy still
// OFF). Completely separate from the main sweep above: it never opens/writes phase2_results.csv
// or findings.json, so the frozen reuse=1 handoff to Phases 3/4 is never at risk.
//
// Block counts are searched once at reuse_N=1, verified stable at a second N (kReuseCheckN),
// then held fixed across all six reuse_N values for that cell -- so cost stays ~6x a single
// reuse=1 run rather than 6x a fresh search per N.
static const std::vector<int> kReuseNs = {1, 2, 4, 8, 16, 32};
static const int kReuseCheckN = 4;

static bool runReuseSweep(const std::vector<CellConfig>& cells, const std::string& outPath,
                           const EnvInfo& env) {
    const int kTrials = 10;

    FILE* csv = fopen(outPath.c_str(), "w");
    if (!csv) {
        fprintf(stderr, "Cannot open %s for writing\n", outPath.c_str());
        exit(1);
    }
    fprintf(csv,
            "mode,reuse_N,k0_bytes,k1_bytes,combined_read_footprint_bytes,"
            "blocks_k0,blocks_k1,threads_per_block,trials,"
            "wall_ms_median,agg_GBps_median,k0_GBps_median,k1_GBps_median,"
            "single_k0_GBps_ref,single_k1_GBps_ref,scaling_efficiency,"
            "gpu_clock_mhz,power_mode,soc_temp_c,cuda_version,driver_version\n");

    cudaStream_t s0, s1;
    CUDA_CHECK(cudaStreamCreate(&s0));
    CUDA_CHECK(cudaStreamCreate(&s1));

    bool anyCorrectnessFail = false;

    for (const CellConfig& cfg : cells) {
        size_t n0 = cfg.k0_bytes / sizeof(float);
        size_t n1 = cfg.k1_bytes / sizeof(float);

        float *dA0, *dB0, *dC0, *dA1, *dB1, *dC1;
        CUDA_CHECK(cudaMalloc(&dA0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dB0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dC0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dA1, n1 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dB1, n1 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dC1, n1 * sizeof(float)));

        fillKernel<<<256, cfg.threads_per_block, 0, s0>>>(dA0, dB0, n0);
        fillKernel<<<256, cfg.threads_per_block, 0, s1>>>(dA1, dB1, n1);
        CUDA_CHECK(cudaStreamSynchronize(s0));
        CUDA_CHECK(cudaStreamSynchronize(s1));

        // ---- determine block counts at reuse_N=1, verify stable at kReuseCheckN, hold fixed ----
        int k0AtN1, k1AtN1;
        searchBlocks(dA0, dB0, dC0, n0, dA1, dB1, dC1, n1, cfg.blocks_k0_hint, cfg.blocks_k1_hint,
                     cfg.threads_per_block, 1, s0, s1, k0AtN1, k1AtN1);
        int k0AtCheck, k1AtCheck;
        searchBlocks(dA0, dB0, dC0, n0, dA1, dB1, dC1, n1, cfg.blocks_k0_hint, cfg.blocks_k1_hint,
                     cfg.threads_per_block, kReuseCheckN, s0, s1, k0AtCheck, k1AtCheck);

        int heldK0 = k0AtN1, heldK1 = k1AtN1;
        if (k0AtN1 != k0AtCheck || k1AtN1 != k1AtCheck) {
            fprintf(stderr,
                    "NOTE: block saturation NOT stable across reuse_N at mode=%s k0=%zu k1=%zu "
                    "(N=1 -> %d,%d ; N=%d -> %d,%d). Using the element-wise max (safer, avoids "
                    "under-saturation) and holding it across the reuse sweep.\n",
                    cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, k0AtN1, k1AtN1, kReuseCheckN,
                    k0AtCheck, k1AtCheck);
            heldK0 = clampBlocks(std::max(k0AtN1, k0AtCheck));
            heldK1 = clampBlocks(std::max(k1AtN1, k1AtCheck));
        }

        size_t combinedFootprint = 2 * cfg.k0_bytes + 2 * cfg.k1_bytes;

        for (size_t ri = 0; ri < kReuseNs.size(); ++ri) {
            int reuseN = kReuseNs[ri];
            ConcurrentResult r = measureConcurrent(dA0, dB0, dC0, n0, heldK0, dA1, dB1, dC1, n1,
                                                    heldK1, cfg.threads_per_block, reuseN, kTrials,
                                                    s0, s1);

            double relStd = r.wall_ms.stddev / r.wall_ms.median;
            if (relStd > 0.05) {
                fprintf(stderr,
                        "WARNING: high variance (stddev/median=%.3f) at mode=%s k0=%zu k1=%zu "
                        "reuse_N=%d\n",
                        relStd, cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, reuseN);
            }

            // Correctness sample-check at only the smallest and largest reuse_N (Verification:
            // "sample-check both kernels at a couple of reuse_N values") -- the kernel body is
            // identical at every N, so a full per-N check would be redundant.
            if (ri == 0 || ri == kReuseNs.size() - 1) {
                if (!checkCorrectness(dC0, n0) || !checkCorrectness(dC1, n1)) {
                    fprintf(stderr,
                            "CORRECTNESS FAILURE (reuse overlay) at mode=%s k0=%zu k1=%zu "
                            "reuse_N=%d\n",
                            cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, reuseN);
                    anyCorrectnessFail = true;
                }
            }

            double scalingEff = -1.0;
            if (cfg.single_k0_GBps_ref > 0 && cfg.single_k1_GBps_ref > 0) {
                scalingEff = r.agg_GBps_median / (cfg.single_k0_GBps_ref + cfg.single_k1_GBps_ref);
            }

            fprintf(csv,
                    "%s,%d,%zu,%zu,%zu,%d,%d,%d,%d,"
                    "%.6f,%.3f,%.3f,%.3f,"
                    "%.3f,%.3f,%.6f,"
                    "%d,%s,%.1f,%s,%s\n",
                    cfg.mode.c_str(), reuseN, cfg.k0_bytes, cfg.k1_bytes, combinedFootprint,
                    heldK0, heldK1, cfg.threads_per_block, kTrials, r.wall_ms.median,
                    r.agg_GBps_median, r.k0_GBps_median, r.k1_GBps_median, cfg.single_k0_GBps_ref,
                    cfg.single_k1_GBps_ref, scalingEff, env.gpu_clock_mhz, env.power_mode.c_str(),
                    env.soc_temp_c, env.cuda_version.c_str(), env.driver_version.c_str());
        }

        CUDA_CHECK(cudaFree(dA0)); CUDA_CHECK(cudaFree(dB0)); CUDA_CHECK(cudaFree(dC0));
        CUDA_CHECK(cudaFree(dA1)); CUDA_CHECK(cudaFree(dB1)); CUDA_CHECK(cudaFree(dC1));

        fprintf(stderr, "done (reuse overlay) mode=%s k0=%zu k1=%zu held_blocks=(%d,%d)\n",
                cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, heldK0, heldK1);
    }

    CUDA_CHECK(cudaStreamDestroy(s0));
    CUDA_CHECK(cudaStreamDestroy(s1));
    fclose(csv);

    if (anyCorrectnessFail) {
        fprintf(stderr, "STOP: correctness check failed in reuse overlay, see above.\n");
        return false;
    }
    fprintf(stderr, "Wrote %s\n", outPath.c_str());
    return true;
}

int main(int argc, char** argv) {
    std::string configPath = "results/phase2_config.csv";
    std::string outPath = "results/phase2_results.csv";
    std::string reuseOutPath;  // empty => standard reuse=1 sweep (default, unchanged behavior)
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--config" && i + 1 < argc) configPath = argv[++i];
        else if (a == "--out" && i + 1 < argc) outPath = argv[++i];
        else if (a == "--reuse-out" && i + 1 < argc) reuseOutPath = argv[++i];
    }

    const int kTrials = 10;
    const int kIsolatedTrials = 5;

    EnvInfo env = queryEnv();
    fprintf(stderr, "GPU clock: %d MHz, power mode: %s, SoC temp: %.1f C, CUDA %s, driver %s\n",
            env.gpu_clock_mhz, env.power_mode.c_str(), env.soc_temp_c, env.cuda_version.c_str(),
            env.driver_version.c_str());

    std::vector<CellConfig> cells = readConfig(configPath);
    if (cells.empty()) {
        fprintf(stderr, "No cells to run (empty/missing config %s)\n", configPath.c_str());
        return 1;
    }

    // v2 add-on (prompts/02_two_kernel_size_v2.md): --reuse-out switches entirely to the
    // reuse-sweep overlay mode -- it does NOT also write outPath, so the frozen reuse=1
    // phase2_results.csv / findings.json handoff can never be clobbered by this mode.
    if (!reuseOutPath.empty()) {
        return runReuseSweep(cells, reuseOutPath, env) ? 0 : 1;
    }

    FILE* csv = fopen(outPath.c_str(), "w");
    if (!csv) {
        fprintf(stderr, "Cannot open %s for writing\n", outPath.c_str());
        return 1;
    }
    fprintf(csv,
            "mode,k0_bytes,k1_bytes,combined_read_footprint_bytes,"
            "blocks_k0,blocks_k1,threads_per_block,trials,"
            "wall_ms_median,agg_GBps_median,k0_GBps_median,k1_GBps_median,"
            "single_k0_GBps_ref,single_k1_GBps_ref,scaling_efficiency,"
            "gpu_clock_mhz,power_mode,soc_temp_c,cuda_version,driver_version\n");

    cudaStream_t s0, s1;
    CUDA_CHECK(cudaStreamCreate(&s0));
    CUDA_CHECK(cudaStreamCreate(&s1));

    bool anyCorrectnessFail = false;

    for (const CellConfig& cfg : cells) {
        size_t n0 = cfg.k0_bytes / sizeof(float);
        size_t n1 = cfg.k1_bytes / sizeof(float);

        float *dA0, *dB0, *dC0, *dA1, *dB1, *dC1;
        CUDA_CHECK(cudaMalloc(&dA0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dB0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dC0, n0 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dA1, n1 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dB1, n1 * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dC1, n1 * sizeof(float)));

        fillKernel<<<256, cfg.threads_per_block, 0, s0>>>(dA0, dB0, n0);
        fillKernel<<<256, cfg.threads_per_block, 0, s1>>>(dA1, dB1, n1);
        CUDA_CHECK(cudaStreamSynchronize(s0));
        CUDA_CHECK(cudaStreamSynchronize(s1));

        // ---- confirm aggregate plateau: 1D search on K0 blocks, then K1 blocks (reuse_N=1) ----
        int bestK0, bestK1;
        searchBlocks(dA0, dB0, dC0, n0, dA1, dB1, dC1, n1, cfg.blocks_k0_hint, cfg.blocks_k1_hint,
                     cfg.threads_per_block, /*reuseN=*/1, s0, s1, bestK0, bestK1);

        // ---- final measured cell at the chosen (bestK0, bestK1) ----
        ConcurrentResult r = measureConcurrent(dA0, dB0, dC0, n0, bestK0, dA1, dB1, dC1, n1,
                                                bestK1, cfg.threads_per_block, /*reuseN=*/1,
                                                kTrials, s0, s1);

        double relStd = r.wall_ms.stddev / r.wall_ms.median;
        if (relStd > 0.05) {
            fprintf(stderr, "WARNING: high variance (stddev/median=%.3f) at mode=%s k0=%zu k1=%zu\n",
                    relStd, cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes);
        }

        // ---- overlap sanity check (Verification: wall < serial sum), not stored in CSV ----
        double isoK0 = measureIsolatedMs(dA0, dB0, dC0, n0, bestK0, cfg.threads_per_block, s0,
                                          kIsolatedTrials);
        double isoK1 = measureIsolatedMs(dA1, dB1, dC1, n1, bestK1, cfg.threads_per_block, s1,
                                          kIsolatedTrials);
        double serialSum = isoK0 + isoK1;
        if (r.wall_ms.median >= serialSum) {
            fprintf(stderr,
                    "WARNING: no measured overlap at mode=%s k0=%zu k1=%zu "
                    "(wall_ms=%.4f >= serial_sum_ms=%.4f) -- streams may not be concurrent\n",
                    cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, r.wall_ms.median, serialSum);
        }

        if (!checkCorrectness(dC0, n0) || !checkCorrectness(dC1, n1)) {
            fprintf(stderr, "CORRECTNESS FAILURE at mode=%s k0=%zu k1=%zu\n", cfg.mode.c_str(),
                    cfg.k0_bytes, cfg.k1_bytes);
            anyCorrectnessFail = true;
        }

        double scalingEff = -1.0;
        if (cfg.single_k0_GBps_ref > 0 && cfg.single_k1_GBps_ref > 0) {
            scalingEff = r.agg_GBps_median / (cfg.single_k0_GBps_ref + cfg.single_k1_GBps_ref);
        }

        size_t combinedFootprint = 2 * cfg.k0_bytes + 2 * cfg.k1_bytes;
        fprintf(csv,
                "%s,%zu,%zu,%zu,%d,%d,%d,%d,"
                "%.6f,%.3f,%.3f,%.3f,"
                "%.3f,%.3f,%.6f,"
                "%d,%s,%.1f,%s,%s\n",
                cfg.mode.c_str(), cfg.k0_bytes, cfg.k1_bytes, combinedFootprint, bestK0, bestK1,
                cfg.threads_per_block, kTrials, r.wall_ms.median, r.agg_GBps_median,
                r.k0_GBps_median, r.k1_GBps_median, cfg.single_k0_GBps_ref, cfg.single_k1_GBps_ref,
                scalingEff, env.gpu_clock_mhz, env.power_mode.c_str(), env.soc_temp_c,
                env.cuda_version.c_str(), env.driver_version.c_str());

        CUDA_CHECK(cudaFree(dA0)); CUDA_CHECK(cudaFree(dB0)); CUDA_CHECK(cudaFree(dC0));
        CUDA_CHECK(cudaFree(dA1)); CUDA_CHECK(cudaFree(dB1)); CUDA_CHECK(cudaFree(dC1));

        fprintf(stderr, "done mode=%s k0=%zu k1=%zu blocks=(%d,%d)\n", cfg.mode.c_str(),
                cfg.k0_bytes, cfg.k1_bytes, bestK0, bestK1);
    }

    CUDA_CHECK(cudaStreamDestroy(s0));
    CUDA_CHECK(cudaStreamDestroy(s1));
    fclose(csv);

    if (anyCorrectnessFail) {
        fprintf(stderr, "STOP: correctness check failed, see above.\n");
        return 1;
    }
    fprintf(stderr, "Wrote %s\n", outPath.c_str());
    return 0;
}
