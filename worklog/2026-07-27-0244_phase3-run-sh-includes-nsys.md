# Worklog — 2026-07-27 02:44 — phase3-run-sh-includes-nsys

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only
**State:** completed

## Summary
Now that the nsys overlap verification is down to 4 cells (peak-bandwidth point per
mode, previous entry), the user asked for `scripts/run.sh` to run it automatically
every time instead of needing a separate `scripts/verify_overlap_nsys.sh` invocation
-- consistent with the project's "run.sh is the single entry point" convention.

## What I did
- `scripts/run.sh`: added a `RUN_NSYS_OVERLAP` step (default on) right after the
  reuse_N overlay step, calling `python3 scripts/run_overlap_nsys.py` directly
  (not shelling out to `verify_overlap_nsys.sh`, to avoid redundantly re-locking
  clocks / re-checking build staleness that `run.sh` already did earlier in the
  same script). Guards with `command -v nsys` / `command -v timeout` first and
  prints a WARNING + skips (not fatal) if either is missing, same pattern as the
  existing sudo/reuse-overlay steps. Added `--skip-nsys` (parity with the existing
  `--skip-reuse`) for anyone who wants to opt out.
- After `plot.py`, added a conditional call to `plot_overlap_nsys.py` if
  `results/overlap_nsys.csv` exists (so a `--skip-nsys` run, or a device without
  nsys, doesn't fail trying to plot a CSV that was never written).
- Updated the final "Done." summary block to list the nsys CSV path when present.
- Updated `README.md`'s layout table and "Running" section to document the new
  steps/scripts/flags (`run_overlap_nsys.py`, `parse_nsys_sqlite.py`,
  `plot_overlap_nsys.py`, `verify_overlap_nsys.sh`'s role as a standalone
  re-run-just-this-step alternative, `--skip-nsys`).
- Syntax-checked `run.sh` with `bash -n`; confirmed via `git status` that only
  `run.sh` and `README.md` changed (no results/CSV/findings touched).

## Files modified
- `experiments/03_green_context/scripts/run.sh`
- `experiments/03_green_context/README.md`

## Key decisions & rationale
- Inlined the two Python calls into `run.sh` rather than calling
  `verify_overlap_nsys.sh` as a subprocess, since the latter duplicates
  clock-locking and the build-staleness check that `run.sh` already did moments
  earlier in the same invocation -- `verify_overlap_nsys.sh` remains useful as a
  standalone way to re-run just the nsys step later without redoing the whole sweep.
- Kept the nsys step strictly best-effort/non-fatal (missing tools, or
  `run_overlap_nsys.py` itself failing) so a device without Nsight Systems
  installed, or any nsys-side hiccup, never blocks the throughput sweep/plots/
  findings that `run.sh` exists to guarantee.

## Handoff → next session
No new on-device steps beyond what earlier entries already list -- `bash
scripts/run.sh` now does the nsys verification automatically as part of its
normal flow, so there is no separate step to remember to run afterward.

## Suggested commit message
```
feat(phase3): run.sh now runs nsys overlap verification automatically

Now that the nsys pass profiles only 4 cells (peak-bandwidth point per mode),
folds it into run.sh's single-entry-point flow (best-effort, skipped with a
warning if nsys/timeout are missing) instead of requiring a separate
verify_overlap_nsys.sh invocation. Adds --skip-nsys for parity with
--skip-reuse; plot_overlap_nsys.py runs conditionally if its CSV exists.
```
