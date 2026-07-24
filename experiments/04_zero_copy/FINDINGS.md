# Phase 4 Findings — Zero Copy + Reuse Crossover

Generated 2026-07-24T08:58:29Z from `experiments/04_zero_copy/results/phase4_results.csv`. All numbers below are computed directly from that CSV (and `results/l2_profile.csv` if present) by `scripts/derive_findings.py` — re-run it (do not hand-edit) if either CSV changes.

## Headline

Zero copy helped most at 'sym_0' (shared): +21.5% aggregate throughput at reuse N=1, crossing over to cache-favored around reuse N=4 — evidence the bottleneck there was L2/SLC contention, not compute.

## Per test point / config

| test_point_id | config | zc delta @ N=1 | crossover N | bound conclusion | L2 bypass verified |
|---|---|---|---|---|---|
| asym_2 | shared | -11.9% | 2 | compute-bound | NO — l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| sym_0 | shared | +21.5% | 4 | memory-bound | NO — l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |
| sym_1 | shared | +14.2% | none in 1..32 | memory-bound | NO — l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh) |

## L2 bypass verification

Each row's `l2_bypass_verified` comes from `results/l2_profile.csv` (threshold: zero-copy L2 hit rate <= 10.0%). If it says NO, the profiler either hasn't been run yet (`scripts/profile_l2.sh`) or the bypass did not show the expected near-zero L2 hit rate — investigate before trusting the bound_conclusion for that row.

## Consumed upstream findings

- experiments/01_single_kernel_size/findings.json
- experiments/02_two_kernel_size/findings.json
- experiments/03_green_context/findings.json
