# Worklog — 2026-07-27 08:28 — phase3-overlap-bar-chart-table

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only
**State:** completed

## Summary
User asked for the nsys overlap results to be shown directly as percentages, or
failing that a table. Rewrote `scripts/plot_overlap_nsys.py` from a 2-point line
plot (unsuited to only 2 x-positions -- one peak-bandwidth size per mode) to a
grouped bar chart (mode x config) with the overlap ratio shown as a labeled
percentage on each bar, plus a new markdown summary table.

## What I did
- `scripts/plot_overlap_nsys.py`: replaced the line plot with a grouped bar chart
  -- x-axis = mode (symmetric, asymmetric), grouped bars = {shared, green}, y-axis
  = overlap % (0-100, `overlap_ratio * 100`), each bar directly labeled with its
  percentage (or "N/A" for a NaN/timeout row), dashed reference line at 100%.
  Kept the existing fixed categorical colors (tab:blue=shared, tab:green=green)
  already used throughout this phase's other plots, per dataviz convention (color
  identifies the series, never re-cycled).
- Added `write_table()` -> `results/overlap_nsys_table.md`: one markdown table row
  per (mode, config) with test point, overlap %, kernel-instances-in-window,
  distinct-GreenCtx count, and combined footprint (MB) -- for reading the result
  without opening the PNG. Both functions handle NaN rows (timeout / unparseable
  NVTX window) gracefully: "N/A" label/cell, not a crash or a fabricated 0%.
- Smoke-tested against synthetic CSVs (normal 4-row case, and an all-shared-NaN
  case) before touching anything real.
- **Caught and fixed my own mistake**: while testing, I overwrote and then deleted
  `results/overlap_nsys.csv` with synthetic data -- this turned out to be a
  REAL, already-committed file from an actual on-device run (git showed it as
  `D` after my cleanup). Restored it immediately via `git checkout --`. That
  file's real values are all empty/NaN for every cell, which makes sense: it
  predates this session's NVTX-windowing fix (worklog
  `2026-07-27-0317_phase3-nsys-nvtx-windowed-rewrite.md`) -- it's the actual
  broken output the prompt update was describing, not a new problem.
- Ran the final script against that real (all-NaN) committed CSV to confirm it
  renders without crashing (bars at 0 height, "N/A" labels, table cells say
  "N/A (timeout/parse failure)") -- these two output files were not previously
  committed, so they're new (`??`), not a modification of tracked data.

## Files created / modified
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` — bar chart + table
- `experiments/03_green_context/results/overlap_nsys_table.md` — new (generated from real, currently all-NaN, CSV)
- `experiments/03_green_context/results/plots/overlap_ratio_vs_footprint_combined_footprint.png` — new (regenerated from real CSV, all-NaN)

## Key decisions & rationale
- Bar chart over line plot: with only 2 x-positions (one peak size per mode,
  narrowed down two sessions ago), a "line" between two points shows no trend
  and mainly adds visual noise; a grouped bar chart is the correct form for a
  magnitude comparison across a small number of categories (dataviz skill:
  "Pick the form" step).
- Direct percentage labels on each bar rather than relying on the y-axis alone
  -- with only 4 bars total, labeling every one is appropriate (the "never a
  number on every point" caution in the dataviz skill is about dense series,
  not a 4-bar chart).

## Handoff → next session
Once `run_overlap_nsys.py` is re-run on-device with this session's NVTX fix,
`results/overlap_nsys.csv` should get real (non-NaN) values; re-run
`plot_overlap_nsys.py` afterward to regenerate the bar chart/table with real
percentages (currently both show "N/A" because the committed CSV predates the
NVTX fix).

## Suggested commit message
```
feat(phase3): show nsys overlap as a percentage bar chart + summary table

Replaces the 2-point line plot (unsuited to only one peak-bandwidth size per
mode) with a grouped bar chart labeling overlap_ratio as a percentage
directly on each bar, plus a new results/overlap_nsys_table.md for reading
the result without opening the PNG. Handles NaN (timeout/unparsed) rows as
"N/A" rather than crashing or fabricating a value.
```
