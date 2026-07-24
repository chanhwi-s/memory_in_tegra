# Work Prompt — Phase 3 (v2 re-run): Green Context with in-context block saturation and a widened size sweep

**Prerequisites:** read `../OVERVIEW.md`, `00_conventions.md`, and the ORIGINAL
`prompts/03_green_context.md` first. Standard phase layout, worklog, and findings rules apply.
Output stays under `experiments/03_green_context/` — you are **revising this phase in place**, and
this run **supersedes** the first Phase 3 run. Do not modify files outside your phase directory
(read upstream `findings.json` only).

> **Why this re-run exists.** The first Phase 3 run had two methodology gaps that biased the
> conclusion ("green context never helps"):
>
> 1. **Block counts were never re-swept in context.** `scripts/sweep.py` pulled block counts from
>    Phase 1's *single-kernel* `saturation_blocks_by_size` via nearest-neighbor and held them
>    **fixed** (e.g. 917504 → 64 blocks). It did no in-context saturation search. Consequence: the
>    shared baseline came out **under-saturated** — 135.5 GB/s at the symmetric 917504 point, versus
>    Phase 2's own measurement of the *same* point at **143.5 GB/s** (Phase 2 used 128:256 blocks
>    after its local `{1,2,4}×` search). Green was then compared against a weakened baseline, and for
>    green configs the per-partition SM count is *smaller*, so the single-kernel/16-SM block count is
>    even less likely to saturate each partition.
> 2. **The size sweep was pinned to Phase 2's 3 roofline points** (per-kernel 0.79–2 MB, all near the
>    L2/SLC overflow, all classified DRAM-bound). Green context's *predicted* benefit — L1 /
>    occupancy / scheduling isolation — shows up where the **per-SM working set is near L1 (192 KB/SM)**
>    and where scheduling contention bites, i.e. the **small-size end**, which the sweep never entered.
>    "Green never helps" was therefore a foregone conclusion of the point selection, not a measurement.

Zero copy stays **OFF** this phase (unchanged).

## Dependency (unchanged, but read carefully)
- Consumes `experiments/02_two_kernel_size/findings.json` (`recommended_phase3_test_points`, and the
  raw sweep for anchor labeling) and `experiments/01_single_kernel_size/findings.json` (tier steps,
  `recommended_threads_per_block`, and `saturation_blocks_by_size` — now used only as a **search
  seed**, never as a fixed block count). Read at run time; fail loudly if a required key is missing;
  never fabricate.

---

## Change 1 — Saturate block count **in context**, per (test point × config × sm_split)

