# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated 2026-07-27T04:32:27Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Grid alignment with Phase 2 (v3 Change 1)

This run's symmetric per-kernel size grid (18 sizes) is Phase 2's own grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`) plus a small-end extension (32 KiB, 64 KiB) for the L1/scheduling regime, imported directly rather than re-derived -- so Phase 1/2/3 curves now sit at the SAME x positions and are directly overlayable. This supersedes v2's independent 1.8x geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the 3 anchor points. Sizes (bytes): 32,768, 65,536, 131,072, 262,144, 524,288, 786,432, 917,504, 1,048,576, 1,310,720, 1,572,864, 1,835,008, 2,097,152, 2,359,296, 3,145,728, 4,194,304, 6,291,456, 12,582,912, 25,165,824.

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 168.494 GB/s vs Phase 2's own measurement 146.449 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (29 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=211.647 GB/s (plateau=False), best green=194.866 GB/s at split 12:4 (plateau=True, delta -7.929%)
- **asym_131072** (asymmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=206.714 GB/s (plateau=False), best green=205.944 GB/s at split 12:4 (plateau=False, delta -0.372%)
- **asym_262144** (asymmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=164.498 GB/s (plateau=True), best green=171.86 GB/s at split 10:6 (plateau=True, delta 4.475%)
- **asym_524288** (asymmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=180.595 GB/s (plateau=False), best green=156.868 GB/s at split 8:8 (plateau=False, delta -13.138%)
- **asym_1048576** (asymmetric, 1,048,576 B, regime: L2+SLC-resident): shared=147.493 GB/s (plateau=True), best green=138.067 GB/s at split 8:8 (plateau=True, delta -6.391%)
- **asym_1572864** (asymmetric, 1,572,864 B, regime: L2+SLC-resident): shared=155.054 GB/s (plateau=True), best green=144.65 GB/s at split 6:10 (plateau=False, delta -6.71%)
- **asym_anchor_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=162.307 GB/s (plateau=True), best green=148.234 GB/s at split 6:10 (plateau=True, delta -8.671%)
- **asym_2621440** (asymmetric, 2,621,440 B, regime: DRAM-bound): shared=166.335 GB/s (plateau=True), best green=150.476 GB/s at split 6:10 (plateau=True, delta -9.534%)
- **asym_3145728** (asymmetric, 3,145,728 B, regime: DRAM-bound): shared=168.401 GB/s (plateau=True), best green=155.976 GB/s at split 4:12 (plateau=False, delta -7.378%)
- **asym_4194304** (asymmetric, 4,194,304 B, regime: DRAM-bound): shared=172.191 GB/s (plateau=False), best green=161.233 GB/s at split 4:12 (plateau=True, delta -6.364%)
- **asym_6291456** (asymmetric, 6,291,456 B, regime: DRAM-bound): shared=176.647 GB/s (plateau=True), best green=167.102 GB/s at split 4:12 (plateau=False, delta -5.403%)
- **sym_32768** (symmetric, 32,768 B, regime: L1/scheduling-sensitive): shared=13.964 GB/s (plateau=True), best green=12.251 GB/s at split 8:8 (plateau=False, delta -12.267%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=26.511 GB/s (plateau=False), best green=23.207 GB/s at split 8:8 (plateau=True, delta -12.463%)
- **sym_131072** (symmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=53.954 GB/s (plateau=False), best green=48.859 GB/s at split 8:8 (plateau=True, delta -9.443%)
- **sym_262144** (symmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=103.369 GB/s (plateau=True), best green=89.857 GB/s at split 8:8 (plateau=True, delta -13.072%)
- **sym_524288** (symmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=169.49 GB/s (plateau=False), best green=159.584 GB/s at split 8:8 (plateau=True, delta -5.845%)
- **sym_786432** (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=159.24 GB/s (plateau=True), best green=149.323 GB/s at split 8:8 (plateau=True, delta -6.228%)
- **sym_anchor_917504** [ANCHOR] (symmetric, 917,504 B, regime: L2+SLC-resident): shared=168.494 GB/s (plateau=True), best green=132.69 GB/s at split 8:8 (plateau=False, delta -21.249%)
- **sym_anchor_1048576** [ANCHOR] (symmetric, 1,048,576 B, regime: L2+SLC-resident): shared=148.16 GB/s (plateau=True), best green=132.798 GB/s at split 8:8 (plateau=True, delta -10.369%)
- **sym_1310720** (symmetric, 1,310,720 B, regime: L2+SLC-resident): shared=157.337 GB/s (plateau=False), best green=139.32 GB/s at split 8:8 (plateau=True, delta -11.451%)
- **sym_1572864** (symmetric, 1,572,864 B, regime: L2+SLC-resident): shared=160.934 GB/s (plateau=True), best green=145.78 GB/s at split 8:8 (plateau=False, delta -9.416%)
- **sym_1835008** (symmetric, 1,835,008 B, regime: L2+SLC-resident): shared=165.575 GB/s (plateau=True), best green=156.109 GB/s at split 8:8 (plateau=True, delta -5.717%)
- **sym_2097152** (symmetric, 2,097,152 B, regime: DRAM-bound): shared=167.29 GB/s (plateau=False), best green=160.007 GB/s at split 8:8 (plateau=True, delta -4.354%)
- **sym_2359296** (symmetric, 2,359,296 B, regime: DRAM-bound): shared=169.717 GB/s (plateau=True), best green=159.988 GB/s at split 8:8 (plateau=True, delta -5.732%)
- **sym_3145728** (symmetric, 3,145,728 B, regime: DRAM-bound): shared=175.726 GB/s (plateau=True), best green=167.874 GB/s at split 8:8 (plateau=True, delta -4.468%)
- **sym_4194304** (symmetric, 4,194,304 B, regime: DRAM-bound): shared=179.715 GB/s (plateau=True), best green=172.861 GB/s at split 8:8 (plateau=True, delta -3.814%)
- **sym_6291456** (symmetric, 6,291,456 B, regime: DRAM-bound): shared=182.82 GB/s (plateau=True), best green=178.329 GB/s at split 8:8 (plateau=True, delta -2.457%)
- **sym_12582912** (symmetric, 12,582,912 B, regime: DRAM-bound): shared=185.954 GB/s (plateau=True), best green=183.653 GB/s at split 8:8 (plateau=True, delta -1.237%)
- **sym_25165824** (symmetric, 25,165,824 B, regime: DRAM-bound): shared=188.476 GB/s (plateau=True), best green=181.558 GB/s at split 8:8 (plateau=True, delta -3.67%)

**15 point(s) had a shared or best-green cell that did not reach the block-count plateau within the search cap** -- their throughput is a lower bound; see run-time WARNINGs / `scripts/sweep.py` stderr log for which cells.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -1.237% at sym_12582912)
- symmetric / L1/scheduling-sensitive: 8:8 (delta -5.845% at sym_524288)
- symmetric / L2+SLC-resident: 8:8 (delta -5.717% at sym_1835008)
- asymmetric / DRAM-bound: 4:12 (delta -5.403% at asym_6291456)
- asymmetric / L1/scheduling-sensitive: 10:6 (delta 4.475% at asym_262144)
- asymmetric / L2+SLC-resident: 8:8 (delta -6.391% at asym_1048576)

## When does green context help?

Green beat shared by >2.0% at 1 point(s) (regimes: L1/scheduling-sensitive), swept-size range 262,144-262,144 bytes.

## Configs recommended for Phase 4

- asym_65536 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_131072 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_262144 (asymmetric, L1/scheduling-sensitive): config=green, sm_split=10:6
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
- sym_786432 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_917504 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_anchor_1048576 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
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
*same point* at **146.449 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**168.494 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

At least one subset size shows green's delta improving with reuse_N (the predicted L1 inter-launch-reuse benefit).

- **reuse_sym_1048576** (1,048,576 B/kernel): delta @ reuse_N=1 = -7.65%, @ reuse_N=32 = -13.51% -- flat/no improvement with reuse
- **reuse_sym_32768** (32,768 B/kernel): delta @ reuse_N=1 = -3.72%, @ reuse_N=32 = +1.06% -- CROSSES into green-helps at higher reuse
- **reuse_sym_4194304** (4,194,304 B/kernel): delta @ reuse_N=1 = -3.07%, @ reuse_N=32 = -3.82% -- flat/no improvement with reuse
- **reuse_sym_917504** (917,504 B/kernel): delta @ reuse_N=1 = -21.24%, @ reuse_N=32 = -28.56% -- flat/no improvement with reuse

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
