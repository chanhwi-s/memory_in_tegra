# Worklog — 2026-07-27 13:45 — unified-size-grid

**Session/agent:** Claude Code
**Phase / directory worked on:** cross-phase (`shared/`, `experiments/01_single_kernel_size/`,
`experiments/02_two_kernel_size/`, `experiments/03_green_context/`) per the explicit exception
in `prompts/05_unified_size_grid_and_plots.md`
**State:** completed (code + off-device verification); **no hardware re-run performed** — this
dev environment has no CUDA toolchain / Jetson device (same constraint noted in every prior
phase worklog)

## Summary
Implemented `prompts/05_unified_size_grid_and_plots.md` in full: a new `shared/size_grid.py`
single source of truth for the symmetric size grid (24 points, densified 1-4MB around the
*measured* 2MB cache boundary) and Phase 1's size list (32 points), wired into Phases 1-3;
fixed the reuse-overlay plot label, removed the misleading `green_vs_shared.png`, added a
full-grid reuse_N=32 measurement + its own combined-footprint figure, and rewrote the nsys
overlap-cell selection to find the actual cache-bound peak instead of the grid's largest size.
All Python-level verification (grid asserts, dry-runs, asymmetric-grid byte-for-byte diffs,
plot regeneration against existing CSVs) passed off-device; the actual hardware re-measurement
(01→02→03 in order) is **not yet done** and is the next session's job.

## What I did
- **Change 0 — `shared/size_grid.py` (new):** `combined_footprint_grid_bytes()` (24 F points:
  coarse <1MB, 256KB-dense 1-4MB, coarse >4MB), `symmetric_per_kernel_sizes_bytes()` (S=F/4, 24
  values), `phase1_sizes_bytes()` (union of F/2 and F/4, 32 values). Self-check `__main__` block
  asserts F%4==0, F%131072==0, no zero/unaligned derived sizes.
- **Change 1 — Phase 1:** added `--sizes <csv>` to `phase1_bench.cu` (hardcoded 16-value list
  kept as a stderr-warned fallback when `--sizes` is absent); new `scripts/gen_sizes.py` prints
  `phase1_sizes_bytes()`; `scripts/run.sh` now passes it via `--sizes`.
