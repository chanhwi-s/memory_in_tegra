# Phase 3 Findings — Green Context on the Two-Kernel Roofline

Generated 2026-07-24T08:57:29Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated.

Upstream consumed: experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Per test point

- **asym_2** (asymmetric): shared=155.176 GB/s, best green=144.176 GB/s at split 6:10 (delta -7.089%), regime: DRAM-bound
- **sym_0** (symmetric): shared=135.512 GB/s, best green=127.952 GB/s at split 10:6 (delta -5.579%), regime: DRAM-bound
- **sym_1** (symmetric): shared=156.286 GB/s, best green=137.424 GB/s at split 8:8 (delta -12.069%), regime: DRAM-bound

## Best partition ratios

- symmetric: 10:6
- asymmetric: 6:10

## When does green context help?

neutral/hurt at: asym_2, sym_0, sym_1 (threshold: best-green delta > 2.0% vs shared).

## Configs recommended for Phase 4

- asym_2: config=shared, sm_split=16:16
- sym_0: config=shared, sm_split=16:16
- sym_1: config=shared, sm_split=16:16

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
