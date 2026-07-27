# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated 2026-07-27T10:05:33Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: shared/size_grid.py, experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Grid alignment with Phase 2 (v3 Change 1)

This run's symmetric per-kernel size grid (18 sizes) is Phase 2's own grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`, itself `shared/size_grid.py::symmetric_per_kernel_sizes_bytes()`), imported directly rather than re-derived, with NO per-phase extension -- so this grid is element-wise IDENTICAL to Phase 2's (asserted in scripts/sweep.py), and Phase 1/2/3 curves sit at the SAME x positions and are directly overlayable. The shared grid is densified over combined footprint F = 1-4 MB (the *measured* effective cache boundary, not the nominal 4MB/8MB tiers this grid used to target). This supersedes v2's independent 1.8x geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the 3 anchor points, and the v3-era small-end extension (32 KiB, 64 KiB), which the shared grid's own 32 KiB floor made redundant. Sizes (bytes): 32,768, 65,536, 131,072, 262,144, 524,288, 786,432, 917,504, 1,048,576, 1,310,720, 1,572,864, 1,835,008, 2,097,152, 2,359,296, 3,145,728, 4,194,304, 6,291,456, 12,582,912, 25,165,824.

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 159.068 GB/s vs Phase 2's own measurement 146.123 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (29 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=207.238 GB/s (plateau=True), best green=168.058 GB/s at split 12:4 (plateau=True, delta -18.906%)
- **asym_131072** (asymmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=212.882 GB/s (plateau=True), best green=187.285 GB/s at split 12:4 (plateau=True, delta -12.024%)
- **asym_262144** (asymmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=182.993 GB/s (plateau=True), best green=151.144 GB/s at split 12:4 (plateau=True, delta -17.404%)
- **asym_524288** (asymmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=155.135 GB/s (plateau=True), best green=148.346 GB/s at split 8:8 (plateau=True, delta -4.376%)
- **asym_1048576** (asymmetric, 1,048,576 B, regime: L2+SLC-resident): shared=145.259 GB/s (plateau=True), best green=133.203 GB/s at split 6:10 (plateau=True, delta -8.3%)
- **asym_1572864** (asymmetric, 1,572,864 B, regime: L2+SLC-resident): shared=156.685 GB/s (plateau=True), best green=139.438 GB/s at split 8:8 (plateau=True, delta -11.007%)
- **asym_anchor_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=159.714 GB/s (plateau=True), best green=142.745 GB/s at split 4:12 (plateau=True, delta -10.625%)
- **asym_2621440** (asymmetric, 2,621,440 B, regime: DRAM-bound): shared=162.678 GB/s (plateau=True), best green=148.978 GB/s at split 4:12 (plateau=True, delta -8.422%)
- **asym_3145728** (asymmetric, 3,145,728 B, regime: DRAM-bound): shared=166.723 GB/s (plateau=True), best green=153.181 GB/s at split 6:10 (plateau=True, delta -8.122%)
- **asym_4194304** (asymmetric, 4,194,304 B, regime: DRAM-bound): shared=172.131 GB/s (plateau=True), best green=160.418 GB/s at split 4:12 (plateau=True, delta -6.805%)
- **asym_6291456** (asymmetric, 6,291,456 B, regime: DRAM-bound): shared=178.665 GB/s (plateau=True), best green=165.455 GB/s at split 2:14 (plateau=True, delta -7.394%)
- **sym_32768** (symmetric, 32,768 B, regime: L1/scheduling-sensitive): shared=12.4 GB/s (plateau=True), best green=11.895 GB/s at split 8:8 (plateau=True, delta -4.073%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=25.284 GB/s (plateau=True), best green=23.563 GB/s at split 8:8 (plateau=True, delta -6.807%)
- **sym_131072** (symmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=50.361 GB/s (plateau=True), best green=45.094 GB/s at split 8:8 (plateau=True, delta -10.458%)
- **sym_262144** (symmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=96.566 GB/s (plateau=True), best green=83.45 GB/s at split 8:8 (plateau=True, delta -13.582%)
- **sym_524288** (symmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=182.044 GB/s (plateau=True), best green=149.854 GB/s at split 8:8 (plateau=True, delta -17.683%)
- **sym_786432** (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=152.252 GB/s (plateau=True), best green=133.384 GB/s at split 8:8 (plateau=True, delta -12.393%)
- **sym_anchor_917504** [ANCHOR] (symmetric, 917,504 B, regime: L2+SLC-resident): shared=159.068 GB/s (plateau=True), best green=129.884 GB/s at split 8:8 (plateau=True, delta -18.347%)
- **sym_anchor_1048576** [ANCHOR] (symmetric, 1,048,576 B, regime: L2+SLC-resident): shared=144.299 GB/s (plateau=True), best green=131.775 GB/s at split 8:8 (plateau=True, delta -8.679%)
- **sym_1310720** (symmetric, 1,310,720 B, regime: L2+SLC-resident): shared=156.635 GB/s (plateau=True), best green=140.154 GB/s at split 8:8 (plateau=True, delta -10.522%)
- **sym_1572864** (symmetric, 1,572,864 B, regime: L2+SLC-resident): shared=159.154 GB/s (plateau=True), best green=147.604 GB/s at split 8:8 (plateau=True, delta -7.257%)
- **sym_1835008** (symmetric, 1,835,008 B, regime: L2+SLC-resident): shared=162.986 GB/s (plateau=True), best green=154.705 GB/s at split 8:8 (plateau=True, delta -5.081%)
- **sym_2097152** (symmetric, 2,097,152 B, regime: DRAM-bound): shared=165.914 GB/s (plateau=True), best green=158.172 GB/s at split 8:8 (plateau=True, delta -4.666%)
- **sym_2359296** (symmetric, 2,359,296 B, regime: DRAM-bound): shared=168.939 GB/s (plateau=True), best green=162.755 GB/s at split 8:8 (plateau=True, delta -3.66%)
- **sym_3145728** (symmetric, 3,145,728 B, regime: DRAM-bound): shared=173.964 GB/s (plateau=True), best green=167.397 GB/s at split 8:8 (plateau=True, delta -3.775%)
- **sym_4194304** (symmetric, 4,194,304 B, regime: DRAM-bound): shared=179.694 GB/s (plateau=True), best green=173.72 GB/s at split 8:8 (plateau=True, delta -3.325%)
- **sym_6291456** (symmetric, 6,291,456 B, regime: DRAM-bound): shared=183.332 GB/s (plateau=True), best green=177.058 GB/s at split 8:8 (plateau=True, delta -3.422%)
- **sym_12582912** (symmetric, 12,582,912 B, regime: DRAM-bound): shared=186.882 GB/s (plateau=True), best green=184.212 GB/s at split 8:8 (plateau=True, delta -1.429%)
- **sym_25165824** (symmetric, 25,165,824 B, regime: DRAM-bound): shared=189.319 GB/s (plateau=True), best green=187.443 GB/s at split 8:8 (plateau=True, delta -0.991%)

All measured cells reached the block-count plateau within the search cap.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -0.991% at sym_25165824)
- symmetric / L1/scheduling-sensitive: 8:8 (delta -4.073% at sym_32768)
- symmetric / L2+SLC-resident: 8:8 (delta -5.081% at sym_1835008)
- asymmetric / DRAM-bound: 4:12 (delta -6.805% at asym_4194304)
- asymmetric / L1/scheduling-sensitive: 8:8 (delta -4.376% at asym_524288)
- asymmetric / L2+SLC-resident: 6:10 (delta -8.3% at asym_1048576)

## When does green context help?

None across the 64KB-8MB/kernel sweep: best-green never beat shared by more than 2.0% at any measured point (symmetric or asymmetric).

## Configs recommended for Phase 4

- asym_65536 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
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
*same point* at **146.123 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**159.068 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

At least one subset size shows green's delta improving with reuse_N (the predicted L1 inter-launch-reuse benefit).

- **reuse_sym_1048576** (1,048,576 B/kernel): delta @ reuse_N=1 = -1.50%, @ reuse_N=32 = -14.00% -- flat/no improvement with reuse
- **reuse_sym_32768** (32,768 B/kernel): delta @ reuse_N=1 = +0.30%, @ reuse_N=32 = +33.51% -- delta improves with reuse (still not a win)
- **reuse_sym_4194304** (4,194,304 B/kernel): delta @ reuse_N=1 = -2.83%, @ reuse_N=32 = -2.67% -- flat/no improvement with reuse
- **reuse_sym_917504** (917,504 B/kernel): delta @ reuse_N=1 = -5.08%, @ reuse_N=32 = -25.98% -- flat/no improvement with reuse

## Full-grid reuse_N=32 overlay (05_unified_size_grid_and_plots.md Change 5 -- diagnostic
only, does NOT feed findings.json / Phase 4; feeds green_vs_shared_combined_footprint_n32.png)

Rationale: at reuse_N=1 the aggregate curve is dominated by cold-miss DRAM traffic and green loses at every point -- the mechanism green is supposed to exploit (stabilized inter-launch L1 residency) only exists when there IS inter-launch reuse. The existing 4-point overlay (see "Reuse overlay" above) showed green's only win (+33.5% at sym_32768) and its worst loss (-26.0% at sym_917504) at N=32, so this full-grid N=32 curve is the figure that actually maps green's useful range.

Not run this session -- `results/phase3_reuse32_results.csv` does not exist. Run `scripts/sweep_reuse32.py` (after `scripts/sweep.py`) to generate the full-grid reuse_N=32 overlay and re-run this script to fill in this section.

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
