# Work Prompt — Phase 3: Green Context (SM partitioning) on the Two-Kernel Roofline

**Prerequisites:** read `../OVERVIEW.md` and `00_conventions.md` first. Standard phase layout,
worklog, findings rules apply. Output under `experiments/03_green_context/`. Do not modify files
outside your phase directory.

## Dependency (important for parallel work)
- Consumes `experiments/02_two_kernel_size/findings.json` (the `recommended_phase3_test_points`:
  contention onset and the ~90%-below point, for symmetric and asymmetric) and
  `experiments/01_single_kernel_size/findings.json` (saturation blocks, tpb).
- Implement the green-context harness, partition-ratio sweep, and plotting **now**. Read the actual
  **test-point sizes and partition ratios** from upstream `findings.json` at run time; if absent,
  expose as CLI/config with `TODO(read from phase2 findings)` placeholders and **do not fabricate**.

## Goal
At the Phase 2 roofline points (and ~90% below them), compare **shared-SM** (no green context, the
Phase 2 baseline) vs **partitioned-SM** (green context) for two concurrent A+B kernels. Quantify the
benefit of giving each kernel a disjoint SM set (L1/occupancy isolation + reduced scheduling
contention). Zero copy stays **OFF** this phase.

## Green context implementation notes
- Use the CUDA driver green-context API (CUDA ≥ 12.4): generate an SM resource descriptor, split SMs
  by count (`cuDevSmResourceSplitByCount` / equivalent), create a green context per partition
  (`cuGreenCtxCreate`), and launch each kernel into its partition (via the stream created from the
  green context). **First verify the API and required CUDA version are available on this device**; if
  not, stop and report in the worklog rather than faking partitioning.
- Baseline (shared) = same launch as Phase 2 (both kernels on all 16 SMs via two streams).

## Swept axes
- **test point** (from Phase 2): {symmetric onset, symmetric 90%, asymmetric at `k`, ...}.
- **partition ratio** (green context only): SMs split between K0:K1. For symmetric start at **8:8**;
  also sweep a few ratios (e.g. 4:12, 6:10, 8:8, 10:6, 12:4) to find the best split. For asymmetric,
  sweep ratios around the size ratio of the two kernels.
- For each: measure **shared vs partitioned**.

## Metrics
Aggregate + per-kernel throughput and wall time, same discipline as earlier phases (warm-up, CUDA
events, ≥10 trials, median/min/max/std, >5% variance flag). Primary output = **delta vs Phase 2
shared baseline** at each test point.

## CSV — `results/phase3_results.csv`
```
test_point_id, mode(symmetric|asymmetric), k0_bytes, k1_bytes,
config(shared|green), sm_split_k0, sm_split_k1, blocks_k0, blocks_k1, threads_per_block,
trials, wall_ms_median, agg_GBps_median, k0_GBps_median, k1_GBps_median,
delta_vs_shared_pct, gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
```

## Plots — `results/plots/`
1. `green_vs_shared.png`: aggregate GB/s, shared vs best-green, per test point (grouped bars).
2. `partition_sweep.png`: aggregate + per-kernel GB/s vs SM split ratio, for the onset test point.

## Verification
- Confirm partitioning actually took effect **without a profiler**: in a debug build, have each
  kernel record its SM id via the `%smid` special register and assert each kernel only ran on its
  assigned SM set. Report the observed SM sets.
- Sanity: green context should help most where per-SM working set is near L1 and/or scheduling
  contention was high; it should NOT help (may slightly hurt via reduced total SM count per kernel)
  when the workload is purely DRAM-bandwidth-bound. State which regime each test point fell in.

## Findings handoff — `findings.json` (`results` keys)
```json
"results": {
  "per_point": [
    { "test_point_id": "sym_onset", "shared_agg_GBps": 0.0, "best_green_agg_GBps": 0.0,
      "best_sm_split": "8:8", "delta_pct": 0.0, "regime": "L1/scheduling|DRAM-bound" }
  ],
  "best_partition_ratios": { "symmetric": "8:8", "asymmetric": "x:y" },
  "green_context_helps_when": "short prose condition",
  "configs_for_phase4": [ { "test_point_id":"sym_onset", "config":"green", "sm_split":"8:8" } ]
}
```
Also write `FINDINGS.md` and a worklog entry; list consumed upstream findings.
