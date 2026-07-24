# Phase 3 v2 Findings — Green Context, In-Context Saturation + Widened Size Sweep

Generated 2026-07-24T12:24:38Z from `experiments/03_green_context/results/phase3_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v2.md` for the full
methodology; this supersedes the original Phase 3 run (`prompts/03_green_context.md`).

Upstream consumed: experiments/01_single_kernel_size/findings.json, experiments/02_two_kernel_size/findings.json

## Change 1 sanity gate (block-count saturation)

v2 re-swept shared @ 917504 B/kernel = 148.24 GB/s vs Phase 2's own measurement 143.599 GB/s (gate_passed=True); v1 (pre-widened-sweep) shared @ the same point was 135.512 GB/s (sym_0 in the pre-v2 run (git history)).

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point (23 points: widened sweep + Phase 2 anchors)

- **asym_65536** (asymmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=160.813 GB/s (plateau=False), best green=174.516 GB/s at split 14:2 (plateau=True, delta 8.521%)
- **asym_117965** (asymmetric, 117,965 B, regime: L1/scheduling-sensitive): shared=231.947 GB/s (plateau=False), best green=207.323 GB/s at split 12:4 (plateau=False, delta -10.616%)
- **asym_212337** (asymmetric, 212,337 B, regime: L1/scheduling-sensitive): shared=183.414 GB/s (plateau=True), best green=153.82 GB/s at split 14:2 (plateau=True, delta -16.135%)
- **asym_382206** (asymmetric, 382,206 B, regime: L1/scheduling-sensitive): shared=162.984 GB/s (plateau=False), best green=158.647 GB/s at split 10:6 (plateau=False, delta -2.661%)
- **asym_687971** (asymmetric, 687,971 B, regime: L1/scheduling-sensitive): shared=137.792 GB/s (plateau=False), best green=136.578 GB/s at split 10:6 (plateau=False, delta -0.881%)
- **asym_1238347** (asymmetric, 1,238,347 B, regime: L2+SLC-resident): shared=153.361 GB/s (plateau=True), best green=137.435 GB/s at split 6:10 (plateau=False, delta -10.385%)
- **asym_anchor_2_2097152** [ANCHOR] (asymmetric, 2,097,152 B, regime: DRAM-bound): shared=161.951 GB/s (plateau=True), best green=149.021 GB/s at split 6:10 (plateau=True, delta -7.984%)
- **asym_2229025** (asymmetric, 2,229,025 B, regime: DRAM-bound): shared=156.613 GB/s (plateau=True), best green=147.728 GB/s at split 6:10 (plateau=True, delta -5.673%)
- **asym_4012245** (asymmetric, 4,012,245 B, regime: DRAM-bound): shared=162.958 GB/s (plateau=True), best green=161.05 GB/s at split 4:12 (plateau=False, delta -1.171%)
- **asym_7222041** (asymmetric, 7,222,041 B, regime: DRAM-bound): shared=179.942 GB/s (plateau=True), best green=168.138 GB/s at split 4:12 (plateau=False, delta -6.56%)
- **asym_8388608** (asymmetric, 8,388,608 B, regime: DRAM-bound): shared=180.117 GB/s (plateau=True), best green=170.371 GB/s at split 4:12 (plateau=False, delta -5.411%)
- **sym_65536** (symmetric, 65,536 B, regime: L1/scheduling-sensitive): shared=28.248 GB/s (plateau=True), best green=24.454 GB/s at split 12:4 (plateau=True, delta -13.431%)
- **sym_117965** (symmetric, 117,965 B, regime: L1/scheduling-sensitive): shared=49.152 GB/s (plateau=True), best green=45.936 GB/s at split 10:6 (plateau=True, delta -6.543%)
- **sym_212337** (symmetric, 212,337 B, regime: L1/scheduling-sensitive): shared=80.026 GB/s (plateau=False), best green=73.186 GB/s at split 8:8 (plateau=True, delta -8.547%)
- **sym_382206** (symmetric, 382,206 B, regime: L1/scheduling-sensitive): shared=145.805 GB/s (plateau=True), best green=133.203 GB/s at split 6:10 (plateau=True, delta -8.643%)
- **sym_687971** (symmetric, 687,971 B, regime: L1/scheduling-sensitive): shared=173.03 GB/s (plateau=False), best green=172.222 GB/s at split 8:8 (plateau=False, delta -0.467%)
- **sym_anchor_1_786432** [ANCHOR] (symmetric, 786,432 B, regime: L1/scheduling-sensitive): shared=147.088 GB/s (plateau=True), best green=130.204 GB/s at split 8:8 (plateau=True, delta -11.479%)
- **sym_anchor_0_917504** [ANCHOR] (symmetric, 917,504 B, regime: L2+SLC-resident): shared=148.24 GB/s (plateau=True), best green=143.062 GB/s at split 8:8 (plateau=True, delta -3.493%)
- **sym_1238347** (symmetric, 1,238,347 B, regime: L2+SLC-resident): shared=151.758 GB/s (plateau=True), best green=138.579 GB/s at split 6:10 (plateau=True, delta -8.684%)
- **sym_2229025** (symmetric, 2,229,025 B, regime: DRAM-bound): shared=165.162 GB/s (plateau=True), best green=160.469 GB/s at split 8:8 (plateau=True, delta -2.841%)
- **sym_4012245** (symmetric, 4,012,245 B, regime: DRAM-bound): shared=178.82 GB/s (plateau=True), best green=172.644 GB/s at split 8:8 (plateau=True, delta -3.454%)
- **sym_7222041** (symmetric, 7,222,041 B, regime: DRAM-bound): shared=182.498 GB/s (plateau=True), best green=177.684 GB/s at split 8:8 (plateau=True, delta -2.638%)
- **sym_8388608** (symmetric, 8,388,608 B, regime: DRAM-bound): shared=182.403 GB/s (plateau=True), best green=174.414 GB/s at split 8:8 (plateau=False, delta -4.38%)

**11 point(s) had a shared or best-green cell that did not reach the block-count plateau within the search cap** -- their throughput is a lower bound; see run-time WARNINGs / `scripts/sweep.py` stderr log for which cells.

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

- symmetric / DRAM-bound: 8:8 (delta -2.638% at sym_7222041)
- symmetric / L1/scheduling-sensitive: 8:8 (delta -0.467% at sym_687971)
- symmetric / L2+SLC-resident: 8:8 (delta -3.493% at sym_anchor_0_917504)
- asymmetric / DRAM-bound: 4:12 (delta -1.171% at asym_4012245)
- asymmetric / L1/scheduling-sensitive: 14:2 (delta 8.521% at asym_65536)
- asymmetric / L2+SLC-resident: 6:10 (delta -10.385% at asym_1238347)

## When does green context help?

Green beat shared by >2.0% at 1 point(s) (regimes: L1/scheduling-sensitive), swept-size range 65,536-65,536 bytes.

## Configs recommended for Phase 4

- asym_65536 (asymmetric, L1/scheduling-sensitive): config=green, sm_split=14:2
- asym_117965 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_212337 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_382206 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_687971 (asymmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- asym_1238347 (asymmetric, L2+SLC-resident): config=shared, sm_split=16:16
- asym_anchor_2_2097152 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_2229025 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_4012245 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_7222041 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- asym_8388608 (asymmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_65536 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_117965 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_212337 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_382206 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_687971 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_1_786432 (symmetric, L1/scheduling-sensitive): config=shared, sm_split=16:16
- sym_anchor_0_917504 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_1238347 (symmetric, L2+SLC-resident): config=shared, sm_split=16:16
- sym_2229025 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_4012245 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_7222041 (symmetric, DRAM-bound): config=shared, sm_split=16:16
- sym_8388608 (symmetric, DRAM-bound): config=shared, sm_split=16:16

## Discrepancy vs the first Phase 3 run (00_conventions.md #2: do not overwrite upstream, record discrepancies)

The original Phase 3 run (`prompts/03_green_context.md`, now superseded) held block counts fixed
from Phase 1's single-kernel/16-SM `saturation_blocks_by_size` lookup instead of re-searching them
in context. At the symmetric 917504-byte anchor point this measured an under-saturated shared
baseline of **135.512 GB/s**, versus Phase 2's own local-search measurement of the
*same point* at **143.599 GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**148.24 GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
