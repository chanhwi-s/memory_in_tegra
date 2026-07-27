// Phase 1 — single-kernel memory-hierarchy characterization (see prompts/01_single_kernel_size.md)
// Build: nvcc -O3 -arch=sm_87 -o phase1_bench phase1_bench.cu
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

// ---- one measured cell: fixed size S, reuse N, blocks, threadsPerBlock ----

struct CellResult {
    size_t n_elems;
    int reuse_N;
    int blocks;
    int threads_per_block;
    int trials;
    Stats time_ms;
    double per_launch_ms_median;
    double achieved_GBps_median;
};

static CellResult measureCell(const float* dA, const float* dB, float* dC, size_t n_elems,
                               int reuse_N, int blocks, int threads_per_block, int trials) {
    // warm-up: untimed launches before the measured cell (00_conventions.md #4)
    for (int w = 0; w < 3; ++w) {
        addKernel<<<blocks, threads_per_block>>>(dA, dB, dC, n_elems);
    }
    CUDA_CHECK(cudaDeviceSynchronize());

    cudaEvent_t start, stop;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    std::vector<double> times_ms;
    times_ms.reserve(trials);
    for (int t = 0; t < trials; ++t) {
        CUDA_CHECK(cudaEventRecord(start));
        for (int j = 0; j < reuse_N; ++j) {
            addKernel<<<blocks, threads_per_block>>>(dA, dB, dC, n_elems);
        }
        CUDA_CHECK(cudaEventRecord(stop));
        CUDA_CHECK(cudaEventSynchronize(stop));
        float ms = 0;
        CUDA_CHECK(cudaEventElapsedTime(&ms, start, stop));
        times_ms.push_back(ms);
    }
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));

    CellResult r;
    r.n_elems = n_elems;
    r.reuse_N = reuse_N;
    r.blocks = blocks;
    r.threads_per_block = threads_per_block;
    r.trials = trials;
    r.time_ms = computeStats(times_ms);
    r.per_launch_ms_median = r.time_ms.median / reuse_N;
    double bytes = 3.0 * (double)n_elems * 4.0 * (double)reuse_N;  // A read + B read + C write
    r.achieved_GBps_median = bytes / (r.time_ms.median / 1000.0) / 1e9;
    return r;
}

// ---- correctness check ----

static bool checkCorrectness(const float* dC, size_t n_elems) {
    size_t nsample = std::min<size_t>(n_elems, 4096);
    std::vector<float> host(nsample);
    CUDA_CHECK(cudaMemcpy(host.data(), dC, nsample * sizeof(float), cudaMemcpyDeviceToHost));
    for (size_t i = 0; i < nsample; ++i) {
        if (std::fabs(host[i] - 3.0f) > 1e-5f) return false;
    }
    return true;
}

