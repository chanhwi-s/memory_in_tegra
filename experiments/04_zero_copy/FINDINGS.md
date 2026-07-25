# Phase 4 v2 Findings -- Zero Copy + Reuse Crossover (widened sweep, re-saturated blocks)

Generated 2026-07-25T02:18:55Z from `experiments/04_zero_copy/results/phase4_results.csv`. All numbers below are computed directly from that CSV (and `results/l2_profile.csv` if present) by `scripts/derive_findings.py` -- re-run it (do not hand-edit) if either CSV changes. This run **supersedes** the first Phase 4 run per `prompts/04_zero_copy_v2.md`.

## Headline

Across the widened asymmetric K1 sweep (1.50MB -> 24.62MB), zero copy helps (memory-bound) in the 1.50MB-1.50MB range, peaking at asym_00 (l1 regime): +11.0% at reuse N=1, crossing over around reuse N=>32. Beyond that (2.00MB-24.62MB), the workload is DRAM/compute-limited enough that bypassing cache costs throughput instead (zero copy loses).

## Sanity gate (Change 1: block saturation must not regress vs the first run)

SANITY GATE FAILED -- re-swept cached aggregate is LOWER than v1 at one or more anchor points; the block-saturation search is too narrow, do not trust the zero-copy delta until this is fixed

| test_point_id | config | reuse_N | v1 cached GB/s | v2 cached GB/s | status |
|---|---|---|---|---|---|
| asym_2 | shared | 1 | 122.8 | 131.4 | pass |
| asym_2 | shared | 2 | 146.3 | 144.1 | FAIL |
| asym_2 | shared | 4 | 161.8 | 156.5 | FAIL |
| asym_2 | shared | 8 | 175.0 | 170.1 | FAIL |
| asym_2 | shared | 16 | 183.2 | 175.6 | FAIL |
| asym_2 | shared | 32 | 187.8 | 178.5 | FAIL |
| sym_0 | shared | - | - | - | no v1 baseline match (no v1 baseline row at this exact (config, k0_bytes, k1_bytes) -- likely because v1's gen_test_points.py resolved this label to a different size (see FINDINGS.md discrepancy note).) |
| sym_1 | shared | 1 | 84.3 | 95.8 | pass |
| sym_1 | shared | 2 | 128.1 | 121.0 | FAIL |
| sym_1 | shared | 4 | 171.2 | 160.9 | FAIL |
| sym_1 | shared | 8 | 198.0 | 170.8 | FAIL |
| sym_1 | shared | 16 | 217.8 | 186.7 | FAIL |
| sym_1 | shared | 32 | 231.0 | 195.1 | FAIL |

## Asymmetric large-kernel (K1) sweep -- the headline story

| test_point_id | regime | k1_bytes | zc delta @ N=1 | crossover N | bound conclusion | plateau reached | L2 bypass verified |
|---|---|---|---|---|---|---|---|
| asym_00 | l1 | 1.50MB | +11.0% | none in 1..32 | memory-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_2 | dram | 2.00MB | -10.0% | 2 | compute-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_02 | dram | 2.62MB | +0.6% | 4 | compute-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_03 | dram | 4.59MB | -1.3% | 2 | compute-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_04 | dram | 8.04MB | -0.1% | none in 1..32 | dram-bound-throughout | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_05 | dram | 14.07MB | -0.8% | 2 | compute-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| asym_06 | dram | 24.62MB | -0.2% | 2 | compute-bound | False | NO -- l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |

## Symmetric anchors (secondary -- NOT the large-kernel story, kept for continuity)

Both kernels are the same size here, so this is a contention point, not a large/streaming-kernel test (prompts/04_zero_copy_v2.md Change 2). See the discrepancy note below for why v1's sym_0/sym_1 rows are not directly comparable.

| test_point_id | k_bytes | zc delta @ N=1 | crossover N | bound conclusion |
|---|---|---|---|---|
| sym_0 | 768KB | +10.8% | 32 | memory-bound |
| sym_1 | 896KB | +24.4% | none in 1..32 | memory-bound |
| sym_ctx_large | 24.62MB | -0.1% | 2 | compute-bound |
| sym_ctx_small | 1.50MB | +8.1% | 2 | memory-bound |

## Discrepancy vs first Phase 4 run

- **sym_0 / sym_1 were NOT distinct sizes in the first run.** The v1 `gen_test_points.py` matched Phase 3's `test_point_id` strings to Phase 2 sizes via a `"90" in tpid` substring check; since neither `sym_0` nor `sym_1` contained `"90"`, BOTH resolved to the `onset` size (917504 bytes) -- `results/test_points_config.csv` from the first run shows both rows with `k0_bytes=k1_bytes=917504`. So the first run's headline ("zero copy helps most at sym_0") was really just two measurements of the *same* symmetric point, not the two distinct roofline sizes Phase 2 recommended. v2 fixes this by reading Phase 2's `symmetric_roofline_points.{ninety_pct,onset}` directly (sym_0=786432, sym_1=917504) instead of matching through Phase 3's id strings.
- **Block counts were fixed, not saturated.** v1 held `blocks_k0`/`blocks_k1` fixed from Phase 1's single-kernel nearest-neighbor lookup for both the cached and zero-copy paths. v2 runs an independent in-context search per (test point, config, cached|zerocopy path) -- see the sanity gate above for whether this actually raised the cached baseline.
- **The size sweep was 3 points, 2 of them not actually "large".** v1's headline used `sym_0` as the "large kernel" evidence, but symmetric points have no large kernel by definition. v2's headline is drawn from the widened asymmetric K1 sweep above instead.

## L2 bypass verification

Each row's `l2_bypass_verified` comes from `results/l2_profile.csv` (threshold: zero-copy L2 hit rate <= 10.0%). If it says NO, the profiler either hasn't been run yet (`scripts/profile_l2.sh`) or the bypass did not show the expected near-zero L2 hit rate -- investigate before trusting the bound_conclusion for that row.

## Consumed upstream findings

- experiments/01_single_kernel_size/findings.json
- experiments/02_two_kernel_size/findings.json