For **every measured cell**, sweep grid/block count until aggregate throughput plateaus, and report
the plateau (`00_conventions.md` §4: "block count is a knob, not a reported axis; sweep until
throughput flattens"). Requirements:

- **Do not** treat Phase 1's `saturation_blocks_by_size` as the answer. Use the nearest-size value
  only as the **lower bound / seed** of the search.
- The saturation search must run **independently for each config and each SM split**, not once per
  test point. A shared (16:16) cell and a green (8:8) cell for the same sizes generally plateau at
  different block counts — the 8-SM partition needs enough blocks to fill *its* 8 SMs, and the search
  range must scale with the assigned SM count (e.g. sweep blocks per kernel geometrically from
  `~blocks_per_sm_min × assigned_sm_count` up to a cap like 1024, per partition).
- Sweep K0 and K1 block counts to their joint aggregate plateau. A phase2_bench-style local search
  (independent 1-D passes over K0 then K1, widened multiplier set e.g. `{1,2,4,8}× seed` capped at
  1024) is acceptable; a fuller 2-D search is better if cheap. Document the method in `README.md`.
- Prefer implementing the saturation search **inside `phase3_bench`** (so one binary invocation
  returns the saturated cell), mirroring `phase2_bench`'s "local block-count search" but wider and
  split-aware. Alternatively do it in `sweep.py`. Either way it must be per-config.
- Emit the chosen `blocks_k0, blocks_k1` (already CSV columns) plus a boolean/flag indicating the
  plateau was actually reached (throughput gain of the top block count over the previous step
  < ~2%). If a cell never plateaus within the cap, flag it in the run log and `FINDINGS.md`.

**Sanity gate:** the re-swept **shared** baseline at the symmetric 917504 point should now be ≥ Phase
2's 143.5 GB/s for that point (within noise). If it is not, the saturation search is still too narrow
— fix it before trusting any green delta.

## Change 2 — Widen the size sweep into the L1 / small-working-set regime

Do **not** restrict the sweep to Phase 2's 3 recommended points. Build Phase 3's **own** geometric
per-kernel size sweep that spans from small (per-SM working set ≈ L1) through the Phase 2 roofline and
into clearly DRAM-bound:

- **Symmetric:** per-kernel sizes on a ~1.5–2× geometric grid from **~64 KB up to ~8 MB** (combined
  read footprint ~0.5 MB → ~64 MB), covering: (a) the small end where per-SM working set approaches
  the 192 KB/SM L1, (b) the L2 (≤1 MB) and L2+SLC (≤2 MB) tiers from Phase 1, (c) the Phase 2 roofline
  (~0.79–0.92 MB/kernel), and (d) the DRAM-bound tail (> 8 MB combined).
- **Asymmetric:** keep K0 fixed small (1 MB) and sweep K1 across the same wide range (small → DRAM-bound).
- **Anchor labeling:** read Phase 2's `recommended_phase3_test_points` and mark those exact sizes as
  labeled anchor rows within the sweep (so the roofline points remain directly comparable to the
  original run), but the sweep is **not capped** to them.
- Per-SM working set context: for a symmetric size S per kernel on `sm_k` SMs, per-SM read footprint
  ≈ `2·S / sm_k`. Note in `README.md` which sizes put this near/below 192 KB — that is where green is
  predicted to help, and where this sweep must have resolution.

For each size, measure **shared (16:16)** and the SM-split sweep (symmetric splits as before plus
finer splits if useful; asymmetric splits around the size ratio). Record the **best split per size**.

---

## Metrics / CSV / plots
- CSV `results/phase3_results.csv`: same schema as the original prompt (add a `plateau_reached`
  column if not already present). Now spans the full size sweep, not 3 points.
- Plots (`results/plots/`): (1) `green_vs_shared.png` — aggregate GB/s, shared vs best-green, **as a
  function of per-kernel size** (line/grouped bars across the sweep), with the roofline anchors
  marked; (2) `partition_sweep.png` — aggregate + per-kernel GB/s vs SM split, at a small-size point
  AND at the roofline point (so the two regimes are contrasted); (3) `delta_vs_size.png` — green delta
  (%) vs per-kernel size, with the zero line marked, so any crossover into "green helps" is visible.

## Verification (keep original checks, add these)
- **%smid partition check** unchanged (each partition's blocks ran only on assigned SMs; disjoint sets).
- **Baseline saturation check** (Change 1 sanity gate above): re-swept shared 917504 ≥ Phase 2's 143.5
  GB/s. State the number in `FINDINGS.md`.
- **Regime labeling:** classify each size as L1/scheduling-sensitive vs DRAM-bound (using Phase 1 tier
  steps and per-SM working set), and report the size range (if any) where best-green beats shared by
  > 2%. If green still never wins anywhere across the widened sweep, say so explicitly and give the
  per-SM-working-set evidence — that is now a real result, not an artifact of point selection.

## Findings handoff — `findings.json`
Keep the original `results` schema, but:
- `per_point` now covers the widened sweep (or at minimum: all anchors + the best-per-regime points).
- Add `green_helps_size_regime`: prose + numeric range where green ≥ shared (or "none across
  64KB–8MB/kernel sweep").
- `best_partition_ratios` and `configs_for_phase4`: report per regime (small vs roofline vs
  DRAM-bound), since Phase 4 will consume these — do **not** collapse to a single split if it varies
  with size.
- **Do not overwrite** Phase 1/2 findings. In `FINDINGS.md`, record the discrepancy vs the first
  Phase 3 run (old shared 135.5 → new saturated value) and note the first run under-saturated.

Write `FINDINGS.md`, a new `worklog/YYYY-MM-DD-HHMM_phase3-v2-resweep.md`, and print a suggested
one-line git commit message. Do not commit automatically.
