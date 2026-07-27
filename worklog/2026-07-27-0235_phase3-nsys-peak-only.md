# Worklog — 2026-07-27 02:35 — phase3-nsys-peak-only

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only
**State:** completed

## Summary
Immediate follow-up to `2026-07-27-0230_phase3-symmetric-8-8-and-nsys-scope.md` in
this same session: the user considered 58 nsys-profiled cells (shared + best-green
across all 29 sizes) excessive for a concurrency sanity check and asked to narrow it
further to just the single peak-bandwidth test point per mode (symmetric,
asymmetric) -- explicitly **not hardcoded**, computed from the real CSV every run.

## What I did
- `scripts/run_overlap_nsys.py`: added `select_peak_bandwidth_test_points(df)` --
  `{mode: g.loc[g.agg_GBps_median.idxmax(), "test_point_id"] for mode, g in
  df.groupby("mode")}` -- computed fresh from `results/phase3_results.csv` on every
  invocation, nothing hardcoded. `select_plotted_cells()` now restricts to just
  those 2 test points before applying the existing shared+best-green selection,
  bringing the profiled set from 58 cells down to 4 (2 modes x shared+green).
  Printed the computed peak test points to stderr for visibility
  (`Peak-bandwidth test point per mode (computed from this CSV, not hardcoded): ...`).
- Verified with `--dry-run` against the real, already-present
  `results/phase3_results.csv`: correctly selected `asym_131072` (214.326 GB/s) and
  `sym_524288` (193.702 GB/s) as the two peaks -- these numbers appear only in
  program output/verification, never written into the source as constants.
  Re-ran the earlier mocked-subprocess smoke test (normal / timeout / rc=4 paths)
  against the updated selection -- all three still pass.
- Updated stale docstrings/comments in `run_overlap_nsys.py`, `verify_overlap_nsys.sh`,
  and `plot_overlap_nsys.py` that said "per size" / "every size" to reflect the new
  2-test-point (4-cell) scope.

## Files modified
- `experiments/03_green_context/scripts/run_overlap_nsys.py`
- `experiments/03_green_context/scripts/verify_overlap_nsys.sh` (comments only)
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` (docstring only)

## Key decisions & rationale
- "Peak bandwidth" is computed as `agg_GBps_median.idxmax()` across ALL rows of a
  mode (any config), not restricted to `shared` rows only -- in the current CSV both
  peaks happen to be `shared` rows, but the selection doesn't assume that; it's
  whichever single row is fastest, then that row's `test_point_id` is used to also
  pull the matching best-green row for the same size.
- Kept this a direct chat-instruction change rather than a new prompt file -- the
  user gave the instruction directly rather than adding a `.md` prompt; implemented
  it in place without asking them to formalize it into a prompt doc.

## Handoff → next session
No change to the on-device next-steps already listed in
`2026-07-27-0230_phase3-symmetric-8-8-and-nsys-scope.md` items 1-3, except that the
nsys pass in step 2 will now profile 4 cells instead of 58 -- much faster to
sanity-check.

## Suggested commit message
```
fix(phase3): narrow nsys overlap verification to the peak-bandwidth point per mode

select_peak_bandwidth_test_points() picks, per mode, the test_point_id with
max agg_GBps_median from the real phase3_results.csv at run time (never
hardcoded) -- profiling only that point's shared+best-green cells (4 total)
instead of every size (58), since the peak/roofline point is the single most
informative place to sanity-check concurrent overlap.
```
