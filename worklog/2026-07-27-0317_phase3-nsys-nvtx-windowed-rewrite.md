# Worklog — 2026-07-27 03:17 — phase3-nsys-nvtx-windowed-rewrite

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only (per standing
instruction: this session develops Phase 3 exclusively)
**State:** completed (code + logic validated with synthetic fixtures; needs an
on-device nsys run to produce real numbers)

## Summary
Implemented the revised `prompts/03_green_context/03_verify_overlap_nsys.md`
("clean nsys overlap verification (NVTX-windowed, plotted cells)"), which
supersedes the earlier sqlite-based attempt after two facts were discovered
on the real Jetson: (1) `nsys export --type=sqlite` produces an empty (0-table)
database on this project's nsys version (2025.6.3), so the previous
`parse_nsys_sqlite.py` approach cannot work here at all; (2) counting every
kernel launch in the whole trace (warmup + in-context block-saturation search
+ measured trials) badly dilutes the overlap ratio (an unwindowed run measured
green~=0.10, shared~=0.01). Before implementing, updated the prompt doc itself
to reflect the peak-bandwidth-only (4-cell) scope from the prior session --
the prompt's own text had reverted to describing "all sizes" (~58 cells),
which the user confirmed should stay narrowed to 4 (per-mode peak).

## What I did
1. **Updated `prompts/03_green_context/03_verify_overlap_nsys.md`** (per explicit
   instruction): rewrote the "Cell selection" section to say peak-bandwidth
   point per mode (4 cells), not "all sizes" (~58 cells), so the doc matches
   what's actually implemented and doesn't re-confuse a future session.
2. **`src/phase3_bench.cu`**: added `#include <nvtx3/nvToolsExt.h>`. Gave
   `measureSharedWallMs`/`measureGreenWallMs` a new `bool tagMeasuredTrials =
   false` parameter; when true, wraps ONLY the timed-trial `for` loop (not the
   warmup launches above it, not the whole function) in
   `nvtxRangePush("measure")`/`nvtxRangePop()`. Passed `true` only at the two
   "final measured cell" call sites (after the in-context block-search has
   already picked `bestBlocks0/1`); left the block-search's own calls to these
   same functions (via the `aggGBpsForPair` lambda, `kSearchTrials`) at the
   default `false` so they're never inside the NVTX range. `build.sh` comment
   updated to note NVTX3 is normally header-only (dlopen-based, no link flag
   needed) with a fallback note to add `-lnvToolsExt` if a given toolkit needs it.
3. **New `scripts/parse_nsys_csv.py`** (replaces `parse_nsys_sqlite.py`, deleted):
   `find_measure_window()` locates the NVTX range named `measure` in an
   `nvtx_pushpop_trace` CSV; `load_kernel_intervals_in_window()` keeps
   `addKernel(...)` rows (excludes `fillKernel`) from a `cuda_gpu_trace` CSV
   whose interval falls entirely inside that window, and collects distinct
   `GreenCtx` values; `compute_overlap_in_window()` runs the same sweep-line
   union/concurrent algorithm as the old sqlite parser over those filtered
   intervals. Column names are resolved defensively (a short candidate list
   per column, e.g. `"Start (ns)"` vs `"Start"`) since nsys's stats CSV schema
   shifts across releases; raises a clear `RuntimeError` listing actual
   columns/range-names if nothing matches, rather than guessing.
   **Validated with hand-built synthetic CSVs**: 3 kept `addKernel` intervals
   (one pair overlapping, one isolated) inside a `[1000, 2000]` window, one
   `fillKernel` decoy correctly excluded, one interval before and one after
   the window correctly excluded, 2 distinct `GreenCtx` values -> computed
   `union_busy_ms`/`concurrent_ms`/`overlap_ratio`/`distinct_greenctx` all
   matched hand calculation exactly (overlap_ratio=0.25). Also verified the
   `"Start"/"End"` column-name fallback and the "no 'measure' range found"
   clear-error path.
