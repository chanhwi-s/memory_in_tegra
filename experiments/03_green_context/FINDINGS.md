# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated 2026-07-25T02:18:26Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Grid alignment with Phase 2 (v3 Change 1)

This run's symmetric per-kernel size grid (18 sizes) is Phase 2's own grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`) plus a small-end extension (32 KiB, 64 KiB) for the L1/scheduling regime, imported directly rather than re-derived -- so Phase 1/2/3 curves now sit at the SAME x positions and are directly overlayable. This supersedes v2's independent 1.8x geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the 3 anchor points. Sizes (bytes): 32,768, 65,536, 131,072, 262,144, 524,288, 786,432, 917,504, 1,048,576, 1,310,720, 1,572,864, 1,835,008, 2,097,152, 2,359,296, 3,145,728, 4,194,304, 6,291,456, 12,582,912, 25,165,824.

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 163.218 GB/s vs Phase 2's own measurement 137.957 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (29 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=214.033 GB/s (plateau=True), best green=186.016 GB/s at split 14:2 (plateau=True, delta -13.09%)
- **asym_131072** (asymmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=183.86 GB/s (plateau=True), best green=194.191 GB/s at split 12:4 (plateau=True, delta 5.619%)
- **asym_262144** (asymmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=199.805 GB/s (plateau=False), best green=160.104 GB/s at split 10:6 (plateau=True, delta -19.87%)
- **asym_524288** (asymmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=164.663 GB/s (plateau=True), best green=149.474 GB/s at split 8:8 (plateau=False, delta -9.224%)
- **asym_1048576** (asymmetric, 1,048,576 B, regime: L2+SLC-resident): shared=149.228 GB/s (plateau=True), best green=141.597 GB/s at split 6:10 (plateau=True, delta -5.114%)
- **asym_1572864** (asymmetric, 1,572,864 B, regime: L2+SLC-resident): shared=158.045 GB/s (plateau=True), best green=143.845 GB/s at split 6:10 (plateau=False, delta -8.985%)
- **asym_anchor_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=154.931 GB/s (plateau=False), best green=147.863 GB/s at split 6:10 (plateau=True, delta -4.562%)
- **asym_2621440** (asymmetric, 2,621,440 B, regime: DRAM-bound): shared=165.455 GB/s (plateau=False), best green=151.303 GB/s at split 6:10 (plateau=True, delta -8.553%)
- **asym_3145728** (asymmetric, 3,145,728 B, regime: DRAM-bound): shared=168.041 GB/s (plateau=True), best green=156.785 GB/s at split 4:12 (plateau=True, delta -6.698%)
- **asym_4194304** (asymmetric, 4,194,304 B, regime: DRAM-bound): shared=171.62 GB/s (plateau=True), best green=159.74 GB/s at split 4:12 (plateau=True, delta -6.922%)
- **asym_6291456** (asymmetric, 6,291,456 B, regime: DRAM-bound): shared=174.298 GB/s (plateau=True), best green=166.114 GB/s at split 4:12 (plateau=False, delta -4.695%)
- **sym_32768** (symmetric, 32,768 B, regime: L1/scheduling-sensitive): shared=13.128 GB/s (plateau=True), best green=12.564 GB/s at split 8:8 (plateau=True, delta -4.296%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=27.927 GB/s (plateau=True), best green=25.31 GB/s at split 8:8 (plateau=True, delta -9.371%)
- **sym_131072** (symmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=55.351 GB/s (plateau=True), best green=48.714 GB/s at split 6:10 (plateau=True, delta -11.991%)
- **sym_262144** (symmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=99.902 GB/s (plateau=True), best green=92.652 GB/s at split 4:12 (plateau=True, delta -7.257%)
- **sym_524288** (symmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=192.564 GB/s (plateau=False), best green=167.184 GB/s at split 6:10 (plateau=False, delta -13.18%)
- **sym_anchor_786432** [ANCHOR] (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=160.104 GB/s (plateau=True), best green=144.991 GB/s at split 6:10 (plateau=True, delta -9.439%)
- **sym_anchor_917504** [ANCHOR] (symmetric, 917,504 B, regime: L2+SLC-resident): shared=163.218 GB/s (plateau=True), best green=139.863 GB/s at split 6:10 (plateau=True, delta -14.309%)
- **sym_1048576** (symmetric, 1,048,576 B, regime: L2+SLC-resident): shared=150.14 GB/s (plateau=True), best green=146.504 GB/s at split 8:8 (plateau=True, delta -2.422%)
- **sym_1310720** (symmetric, 1,310,720 B, regime: L2+SLC-resident): shared=157.538 GB/s (plateau=True), best green=145.077 GB/s at split 8:8 (plateau=True, delta -7.91%)
- **sym_1572864** (symmetric, 1,572,864 B, regime: L2+SLC-resident): shared=155.832 GB/s (plateau=True), best green=150.044 GB/s at split 8:8 (plateau=True, delta -3.714%)
- **sym_1835008** (symmetric, 1,835,008 B, regime: L2+SLC-resident): shared=165.415 GB/s (plateau=True), best green=153.944 GB/s at split 8:8 (plateau=True, delta -6.935%)
- **sym_2097152** (symmetric, 2,097,152 B, regime: DRAM-bound): shared=168.365 GB/s (plateau=True), best green=159.165 GB/s at split 8:8 (plateau=True, delta -5.464%)
- **sym_2359296** (symmetric, 2,359,296 B, regime: DRAM-bound): shared=168.265 GB/s (plateau=True), best green=159.211 GB/s at split 8:8 (plateau=True, delta -5.381%)
- **sym_3145728** (symmetric, 3,145,728 B, regime: DRAM-bound): shared=175.412 GB/s (plateau=True), best green=167.587 GB/s at split 8:8 (plateau=True, delta -4.461%)
- **sym_4194304** (symmetric, 4,194,304 B, regime: DRAM-bound): shared=178.836 GB/s (plateau=True), best green=172.88 GB/s at split 8:8 (plateau=True, delta -3.33%)
- **sym_6291456** (symmetric, 6,291,456 B, regime: DRAM-bound): shared=182.396 GB/s (plateau=True), best green=177.618 GB/s at split 8:8 (plateau=True, delta -2.62%)
- **sym_12582912** (symmetric, 12,582,912 B, regime: DRAM-bound): shared=186.094 GB/s (plateau=True), best green=184.004 GB/s at split 8:8 (plateau=True, delta -1.123%)
- **sym_25165824** (symmetric, 25,165,824 B, regime: DRAM-bound): shared=188.797 GB/s (plateau=True), best green=187.027 GB/s at split 8:8 (plateau=True, delta -0.938%)

**7 point(s) had a shared or best-green cell that did not reach the block-count plateau within the search cap** -- their throughput is a lower bound; see run-time WARNINGs / `scripts/sweep.py` stderr log for which cells.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -0.938% at sym_25165824)
- symmetric / L1/scheduling-sensitive: 8:8 (delta -4.296% at sym_32768)
- symmetric / L2+SLC-resident: 8:8 (delta -2.422% at sym_1048576)
- asymmetric / DRAM-bound: 6:10 (delta -4.562% at asym_anchor_2097152)
- asymmetric / L1/scheduling-sensitive: 12:4 (delta 5.619% at asym_131072)
- asymmetric / L2+SLC-resident: 6:10 (delta -5.114% at asym_1048576)

## When does green context help?

Green beat shared by >2.0% at 1 point(s) (regimes: L1/scheduling-sensitive), swept-size range 131,072-131,072 bytes.

## Configs recommended for Phase 4

- asym_65536 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_131072 (asymmetric, L1/scheduling-sensitive): config=green, sm_split=12:4
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
*same point* at **137.957 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**163.218 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

Not run this session -- `results/phase3_reuse_results.csv` does not exist. Run `scripts/sweep_reuse.py` (after `scripts/sweep.py`) to generate the reuse_N overlay and re-run this script to fill in this section.

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
