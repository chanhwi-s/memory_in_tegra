# Work Prompt — Phase 2: Two-Kernel Size Sweep (concurrent, no green context, no zero copy)

**Prerequisites:** read `../OVERVIEW.md` and `00_conventions.md` first. Follow the standard phase
layout, worklog, and findings-handoff rules there. Output goes under
`experiments/02_two_kernel_size/`. Do not modify files outside your phase directory.

## Dependency (important for parallel work)
- This phase **consumes** `experiments/01_single_kernel_size/findings.json`
  (measured DRAM peak, cache tier steps, per-size saturation block counts, recommended tpb).
- You may implement the full harness, sweep driver, and plotting **now**, independently of Phase 1.
- **Measured runs and parameter choices** (which sizes, the asymmetric `k`) must be read from Phase 1's
  `findings.json` **at run time**. If it is not present yet, expose those as CLI/config parameters with
  sensible placeholder defaults and a clear `TODO(read from phase1 findings)` — **never fabricate the
  numbers**. Record in your worklog that the run is pending Phase 1.

## Goal
Characterize two concurrent `C = A + B` kernels (same kernel as Phase 1) as their sizes grow, with
**green context OFF and zero copy OFF**. Find where concurrency starts to degrade aggregate
throughput (shared-cache / memory contention onset) — this is the roofline that Phases 3 and 4 target.

## Setup
- Two kernels K0, K1, each with its own buffers, launched **concurrently on two CUDA streams**.
- Same uniform/coalesced grid-stride A+B kernel and plain `cudaMalloc` cached path as Phase 1.
- Saturation: use Phase 1's per-size saturation block counts as the starting point for each kernel;
  confirm the aggregate plateau. Block count remains a knob, not a reported axis.

## Swept axes
**2a — symmetric.** Both kernels size S (equal). Sweep S across the same tiers as Phase 1
(densify near L2 = 4 MB and L2+SLC = 8 MB, per combined footprint of both kernels).
**2b — asymmetric.** K0 fixed at S=1 MB; grow K1 to `k`. Choose `k` from Phase 1 findings:
the cache-overflow / bound-crossover point (`tier_steps`). Sweep K1 up to and past `k`.

## Metrics
For each cell: **aggregate throughput** (both kernels), **per-kernel throughput**, and total
wall time (both streams complete). Compare against:
- single-kernel baseline from Phase 1 (same per-kernel size), and
- the ideal `2×` (perfect scaling).
Contention = aggregate < 2× isolated, or per-kernel < isolated. Same measurement discipline as
Phase 1 (warm-up, CUDA events, ≥10 trials, median/min/max/std, flag >5% variance).

## CSV — `results/phase2_results.csv`
```
mode(symmetric|asymmetric), k0_bytes, k1_bytes, combined_read_footprint_bytes,
blocks_k0, blocks_k1, threads_per_block, trials,
wall_ms_median, agg_GBps_median, k0_GBps_median, k1_GBps_median,
single_k0_GBps_ref, single_k1_GBps_ref, scaling_efficiency,
gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
```
(`scaling_efficiency = agg / (single_k0_ref + single_k1_ref)`, `_ref` read from Phase 1 findings.)

## Plots — `results/plots/`
1. `sym_agg_vs_footprint.png`: aggregate + per-kernel GB/s and scaling_efficiency vs combined
   footprint (log x); mark L2 / L2+SLC / DRAM-peak references and the contention-onset point.
2. `asym_vs_k1.png`: per-kernel and aggregate GB/s vs K1 size (K0 fixed 1 MB), mark `k`.

## Verification
- Confirm the two streams truly overlap by timing only: measured wall time must be well below the
  serial sum of the two isolated kernel times. If wall ≈ serial sum, they are not overlapping — fix
  the stream/launch setup before trusting any results.
- Sanity: when combined footprint ≪ L2, scaling_efficiency ≈ 1 (little contention); as combined
  footprint exceeds cache, efficiency should drop. If not, investigate before reporting.
- Correctness sample-check on both kernels' outputs.

## Findings handoff — `findings.json` (`results` keys)
```json
"results": {
  "symmetric_contention_onset": { "per_kernel_bytes": 0, "combined_footprint_bytes": 0, "scaling_efficiency": 0.0 },
  "symmetric_roofline_points": { "onset": {"per_kernel_bytes":0}, "ninety_pct": {"per_kernel_bytes":0} },
  "asymmetric_k_used_bytes": 0,
  "asymmetric_result_at_k": { "agg_GBps": 0.0, "k0_GBps": 0.0, "k1_GBps": 0.0 },
  "recommended_phase3_test_points": [ {"mode":"symmetric","per_kernel_bytes":0}, {"mode":"asymmetric","k1_bytes":0} ]
}
```
Also write `FINDINGS.md` (prose) and a worklog entry. `consumed` must list the Phase 1 findings path.
The `recommended_phase3_test_points` should include the contention onset **and a point ~90% below it**
(Phases 3/4 test at and just below the roofline).
