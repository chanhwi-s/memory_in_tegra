# Phase 3 nsys overlap verification -- summary table

One row per (mode, config) at that mode's cache-bound local peak + its two grid neighbours (scripts/run_overlap_nsys.py, 05_unified_size_grid_and_plots.md Change 6). Verification-only -- not throughput. K0/K1/SM-split/blocks/threads-per-block are the EXACT configuration that cell was profiled at (reconstructed via --fixed-blocks0/1 from the matching results/phase3_results.csv row). "Failure reason" distinguishes an nsys timeout from a parse failure -- both used to show as an undifferentiated N/A.

| Test point | Mode | Config | Overlap % | Kernels in window | Distinct GreenCtx | K0 size | K1 size | SM split (K0:K1) | Blocks (K0:K1) | Threads/block | Combined footprint (MB) | Failure reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| asym_131072 | asymmetric | green | 5.4% | 20 | 2 | 1MB | 128KB | 12:4 | 64:32 | 256 | 2.250 |  |
| asym_262144 | asymmetric | green | 5.1% | 20 | 2 | 1MB | 256KB | 12:4 | 128:64 | 256 | 2.500 |  |
| asym_524288 | asymmetric | green | 36.0% | 20 | 2 | 1MB | 512KB | 8:8 | 128:128 | 256 | 3.000 |  |
| asym_131072 | asymmetric | shared | 0.0% | 20 | 0 | 1MB | 128KB | 16:16 | 512:64 | 256 | 2.250 |  |
| asym_262144 | asymmetric | shared | 0.0% | 20 | 0 | 1MB | 256KB | 16:16 | 256:64 | 256 | 2.500 |  |
| asym_524288 | asymmetric | shared | 18.7% | 20 | 0 | 1MB | 512KB | 16:16 | 512:64 | 256 | 3.000 |  |
| sym_393216 | symmetric | green | 3.3% | 20 | 2 | 384KB | 384KB | 8:8 | 1024:64 | 256 | 1.500 |  |
| sym_458752 | symmetric | green | 3.6% | 20 | 2 | 448KB | 448KB | 8:8 | 1024:64 | 256 | 1.750 |  |
| sym_524288 | symmetric | green | 0.0% | 20 | 2 | 512KB | 512KB | 8:8 | 256:64 | 256 | 2.000 |  |
| sym_393216 | symmetric | shared | 0.1% | 20 | 0 | 384KB | 384KB | 16:16 | 2048:64 | 256 | 1.500 |  |
| sym_458752 | symmetric | shared | 0.0% | 20 | 0 | 448KB | 448KB | 16:16 | 1024:64 | 256 | 1.750 |  |
| sym_524288 | symmetric | shared | 0.0% | 20 | 0 | 512KB | 512KB | 16:16 | 1024:64 | 256 | 2.000 |  |
