# Phase 3 nsys overlap verification -- summary table

One row per (mode, config) at that mode's peak-bandwidth test point (scripts/run_overlap_nsys.py). Verification-only -- not throughput.

| Test point | Mode | Config | Overlap % | Kernels in window | Distinct GreenCtx | Combined footprint (MB) |
|---|---|---|---|---|---|---|
| asym_65536 | asymmetric | green | N/A (timeout/parse failure) |  |  | 2.125 |
| asym_65536 | asymmetric | shared | N/A (timeout/parse failure) |  |  | 2.125 |
| sym_25165824 | symmetric | green | N/A (timeout/parse failure) |  |  | 96.000 |
| sym_25165824 | symmetric | shared | N/A (timeout/parse failure) |  |  | 96.000 |
