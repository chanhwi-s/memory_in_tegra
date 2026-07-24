# Work Prompt — Phase 1: Single-Kernel Memory-Hierarchy Characterization

**Prerequisites:** read `../OVERVIEW.md` (study context + hardware facts) and
`00_conventions.md` (directory layout, findings handoff, env logging, measurement discipline)
before starting. This prompt only states what is specific to Phase 1.

**Output location:** create everything under `experiments/01_single_kernel_size/` following the
standard phase layout in `00_conventions.md`. Do not modify files outside your phase directory.

---

## Goal

Establish the clean single-kernel baseline: how achieved bandwidth for a memory-bound kernel
(`C = A + B`) behaves as working-set size and reuse vary, with **zero copy OFF and green context
OFF**. Identify the cache-tier bandwidth steps (L1 → L2 → SLC → DRAM), the measured DRAM peak, and
per-size saturation block counts. These feed every later phase via `findings.json`.

Expected: **no compute-bound crossover** (arithmetic intensity ≈ 0.08 flop/byte). The roofline is
the bandwidth ceiling of each cache tier.

---

## Kernel (uniform, coalesced, grid-stride)

```cuda
__global__ void addKernel(const float* __restrict__ A,
                          const float* __restrict__ B,
                          float* __restrict__ C, size_t n) {
    size_t stride = (size_t)gridDim.x * blockDim.x;
    for (size_t i = (size_t)blockIdx.x * blockDim.x + threadIdx.x;
         i < n; i += stride) {
        C[i] = A[i] + B[i];
    }
}
```

- Grid-stride loop so block count is decoupled from data size (saturation knob).
- Allocate A, B, C with **plain `cudaMalloc`** (normal GPU-cached path). Initialize A, B once.
- Do **not** re-init / memset / reallocate between reuse launches — data must stay resident.

---

## Swept axes (only these two are reported)

**Axis 1 — size.** Per-buffer bytes S (= n·4). Report S, read-footprint 2·S, total-footprint 3·S.
Densify near L2 (4 MB) and L2+SLC (8 MB). Suggested S:
`32KB, 64KB, 128KB, 256KB, 512KB, 1MB, 2MB, 3MB, 4MB, 6MB, 8MB, 12MB, 16MB, 24MB, 48MB, 96MB`.

**Axis 2 — reuse N.** `1, 2, 4, 8, 16, 32` launches over the identical buffers.

**Saturation knob (not an axis).** For each (S, N): sweep `blocks ∈ {16,32,64,128,256,512,1024}`
with `threadsPerBlock = 256`, find the throughput plateau, report the plateau value, and record
the **minimum blocks to saturate**. Do a one-off `threadsPerBlock ∈ {128,256,512}` check at one
mid size to confirm 256 is reasonable, then hold it fixed.

---

## Measurement (see `00_conventions.md` §4 for the full discipline)

- Warm-up ≥3 launches; time the N-launch loop with CUDA events; 10 trials; median/min/max/std.
- Achieved BW: bytes = `3·n·4·N`; `achieved_GBps = bytes / median_time_s / 1e9`.
- Lock clocks (`nvpmodel -m 0`, `jetson_clocks`), CPU idle, single GPU process.

### CSV — `results/phase1_results.csv`
```
size_per_buffer_bytes, read_footprint_bytes, total_footprint_bytes,
reuse_N, blocks, threads_per_block, saturated,
trials, time_ms_median, time_ms_min, time_ms_max, time_ms_std,
per_launch_ms_median, achieved_GBps_median,
gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
```

### Plots — `results/plots/`
1. `bw_vs_footprint.png`: achieved_GBps vs read_footprint (log x), one line per reuse_N;
   annotate 4 MB (L2), 8 MB (L2+SLC), and measured DRAM-peak reference lines.
2. `saturation.png`: achieved_GBps vs blocks for 3 representative sizes (L2-resident, SLC-region,
   DRAM-bound) to justify the plateau choice.

---

## Verification (do not skip)

- **Correctness:** sample-check `C[i] == A[i] + B[i]` after a run.
- **Saturation valid:** top block counts within ~2% of each other.
- **Tier sanity:** (a) largest size (footprint ≫ 8 MB) → reuse gives ~no BW gain, BW ≈ measured DRAM
  peak; (b) small size (footprint ≤ 4 MB) → reuse pushes BW **above** DRAM peak (L2 hits). If these
  don't appear, STOP and report — the cache path or reuse loop is misbehaving.
- Flag cells with stddev/median > 5%.

---

## Findings handoff — `findings.json` (envelope per `00_conventions.md` §2)

Populate `results` with the numbers Phase 2+ will consume:
```json
"results": {
  "measured_dram_peak_GBps": 0.0,
  "tier_steps": {
    "l2_resident_max_read_footprint_bytes": 0,     // largest footprint still L2-served
    "slc_region_max_read_footprint_bytes": 0,      // largest footprint still cache-served (L2+SLC)
    "dram_bound_min_read_footprint_bytes": 0        // footprint at/after which BW ≈ DRAM peak
  },
  "saturation_blocks_by_size": { "1048576": 0, "4194304": 0, "...": 0 },
  "recommended_threads_per_block": 256,
  "reuse_crossover_note": "where reuse stops lifting BW vs footprint",
  "compute_bound_observed": false
}
```
Also write `FINDINGS.md` summarizing, in prose, the observed tier boundaries, DRAM peak, saturation
behavior, and any surprises — this is what a human (and the next prompt author) reads first.

Deliver: working build (`nvcc -arch=sm_87`), the CSV, both plots, `README.md`, `FINDINGS.md`,
`findings.json`, and the `shared/env.md` env log.
