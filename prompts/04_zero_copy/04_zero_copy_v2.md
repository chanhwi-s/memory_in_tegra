# Work Prompt — Phase 4 (v2 re-run): Zero Copy with in-context block saturation and a widened size sweep

**Prerequisites:** read `../OVERVIEW.md`, `00_conventions.md`, and the ORIGINAL
`prompts/04_zero_copy.md` first. Standard phase layout, worklog, and findings rules apply. Output
stays under `experiments/04_zero_copy/` — you are **revising this phase in place**, and this run
**supersedes** the first Phase 4 run. Do not modify files outside your phase directory.

> **Why this re-run exists.** Same two gaps as Phase 3:
>
> 1. **Block counts were never re-swept in context.** `scripts/gen_test_points.py` pulled block
>    counts from Phase 1's *single-kernel* `saturation_blocks_by_size` via nearest-neighbor
>    (`blocks_for()`) and held them **fixed** for both the cached and the zero-copy paths. The
>    zero-copy (mapped-pinned, cache-bypassing) path has a different memory-latency profile than the
>    cached path and generally saturates at a **different** block count, so a single fixed value can
>    under- or over-subscribe one of the two paths and bias the cached-vs-zerocopy delta.
> 2. **The size sweep was pinned to 3 points.** Worse, two of the three (`sym_0`, `sym_1`) were
>    **symmetric** — the "large / streaming kernel" that zero copy is supposed to target was **not
>    actually larger** than its neighbor. Only `asym_2` had a genuinely larger kernel. So the
>    headline ("zero copy helps at sym_0") rests on a point where "large kernel" is a misnomer, and
>    the memory-bound-vs-compute-bound conclusion was measured over a razor-thin slice of size space.

## Dependency (read the UPDATED Phase 3 v2 findings)
- Consumes `experiments/02_two_kernel_size/findings.json` (roofline points, asymmetric `k`),
  `experiments/03_green_context/findings.json` (**the v2 re-run** — `configs_for_phase4` may now vary
  by size regime), and `experiments/01_single_kernel_size/findings.json` (tier steps, reuse-crossover
  note; `saturation_blocks_by_size` only as a **search seed**, never fixed).
- **Ordering:** run this **after** Phase 3 v2 so you consume the re-swept green configs. If Phase 3 v2
  findings are absent, fail loudly (or fall back to `shared` with a loud TODO warning, as the original
  harness does) — do not silently use the stale first-run configs.

Read all test points, green-context configs, and reuse ranges from upstream `findings.json` at run
time; never fabricate.

---

## Change 1 — Saturate block count **in context**, per (test point × config × path × ...)

For every measured cell, sweep grid/block count until aggregate throughput plateaus and report the
plateau (`00_conventions.md` §4). Requirements:

- Phase 1's `saturation_blocks_by_size` is only the **seed / lower bound** of the search, not the answer.
- Run the saturation search **independently for the cached path and the zero-copy path** (and for
  green vs shared configs, per Phase 3 v2). The cache-bypassing kernel is latency-bound differently
  and needs its own plateau. A phase2_bench-style widened local search (`{1,2,4,8}× seed`, capped
  1024, K0 then K1) inside `phase4_bench` is acceptable; document the method in `README.md`.
- Block saturation can be determined at a **fixed reuse N (e.g. N=1)** per (test point, config, path)
  and then reused across the reuse sweep — verify once that the plateau block count is stable across a
  couple of N values, then hold it. Emit chosen `blocks_k0, blocks_k1` and a `plateau_reached` flag.

**Sanity gate:** the re-swept **cached** aggregate at each anchor should be ≥ the first Phase 4 run's
cached number for the same point (the original was likely under-saturated, like Phase 3). If lower,
the search is too narrow — fix before trusting any zero-copy delta.

## Change 2 — Widen the size sweep so "large kernel" is real, across tiers

Do **not** restrict to the 3 original points. Zero copy targets the **large / streaming kernel**, so
the sweep must actually grow that kernel across cache tiers:

- **Asymmetric (primary):** keep K0 (the *other*, cached kernel) fixed small (1 MB) and sweep the
  **large kernel K1** on a ~1.5–2× geometric grid from the small end (**per-SM working set ≈ L1,
  192 KB/SM**) up through the L2/SLC tiers and into clearly DRAM-bound (K1 > ~8 MB). This is where the
  memory-bound-vs-compute-bound bottleneck story should actually be mapped. Apply zero copy to K1 only.
- **Symmetric (secondary, keep for continuity):** keep the original symmetric anchors (786432,
  917504) labeled, but treat them as what they are — a symmetric contention point, *not* a
  large-kernel test. Optionally extend a few symmetric sizes for context, but the headline
  memory-bound claim must come from the asymmetric large-kernel sweep, not the symmetric points.
- **Anchors:** mark the original 3 points (`sym_0`, `sym_1`, `asym_2`) as labeled anchor rows so the
  new results are directly comparable to the first run.

For each (size, config), compare **large-kernel cached** vs **large-kernel zero-copy** across the
**reuse sweep N = 1, 2, 4, 8, 16, 32** (unchanged — this is the crossover axis).

---

## Metrics / CSV / plots
- CSV `results/phase4_results.csv`: same schema as the original prompt (add `plateau_reached` if
  absent). Now spans the widened large-kernel size sweep × reuse, per config/path.
- Plots (`results/plots/`): (1) `zc_vs_cached_reuse.png` — aggregate GB/s vs reuse N, cached vs
  zero-copy, one panel per (size, config), crossover N marked; (2) `zc_benefit_map.png` — heatmap of
  zero-copy delta_pct over **(large-kernel size) × (reuse N)**, so the crossover surface across tiers
  is visible (this is the payoff figure); (3) `crossover_vs_size.png` — crossover reuse N vs
  large-kernel size.

## Verification (keep original checks)
- **Bypass by throughput behavior (no profiler):** the zero-copy large kernel is ~flat across reuse N
  and never exceeds DRAM peak; the cached counterpart rises with N and can exceed DRAM peak. If the
  zero-copy path shows reuse-dependent speedup, the mapping is not bypassing cache — fix it.
- **Baseline saturation check** (Change 1 sanity gate).
- **Correctness sample-check** both kernels.
- Optionally run `scripts/profile_l2.sh` to fill `l2_hit_rate_zc` (the first run left it unprofiled);
  if you do, verify zero-copy L2 hit rate ≤ ~10%.

## Findings handoff — `findings.json`
Keep the original `results` schema, but:
- `per_config` now covers the widened large-kernel size sweep. For each, report `crossover_reuse_N`,
  `zc_delta_at_N1_pct`, and `bound_conclusion` **as a function of large-kernel size / tier**, not a
  single verdict.
- `headline`: state where in (large-kernel size × reuse) zero copy helps, and what that implies about
  the bottleneck tier — now backed by a real large-kernel sweep, not a symmetric point.
- **Do not overwrite** Phase 1/2/3 findings. In `FINDINGS.md`, record the discrepancy vs the first
  Phase 4 run (esp. that `sym_0`/`sym_1` "large kernel" was symmetric, and any change from re-swept
  block counts).

Write `FINDINGS.md` (this is the study's payoff section — prose), a new
`worklog/YYYY-MM-DD-HHMM_phase4-v2-resweep.md`, and print a suggested one-line git commit message. Do
not commit automatically.
