# Phase 3 nsys overlap verification -- summary table

One row per (mode, config) at that mode's cache-bound local peak + its two grid neighbours (scripts/run_overlap_nsys.py, 05_unified_size_grid_and_plots.md Change 6). Verification-only -- not throughput. K0/K1/SM-split/blocks/threads-per-block are the EXACT configuration that cell was profiled at (reconstructed via --fixed-blocks0/1 from the matching results/phase3_results.csv row).

| Test point | Mode | Config | Overlap % | Kernels in window | Distinct GreenCtx | K0 size | K1 size | SM split (K0:K1) | Blocks (K0:K1) | Threads/block | Combined footprint (MB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| asym_131072 | asymmetric | green | N/A (timeout/parse failure) |  |  | 1MB | 128KB | 12:4 | 256:64 | 256 | 2.250 |
| asym_131072 | asymmetric | shared | N/A (timeout/parse failure) |  |  | 1MB | 128KB | 16:16 | 512:128 | 256 | 2.250 |
| sym_25165824 | symmetric | green | N/A (timeout/parse failure) |  |  | 24MB | 24MB | 8:8 | 8192:4096 | 256 | 96.000 |
| sym_25165824 | symmetric | shared | N/A (timeout/parse failure) |  |  | 24MB | 24MB | 16:16 | 8192:4096 | 256 | 96.000 |
