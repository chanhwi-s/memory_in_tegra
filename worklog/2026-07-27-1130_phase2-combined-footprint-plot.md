# Worklog — 2026-07-27 11:30 — phase2-combined-footprint-plot

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/02_two_kernel_size/
**State:** completed

## Summary
Implemented `prompts/02_two_kernel_size/02_combined_footprint_plot.md`: an additive plot that
re-expresses Phase 2's asymmetric sweep on the same combined-read-footprint x-axis the
symmetric sweep already used, so both modes (and the reuse overlay) share one cache-pressure
axis with Phase 1/3.

## What I did
- Added `experiments/02_two_kernel_size/scripts/plot_combined_footprint.py` (new file; does not
  touch `results/phase2_results.csv`, `results/phase2_reuse_results.csv`, `findings.json`, or
  `scripts/plot.py`).
- `combined_read_footprint_bytes` reuses the column already written by `phase2_bench.cu`
  (`2*k0_bytes + 2*k1_bytes`) rather than recomputing it, with a fallback derivation only if a
  CSV is ever missing the column.
- Reads both `phase2_results.csv` (reuse=1 baseline: aggregate/K0/K1 GB/s + scaling_efficiency)
  and, if present, `phase2_reuse_results.csv` (overlays one additional aggregate-GB/s line per
  `reuse_N` on the same combined-footprint x-axis).
- Reference lines (cache boundary, DRAM peak) read from
  `experiments/01_single_kernel_size/findings.json`
  (`tier_steps.slc_region_max_read_footprint_bytes`, `measured_dram_peak_GBps`), falling back to
  the prompt's stated values (2 MB / 177 GB/s) with a logged note if that file is absent.
- Guards against overwriting its own prior output on re-run (prints a NOTE and skips), mirroring
  the sibling `experiments/01_single_kernel_size/scripts/plot_combined_footprint.py`
  (`worklog/2026-07-27-0134_phase1-combined-footprint-plot.md`) for consistency.
- Ran it against the real, already-measured CSVs in this repo to verify end-to-end (including
  the overwrite guard on a second run); output:
  `experiments/02_two_kernel_size/results/plots/sym_vs_combined_footprint.png` and
  `.../asym_vs_combined_footprint.png`.

## Files created / modified
- `experiments/02_two_kernel_size/scripts/plot_combined_footprint.py` — new, additive plot script.
- `experiments/02_two_kernel_size/results/plots/sym_vs_combined_footprint.png` — new plot output.
- `experiments/02_two_kernel_size/results/plots/asym_vs_combined_footprint.png` — new plot output.

## Key decisions & rationale
- One figure per mode (symmetric, asymmetric) rather than one combined figure, since the
  existing `plot.py` already separates them this way and the reuse overlay (which only applies
  cleanly per-mode) reads more clearly split out.
- Plotted per-kernel GB/s and scaling_efficiency only at reuse_N=1 (the baseline sweep); the
  reuse CSV only adds aggregate-GB/s lines per N, per the prompt's "draw one aggregate line per
  reuse_N" wording — per-kernel/efficiency curves at higher N would clutter the plot and aren't
  asked for.
- Filenames end in `_combined_footprint` (`sym_vs_combined_footprint.png`,
  `asym_vs_combined_footprint.png`) and are new names entirely, so the original
  `sym_agg_vs_footprint.png` / `asym_vs_k1.png` / `reuse_bw_vs_footprint.png` are never at risk
  of being overwritten regardless of the explicit guard.

## Results / findings produced
No new findings.json entries (additive plot only, per prompt). Visually confirms the handoff's
finding #3 (`worklog/2026-07-27-1015_HANDOFF.md`): the reuse-boost peak (up to ~322 GB/s at
N=32) sits right at the ~2 MB combined-footprint cache boundary for the symmetric sweep, and
both aggregate and per-kernel curves converge toward the ~179 GB/s measured DRAM peak at large
combined footprint in both modes.

## Upstream I consumed
- `experiments/02_two_kernel_size/results/phase2_results.csv`,
  `results/phase2_reuse_results.csv` (read-only)
- `experiments/01_single_kernel_size/findings.json` (read-only, for reference-line values)
- `worklog/2026-07-27-1015_HANDOFF.md` (context) and
  `worklog/2026-07-27-0134_phase1-combined-footprint-plot.md` (sibling implementation, matched
  its overwrite-guard convention)

## Open questions / blockers
None. Did not touch Phase 3/4 or the Phase 4 block-saturation bug (handoff §4) — out of scope.

## Handoff → next session
- If Phase 3 also wants this treatment (handoff implies Phase 3 currently plots per-kernel size,
  not combined footprint), that needs its own prompt/script in `experiments/03_green_context/`.
- Suggested commit message: `feat(phase2): add combined-footprint plot (additive, unifies x-axis with phases 1/3)`
