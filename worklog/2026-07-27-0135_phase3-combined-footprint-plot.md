# Worklog — 2026-07-27 01:35 — phase3-combined-footprint-plot

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ (additive only)
**State:** completed

## Summary
Implemented `prompts/03_green_context/03_combined_footprint_plot.md`: added
`scripts/plot_combined_footprint.py`, re-plotting Phase 3's existing results on the unified
combined-read-footprint x-axis (`2*k0_bytes + 2*k1_bytes`, MB, log2) instead of per-kernel
size, so Phase 3 lands on the same axis Phase 2 uses for the same underlying data
(worklog/2026-07-27-1015_HANDOFF.md S2.3). Purely additive per the prompt's constraint --
did not touch `scripts/plot.py`, any CSV, or `findings.json`.

## What I did
- Read `prompts/03_green_context/03_combined_footprint_plot.md`, `worklog/2026-07-27-1015_HANDOFF.md`,
  and current `experiments/01_single_kernel_size/findings.json` (measured DRAM peak 179.2 GB/s,
  `slc_region_max_read_footprint_bytes` = 2097152 -- confirms the handoff's "~2MB cache boundary"
  and "~177 GB/s DRAM peak" are the right reference values to draw).
- Wrote `scripts/plot_combined_footprint.py`:
  - `combined_footprint_mb(df) = (2*k0_bytes + 2*k1_bytes) / MB`, applied identically to both
    `results/phase3_results.csv` and `results/phase3_reuse_results.csv` (same columns in both).
  - `green_vs_shared_combined_footprint.png`: shared vs best-green aggregate GB/s, symmetric AND
    asymmetric test points merged onto the SAME x-axis (this is the whole point of the unified
    footprint definition -- unlike `scripts/plot.py`'s per-kernel-size axis, which needs two
    separate panels because "per-kernel size" means different things in each mode).
  - `reuse_green_vs_shared_combined_footprint.png`: one line per `reuse_N`, shared vs green, same
    x-axis; skips cleanly (prints a NOTE, does not fail) if `phase3_reuse_results.csv` doesn't exist,
    matching the additive-overlay convention already used in `scripts/plot.py`.
  - Reference lines (cache boundary vertical, DRAM peak horizontal) read from Phase 1's
    `findings.json` at run time, with a stated fallback (2 MB / 177 GB/s) + stderr NOTE if that file
    or key is missing -- never fabricated silently.
- Ran it against the real on-device CSVs (both files already present in this checkout): both PNGs
  generated with no fallback notes printed (Phase 1 findings.json had both reference keys).
  Visually confirmed the ~2 MB cache-boundary line lands right at the peak of the combined curve,
  and that symmetric/asymmetric shared curves overlay smoothly across the unified x-axis.

## Files created / modified
- `experiments/03_green_context/scripts/plot_combined_footprint.py` — new
- `experiments/03_green_context/results/plots/green_vs_shared_combined_footprint.png` — new (generated)
- `experiments/03_green_context/results/plots/reuse_green_vs_shared_combined_footprint.png` — new (generated)

## Key decisions & rationale
- Merged symmetric + asymmetric onto one panel/x-axis rather than mirroring `scripts/plot.py`'s
  two-panel split -- the prompt's stated goal ("aligns the ~2 MB boundary across phases",
  "Phase 3 shared reproduces Phase 2") only holds once both modes share the same x quantity;
  splitting them again would have defeated the point of the exercise.
- Reused the existing `scripts/plot.py` conventions (Agg backend, `matplotlib.ticker` for log-scale
  tick formatting, skip-cleanly-if-missing for the reuse overlay) rather than inventing new patterns,
  since this file lives alongside it and should read as part of the same codebase.

## Results / findings produced
No `findings.json` changes (out of scope for this prompt -- plot-only). Visual finding worth
carrying forward: on the combined-footprint axis, the peak of both shared and green curves sits
almost exactly at the 2 MB cache-boundary line, and green's advantage/disadvantage pattern
(loses 2-4 MB, catches back up by ~8 MB) is now directly comparable to whatever Phase 2's own
combined-footprint plot shows at the same x-values, once that prompt is implemented too.

## Upstream I consumed
- `experiments/01_single_kernel_size/findings.json` (read-only: `measured_dram_peak_GBps`,
  `tier_steps.slc_region_max_read_footprint_bytes`).
- `experiments/03_green_context/results/phase3_results.csv`, `phase3_reuse_results.csv` (read-only).
- `worklog/2026-07-27-1015_HANDOFF.md` for context on why this unification matters and the
  expected reference values.

## Open questions / blockers
- None. Phase 1's and Phase 2's own `03_combined_footprint_plot.md`-equivalent prompts
  (`prompts/01_single_kernel_size/01_combined_footprint_plot.md`,
  `prompts/02_two_kernel_size/02_combined_footprint_plot.md`) exist but were not implemented in
  this session (out of scope -- this session only covered Phase 3's prompt file). Once Phase 2's
  version exists, worth eyeballing its combined-footprint plot next to this one to confirm the
  "Phase 3 shared reproduces Phase 2" claim visually, per this prompt's Verification section.

## Handoff → next session
- If picking up Phase 1/2's equivalent combined-footprint prompts, mirror this file's structure
  (same `combined_read_footprint_bytes` formula, same MB/log2 axis, same additive/new-file-only
  constraint) so all three phases' figures are visually and numerically comparable.

## Suggested commit message
```
feat(phase3): add combined-footprint plot (additive)

Re-plots Phase 3's existing results on the unified combined-read-footprint
x-axis (2*k0+2*k1 bytes, MB, log2) so it aligns with Phase 2 on the same
underlying data. New script + new PNGs only; no existing CSV/findings/plot.py touched.
```
