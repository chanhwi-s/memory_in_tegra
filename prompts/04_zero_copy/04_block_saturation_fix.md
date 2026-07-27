# Work Prompt — Phase 4: fix block saturation, then re-run (BROKEN → trustworthy)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md` (§4 documents this bug). This modifies Phase 4's own directory only.

## Problem
Phase 4's zero-copy deltas are untrusted because the large zero-copy kernel is **under-saturated**:
the in-context block-count search in `experiments/04_zero_copy/src/phase4_bench.cu` is too narrow, so
**17 of 22 cells never reached the throughput plateau** (`results/chosen_blocks.csv`,
`plateau_reached=0`) and the chosen `blocks_k1` is pinned at the search cap (1024). Reported throughput
is therefore a launch-config artifact, not the true memory-path difference — the sanity gate fails and
the headline zc benefit is unstable run-to-run.

## What "block saturation" means (for context)
The grid-stride kernel decouples block count from data size. Too few blocks → SMs/warps underused →
artificially low, noisy throughput. The harness must sweep block counts until throughput **plateaus**
and report that plateau. A streaming, DRAM-bound zero-copy kernel needs far more blocks to plateau
than the current search allows.

## Fix (in `experiments/04_zero_copy/src/phase4_bench.cu`)
- `clampBlocks` cap **1024 → 8192**
- `kSearchMultipliers = {1,2,4,8}` → **add 16** (`{1,2,4,8,16}`)
- `kSearchTrials = 3 → 10`
- The chosen block count must be a **true plateau** (throughput within ~2% of the next larger count),
  **not** the search cap. If a cell still hits the cap, widen further and warn — do not accept a
  cap-pinned result as saturated.

## Then re-run and validate
1. Rebuild and rerun Phase 4 (`bash experiments/04_zero_copy/scripts/run.sh`) with clocks locked
   (MAXN + jetson_clocks).
2. Require: **`plateau_reached=1` for (nearly) all cells** in `results/chosen_blocks.csv`, and the
   **sanity gate passes** (re-swept cached aggregate no longer falls below the v1 baseline).
3. Re-derive `findings.json` / `FINDINGS.md`; the "do not trust the zero-copy delta" caveat must be
   removed only once the gate passes. Report the crossover reuse N and the memory-vs-compute-bound
   conclusion with the now-trustworthy magnitudes.

## Also
- Ensure `scripts/run.sh` calls `derive_findings.py` and `plot.py` at the end automatically (this was
  missing earlier and had to be run by hand).
- End with a `worklog/` entry and a suggested one-line commit message.
