# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated 2026-07-27T10:21:49Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: shared/size_grid.py, experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Grid alignment with Phase 2 (v3 Change 1)

This run's symmetric per-kernel size grid (24 sizes) is Phase 2's own grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`, itself `shared/size_grid.py::symmetric_per_kernel_sizes_bytes()`), imported directly rather than re-derived, with NO per-phase extension -- so this grid is element-wise IDENTICAL to Phase 2's (asserted in scripts/sweep.py), and Phase 1/2/3 curves sit at the SAME x positions and are directly overlayable. The shared grid is densified over combined footprint F = 1-4 MB (the *measured* effective cache boundary, not the nominal 4MB/8MB tiers this grid used to target). This supersedes v2's independent 1.8x geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the 3 anchor points, and the v3-era small-end extension (32 KiB, 64 KiB), which the shared grid's own 32 KiB floor made redundant. Sizes (bytes): 32,768, 65,536, 131,072, 262,144, 327,680, 393,216, 458,752, 524,288, 589,824, 655,360, 720,896, 786,432, 851,968, 917,504, 983,040, 1,048,576, 1,310,720, 1,572,864, 2,097,152, 3,145,728, 4,194,304, 6,291,456, 12,582,912, 25,165,824.

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 144.686 GB/s vs Phase 2's own measurement 143.526 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (35 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=198.006 GB/s (plateau=True), best green=183.082 GB/s at split 14:2 (plateau=True, delta -7.537%)
- **asym_131072** (asymmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=168.714 GB/s (plateau=True), best green=189.532 GB/s at split 12:4 (plateau=True, delta 12.339%)
- **asym_262144** (asymmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=185.06 GB/s (plateau=True), best green=163.296 GB/s at split 12:4 (plateau=True, delta -11.761%)
- **asym_524288** (asymmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=184.551 GB/s (plateau=True), best green=148.645 GB/s at split 8:8 (plateau=True, delta -19.456%)
- **asym_1048576** (asymmetric, 1,048,576 B, regime: L2+SLC-resident): shared=147.548 GB/s (plateau=True), best green=135.358 GB/s at split 8:8 (plateau=True, delta -8.262%)
- **asym_1572864** (asymmetric, 1,572,864 B, regime: L2+SLC-resident): shared=154.033 GB/s (plateau=True), best green=137.143 GB/s at split 8:8 (plateau=True, delta -10.965%)
- **asym_anchor_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=159.24 GB/s (plateau=True), best green=144.565 GB/s at split 6:10 (plateau=True, delta -9.216%)
- **asym_2621440** (asymmetric, 2,621,440 B, regime: DRAM-bound): shared=161.041 GB/s (plateau=True), best green=148.24 GB/s at split 4:12 (plateau=True, delta -7.949%)
- **asym_3145728** (asymmetric, 3,145,728 B, regime: DRAM-bound): shared=164.767 GB/s (plateau=True), best green=156.41 GB/s at split 4:12 (plateau=True, delta -5.072%)
- **asym_4194304** (asymmetric, 4,194,304 B, regime: DRAM-bound): shared=172.584 GB/s (plateau=True), best green=161.897 GB/s at split 4:12 (plateau=True, delta -6.192%)
- **asym_6291456** (asymmetric, 6,291,456 B, regime: DRAM-bound): shared=177.765 GB/s (plateau=True), best green=163.879 GB/s at split 4:12 (plateau=True, delta -7.811%)
- **sym_32768** (symmetric, 32,768 B, regime: L1/scheduling-sensitive): shared=13.284 GB/s (plateau=True), best green=11.703 GB/s at split 8:8 (plateau=True, delta -11.902%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=24.9 GB/s (plateau=True), best green=24.165 GB/s at split 8:8 (plateau=True, delta -2.952%)
- **sym_131072** (symmetric, 131,072 B, regime: L1/scheduling-sensitive): shared=51.468 GB/s (plateau=True), best green=46.946 GB/s at split 8:8 (plateau=True, delta -8.786%)
- **sym_262144** (symmetric, 262,144 B, regime: L1/scheduling-sensitive): shared=97.718 GB/s (plateau=True), best green=84.021 GB/s at split 8:8 (plateau=True, delta -14.017%)
- **sym_327680** (symmetric, 327,680 B, regime: L1/scheduling-sensitive): shared=118.154 GB/s (plateau=True), best green=106.114 GB/s at split 8:8 (plateau=True, delta -10.19%)
- **sym_393216** (symmetric, 393,216 B, regime: L1/scheduling-sensitive): shared=140.702 GB/s (plateau=True), best green=118.343 GB/s at split 8:8 (plateau=True, delta -15.891%)
- **sym_458752** (symmetric, 458,752 B, regime: L1/scheduling-sensitive): shared=165.894 GB/s (plateau=True), best green=138.624 GB/s at split 8:8 (plateau=True, delta -16.438%)
- **sym_524288** (symmetric, 524,288 B, regime: L1/scheduling-sensitive): shared=147.052 GB/s (plateau=True), best green=156.535 GB/s at split 8:8 (plateau=True, delta 6.449%)
- **sym_589824** (symmetric, 589,824 B, regime: L1/scheduling-sensitive): shared=200.894 GB/s (plateau=True), best green=168.329 GB/s at split 8:8 (plateau=True, delta -16.21%)
- **sym_655360** (symmetric, 655,360 B, regime: L1/scheduling-sensitive): shared=182.45 GB/s (plateau=True), best green=138.926 GB/s at split 8:8 (plateau=True, delta -23.855%)
- **sym_720896** (symmetric, 720,896 B, regime: L1/scheduling-sensitive): shared=156.264 GB/s (plateau=True), best green=145.655 GB/s at split 8:8 (plateau=True, delta -6.789%)
- **sym_anchor_786432** [ANCHOR] (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=147.382 GB/s (plateau=True), best green=146.577 GB/s at split 8:8 (plateau=True, delta -0.546%)
- **sym_anchor_851968** [ANCHOR] (symmetric, 851,968 B, regime: L2+SLC-resident): shared=142.374 GB/s (plateau=True), best green=136.3 GB/s at split 8:8 (plateau=True, delta -4.266%)
- **sym_917504** (symmetric, 917,504 B, regime: L2+SLC-resident): shared=144.686 GB/s (plateau=True), best green=136.155 GB/s at split 8:8 (plateau=True, delta -5.896%)
- **sym_983040** (symmetric, 983,040 B, regime: L2+SLC-resident): shared=145.248 GB/s (plateau=True), best green=131.422 GB/s at split 8:8 (plateau=True, delta -9.519%)
- **sym_1048576** (symmetric, 1,048,576 B, regime: L2+SLC-resident): shared=146.777 GB/s (plateau=True), best green=132.307 GB/s at split 8:8 (plateau=True, delta -9.858%)
- **sym_1310720** (symmetric, 1,310,720 B, regime: L2+SLC-resident): shared=153.889 GB/s (plateau=True), best green=143.259 GB/s at split 8:8 (plateau=True, delta -6.908%)
- **sym_1572864** (symmetric, 1,572,864 B, regime: L2+SLC-resident): shared=160.759 GB/s (plateau=True), best green=146.431 GB/s at split 8:8 (plateau=True, delta -8.913%)
- **sym_2097152** (symmetric, 2,097,152 B, regime: DRAM-bound): shared=166.758 GB/s (plateau=True), best green=159.358 GB/s at split 8:8 (plateau=True, delta -4.438%)
- **sym_3145728** (symmetric, 3,145,728 B, regime: DRAM-bound): shared=174.582 GB/s (plateau=True), best green=165.032 GB/s at split 8:8 (plateau=True, delta -5.47%)
- **sym_4194304** (symmetric, 4,194,304 B, regime: DRAM-bound): shared=178.491 GB/s (plateau=True), best green=173.836 GB/s at split 8:8 (plateau=True, delta -2.608%)
- **sym_6291456** (symmetric, 6,291,456 B, regime: DRAM-bound): shared=181.722 GB/s (plateau=True), best green=177.993 GB/s at split 8:8 (plateau=True, delta -2.052%)
- **sym_12582912** (symmetric, 12,582,912 B, regime: DRAM-bound): shared=187.305 GB/s (plateau=True), best green=183.896 GB/s at split 8:8 (plateau=True, delta -1.82%)
- **sym_25165824** (symmetric, 25,165,824 B, regime: DRAM-bound): shared=189.437 GB/s (plateau=True), best green=187.532 GB/s at split 8:8 (plateau=True, delta -1.006%)

All measured cells reached the block-count plateau within the search cap.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -1.006% at sym_25165824)
- symmetric / L1/scheduling-sensitive: 8:8 (delta 6.449% at sym_524288)
- symmetric / L2+SLC-resident: 8:8 (delta -4.266% at sym_anchor_851968)
- asymmetric / DRAM-bound: 4:12 (delta -5.072% at asym_3145728)
- asymmetric / L1/scheduling-sensitive: 12:4 (delta 12.339% at asym_131072)
- asymmetric / L2+SLC-resident: 8:8 (delta -8.262% at asym_1048576)

## When does green context help?

Green beat shared by >2.0% at 2 point(s) (regimes: L1/scheduling-sensitive), swept-size range 131,072-524,288 bytes.

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
- sym_327680 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_393216 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_458752 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_524288 (symmetric, L1/scheduling-sensitive): config=green, sm_split=8:8
- sym_589824 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_655360 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_720896 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_786432 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_851968 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_917504 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_983040 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1048576 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1310720 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1572864 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_2097152 (symmetric, DRAM-bound): config=shared, sm_split=16:16
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
*same point* at **143.526 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**144.686 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

At least one subset size shows green's delta improving with reuse_N (the predicted L1 inter-launch-reuse benefit).

- **reuse_sym_32768** (32,768 B/kernel): delta @ reuse_N=1 = -6.13%, @ reuse_N=32 = -1.54% -- delta improves with reuse (still not a win)
- **reuse_sym_4194304** (4,194,304 B/kernel): delta @ reuse_N=1 = -2.82%, @ reuse_N=32 = -3.56% -- flat/no improvement with reuse
- **reuse_sym_786432** (786,432 B/kernel): delta @ reuse_N=1 = -5.68%, @ reuse_N=32 = -9.01% -- flat/no improvement with reuse
- **reuse_sym_851968** (851,968 B/kernel): delta @ reuse_N=1 = -5.51%, @ reuse_N=32 = -10.24% -- flat/no improvement with reuse

## Full-grid reuse_N=32 overlay (05_unified_size_grid_and_plots.md Change 5 -- diagnostic
only, does NOT feed findings.json / Phase 4; feeds green_vs_shared_combined_footprint_n32.png)

Rationale: at reuse_N=1 the aggregate curve is dominated by cold-miss DRAM traffic and green loses at every point -- the mechanism green is supposed to exploit (stabilized inter-launch L1 residency) only exists when there IS inter-launch reuse. The existing 4-point overlay (see "Reuse overlay" above) showed green's only win (+33.5% at sym_32768) and its worst loss (-26.0% at sym_917504) at N=32, so this full-grid N=32 curve is the figure that actually maps green's useful range.

- **reuse32_sym_32768** (32,768 B/kernel): shared=25.0 GB/s, green(N=1-optimal split 8:8)=24.1 GB/s, delta=-3.53%
- **reuse32_sym_65536** (65,536 B/kernel): shared=44.3 GB/s, green(N=1-optimal split 8:8)=48.5 GB/s, delta=+9.50%
- **reuse32_sym_131072** (131,072 B/kernel): shared=87.0 GB/s, green(N=1-optimal split 8:8)=88.4 GB/s, delta=+1.60%
- **reuse32_sym_262144** (262,144 B/kernel): shared=134.9 GB/s, green(N=1-optimal split 8:8)=159.0 GB/s, delta=+17.83%
- **reuse32_sym_327680** (327,680 B/kernel): shared=162.2 GB/s, green(N=1-optimal split 8:8)=172.9 GB/s, delta=+6.60%
- **reuse32_sym_393216** (393,216 B/kernel): shared=190.4 GB/s, green(N=1-optimal split 8:8)=197.0 GB/s, delta=+3.47%
- **reuse32_sym_458752** (458,752 B/kernel): shared=254.8 GB/s, green(N=1-optimal split 8:8)=236.9 GB/s, delta=-7.02%
- **reuse32_sym_524288** (524,288 B/kernel): shared=281.1 GB/s, green(N=1-optimal split 8:8)=261.8 GB/s, delta=-6.86%
- **reuse32_sym_589824** (589,824 B/kernel): shared=253.5 GB/s, green(N=1-optimal split 8:8)=243.5 GB/s, delta=-3.94%
- **reuse32_sym_655360** (655,360 B/kernel): shared=261.5 GB/s, green(N=1-optimal split 8:8)=200.6 GB/s, delta=-23.30%
- **reuse32_sym_720896** (720,896 B/kernel): shared=252.1 GB/s, green(N=1-optimal split 8:8)=228.2 GB/s, delta=-9.47%
- **reuse32_sym_786432** (786,432 B/kernel): shared=239.7 GB/s, green(N=1-optimal split 8:8)=212.6 GB/s, delta=-11.32%
- **reuse32_sym_851968** (851,968 B/kernel): shared=219.4 GB/s, green(N=1-optimal split 8:8)=181.0 GB/s, delta=-17.51%
- **reuse32_sym_917504** (917,504 B/kernel): shared=224.7 GB/s, green(N=1-optimal split 8:8)=167.1 GB/s, delta=-25.64%
- **reuse32_sym_983040** (983,040 B/kernel): shared=220.8 GB/s, green(N=1-optimal split 8:8)=172.2 GB/s, delta=-22.01%
- **reuse32_sym_1048576** (1,048,576 B/kernel): shared=190.0 GB/s, green(N=1-optimal split 8:8)=167.9 GB/s, delta=-11.64%
- **reuse32_sym_1310720** (1,310,720 B/kernel): shared=178.6 GB/s, green(N=1-optimal split 8:8)=166.7 GB/s, delta=-6.64%
- **reuse32_sym_1572864** (1,572,864 B/kernel): shared=177.3 GB/s, green(N=1-optimal split 8:8)=163.6 GB/s, delta=-7.72%
- **reuse32_sym_2097152** (2,097,152 B/kernel): shared=183.1 GB/s, green(N=1-optimal split 8:8)=169.8 GB/s, delta=-7.26%
- **reuse32_sym_3145728** (3,145,728 B/kernel): shared=187.5 GB/s, green(N=1-optimal split 8:8)=178.2 GB/s, delta=-4.96%
- **reuse32_sym_4194304** (4,194,304 B/kernel): shared=187.8 GB/s, green(N=1-optimal split 8:8)=181.1 GB/s, delta=-3.54%
- **reuse32_sym_6291456** (6,291,456 B/kernel): shared=187.7 GB/s, green(N=1-optimal split 8:8)=181.1 GB/s, delta=-3.48%
- **reuse32_sym_12582912** (12,582,912 B/kernel): shared=189.4 GB/s, green(N=1-optimal split 8:8)=186.8 GB/s, delta=-1.37%
- **reuse32_sym_25165824** (25,165,824 B/kernel): shared=189.3 GB/s, green(N=1-optimal split 8:8)=188.1 GB/s, delta=-0.61%

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
