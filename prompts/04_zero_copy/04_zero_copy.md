# Work Prompt — Phase 4: Zero Copy (cache bypass) on one kernel + reuse crossover

**Prerequisites:** read `../OVERVIEW.md` and `00_conventions.md` first. Standard phase layout,
worklog, findings rules apply. Output under `experiments/04_zero_copy/`. Do not modify files outside
your phase directory.

## Dependency (important for parallel work)
- Consumes `experiments/02_two_kernel_size/findings.json` (roofline test points, asymmetric `k`),
  `experiments/03_green_context/findings.json` (`configs_for_phase4`: which points use green context
  and the SM splits), and `experiments/01_single_kernel_size/findings.json` (reuse-crossover note,
  tier steps).
- Implement the zero-copy harness, reuse sweep, and plotting **now**. Read the actual test points,
  green-context configs, and reuse ranges from upstream `findings.json` at run time; if absent,
  expose as CLI/config with `TODO(read from upstream findings)` placeholders and **do not fabricate**.

## Goal
On top of the Phase 2/3 two-kernel configs, apply **zero copy (GPU-cache-bypass, straight to DRAM)**
to the **large / streaming kernel**, and sweep **reuse N** to locate the crossover where zero copy
stops helping. If bypassing cache on the large kernel improves aggregate throughput, the bottleneck
was **memory (L2/SLC contention) bound**, not compute — that is the headline result.

## Zero-copy implementation notes
- On the Jetson iGPU, implement zero copy via **mapped pinned memory**: `cudaHostAlloc(..., cudaHostAllocMapped)`
  + `cudaHostGetDevicePointer` (or `cudaHostRegister` on existing host memory), so the kernel's reads go
  to system DRAM **without being cached in GPU L2**. Apply it to **one kernel only** (the large one);
  the other kernel keeps the normal `cudaMalloc` cached path.
- **Confirm the bypass by throughput behavior (no profiler needed).** A truly cache-bypassing kernel
  has two signatures: (a) its throughput is **flat vs reuse N** (no cache reuse to gain), while the
  cached path speeds up as N grows; and (b) even at small footprints it **never exceeds DRAM peak**
  (cached path does, via cache hits). Use these behavioral checks as the bypass evidence.

## Swept axes
- **test point / config** (from Phase 2 & 3): the roofline points, symmetric and asymmetric, each in
  the config Phase 3 recommended (shared or green). For each, compare **large-kernel cached** vs
  **large-kernel zero-copy**.
- **reuse N**: `1, 2, 4, 8, 16, 32` (full-buffer reuse via N launches, same definition as Phase 1).
  This is the axis that should reveal the crossover: zero copy favored at low reuse, cache favored as
  reuse grows.

## Metrics
Aggregate + per-kernel throughput and wall time; same discipline (warm-up, CUDA events, ≥10 trials,
median/min/max/std, >5% flag). Primary output = **zero-copy delta vs cached** at each (test point,
config, reuse N), and the **crossover reuse N** where the sign of the delta flips.

## CSV — `results/phase4_results.csv`
```
test_point_id, mode(symmetric|asymmetric), config(shared|green), sm_split,
k0_bytes, k1_bytes, large_kernel_id, large_kernel_path(cached|zerocopy), reuse_N,
blocks_k0, blocks_k1, threads_per_block, trials,
wall_ms_median, agg_GBps_median, k0_GBps_median, k1_GBps_median,
large_kernel_GBps_median, delta_vs_cached_pct,
gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
```

## Plots — `results/plots/`
1. `zc_vs_cached_reuse.png`: aggregate GB/s vs reuse N, cached vs zero-copy lines, one panel per test
   point/config; mark the crossover N where they cross.
2. `zc_benefit_map.png`: heatmap of zero-copy delta_pct over (test point) × (reuse N).

## Verification
- Confirm cache bypass by throughput behavior (no profiler): the zero-copy large kernel's throughput
  is ~flat across reuse N and never exceeds DRAM peak, whereas its cached counterpart rises with N
  and can exceed DRAM peak. If the zero-copy path shows reuse-dependent speedup, the mapping is NOT
  bypassing cache — fix it before reporting.
- Sanity: at reuse N=1 with combined footprint > cache, zero copy should be ≥ cached (no reuse to
  lose, less pollution); as reuse N grows for a cache-fitting kernel, cached should overtake. If the
  crossover never appears, state whether the workload was DRAM-bound at every N (in which case zero
  copy ≈ cached throughout) and back it with the profiled numbers.
- Correctness sample-check both kernels.

## Findings handoff — `findings.json` (`results` keys)
```json
"results": {
  "per_config": [
    { "test_point_id": "sym_onset", "config": "green",
      "crossover_reuse_N": 0, "zc_delta_at_N1_pct": 0.0,
      "bound_conclusion": "memory-bound|compute-bound|dram-bound-throughout",
      "bypass_confirmed_by_throughput": true }
  ],
  "headline": "one-sentence conclusion: where/when zero copy helped and what that implies about the bottleneck"
}
```
Also write `FINDINGS.md` (prose, this is the study's payoff section) and a worklog entry; list all
consumed upstream findings.
