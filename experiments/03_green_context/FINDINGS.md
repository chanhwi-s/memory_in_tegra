# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated 2026-07-27T02:47:36Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Grid alignment with Phase 2 (v3 Change 1)

This run's symmetric per-kernel size grid (18 sizes) is Phase 2's own grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`) plus a small-end extension (32 KiB, 64 KiB) for the L1/scheduling regime, imported directly rather than re-derived -- so Phase 1/2/3 curves now sit at the SAME x positions and are directly overlayable. This supersedes v2's independent 1.8x geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the 3 anchor points. Sizes (bytes): 32,768, 65,536, 131,072, 262,144, 524,288, 786,432, 917,504, 1,048,576, 1,310,720, 1,572,864, 1,835,008, 2,097,152, 2,359,296, 3,145,728, 4,194,304, 6,291,456, 12,582,912, 25,165,824.

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 145.113 GB/s vs Phase 2's own measurement 141.241 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (29 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=167.923 GB/s (plateau=True), best green=186.514 GB/s at split 12:4 (plateau=True, delta 11.071%)
- **asym_131072** (asymmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=186.811 GB/s (plateau=True), best green=158.669 GB/s at split 12:4 (plateau=False, delta -15.064%)
- **asym_262144** (asymmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=178.995 GB/s (plateau=True), best green=143.468 GB/s at split 10:6 (plateau=True, delta -19.848%)
- **asym_524288** (asymmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=158.3 GB/s (plateau=True), best green=141.921 GB/s at split 10:6 (plateau=True, delta -10.347%)
- **asym_1048576** (asymmetric, 1,048,576 B, regime: L2+SLC-resident): shared=149.285 GB/s (plateau=True), best green=134.295 GB/s at split 8:8 (plateau=True, delta -10.041%)
- **asym_1572864** (asymmetric, 1,572,864 B, regime: L2+SLC-resident): shared=156.585 GB/s (plateau=True), best green=142.967 GB/s at split 6:10 (plateau=True, delta -8.697%)
- **asym_anchor_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=161.64 GB/s (plateau=True), best green=145.996 GB/s at split 6:10 (plateau=True, delta -9.678%)
- **asym_2621440** (asymmetric, 2,621,440 B, regime: DRAM-bound): shared=164.506 GB/s (plateau=False), best green=150.082 GB/s at split 6:10 (plateau=True, delta -8.768%)
- **asym_3145728** (asymmetric, 3,145,728 B, regime: DRAM-bound): shared=167.184 GB/s (plateau=True), best green=155.329 GB/s at split 4:12 (plateau=True, delta -7.091%)
- **asym_4194304** (asymmetric, 4,194,304 B, regime: DRAM-bound): shared=169.577 GB/s (plateau=True), best green=160.078 GB/s at split 4:12 (plateau=False, delta -5.602%)
- **asym_6291456** (asymmetric, 6,291,456 B, regime: DRAM-bound): shared=176.806 GB/s (plateau=False), best green=166.114 GB/s at split 4:12 (plateau=False, delta -6.047%)
- **sym_32768** (symmetric, 32,768 B, regime: L1/scheduling-sensitive): shared=13.669 GB/s (plateau=True), best green=12.526 GB/s at split 8:8 (plateau=True, delta -8.362%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=27.676 GB/s (plateau=True), best green=25.362 GB/s at split 8:8 (plateau=True, delta -8.361%)
- **sym_131072** (symmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=52.682 GB/s (plateau=False), best green=47.953 GB/s at split 8:8 (plateau=True, delta -8.977%)
- **sym_262144** (symmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=98.897 GB/s (plateau=True), best green=89.53 GB/s at split 8:8 (plateau=False, delta -9.471%)
- **sym_524288** (symmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=159.455 GB/s (plateau=True), best green=144.884 GB/s at split 8:8 (plateau=False, delta -9.138%)
- **sym_anchor_786432** [ANCHOR] (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=167.754 GB/s (plateau=True), best green=143.44 GB/s at split 8:8 (plateau=True, delta -14.494%)
- **sym_anchor_917504** [ANCHOR] (symmetric, 917,504 B, regime: L2+SLC-resident): shared=145.113 GB/s (plateau=True), best green=130.873 GB/s at split 8:8 (plateau=True, delta -9.813%)
- **sym_1048576** (symmetric, 1,048,576 B, regime: L2+SLC-resident): shared=147.714 GB/s (plateau=True), best green=134.571 GB/s at split 8:8 (plateau=True, delta -8.898%)
- **sym_1310720** (symmetric, 1,310,720 B, regime: L2+SLC-resident): shared=155.005 GB/s (plateau=True), best green=145.549 GB/s at split 8:8 (plateau=True, delta -6.1%)
- **sym_1572864** (symmetric, 1,572,864 B, regime: L2+SLC-resident): shared=161.684 GB/s (plateau=True), best green=151.626 GB/s at split 8:8 (plateau=True, delta -6.221%)
- **sym_1835008** (symmetric, 1,835,008 B, regime: L2+SLC-resident): shared=162.678 GB/s (plateau=True), best green=155.932 GB/s at split 8:8 (plateau=True, delta -4.147%)
- **sym_2097152** (symmetric, 2,097,152 B, regime: DRAM-bound): shared=167.29 GB/s (plateau=False), best green=157.067 GB/s at split 8:8 (plateau=True, delta -6.111%)
- **sym_2359296** (symmetric, 2,359,296 B, regime: DRAM-bound): shared=169.75 GB/s (plateau=False), best green=161.743 GB/s at split 8:8 (plateau=True, delta -4.717%)
- **sym_3145728** (symmetric, 3,145,728 B, regime: DRAM-bound): shared=175.491 GB/s (plateau=True), best green=167.042 GB/s at split 8:8 (plateau=True, delta -4.814%)
- **sym_4194304** (symmetric, 4,194,304 B, regime: DRAM-bound): shared=179.142 GB/s (plateau=True), best green=172.086 GB/s at split 8:8 (plateau=False, delta -3.939%)
- **sym_6291456** (symmetric, 6,291,456 B, regime: DRAM-bound): shared=182.439 GB/s (plateau=True), best green=177.364 GB/s at split 8:8 (plateau=True, delta -2.782%)
- **sym_12582912** (symmetric, 12,582,912 B, regime: DRAM-bound): shared=186.52 GB/s (plateau=True), best green=182.509 GB/s at split 8:8 (plateau=True, delta -2.15%)
- **sym_25165824** (symmetric, 25,165,824 B, regime: DRAM-bound): shared=188.337 GB/s (plateau=True), best green=185.596 GB/s at split 8:8 (plateau=True, delta -1.455%)

**10 point(s) had a shared or best-green cell that did not reach the block-count plateau within the search cap** -- their throughput is a lower bound; see run-time WARNINGs / `scripts/sweep.py` stderr log for which cells.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -1.455% at sym_25165824)
- symmetric / L1/scheduling-sensitive: 8:8 (delta -8.361% at sym_65536)
- symmetric / L2+SLC-resident: 8:8 (delta -4.147% at sym_1835008)
- asymmetric / DRAM-bound: 4:12 (delta -5.602% at asym_4194304)
- asymmetric / L1/scheduling-sensitive: 12:4 (delta 11.071% at asym_65536)
- asymmetric / L2+SLC-resident: 6:10 (delta -8.697% at asym_1572864)

## When does green context help?

Green beat shared by >2.0% at 1 point(s) (regimes: L1/scheduling-sensitive), swept-size range 65,536-65,536 bytes.

## Configs recommended for Phase 4

- asym_65536 (asymmetric, L1/scheduling-sensitive): config=green, sm_split=12:4
- asym_131072 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_262144 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_524288 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_1048576 (asymmetric, L2+SLC-resident): config=shared, sm_split=16:16
- asym_1572864 (asymmetric, L2+SLC-resident): config=shared, sm_split=16:16
- asym_anchor_2097152 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_2621440 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_3145728 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_4194304 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_6291456 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_32768 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_65536 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_131072 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_262144 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_524288 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_786432 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_917504 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1048576 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1310720 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1572864 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1835008 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_2097152 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_2359296 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_3145728 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_4194304 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_6291456 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_12582912 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_25165824 (symmetric, DRAM-bound): config=shared, sm_split=16:16

## Discrepancy vs the first Phase 3 run (00_conventions.md #2: do not overwrite upstream, record discrepancies)

The original Phase 3 run (`prompts/03_green_context.md`, now superseded) held block counts fixed
from Phase 1's single-kernel/16-SM `saturation_blocks_by_size` lookup instead of re-searching them
in context. At the symmetric 917504-byte anchor point this measured an under-saturated shared
baseline of **135.512 GB/s**, versus Phase 2's own local-search measurement of the
*same point* at **141.241 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**145.113 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

At least one subset size shows green's delta improving with reuse_N (the predicted L1 inter-launch-reuse benefit).

- **reuse_sym_32768** (32,768 B/kernel): delta @ reuse_N=1 = -4.74%, @ reuse_N=32 = -4.73% -- flat/no improvement with reuse
- **reuse_sym_4194304** (4,194,304 B/kernel): delta @ reuse_N=1 = -2.87%, @ reuse_N=32 = -5.18% -- flat/no improvement with reuse
- **reuse_sym_786432** (786,432 B/kernel): delta @ reuse_N=1 = -13.94%, @ reuse_N=32 = +0.35% -- CROSSES into green-helps at higher reuse
- **reuse_sym_917504** (917,504 B/kernel): delta @ reuse_N=1 = -3.39%, @ reuse_N=32 = -17.72% -- flat/no improvement with reuse

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
