# Worklog — 2026-07-27 01:34 — phase1-combined-footprint-plot

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/01_single_kernel_size/
**State:** completed

## Summary
Implemented `prompts/01_single_kernel_size/01_combined_footprint_plot.md`: an additive
plot re-expressing Phase 1's x-axis as combined read footprint, so it lines up with
Phases 2-3's cache-boundary axis convention.

## What I did
- Added `experiments/01_single_kernel_size/scripts/plot_combined_footprint.py` (new file,
  does not touch `results/phase1_results.csv`, `findings.json`, or `scripts/plot.py`).
- `combined_read_footprint_bytes` reuses the existing `read_footprint_bytes` CSV column
  directly (Phase 1 is a single 2-input-buffer kernel, so they're identical by definition
  — no recomputation needed).
- Reference lines (cache boundary, DRAM peak) are read from `findings.json` at
  `tier_steps.slc_region_max_read_footprint_bytes` / `measured_dram_peak_GBps`, with a
  logged fallback to the prompt's stated values (2 MB / 177 GB/s) if either key is absent.
- Ran it against the real (already-measured) CSV + findings.json in this repo to verify
  end-to-end; output written to
  `experiments/01_single_kernel_size/results/plots/bw_vs_footprint_combined_footprint.png`.

## Files created / modified
- `experiments/01_single_kernel_size/scripts/plot_combined_footprint.py` — new, additive plot script.
- `experiments/01_single_kernel_size/results/plots/bw_vs_footprint_combined_footprint.png` — new plot output (from the existing CSV, not regenerated).

## Key decisions & rationale
- Used the *actual* findings.json values (measured_dram_peak_GBps=179.2, slc_region_max=2097152
  bytes) rather than the prompt's stated 177 GB/s / 2 MB, since findings.json was present —
  matches the prompt's own priority order ("Read these from findings.json if present;
  otherwise use the stated values").
- Filtered to `threads_per_block == 256` and took the per-(footprint, reuse_N) plateau (max
  achieved_GBps), matching the convention already used in `scripts/plot.py`'s
  `bw_vs_footprint.png`, for a visually/methodologically consistent companion plot.
- Refuses to overwrite `bw_vs_footprint_combined_footprint.png` if it already exists (guards
  the "never overwrite existing plots" additive-only constraint on re-runs too, not just
  against the pre-existing `bw_vs_footprint.png`).

## Results / findings produced
No new findings.json entries (additive plot only, per prompt). Visual result: BW peaks at
~2 MB combined footprint (cache-resident, up to ~380 GB/s at reuse N=32), drops sharply past
the cache boundary, and converges to the ~179 GB/s measured DRAM peak line for large
footprints — consistent with `worklog/2026-07-27-1015_HANDOFF.md` §2.2.

## Upstream I consumed
- `experiments/01_single_kernel_size/results/phase1_results.csv` (read-only)
- `experiments/01_single_kernel_size/findings.json` (read-only, for reference-line values)
- `worklog/2026-07-27-1015_HANDOFF.md` (context: measured cache boundary / DRAM peak)

## Open questions / blockers
None. This session did not touch Phases 2-4 or the Phase 4 block-saturation bug noted in
the handoff (§4) — out of scope for this prompt.

## Handoff → next session
- If the same combined-footprint treatment is wanted for Phase 2/3 (the handoff implies
  Phase 2 is already on this axis and Phase 3 is on per-kernel size), that's a separate
  per-phase prompt/script, not this one.
- Suggested commit message: `feat(phase1): add combined-footprint plot (additive, aligns x-axis with phases 2-3)`
