# Worklog — 2026-07-27 02:30 — phase3-symmetric-8-8-and-nsys-scope

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only (per standing
instruction: this session develops Phase 3 exclusively)
**State:** completed (code + logic validated; needs an on-device re-run to produce
final numbers)

## Summary
Implemented two new prompts found under `prompts/03_green_context/`:
1. `03_symmetric_fix_8_8_split.md` -- symmetric green cells now sweep only the 8:8
   SM split (asymmetric untouched); `partition_sweep.png` is now asymmetric-only.
2. `03_verify_overlap_nsys.md` (revised since my last session) -- narrowed the nsys
   verification from "every sweep cell" to just the cells `plot.py`'s
   `green_vs_shared.png` actually shows (shared + best-green per size), reconstructed
   from the already-measured CSV via `--fixed-blocks0/1` instead of re-searching, plus
   a `timeout`-wrapped nsys call with CPU sampling off and NaN-on-timeout handling.

## What I did

### 1. Symmetric 8:8 fix (`03_symmetric_fix_8_8_split.md`)
- `scripts/sweep.py`: replaced `SYMMETRIC_SPLITS = [(4,12),(6,10),(8,8),(10,6),(12,4)]`
  with a single `SYMMETRIC_SPLIT = (8, 8)`; `build_plan()` now emits only that one
  green cell per symmetric size (`[SYMMETRIC_SPLIT] if mode == "symmetric" else
  asymmetric_splits(...)`). Verified via `--dry-run`: total planned cells dropped from
  149 to 77; symmetric green cells confirmed to be exactly 18 (one per size, split
  always `(8, 8)`); asymmetric green cells unchanged at 30.
- `scripts/plot.py`: `_pick_contrast_points()` and `plot_partition_sweep()` now
  restrict to `mode == "asymmetric"` only (previously symmetric-only) -- a symmetric
  partition sweep is now a single point and carries no ratio-shape information. Also
  fixed `_plot_split_panel()`'s x-axis label, which previously always showed
  `k0_bytes` as "per-kernel size" (accurate for symmetric, but wrong for asymmetric
  where K0 is fixed at 1 MB and K1 is the swept size) -- now shows both
  `K0=... B fixed, K1=... B` explicitly, which matters more now that this panel is
  asymmetric-only. Regenerated `results/plots/partition_sweep.png` against the
  existing (pre-fix) CSV to visually confirm it now renders two asymmetric-only
  panels with correct labels -- reverted the other 3 plots
  (`green_vs_shared.png`/`delta_vs_size.png`/`reuse_green_vs_shared.png`) via `git
  checkout` after regeneration since their code paths are unchanged and the
  re-render was pixel-different only from incidental matplotlib metadata, not real
  content (confirmed via `git status`/`git diff --stat` before reverting).
- `scripts/derive_findings.py`: no code change needed. `best_partition_ratios_by_regime()`
  already computes "best" per (mode, regime) from whatever green rows exist for that
  bucket; once the CSV only contains 8:8 rows for symmetric, every symmetric regime
  bucket trivially resolves to `"8:8"` -- this is a consequence of the sweep change,
  not something to special-case in the derivation code. **Did not re-run
  `derive_findings.py`** against the existing (pre-fix) CSV, since that CSV still has
  the old 5-split symmetric data and regenerating `findings.json` from it would not
  yet reflect the "always 8:8" invariant this fix produces -- that requires an actual
  on-device re-run of `scripts/sweep.py` first.

