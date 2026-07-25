# Worklog — 2026-07-25 13:00 — Phase 3 v3 patch (grid alignment + power-of-2 axes + reuse overlay)

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/
**State:** in-progress (v3 code implemented and unit-tested off-device; not yet re-run on the Jetson)

## Summary
Implemented `prompts/03_green_context_v3.md`, a targeted patch on top of the already
hardware-verified v2 run: (1) Phase 3's size grid is now imported directly from Phase 2's own
grid-generating functions instead of an independent 1.8x geometric grid, so all three phases'
x-axes line up; (2) size-axis plots use log base 2 with power-of-two tick labels; (3) a new,
separate, additive `reuse_N` overlay (1..32) on a small subset of sizes, to test whether green
context's predicted L1-inter-launch-reuse benefit shows up at N>1 even where it didn't at N=1.
No CUDA hardware in this session (macOS dev machine, no `nvcc`) — implemented and verified via
`--dry-run` + synthetic-CSV pipeline runs, matching the pattern established in v2's worklog.

**Important correction made mid-session:** discovered that between the v2 worklog and this
session, someone actually ran the v2 harness on real Jetson hardware and committed real
results (`git log`: commit `b7c401d`, "results: phase3, 4 v2 반영 결과 커밋"). My synthetic-CSV
testing procedure initially reused a *stale* scratchpad backup of `results/`/`findings.json`
taken before that real commit — restoring it would have silently overwritten real measured
data with v1 placeholder numbers. Caught this via `git status`/`git diff --stat` before the
restore completed, and switched to `git checkout HEAD -- <paths>` for all subsequent
backup/restore cycles (safe regardless of timing, since it always recovers the actually
committed state rather than a manually-taken snapshot).

## What I did
- Read `prompts/03_green_context_v3.md` in full, cross-referenced `experiments/02_two_kernel_size/scripts/gen_config.py`
  (confirmed `symmetric_sizes_bytes()` / `asymmetric_k1_sizes_bytes(k)` exist exactly as the
  prompt describes) and `experiments/04_zero_copy/src/phase4_bench.cu`'s
  `searchAndVerifyStable()` (the reuse-stability-check pattern to mirror).
- **`src/phase3_bench.cu`:**
  - Added a `reuseN` parameter to `measureSharedWallMs()` / `measureGreenWallMs()`: the timed
    (not warm-up) kernel launches are now wrapped in `for (int j=0;j<reuseN;++j)`, and the
    final byte-count computation multiplies by `reuseN`. `reuseN=1` (existing default)
    reproduces v2 exactly.
  - Added `--reuse-n <N>` (default 1), `--fixed-blocks0/1` (skip the in-context search
    entirely and measure directly at these counts), and `--reuse-overlay` (prints a separate,
    simpler CSV row with a `reuse_N` column instead of the standard v2 row; requires
    `--fixed-blocks0/1`, since the overlay never re-searches per `reuse_N`).
  - The in-context search itself (unchanged algorithm) now runs at whatever `reuseN` was
    requested, so a search invoked at `--reuse-n 4` genuinely searches under N=4 conditions.
- **`scripts/sweep.py` (Change 1):** replaced the v2 geometric-grid generator with
  `build_symmetric_sweep_sizes()` / `build_asymmetric_k1_sizes(k)`, which import
  `gen_config.py` from Phase 2's scripts directory and prepend a small-end extension
  (`[0.03125, 0.0625]` MiB / same fractions of `k`). `build_test_points()` now snaps each
  Phase 2 anchor onto its exact `(mode, k0_bytes, k1_bytes)` grid key in place
  (`is_anchor=True`, id renamed to `{mode}_anchor_{size}`) rather than adding a duplicate
  cell — and exits loudly (not silently) if an anchor doesn't land exactly, since that would
  mean the grid functions have drifted from Phase 2's.