4. **`scripts/run_overlap_nsys.py`**: kept the peak-bandwidth-per-mode (4-cell)
   selection from the prior session unchanged. Rewrote `profile_cell()`:
   `nsys profile` now passes `-t cuda,nvtx` (was `-t cuda`); after a successful
   profile, runs `nsys stats --report cuda_gpu_trace --format csv
   --force-export=true --output <base> <rep>` and the same for
   `nvtx_pushpop_trace` (never `nsys export --type=sqlite`), then calls
   `parse_nsys_csv.compute_overlap_in_window()`. Added a new failure mode: if
   the CSVs come back but the `measure` NVTX range can't be found/parsed
   (`RuntimeError` from the parser), the cell is recorded as a NaN row (same
   treatment as a timeout) rather than dropped, since the throughput
   measurement for that cell is still real -- only the trace's own
   instrumentation failed. CSV schema updated: dropped `reuse_N` (redundant --
   every cell here is reuse_N=1, and the new schema doesn't ask for it),
   renamed `kernel_instances` -> `kernel_instances_in_window`, added
   `distinct_greenctx`. Disk hygiene now cleans up 3 temp files per cell
   (`.nsys-rep` + 2 stats CSVs) instead of 2.
   **Validated end-to-end** via monkeypatched `subprocess.run` (writing real
   synthetic CSVs instead of invoking nsys): normal path, timeout path (NaN
   row, not dropped), rc=4 path (dropped), and the new missing-NVTX-range path
   (NaN row, not dropped/crashed) all behave correctly against a real
   `results/phase3_results.csv` row.
5. **`scripts/verify_overlap_nsys.sh`**: added an explicit `timeout`
   availability check (previously only `run_overlap_nsys.py` checked it
   internally; now the `.sh` entry point fails fast too, consistent with its
   existing `nsys` check).
6. **`README.md`**: updated the `run_overlap_nsys.py` and (renamed)
   `parse_nsys_csv.py` layout-table entries to describe the NVTX-windowed,
   `nsys stats --format csv` flow instead of the sqlite export, and the new
   `distinct_greenctx` field. `plot_overlap_nsys.py` needed no changes (it
   never referenced `reuse_N`/`kernel_instances` by name).

## Files created / modified
- `prompts/03_green_context/03_verify_overlap_nsys.md` -- cell-selection section corrected to 4 cells
- `experiments/03_green_context/src/phase3_bench.cu` -- NVTX instrumentation
- `experiments/03_green_context/scripts/build.sh` -- NVTX link-flag note
- `experiments/03_green_context/scripts/parse_nsys_csv.py` -- new (replaces parse_nsys_sqlite.py)
- `experiments/03_green_context/scripts/parse_nsys_sqlite.py` -- deleted (confirmed non-functional on real nsys)
- `experiments/03_green_context/scripts/run_overlap_nsys.py` -- nsys-stats-CSV flow, new schema
- `experiments/03_green_context/scripts/verify_overlap_nsys.sh` -- added `timeout` check
- `experiments/03_green_context/README.md` -- layout table updated

## Key decisions & rationale
- Used an optional trailing boolean parameter (`tagMeasuredTrials`, default
  `false`) on the existing measurement functions rather than duplicating them
  or wrapping the call sites externally -- wrapping externally doesn't work
  here because both functions do their OWN internal warmup (3 untimed
  launches) before the timed loop; an external wrapper around the whole call
  would incorrectly include that warmup inside the NVTX range.
- A missing/unparseable NVTX `measure` range is treated the same as a timeout
  (NaN row, not dropped) rather than a hard failure, since by construction it
  means "nsys/NVTX instrumentation didn't work for this cell," not "this
  configuration wasn't actually measured" -- the distinction the codebase
  already draws between rc=4 (drop) and everything else (record as NaN,
  investigate later).
- Deleted `parse_nsys_sqlite.py` outright rather than leaving it alongside as
  dead code -- the prompt explicitly says "this supersedes any earlier
  overlap-verification attempt -- implement it as the single clean version,"
  and the sqlite path is confirmed non-functional on the actual target nsys
  version, so keeping it around would only invite someone to accidentally
  resurrect a broken approach.

## Results / findings produced
None yet -- no real nsys trace was run in this session (no CUDA/nsys toolchain
on this Windows dev machine). All validation used hand-built synthetic CSV
fixtures and mocked `subprocess.run` calls to check the Python logic and the
sweep-line/window-filtering math in isolation.

## Upstream I consumed
- `prompts/03_green_context/03_verify_overlap_nsys.md` (both the version I
  implemented against previously and this session's rewrite, via `git diff`).
- `worklog/2026-07-27-1015_HANDOFF.md`, `OVERVIEW.md`, `prompts/00_conventions.md`.
- `experiments/03_green_context/src/phase3_bench.cu`'s current measurement
  functions (`measureSharedWallMs`/`measureGreenWallMs`) and their call sites,
  read in full to find the exact boundary between "in-context block search"
  and "final measured cell" so the NVTX range brackets only the latter.

## Open questions / blockers
- **Not run against real nsys.** The exact `cuda_gpu_trace`/`nvtx_pushpop_trace`
  CSV column names (`"Start (ns)"` vs `"Start"`, the exact `GreenCtx` column
  name) are assumed from the prompt author's on-device discovery and general
  nsys knowledge, not independently re-verified here -- `parse_nsys_csv.py`'s
  defensive column resolution should absorb minor naming differences, but a
  totally different schema would raise a clear `RuntimeError` rather than
  silently misparsing (check stderr on first real run).
- NVTX3 header-only linking is assumed to need no extra build flag; unverified
  against the actual toolkit on this Jetson (build.sh has a fallback note).

## Handoff → next session
1. On the Jetson: rebuild (`scripts/build.sh`, now needs the NVTX header found
   -- should be present in any standard CUDA install) and re-run
   `scripts/verify_overlap_nsys.sh` (or let `scripts/run.sh` invoke it
   automatically). Watch stderr for any column-resolution `RuntimeError` from
   `parse_nsys_csv.py` -- if raised, paste the actual CSV header row from
   `<tmp>/cell_cuda_gpu_trace.csv` / `cell_nvtx_pushpop_trace.csv` (or rerun
   `nsys stats` manually against a kept `.nsys-rep` copy) so the candidate
   column list can be extended.
2. Check `results/overlap_nsys.csv`'s `distinct_greenctx` column: expect 2 for
   the green-config rows (confirms two separate green contexts were actually
   created and traced), 0 or 1 for shared. If green shows 1, that's a real
   finding worth flagging (SM partitioning may not be creating distinct
   contexts, or the GreenCtx column isn't populated the way expected).
3. Per the prompt's Interpretation section: expect green overlap >> shared
   overlap now that the window excludes search/warmup noise; write the actual
   comparison into a follow-up worklog entry once real numbers exist.

## Suggested commit message
```
fix(phase3): NVTX-windowed nsys overlap verification (nsys stats CSV, not sqlite export)

nsys export --type=sqlite produces an empty database on this project's nsys
version (2025.6.3) -- confirmed on-device. Switches extraction to `nsys stats
--report {cuda_gpu_trace,nvtx_pushpop_trace} --format csv`. Adds NVTX
instrumentation (nvtxRangePush/Pop "measure") around ONLY the final
measured-trial loop in phase3_bench.cu, excluding warmup and the in-context
block-search that previously diluted the overlap ratio badly (green~=0.10,
shared~=0.01 unwindowed). New parse_nsys_csv.py replaces parse_nsys_sqlite.py
(deleted); CSV schema drops reuse_N, adds kernel_instances_in_window and
distinct_greenctx. Keeps the existing peak-bandwidth-per-mode (4-cell)
selection scope; corrected the prompt doc itself which had reverted to
describing an all-sizes (~58-cell) selection.
```