- **Change 2 — Phase 2/3 symmetric grid:** `gen_config.py::symmetric_sizes_bytes()` is now a
  thin wrapper over the shared grid (docstring rewritten — old "densified near nominal
  4MB/8MB" claim was actively wrong); `sweep.py`'s `SMALL_END_SYMMETRIC_MIB` extension deleted
  (the shared grid's own 32KB floor already covers it) and a real `assert` added in
  `build_symmetric_sweep_sizes()` that Phase 2's and Phase 3's symmetric grids are identical.
  Asymmetric grids in both phases are byte-for-byte untouched (verified, see below).
- **Change 3 — reuse-overlay label fix:** `plot.py`'s `plot_reuse_overlay()` now labels/titles
  each panel with combined read footprint (`2*k0_bytes+2*k1_bytes`, reusing the CSV column if
  present, else recomputing — same fallback pattern as `plot_combined_footprint.py`), not
  `k0_bytes` alone (which read as the working set but was 4x off).
- **Change 4 — dropped `green_vs_shared.png`:** removed `plot_green_vs_shared()` and its call
  from `plot.py`; deleted the stale PNG. Updated every stale "plot.py is additive-only /
  off-limits" comment I touched (`plot.py`, `run_overlap_nsys.py`, `verify_overlap_nsys.sh`) to
  note the explicit lift for this prompt's Changes 3/4.
- **Change 5 — reuse_N=32 full-grid overlay:** new `scripts/sweep_reuse32.py` (measures every
  symmetric size x {shared, that size's N=1-optimal green split — read back via
  `sweep_reuse.py::find_configs_for_size()`, NOT re-searched} at a single fixed reuse_N=32,
  writes the separate `results/phase3_reuse32_results.csv`). `plot_combined_footprint.py`
  rewritten to produce two figures: `green_vs_shared_combined_footprint_n1.png` (kept, old
  reuse=1 logic) and the new canonical `..._n32.png` (single panel, symmetric only, explicitly
  labeled "conditional" since the green split isn't re-optimized at N=32). Wired both the
  reuse32 sweep and the combined-footprint plot into `run.sh` (which, notably, was **not**
  previously calling `plot_combined_footprint.py` at all — that's now fixed too, since the
  `run.sh` single-entry-point rule requires it).
- **Change 6 — nsys cell re-selection:** `run_overlap_nsys.py`'s
  `select_peak_bandwidth_test_points()` rewritten: `shared`-only rows, sorted by swept size
  ascending, first local maximum (+ its two grid neighbours, clamped at grid ends with a
  WARNING) instead of the old global-argmax-over-all-configs (which degenerated to "largest
  size in the grid" for the symmetric sweep). Falls back to global argmax with a loud WARNING
  if no local max exists. Added a `failure_reason` CSV column (empty / `timeout` /
  `parse_error: <msg>`, commas/newlines scrubbed since the CSV writer is a naive join) so
  `overlap_nsys_table.md` no longer collapses two different failure modes into one "N/A".
  `plot_overlap_nsys.py` rewritten from a 2-bar grouped bar chart into a real line plot (one
  panel per mode, shared vs green, x=combined footprint log2) since there are now 3 points per
  mode instead of 1 — this is what the prompt meant by "finally makes it a real curve". Had to
  add explicit x-limit padding (log-scale autoscale blows up on a single-x-value panel, which
  the old committed 4-row CSV still is) and split shared/green per-point annotations to
  opposite vertical directions (they collided when both configs land at a similar overlap %).
- **Incidental fix (not in the prompt, found while verifying):** Phase 1's
  `derive_findings.py` opened `findings.json`/`FINDINGS.md` without `encoding="utf-8"` — crashed
  on this Windows/cp949 environment the first time it was actually run, on the em-dash in its
  own header. Phase 2/3's `derive_findings.py` already specify the encoding; brought Phase 1 in
  line (2-line fix).
- Added `shared/size_grid.py` to the `consumed` list and echoed the grid into the `README.md` /
  `FINDINGS.md` prose of all three phases per `00_conventions.md` §2.2.

## Files created / modified
- `shared/size_grid.py` — new, single source of truth for the symmetric + Phase 1 grids.
- `experiments/01_single_kernel_size/src/phase1_bench.cu` — `--sizes` CLI arg + fallback.
- `experiments/01_single_kernel_size/scripts/gen_sizes.py` — new.
- `experiments/01_single_kernel_size/scripts/run.sh` — passes `--sizes` from `gen_sizes.py`.
- `experiments/01_single_kernel_size/scripts/derive_findings.py` — `consumed` +
  "Size grid" FINDINGS.md section + utf-8 encoding fix.
- `experiments/01_single_kernel_size/README.md` — echoes the 32-size grid, gen_sizes.py.
- `experiments/02_two_kernel_size/scripts/gen_config.py` — `symmetric_sizes_bytes()` now wraps
  `shared/size_grid.py`; asymmetric untouched.
- `experiments/02_two_kernel_size/scripts/derive_findings.py` — `consumed` + grid note.
- `experiments/02_two_kernel_size/README.md` — echoes the 24-size grid + status note.
- `experiments/03_green_context/scripts/sweep.py` — dropped symmetric small-end extension,
  added the phase2==phase3 grid assert.
- `experiments/03_green_context/scripts/sweep_reuse32.py` — new (Change 5).
- `experiments/03_green_context/scripts/plot.py` — Change 3 label fix, Change 4 removal.
- `experiments/03_green_context/scripts/plot_combined_footprint.py` — n1/n32 figures (Change 5).
- `experiments/03_green_context/scripts/run_overlap_nsys.py` — Change 6 cell selection +
  `failure_reason`.
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` — bar chart -> line plot,
  `failure_reason` surfaced in the table.
- `experiments/03_green_context/scripts/derive_findings.py` — `consumed`, grid-alignment note
  rewrite, new `reuse32_overlay_summary()` + FINDINGS.md section.
- `experiments/03_green_context/scripts/run.sh` — wires in `sweep_reuse32.py` +
  `plot_combined_footprint.py` (previously missing from `run.sh` entirely) + `--skip-reuse32`.
- `experiments/03_green_context/scripts/verify_overlap_nsys.sh` — stale comment fix.
- `experiments/03_green_context/README.md` — extensive updates (grid, Change 5/6 scripts,
  flags, status).
- `experiments/03_green_context/results/plots/green_vs_shared.png` — deleted (Change 4).
- `experiments/03_green_context/results/plots/green_vs_shared_combined_footprint.png` — deleted,
  replaced by `..._n1.png` (regenerated from existing CSV) and `..._n32.png` (not yet generated
  — needs `phase3_reuse32_results.csv` from a real run).
- Regenerated (from existing, pre-unification CSVs, to confirm no crash — NOT new measurements):
  `experiments/01_single_kernel_size/{findings.json,FINDINGS.md,results/plots/*.png}`,
  `experiments/02_two_kernel_size/{findings.json,FINDINGS.md,results/phase2_config.csv,results/plots/*.png}`,
  `experiments/03_green_context/{findings.json,FINDINGS.md,results/overlap_nsys_table.md,results/plots/*.png}`.

## Key decisions & rationale
- **`shared/size_grid.py` is read-only, not append-only** (unlike `shared/env.md`) — it's an
  input every phase consumes, not a log. Put the grid rationale and the F/2-vs-F/4 explanation
  in the module docstring so it's the one place to check when a downstream phase's grid looks
  wrong.
- **Kept Phase 1's hardcoded 16-size list as a fallback**, not deleted — prompt explicitly asked
  for the binary to remain runnable standalone. Warns loudly to stderr when used.
- **`sweep_reuse32.py` as a sibling script, not an extension of `sweep_reuse.py`** — the two
  scripts have genuinely different shapes (fixed single N over the WHOLE grid vs multiple N
  over a ~4-5 size SUBSET); forcing one function to do both would need a branchy API. Reused
  `find_configs_for_size()` / `verify_stable_and_fix_blocks()` from `sweep_reuse.py` directly
  (imported, not copy-pasted) so the "N=1-optimal split" selection can never drift between the
  two overlays.
- **`run.sh` was missing `plot_combined_footprint.py` entirely before this session** — an
  existing gap (Change 5's canonical figure would never have been produced by `run.sh` alone).
  Fixed as part of this change since Change 5 explicitly requires that figure to exist; this
  aligns with the standing `run.sh`-is-the-single-entry-point rule.
- **Cell selection in `run_overlap_nsys.py` uses `shared` rows only** — a green row was never
  supposed to decide which size gets profiled; letting it do so (the old bug) meant a
  particularly good/bad green split could silently shift the selection away from the actual
  bandwidth-curve peak.
- **`plot_overlap_nsys.py`'s bar-chart-to-line-plot rewrite needed two defensive fixes not in
  the prompt:** explicit x-limit padding (matplotlib's log-scale autoscale raises
  `ValueError` on a single unique x value, which the currently-committed 4-row
  `overlap_nsys.csv` still has), and opposite-direction per-config annotation offsets (shared
  above its marker, green below) since same-mode shared/green overlap ratios are often close
  and the annotations otherwise print on top of each other. Verified both against a synthetic
  12-row CSV before treating Change 6 as done.
- **Did not touch `experiments/04_zero_copy/`** — out of scope per the prompt; its asymmetric
  test points derive from Phase 2's untouched asymmetric grid, so it is not invalidated by this
  change (same note the prompt asked to be recorded).

## Results / findings produced
No new *measurements* — everything above is code + off-device verification. Concretely:
- `python3 -c "...size_grid..."` → `combined_footprint_grid_bytes()` len 24,
  `phase1_sizes_bytes()` len 32; all F%4==0 and F%131072==0; no zero/unaligned derived size.
- Phase2/Phase3 symmetric grids confirmed element-wise identical (`==` on the two lists).
- `sweep.py --dry-run` → 89 cells (24 symmetric, 11 asymmetric, 8 at Phase 2 anchors).
- Asymmetric grids diffed against the **currently committed** `results/phase2_results.csv` /
  `results/phase3_results.csv` size columns: byte-for-byte identical in both phases (confirms
  Change 2 did not touch the asymmetric axis).
- `run_overlap_nsys.py --dry-run` → 12 cells, 3 test points/mode. Against the currently
  committed (old-grid) `phase3_results.csv`, the new selection lands on exactly the prompt's
  stated sanity check: symmetric peak = `sym_524288` (0.5MB/kernel) at 182.044 GB/s / 2MB
  combined footprint; asymmetric peak = `asym_131072` at 212.882 GB/s — both match the prompt's
  "182.0 GB/s" / "212.9 GB/s" almost exactly, and both sit in the middle of their 3-point
  triple as expected.
- All phase `plot.py` / `plot_combined_footprint.py` / `plot_overlap_nsys.py` /
  `derive_findings.py` scripts re-run successfully against the existing (pre-unification)
  committed CSVs with no crash; `green_vs_shared.png` confirmed absent afterward.
- `results/phase3_reuse32_results.csv` does **not** exist yet (needs the Jetson) — so
  `green_vs_shared_combined_footprint_n32.png` in the repo right now was NOT regenerated this
  session (the n1 version was).
- **Tier steps: not re-measured, so nothing to report moving or not moving yet.** Phase 1's
  committed `findings.json` still reflects the OLD 16-size grid's tier boundaries. The whole
  point of Change 0 densifying 1-4MB is that Phase 1's re-run *may* move
  `l2_resident_max_read_footprint_bytes` / `slc_region_max_read_footprint_bytes` — that
  observation can only be made after the Jetson re-run in the next session, per the prompt's
  "Findings handoff" note (a move would be legitimate, not an error, and should be flagged for
  `OVERVIEW.md` §0's nominal-vs-measured tier numbers, without editing that file directly).

## Upstream I consumed
- `prompts/05_unified_size_grid_and_plots.md` (this session's prompt), `OVERVIEW.md`,
  `prompts/00_conventions.md`.
- `worklog/2026-07-27-1015_HANDOFF.md` and `worklog/2026-07-27-1230_phase4-block-saturation-fix.md`
  (most recent two entries) — confirmed Phase 4 is separately known-broken/out-of-scope, and
  that this dev environment has no CUDA toolchain (same constraint applies here).
- Read (did not modify) each phase's currently-committed `findings.json` / `results/*.csv` to
  run the byte-for-byte asymmetric-grid diffs and the nsys peak-selection sanity check above.

## Open questions / blockers
- **Blocked on real hardware**, same as every prior session. Someone needs to, on the Jetson
  (clocks locked, MAXN + jetson_clocks), run in order:
  ```bash
  bash experiments/01_single_kernel_size/scripts/run.sh
  bash experiments/02_two_kernel_size/scripts/run.sh
  bash experiments/03_green_context/scripts/run.sh
  ```
  and confirm: (a) Phase 1's tier steps — moved or not, record either way in its `FINDINGS.md`;
  (b) `results/phase2_results.csv` / `phase3_results.csv` now have 24 symmetric rows (not
  16/18); (c) `phase3_reuse32_results.csv` gets created and
  `green_vs_shared_combined_footprint_n32.png` looks sane (a real curve, green's N=1-optimal
  split conditional framing visible on the title); (d) the nsys step produces 12 rows with a
  populated `failure_reason` column where applicable.
- The `.cu` changes (`phase1_bench.cu`'s `--sizes` parsing; nothing changed in
  `phase2_bench.cu`/`phase3_bench.cu` this session) are reviewed but **not compile-checked** —
  same standing constraint as every prior phase.
- Phase 4 is untouched and still separately broken (see the two prior worklog entries) — not
  addressed here, as instructed.

## Handoff → next session
- Run the three `run.sh` commands above, in order, on the Jetson.
- After Phase 1's re-run, check whether `tier_steps` moved vs the currently-committed values
  and record the outcome explicitly in `experiments/01_single_kernel_size/FINDINGS.md` (the
  code already prints a reminder to do this in the "Size grid" section derive_findings.py
  writes).
- After Phase 3's re-run, sanity-check `green_vs_shared_combined_footprint_n32.png` by eye
  (should show green winning only at the smallest size or two, consistent with the 4-point
  overlay's existing +33.5%/-26.0% data points) and confirm the nsys triple still centers on a
  genuine local max (not a fallback-to-global-argmax WARNING).
- Suggested commit message:
  `feat: unify Phase 1-3 size grid on measured cache boundary; fix Phase 3 plots + nsys cell selection`