- **`scripts/plot.py` (Change 2 + 3):** added `_fmt_bytes()` / `_set_log2_bytes_axis()` and
  applied them to `green_vs_shared.png` / `delta_vs_size.png` (not `partition_sweep.png`,
  whose x-axis is the categorical SM split). Added `plot_reuse_overlay()` ->
  `reuse_green_vs_shared.png`, reading the optional `results/phase3_reuse_results.csv`
  (skips cleanly with a stderr note if it doesn't exist yet) and Phase 1's
  `measured_dram_peak_GBps` for the reference line.
- **`scripts/sweep_reuse.py` (new, Change 3):** dynamically picks the subset sizes from the
  just-completed reuse=1 CSV (smallest symmetric size, both `is_anchor` symmetric sizes, size
  closest to 4 MiB), reads back each size's shared blocks and best-green split+blocks,
  verifies block-count stability by re-searching once at `reuse_N=4` (element-wise max +
  stderr note on disagreement, mirroring Phase 4's `searchAndVerifyStable`), then measures
  the full `reuse_N ∈ {1,2,4,8,16,32}` sweep at the final fixed blocks via
  `--fixed-blocks0/1 --reuse-overlay` (re-measuring N=1 and the check-N too, at the final
  blocks, for full self-consistency across the curve). Writes the separate
  `results/phase3_reuse_results.csv`; never touches `results/phase3_results.csv` or
  `findings.json`. `--dry-run` skips the stability-check search entirely (labels the shown
  blocks `UNVERIFIED`) so it makes zero device/binary calls, matching `sweep.py`'s contract.
- **`scripts/derive_findings.py`:** added `grid_alignment_note()` and
  `reuse_overlay_summary()`, both FINDINGS.md-only prose (verified `findings.json`'s
  `results` dict keys are byte-for-byte unchanged from v2 via a synthetic-data run — see
  Verification below). The reuse-overlay summary computes, per subset size, the green-vs-
  shared delta at `reuse_N=1` vs the max `reuse_N` present and classifies it as improving /
  crossing-into-helping / flat.
- **`scripts/run.sh`:** comment-only update describing the v3 grid + pointing at
  `sweep_reuse.py` as a manual, optional follow-up step; no functional change (still runs the
  reuse=1 sweep only).
- **`README.md`:** rewritten for v3 — updated Status section to correctly state that v2's
  committed `results/`/`findings.json` are REAL on-device measurements (not v1 placeholders,
  which was the correct-at-the-time statement in the v2 README before the real run landed),
  and that v3's code is implemented but not yet re-run.
- **Verification performed (off-device):**
  - `python3 -m py_compile` on all four Python scripts; a brace/paren balance smoke test on
    `phase3_bench.cu` (still not a real compile — no `nvcc` here).
  - `scripts/sweep.py --dry-run`: 149 cells, 18 symmetric + 11 asymmetric sizes, confirmed
    against `gen_config.py`'s actual lists; confirmed the 3 anchors (786432, 917504, 2097152)
    land exactly and appear exactly once each (`sym_anchor_786432`, `sym_anchor_917504`,
    `asym_anchor_2097152`), not duplicated like v2.
  - Generated a synthetic `phase3_results.csv` matching the v3 grid + schema (throwaway
    script, not committed) and ran `scripts/plot.py` end to end: `green_vs_shared.png` and
    `delta_vs_size.png` render with correct power-of-2 ticks (64K, 256K, 1M, 4M, 16M) —
    visually confirmed via image inspection, not just "no exception raised".
  - Generated a synthetic `phase3_reuse_results.csv` (4 subset sizes x 2 configs x 6
    `reuse_N`) and confirmed `reuse_green_vs_shared.png` renders correctly (4 panels, log2
    `reuse_N` axis, DRAM-peak reference line pulled from the real Phase 1 `findings.json`:
    177.4 GB/s).
  - `scripts/sweep_reuse.py --dry-run` against the synthetic main CSV: correctly detected
    subset sizes `[32768, 786432, 917504, 4194304]` (exactly matching the prompt's literal
    examples), planned 48 cells, made no device calls.
  - Ran `scripts/derive_findings.py` against the synthetic data: confirmed the new "Grid
    alignment with Phase 2" and "Reuse overlay" sections render correctly in `FINDINGS.md`,
    and confirmed via direct JSON inspection that `findings.json`'s `results` dict has exactly
    the same top-level keys as the real committed v2 file (no new keys leaked in).
  - **Restored the real, on-device-measured v1/v2 `results/`, `findings.json`, `FINDINGS.md`
    via `git checkout HEAD --` after every synthetic-data test** (see the stale-backup
    near-miss above) -- confirmed via `git status --short` that only source/script files show
    as modified afterward, never the committed results.

## Files created / modified
- `experiments/03_green_context/src/phase3_bench.cu` -- reuse_N plumbing, `--fixed-blocks0/1`,
  `--reuse-overlay`.
- `experiments/03_green_context/scripts/sweep.py` -- Phase-2-grid import, exact-match anchor
  snapping (Change 1).
- `experiments/03_green_context/scripts/plot.py` -- power-of-2 axes (Change 2),
  `plot_reuse_overlay()` (Change 3).
- `experiments/03_green_context/scripts/sweep_reuse.py` -- new, reuse overlay driver (Change 3).
- `experiments/03_green_context/scripts/derive_findings.py` -- grid-alignment + reuse-overlay
  FINDINGS.md sections (schema-preserving).
- `experiments/03_green_context/scripts/run.sh` -- comment-only.
- `experiments/03_green_context/README.md` -- rewritten for v3.
- `experiments/03_green_context/results/`, `findings.json`, `FINDINGS.md` -- **untouched**
  (still the real v2 on-device measurements; see Status below).

## Key decisions & rationale
- **Anchors are snapped onto exact grid points and exit loudly on mismatch**, rather than
  duplicated (v2's behavior) or snapped-with-tolerance -- because v3's whole point is exact
  grid alignment; a near-miss anchor would silently mean the grid functions have drifted from
  Phase 2's, which should fail the run, not be smoothed over.
- **The reuse-overlay stability check and full reuse_N sweep are driven from Python
  (`sweep_reuse.py`), not from a single all-in-one C++ invocation** like Phase 2/4's reuse
  overlays. `phase3_bench`'s existing architecture (stated in its own file header from v1) is
  "measures ONE cell per invocation"; I kept that contract rather than bolting on a
  Phase4-style multi-row-per-invocation mode, and mirrored Phase 4's *algorithm*
  (checkN=4, element-wise max, stderr NOTE) at the Python layer instead. Functionally
  equivalent; architecturally consistent with this specific binary's existing design.
- **`--dry-run` in `sweep_reuse.py` never touches the binary/device**, even though the real
  run needs a stability-check search -- matches `sweep.py`'s established dry-run contract.
  Initially got this wrong (my first draft's `build_plan()` unconditionally called the
  stability check), caught it before testing by re-reading my own docstring's claim against
  the actual code path.
- **`findings.json`'s schema is left byte-for-byte identical to v2** (verified, not just
  assumed) -- the v3 prompt requires this explicitly ("same schema as v2 ... from the reuse=1
  sweep only"); both new pieces of information (grid alignment, reuse overlay) are FINDINGS.md
  prose only.
- **Did not overwrite the real v2 results/findings/FINDINGS.md.** Same reasoning as the v2
  worklog: no CUDA device in this session, so I cannot produce real v3 measurements, and
  00_conventions.md #2 forbids fabricating replacement numbers. Unlike the v2 session, this
  time real data already exists and had to be actively protected from a stale-backup mistake
  mid-session (see Summary).

## Results / findings produced
- None yet from v3 (no real measurements this session). The REAL v2 results already in
  `FINDINGS.md` (unmodified by this session) show: sanity gate passed (148.24 ≥ 143.599 GB/s
  @ 917504 B/kernel); green context beat shared by >2% at exactly one point across the whole
  v2 sweep (`asym_65536`, +8.5%), neutral-to-negative everywhere else, including most of the
  small/L1-labeled region -- which is part of why the v3 patch's reuse overlay exists (to
  check whether that changes at reuse_N>1, where L1 inter-launch reuse actually exists).

## Upstream I consumed
- `experiments/02_two_kernel_size/scripts/gen_config.py` (existing, unmodified) -- imported
  directly for the size-grid functions (v3 Change 1's core requirement).
- `experiments/02_two_kernel_size/findings.json` / its `source_csv` -- anchor labels,
  `asymmetric_k_used_bytes`, and the 143.599 GB/s sanity-gate reference (unchanged from v2).
- `experiments/01_single_kernel_size/findings.json` -- block-search seeds, tier_steps, and
  (new for the reuse-overlay plot) `measured_dram_peak_GBps`.
- `experiments/04_zero_copy/src/phase4_bench.cu`'s `searchAndVerifyStable()` -- the reuse-
  stability-check algorithm mirrored (not copied verbatim) into `sweep_reuse.py`.
- `worklog/2026-07-25-1200_phase2-reuse-overlay.md` (read partially, for cross-checking) --
  confirms a sibling session implemented Phase 2's own reuse overlay with the same checkN=4 /
  element-wise-max stability pattern and log2-axis-with-FuncFormatter plot style, so this
  session's choices are consistent with the project's established convention for reuse
  overlays, not a one-off.
- `worklog/2026-07-24-2130_phase3-v2-resweep.md` -- prior session's implementation notes
  (this session's starting point).

## Open questions / blockers
- **No CUDA/Jetson hardware in this session.** `phase3_bench.cu`'s new reuse/fixed-blocks code
  is not compile-checked (only a brace/paren balance smoke test). The actual behavior of
  `--reuse-overlay`/`--fixed-blocks0/1` and the real reuse_N results are unverified until run
  on-device.
- The grid-alignment sanity check ("each Phase 2 anchor lands on an exact grid point") was
  only exercised via `--dry-run` against the *current* `gen_config.py`; if Phase 2's grid
  functions change in the future without a corresponding Phase 3 update, `sweep.py` will now
  fail loudly rather than silently drifting -- confirmed this is the intended behavior per the
  prompt, not a bug to soften.

## Handoff → next session
1. On the Jetson: `cd experiments/03_green_context && scripts/build.sh` -- fix any compile
   errors in the new reuse/fixed-blocks code first (untested off-device).
2. `python3 scripts/sweep.py --dry-run` to re-confirm the 149-cell plan on real upstream
   findings.json (should match this session's off-device dry-run exactly, since nothing about
   Phase 1/2's findings.json changed).
3. `scripts/run.sh` for the reuse=1 main sweep (v3 grid). Check
   `findings.json`'s `results.block_saturation_sanity_gate.gate_passed` first, same as v2.
4. `python3 scripts/sweep_reuse.py` (optional but recommended, given this is the whole point
   of Change 3) then `python3 scripts/plot.py` again to add `reuse_green_vs_shared.png`.
5. Read the regenerated `FINDINGS.md`'s new "Grid alignment with Phase 2" (should just confirm
   supersession) and "Reuse overlay" sections -- the latter is the interesting new result:
   does green's delta actually improve/cross into positive at higher `reuse_N` for the
   small/L1 sizes, where v2 (reuse=1) found it did NOT help?
6. Feed `results.configs_for_phase4` / `results.best_partition_ratios` (per mode x regime,
   unchanged schema) forward to Phase 4 as before; the reuse overlay's finding is
   informational only and should NOT be used to override the reuse=1-derived Phase 4 configs
   (per the prompt's explicit "does not change findings.json" instruction).
- Suggested one-line commit message once this lands:
  `Patch Phase 3 to v3: align size grid to Phase 2, log2 axes, reuse_N overlay`
