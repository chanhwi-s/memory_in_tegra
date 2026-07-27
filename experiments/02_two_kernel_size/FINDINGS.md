# Phase 2 Findings — Two-Kernel Size Sweep

Generated 2026-07-27T10:17:10Z from `experiments/02_two_kernel_size/results/phase2_results.csv`. All numbers below are
computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not hand-edit)
if the CSV is regenerated. Consumed upstream: shared/size_grid.py, experiments/01_single_kernel_size/findings.json.

## Size grid (`prompts/05_unified_size_grid_and_plots.md`)

The symmetric x-axis (`symmetric_sizes_bytes()` in `scripts/gen_config.py`) is now the shared
combined-read-footprint grid (`shared/size_grid.py::symmetric_per_kernel_sizes_bytes()`, S = F/4,
24 points) -- densified over combined footprint F = 1-4 MB, which brackets the *measured*
effective cache boundary (Phase 1's `tier_steps`) rather than the nominal 4MB/8MB tiers this
grid used to target. It is identical to Phase 3's symmetric grid (asserted in
`experiments/03_green_context/scripts/sweep.py`). The asymmetric grid is unchanged and
therefore still not comparable point-for-point against other phases.

## 2a — Symmetric contention onset (worst measured contention, i.e. the local minimum of scaling_efficiency)

- **Per-kernel size (worst measured contention):** 1,048,576 bytes (~1.00 MB)
- **Combined read footprint:** 4,194,304 bytes
- **scaling_efficiency at this point (local minimum):** 0.2757

`symmetric_roofline_points` (onset + ~90%-below point, for Phase 3/4): see `findings.json`.
Onset here is defined as the local minimum of `scaling_efficiency` across the sweep, not the
first point below a fixed threshold -- see the docstring on `contention_onset()` in this script
for why (real data need not decay monotonically from ~1.0).

## 2b — Asymmetric result at k

- **k (per-buffer bytes):** 2,097,152
- **aggregate GB/s at k:** 157.203
- **K0 GB/s at k:** 70.926
- **K1 GB/s at k:** 104.802

## Recommended Phase 3 test points

- {'mode': 'symmetric', 'per_kernel_bytes': 1048576}
- {'mode': 'symmetric', 'per_kernel_bytes': 917504}
- {'mode': 'asymmetric', 'k1_bytes': 2097152}

## Warnings / caveats

None.

## Verification (00_conventions.md / prompt Verification section)

Re-check by eye against `results/plots/sym_agg_vs_footprint.png` and `results/plots/asym_vs_k1.png`:
- scaling_efficiency = agg_GBps_median / (single_k0_GBps_ref + single_k1_GBps_ref) -- how close
  the concurrent run gets to *ideal* 2x scaling (both kernels achieving their own isolated
  Phase-1 throughput at the same time). 1.0 = no contention; ~0.5 is the expected *floor* once
  both kernels are DRAM-bound (they share one memory bus, so aggregate caps near a single
  kernel's DRAM peak while the reference sum assumes two); below ~0.5 means real overhead beyond
  fair bandwidth-sharing (e.g. cache thrashing at a capacity crossover, or SM-scheduling
  contention with green context still OFF).
- On real hardware this need not start at ~1.0 and decay monotonically -- it can dip to its
  *worst* value mid-sweep (near a cache-capacity crossover) and partially recover at larger,
  DRAM-bound sizes. `symmetric_contention_onset` above is that local minimum, not the first
  point below a fixed threshold.
- The benchmark binary itself (`src/phase2_bench.cu`) prints a `WARNING` to stderr for any cell
  where `wall_ms_median >= serial_sum_ms` (no measured overlap) or a correctness mismatch — check
  the run log for these before trusting this file.