static std::vector<size_t> parseSizesArg(const std::string& csv) {
    std::vector<size_t> out;
    size_t start = 0;
    while (start <= csv.size()) {
        size_t comma = csv.find(',', start);
        std::string tok = trim(csv.substr(start, comma == std::string::npos ? std::string::npos : comma - start));
        if (!tok.empty()) out.push_back(static_cast<size_t>(std::stoull(tok)));
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return out;
}

int main(int argc, char** argv) {
    std::string outPath = "results/phase1_results.csv";
    std::string sizesArg;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--out" && i + 1 < argc) outPath = argv[++i];
        if (std::string(argv[i]) == "--sizes" && i + 1 < argc) sizesArg = argv[++i];
    }

    // Fallback list -- only used when --sizes is not supplied, so the binary is still
    // runnable standalone. Prefer shared/size_grid.py::phase1_sizes_bytes() via
    // scripts/gen_sizes.py / scripts/run.sh (prompts/05_unified_size_grid_and_plots.md Change 1).
    const std::vector<size_t> fallbackSizesBytes = {
        32ull * 1024,        64ull * 1024,        128ull * 1024,       256ull * 1024,
        512ull * 1024,       1ull * 1024 * 1024,  2ull * 1024 * 1024,  3ull * 1024 * 1024,
        4ull * 1024 * 1024,  6ull * 1024 * 1024,  8ull * 1024 * 1024,  12ull * 1024 * 1024,
        16ull * 1024 * 1024, 24ull * 1024 * 1024, 48ull * 1024 * 1024, 96ull * 1024 * 1024,
    };
    std::vector<size_t> sizesBytes;
    if (!sizesArg.empty()) {
        sizesBytes = parseSizesArg(sizesArg);
        std::sort(sizesBytes.begin(), sizesBytes.end());
    } else {
        fprintf(stderr,
                "WARNING: --sizes not given, using hardcoded fallback size list "
                "(not the shared/size_grid.py grid). Pass --sizes to use the shared grid.\n");
        sizesBytes = fallbackSizesBytes;
    }

    const std::vector<int> reuseNs = {1, 2, 4, 8, 16, 32};
    const std::vector<int> blockCounts = {16, 32, 64, 128, 256, 512, 1024};
    const int kThreadsPerBlockDefault = 256;
    const int kTrials = 10;
    const size_t kMidSizeForTPCheck = 4ull * 1024 * 1024;  // one-off threads-per-block check

    EnvInfo env = queryEnv();
    fprintf(stderr, "GPU clock: %d MHz, power mode: %s, SoC temp: %.1f C, CUDA %s, driver %s\n",
            env.gpu_clock_mhz, env.power_mode.c_str(), env.soc_temp_c, env.cuda_version.c_str(),
            env.driver_version.c_str());

    FILE* csv = fopen(outPath.c_str(), "w");
    if (!csv) {
        fprintf(stderr, "Cannot open %s for writing\n", outPath.c_str());
        return 1;
    }
    fprintf(csv,
            "size_per_buffer_bytes,read_footprint_bytes,total_footprint_bytes,"
            "reuse_N,blocks,threads_per_block,saturated,"
            "trials,time_ms_median,time_ms_min,time_ms_max,time_ms_std,"
            "per_launch_ms_median,achieved_GBps_median,"
            "gpu_clock_mhz,power_mode,soc_temp_c,cuda_version,driver_version\n");

    bool anyCorrectnessFail = false;
    bool didCorrectnessCheck = false;

    for (size_t sizeBytes : sizesBytes) {
        size_t n = sizeBytes / sizeof(float);

        float *dA, *dB, *dC;
        CUDA_CHECK(cudaMalloc(&dA, n * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dB, n * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&dC, n * sizeof(float)));

        int fillBlocks = 256;
        fillKernel<<<fillBlocks, kThreadsPerBlockDefault>>>(dA, dB, n);
        CUDA_CHECK(cudaDeviceSynchronize());

        for (int reuseN : reuseNs) {
            std::vector<CellResult> cellsThisGroup;
            for (int blocks : blockCounts) {
                CellResult r = measureCell(dA, dB, dC, n, reuseN, blocks, kThreadsPerBlockDefault, kTrials);
                cellsThisGroup.push_back(r);
            }

            if (!didCorrectnessCheck) {
                if (!checkCorrectness(dC, n)) {
                    fprintf(stderr, "CORRECTNESS FAILURE at size=%zu reuse=%d\n", sizeBytes, reuseN);
                    anyCorrectnessFail = true;
                }
                didCorrectnessCheck = true;
            }

            double maxBw = 0;
            for (auto& r : cellsThisGroup) maxBw = std::max(maxBw, r.achieved_GBps_median);
            double satThreshold = 0.98 * maxBw;

            for (auto& r : cellsThisGroup) {
                double relStd = r.time_ms.stddev / r.time_ms.median;
                if (relStd > 0.05) {
                    fprintf(stderr,
                            "WARNING: high variance (stddev/median=%.3f) at size=%zu reuse=%d blocks=%d\n",
                            relStd, sizeBytes, reuseN, r.blocks);
                }
                int saturated = (r.achieved_GBps_median >= satThreshold) ? 1 : 0;
                fprintf(csv,
                        "%zu,%zu,%zu,%d,%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.3f,%d,%s,%.1f,%s,%s\n",
                        sizeBytes, 2 * sizeBytes, 3 * sizeBytes, reuseN, r.blocks, r.threads_per_block,
                        saturated, r.trials, r.time_ms.median, r.time_ms.min, r.time_ms.max,
                        r.time_ms.stddev, r.per_launch_ms_median, r.achieved_GBps_median,
                        env.gpu_clock_mhz, env.power_mode.c_str(), env.soc_temp_c,
                        env.cuda_version.c_str(), env.driver_version.c_str());
            }
        }

        // one-off threads-per-block check at the mid size, reuse=1, representative blocks=256
        if (sizeBytes == kMidSizeForTPCheck) {
            for (int tpb : {128, 256, 512}) {
                CellResult r = measureCell(dA, dB, dC, n, /*reuseN=*/1, /*blocks=*/256, tpb, kTrials);
                fprintf(csv,
                        "%zu,%zu,%zu,%d,%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.3f,%d,%s,%.1f,%s,%s\n",
                        sizeBytes, 2 * sizeBytes, 3 * sizeBytes, 1, 256, tpb, 0, r.trials,
                        r.time_ms.median, r.time_ms.min, r.time_ms.max, r.time_ms.stddev,
                        r.per_launch_ms_median, r.achieved_GBps_median, env.gpu_clock_mhz,
                        env.power_mode.c_str(), env.soc_temp_c, env.cuda_version.c_str(),
                        env.driver_version.c_str());
            }
        }

        CUDA_CHECK(cudaFree(dA));
        CUDA_CHECK(cudaFree(dB));
        CUDA_CHECK(cudaFree(dC));

        fprintf(stderr, "done size=%zu bytes\n", sizeBytes);
    }

    fclose(csv);

    if (anyCorrectnessFail) {
        fprintf(stderr, "STOP: correctness check failed, see above.\n");
        return 1;
    }
    fprintf(stderr, "Wrote %s\n", outPath.c_str());
    return 0;
}
