# Phase 2 Findings — Two-Kernel Size Sweep

Generated 2026-07-25T12:32:47Z from `experiments/02_two_kernel_size/results/phase2_results.csv`. All numbers below are
computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not hand-edit)
if the CSV is regenerated. Consumed upstream: experiments/01_single_kernel_size/findings.json.

## 2a — Symmetric contention onset (worst measured contention, i.e. the local minimum of scaling_efficiency)

- **Per-kernel size (worst measured contention):** 917,504 bytes (~0.88 MB)
- **Combined read footprint:** 3,670,016 bytes
- **scaling_efficiency at this point (local minimum):** 0.2621

`symmetric_roofline_points` (onset + ~90%-below point, for Phase 3/4): see `findings.json`.
Onset here is defined as the local minimum of `scaling_efficiency` across the sweep, not the
first point below a fixed threshold -- see the docstring on `contention_onset()` in this script
for why (real data need not decay monotonically from ~1.0).

## 2b — Asymmetric result at k

- **k (per-buffer bytes):** 2,097,152
- **aggregate GB/s at k:** 158.683
- **K0 GB/s at k:** 83.913
- **K1 GB/s at k:** 105.789

## Recommended Phase 3 test points

- {'mode': 'symmetric', 'per_kernel_bytes': 917504}
- {'mode': 'symmetric', 'per_kernel_bytes': 786432}
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

## Reuse overlay

Two-kernel analog of Phase 1's `bw_vs_footprint.png` (see `results/plots/
reuse_bw_vs_footprint.png`), computed from `results/phase2_reuse_results.csv`
(`scripts/append_reuse_findings.py`; not part of the frozen `findings.json` handoff --
diagnostic only).

### Symmetric

- **Symmetric reuse_N values swept:** [1, 2, 4, 8, 16, 32]
- **Collapse point:** at/above 16.00 MB, reuse N=1 and N=32 aggregate GB/s agree within 5% (no further reuse benefit -- DRAM-bound).
- At the largest tested size (96.00 MB): reuse N=32 aggregate = 190.0 GB/s.
- At the smallest tested size (512.0 KB): reuse N=32 aggregate = 98.3 GB/s vs N=1 = 50.1 GB/s (+96% from reuse).

### Asymmetric

- **Asymmetric reuse_N values swept:** [1, 2, 4, 8, 16, 32]
- **Collapse point:** not reached within the measured range -- reuse N=1 and N=32 still differ by more than 5% at the largest tested size. Consider extending the sweep.
- At the smallest tested size (256.0 KB): reuse N=32 aggregate = 285.7 GB/s vs N=1 = 188.9 GB/s (+51% from reuse).

### Reading the plot

In the cache-resident region (small combined footprint), higher `reuse_N` lifts the aggregate
above the measured DRAM peak (cache hits on the re-read buffers). Once the combined footprint
overflows the effective cache, all `reuse_N` lines collapse onto the DRAM peak line -- reuse
stops helping because every kernel launch has to re-fetch from DRAM regardless of how many times
the same buffer is reused. Compare the collapse point above against Phase 1's single-kernel
collapse (~4 MB read footprint, per Phase 1's `findings.json` /
`reuse_crossover_note`) -- with two kernels sharing the cache concurrently, the collapse is
expected at a smaller *per-kernel* footprint than Phase 1's single-kernel number, since the
effective cache available to each kernel is reduced by the other kernel's concurrent footprint.
