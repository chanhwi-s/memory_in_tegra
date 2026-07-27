# Worklog — 2026-07-27 08:36 — phase3-overlap-per-cell-parameters

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ only
**State:** completed

## Summary
Immediate follow-up: user asked for each of the 4 nsys overlap data points to
show its exact parameters (kernel size, block size, SM split) visibly, not just
the overlap percentage. Extended the overlap_nsys.csv schema and both outputs
(bar chart, table) from the previous entry to surface this.

## What I did
- `scripts/run_overlap_nsys.py`: appended `sm_split_k0`, `sm_split_k1`,
  `blocks_k0`, `blocks_k1`, `threads_per_block` to `CSV_FIELDS` (after the
  prompt-specified columns, so nothing already parsing by the original column
  order breaks) and populated them in `profile_cell()`'s `out` dict straight
  from the `phase3_results.csv` row (the same row `cell_args()` already reads
  to reconstruct the `--fixed-blocks0/1`/`--sm0/1` invocation -- no new data
  source, just also copied into the output).
- `scripts/plot_overlap_nsys.py`:
  - x-tick labels now show each mode's K0/K1 size (`_mode_xtick_label`) --
    identical across that mode's shared/green rows, so shown once per mode.
  - Each bar gets a stacked annotation (`_bar_config_label`): SM split, block
    counts, threads/block. First attempt placed this near the bar's base,
    inside the colored fill -- illegible (gray-on-blue/green contrast, and
    the "anti-patterns" guidance from the dataviz skill against text sitting
    on a fill it wasn't designed for). Moved it to stack in the open white
    space ABOVE each bar (right above the percentage label) instead, which
    reads correctly regardless of bar height or color.
  - Legend moved from `upper right` to `upper center`: with annotations now
    stacked above every bar, upper-right collided with the tallest bar's
    (asymmetric green, 92%) text stack. `upper center` lands in the one empty
    column between the two mode groups.
  - `write_table()`: added K0 size, K1 size, SM split, blocks, threads/block
    columns.
  - **Both functions degrade gracefully** if `overlap_nsys.csv` predates these
    columns (checked via a new `CONFIG_COLS` constant + `has_config_cols`
    guard): a stderr NOTE explaining what's missing and why, table/chart still
    render with just the columns that exist, no crash.
- **Caught my own mistake again while testing** (second time this session):
  overwrote the real, already-committed `results/overlap_nsys.csv` with
  synthetic full-schema data to test the new columns, then discovered the real
  file predates this feature (older schema, no config columns) when
  `plot_overlap_nsys.py` crashed with `AttributeError` on the genuinely-missing
  columns -- which is exactly what led to writing the graceful-degradation
  path above. Restored the real file via `git checkout --` (first pass) and,
  after a second accidental overwrite, via a manual backup-copy/restore
  (second pass) before finishing. Final state: real `overlap_nsys.csv`
  untouched; its regenerated plot/table (both new, uncommitted files) now
  correctly show "N/A" + a stderr NOTE for every cell, since that CSV's
  overlap values are themselves all NaN (predates the NVTX-windowing fix, see
  `2026-07-27-0317_phase3-nsys-nvtx-windowed-rewrite.md`) AND predates the
  config columns added just now.
- `README.md`: updated the `plot_overlap_nsys.py` layout-table entry to
  describe the bar chart + table + per-cell config annotations + graceful
  degradation.

## Files created / modified
- `experiments/03_green_context/scripts/run_overlap_nsys.py` — new CSV columns
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` — chart/table annotations + graceful degradation
- `experiments/03_green_context/README.md` — layout table entry updated
- `experiments/03_green_context/results/overlap_nsys_table.md` — new (generated, degraded/N-A since the real CSV predates these columns)
- `experiments/03_green_context/results/plots/overlap_ratio_vs_footprint_combined_footprint.png` — new (regenerated, degraded/N-A for the same reason)

Confirmed via `git status` that `results/overlap_nsys.csv` itself (the real,
previously-committed device data) is unmodified.

## Key decisions & rationale
- Appended the new columns to the END of `CSV_FIELDS` rather than inserting
  them near `k0_bytes`/`k1_bytes` -- keeps the prompt-specified column order
  (`prompts/03_green_context/03_verify_overlap_nsys.md`) intact for any
  positional consumer, with the extension purely additive.
- Graceful degradation (NOTE + reduced output) instead of failing loudly on
  missing columns -- unlike the "never substitute a guess for a missing
  *upstream finding*" rule (00_conventions.md #2), this is a case of an
  **older version of this phase's own output schema**, not a fabricated
  measurement; showing what's available with a clear note is the right call,
  not silently guessing a config that was never recorded.

## Handoff → next session
Once `run_overlap_nsys.py` is re-run on-device (with both this session's NVTX
fix and this column addition), `overlap_nsys.csv` will have real overlap
percentages AND the config columns together; re-run `plot_overlap_nsys.py`
to get the fully populated chart/table (no more NOTE, no more N/A).

## Suggested commit message
```
feat(phase3): show each nsys overlap cell's exact config (size/blocks/SM split)

Extends overlap_nsys.csv with sm_split_k0/1, blocks_k0/1, threads_per_block
(copied from the phase3_results.csv row already used to reconstruct the
--fixed-blocks invocation). Bar chart now stacks each bar's SM split/block
counts above it (moved off the colored fill after a first attempt read
poorly there); table gains matching columns. Both degrade gracefully with a
stderr note if run against an older overlap_nsys.csv missing these columns.
```