### 2. nsys verification scope change (`03_verify_overlap_nsys.md`, revised)
- Rewrote `scripts/run_overlap_nsys.py`: no longer imports `sweep.build_plan()` /
  iterates the full sweep. Instead reads `results/phase3_results.csv` directly and
  selects, per `test_point_id`, the `shared` row + the green row with max
  `agg_GBps_median` (`select_plotted_cells()` -- the identical few-line selection
  `plot.py`'s `_point_summary`/`plot_green_vs_shared` uses, reimplemented rather than
  imported since `plot.py` stays off-limits for edits per the additive-only
  constraint). `cell_args()` reconstructs each selected row's exact `phase3_bench`
  invocation via `--fixed-blocks0`/`--fixed-blocks1` (skips the in-context
  block-count search, measures at exactly the row's recorded block counts) instead
  of `--blocks0-seed`/`--blocks1-seed`. `profile_cell()` now wraps the `nsys profile`
  call in `timeout 180` and adds `--sample=none --cpuctxsw=none`; a `timeout`
  (rc=124) produces a row with `kernel_instances`/`union_busy_ms`/`concurrent_ms`/
  `overlap_ratio` left empty (-> NaN on CSV read) rather than dropping the cell,
  while an invalid-ratio rejection (rc=4) still drops it (that configuration was
  never actually measured, so there's nothing to report).
  Validated with `--dry-run` against the real, already-present
  `results/phase3_results.csv`: selected 58 cells (29 test points x 2), all args
  correctly reconstructed with `--fixed-blocks0/1` in place of the seed flags.
  Further validated `profile_cell()`'s three branches (normal / timeout / rc=4) by
  monkeypatching `subprocess.run` -- confirmed the normal path's computed
  `overlap_ratio` matches a hand-calculated value from a synthetic sqlite trace, the
  timeout path returns a NaN-sentinel row (not `None`), and the rc=4 path returns
  `None`.
- `scripts/plot_overlap_nsys.py`: updated the docstring/legend label -- with the
  narrowed selection there is now exactly one green row per `test_point_id` (not
  several SM-split rows), so "mean over SM splits" was no longer accurate framing;
  the aggregation is kept (defensive, harmless no-op on single-row groups) but now
  documented as such. Verified the plot still renders correctly with a synthetic CSV
  containing one NaN (timed-out) row -- matplotlib simply skips that point, no crash.
  (Caught and fixed a stray-space bug in my OWN synthetic test CSV along the way --
  not a bug in the actual script; confirmed pandas correctly infers `float64` +
  `NaN` for a properly empty CSV field.)
- `scripts/verify_overlap_nsys.sh`: updated stale comments describing the run as
  "every cell" / "all Phase 3 sweep cells" to reflect the new shared+best-green
  scope; no logic changes needed there (it just invokes the two Python scripts).

## Files created / modified
- `experiments/03_green_context/scripts/sweep.py` — symmetric green split fixed to 8:8
- `experiments/03_green_context/scripts/plot.py` — `partition_sweep.png` asymmetric-only
  + fixed asymmetric axis label
- `experiments/03_green_context/scripts/run_overlap_nsys.py` — cell selection rewritten
  (CSV-driven, not full-sweep), `--fixed-blocks0/1`, `timeout`/`--sample=none
  --cpuctxsw=none`, NaN-on-timeout
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` — docstring/label fix
- `experiments/03_green_context/scripts/verify_overlap_nsys.sh` — comment updates
- `experiments/03_green_context/results/plots/partition_sweep.png` — regenerated
  (asymmetric-only preview against the pre-fix CSV; see caveat below)

Confirmed via `git status` that no files outside `experiments/03_green_context/`
were touched, and that `results/phase3_results.csv`, `findings.json`, and the other
3 plot PNGs are untouched.

## Key decisions & rationale
- Did not extract a shared "best-green selection" helper into a common module: the
  selection is ~3 lines and appears in `plot.py` (protected) and now
  `run_overlap_nsys.py`; the prompt itself frames this as "reuse the SAME
  selection," which I read as "produce identical results," not "must share code" --
  reimplementing a 3-line, well-specified operation is lower-risk here than
  restructuring `plot.py` against its own additive-only constraint.
- Left `derive_findings.py` and `findings.json` alone this session (see above) --
  regenerating findings from stale pre-fix data would misrepresent the new
  invariant as "measured" when it wasn't yet re-measured under the new code.
- `partition_sweep.png` was regenerated (and kept) despite using the stale CSV
  because the code change (asymmetric-only filtering) is correct and safely
  demonstrable against ANY CSV shape, old or new -- it isn't misrepresenting new
  data as old, it's just proving the filter works. The other 3 unaffected plots were
  reverted to avoid meaningless diff noise.

## Results / findings produced
None (no `findings.json` changes this session, correctly -- see above).

## Upstream I consumed
- `prompts/03_green_context/03_symmetric_fix_8_8_split.md`,
  `prompts/03_green_context/03_verify_overlap_nsys.md` (re-read after noticing it was
  modified via `git diff` since my last session), `worklog/2026-07-27-1015_HANDOFF.md`.
- `experiments/03_green_context/src/phase3_bench.cu` (grepped the `--fixed-blocks0/1`
  / `--reuse-overlay` code path to confirm fixed-blocks mode skips the search AND
  still prints the standard `sweep.CSV_HEADER`-shaped row when `--reuse-overlay` is
  NOT also passed -- this is what makes cell reconstruction via fixed blocks work
  correctly here).
- `experiments/03_green_context/scripts/sweep_reuse.py` (read-only, to confirm it
  already reads back "whatever green split has max agg_GBps_median" for a size
  rather than hardcoding a split list -- so it needed no changes for the 8:8 fix;
  it will automatically pick up 8:8 as the only option once the CSV is re-measured).

## Open questions / blockers
- **Needs an on-device re-run** (`bash scripts/run.sh`) to produce the actual
  77-cell CSV with the new symmetric-only-8:8 shape; only then should
  `derive_findings.py` be re-run to regenerate `findings.json`/`FINDINGS.md` with the
  now-trivial `best_partition_ratios.symmetric == "8:8"` for every regime bucket.
- **`verify_overlap_nsys.sh` / `run_overlap_nsys.py` are still unverified against a
  real nsys binary** (none available in this dev environment) -- only the pure
  Python selection/reconstruction/timeout logic was validated via mocks and a
  synthetic sqlite trace, same caveat as the previous nsys session.
- The `timeout` utility's exit-code convention (124 for "killed after limit") is the
  GNU coreutils default; confirm this matches the Jetson's actual `timeout` (L4T is
  Ubuntu-based, so this should hold, but hasn't been checked on the real device).

## Handoff → next session
1. On the Jetson: `bash experiments/03_green_context/scripts/run.sh` to re-measure
   with the new 8:8-only symmetric sweep (77 cells instead of 149 -- should be
   noticeably faster), then re-run `derive_findings.py` if `run.sh` doesn't already
   (it should, per the earlier "single entry point" fix).
2. Then `bash experiments/03_green_context/scripts/verify_overlap_nsys.sh --dry-run`
   to confirm the selection now shows exactly 2 cells per test point (58 total for
   29 test points), then without `--dry-run` for the real nsys pass.
3. Watch stderr for any `timeout` (rc=124) or `rc=4` cells during the nsys run; per
   the prompt, timeouts stay in the CSV as NaN rows (investigate WHY nsys hung
   rather than just re-running), while rc=4 drops are expected/normal (an SM ratio
   the driver rejects, same as the main sweep already tolerates).

## Suggested commit message
```
fix(phase3): symmetric green sweep -> single 8:8 split; narrow nsys verification to plotted cells

Sweeping asymmetric SM ratios for equal-size symmetric kernels added noise
with no research value -- sweep.py now emits only 8:8 for symmetric green
cells (149->77 total cells); plot.py's partition_sweep.png is asymmetric-only
accordingly. Separately, narrows the nsys overlap verification from the full
sweep to just the shared+best-green cells plot.py's green_vs_shared.png shows,
reconstructing each cell via --fixed-blocks0/1 (no re-search) and wrapping
nsys profile in `timeout 180` with CPU sampling off; a timed-out cell is now
recorded as an overlap_ratio=NaN row instead of being dropped.
```
