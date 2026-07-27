# Worklog — 2026-07-27 12:30 — phase4-block-saturation-fix

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/04_zero_copy/
**State:** in-progress (fix applied and reviewed; NOT rebuilt/rerun — no CUDA toolkit / Jetson in this dev environment)

## Summary
Implemented `prompts/04_zero_copy/04_block_saturation_fix.md`: widened the in-context
block-count saturation search in `experiments/04_zero_copy/src/phase4_bench.cu` (root cause of
the "BROKEN, do not trust zero-copy deltas" state in
`worklog/2026-07-27-1015_HANDOFF.md` §4) and tightened the plateau-detection criterion. Could
not rebuild or rerun on real hardware from this machine — that step is still required before the
sanity gate / findings can be trusted.

## What I did
- `experiments/04_zero_copy/src/phase4_bench.cu`:
  - `clampBlocks` cap `1024 -> 8192`.
  - `kSearchMultipliers` `{1,2,4,8} -> {1,2,4,8,16}`.
  - `kSearchTrials` (inside `searchBlockSaturation`) `3 -> 10`.
  - Refactored the two 1-D search passes into a shared `searchOnePass()` helper and changed
    the plateau criterion from "best candidate wasn't the last index tried" to "the *widest*
    candidate tried is within 2% of this pass's best throughput" (`kPlateauRelTol = 0.02`) --
    matching both the fix prompt's literal wording ("throughput within ~2% of the next larger
    count") and the existing 2%-of-max saturation convention already used in Phase 1
    (`experiments/01_single_kernel_size/src/phase1_bench.cu`). The old index-based check could
    mark a cell "plateaued" from a noisy single winning candidate without confirming the curve
    had actually flattened by the top of the search range; the new check requires the edge of
    the range to be genuinely flat, not just non-maximal.
  - `plateau_reached` is still only ever set from real measurement (never assumed true because
    the search happened to hit the cap) -- unchanged behavior, now backed by the stricter check.
- Checked `experiments/04_zero_copy/scripts/run.sh`: it **already** calls `plot.py` and
  `derive_findings.py` at the end (lines 81-85) and its header comment already documents this as
  "the only script you need to run by hand" -- the prompt's "ensure run.sh calls these
  automatically" item was already done by an earlier session (`worklog/2026-07-24-2130_phase4-v2-resweep.md`,
  presumably). No change made here.
- Checked `scripts/derive_findings.py`'s `run_sanity_gate()`: it already dynamically compares
  the re-swept cached aggregate against `results/phase4_results_v1_baseline.csv` per anchor row
  and reports `pass`/`FAIL`/"SANITY GATE FAILED" purely from the data -- there is no hardcoded
  "do not trust" string to manually remove. Once a real re-run with the widened search produces
  a passing gate, `FINDINGS.md`'s sanity-gate section will say so automatically. No change
  needed here either.
- Manually reviewed the edited `.cu` for brace/paren balance and call-site argument order
  (`searchOnePass` call sites vs. its signature) since **no CUDA toolkit exists in this
  environment to actually compile it** -- same constraint noted in every prior phase's worklog
  (`01_single_kernel_size`, `02_two_kernel_size` entries). This is a careful review, not a
  compile-verified change.

## Files created / modified
- `experiments/04_zero_copy/src/phase4_bench.cu` — block-saturation search widened + plateau
  check tightened (see above).

## Key decisions & rationale
- Chose the 2%-of-max plateau criterion over the simpler "last index wasn't the argmax" check
  the code had before, because the prompt names an explicit numeric tolerance ("~2% of the next
  larger count") and the repo already has a precedent for exactly this convention in Phase 1 --
  using the same rule keeps "saturated"/"plateaued" meaning consistent across phases.
- Did not add any automatic further-widening loop when a cell still fails to plateau at the new
  8192 cap. The prompt frames "if a cell still hits the cap, widen further" as an operational
  next step for whoever reruns this on hardware, not a runtime auto-retry -- the code already
  refuses to mark such a cell as saturated (`plateau_reached=0` + a stderr `WARNING`), which is
  the actionable signal; unbounded auto-widening at runtime risked impractically large block
  counts / long run times without a human noticing.
- Left `run.sh` and `derive_findings.py` untouched after confirming both already satisfy their
  respective parts of the prompt -- avoided making unnecessary edits to files that were already
  correct.

## Results / findings produced
None yet. This session did not and could not run the benchmark -- `findings.json` /
`FINDINGS.md` / `results/phase4_results.csv` still reflect the pre-fix (untrusted) v2 sweep.

## Upstream I consumed
- `prompts/04_zero_copy/04_block_saturation_fix.md` (the prompt implemented this session)
- `worklog/2026-07-27-1015_HANDOFF.md` §4 (root-cause description this fix addresses)
- Read (did not modify) `experiments/04_zero_copy/scripts/run.sh` and
  `scripts/derive_findings.py` to confirm the prompt's other two asks were already satisfied.

## Open questions / blockers
- **Blocked on real hardware.** Someone needs to run, on the actual Jetson AGX Orin (clocks
  locked, MAXN + jetson_clocks):
  ```bash
  bash experiments/04_zero_copy/scripts/build.sh
  bash experiments/04_zero_copy/scripts/run.sh
  ```
  and confirm: (a) `results/chosen_blocks.csv` shows `plateau_reached=1` for (nearly) all cells,
  (b) `findings.json.results.saturation_sanity_gate.note` no longer says "SANITY GATE FAILED".
  Only then is the zero-copy delta / crossover-N / bound-conclusion trustworthy.
- If any cell still fails to plateau at the new 8192 cap / 16x multiplier, the fix prompt says to
  widen further -- that would mean bumping `kSearchMultipliers`/`clampBlocks` again and rerunning,
  not something resolved by this pass.

## Handoff → next session
- Run the two commands above on the Jetson; if the gate passes, re-derive findings are already
  produced by `run.sh` itself (no extra step needed) and the "do not trust the zero-copy delta"
  framing in `FINDINGS.md` should read as passing.
- If the gate still fails after this fix, capture the new `chosen_blocks.csv` plateau-reached
  rate and which specific cells are still cap-pinned before deciding whether to widen further or
  look for a different root cause (e.g. reuse-loop overhead, kernel launch queue depth limits).
- Suggested commit message: `fix(phase4): widen block-saturation search (cap 8192, +16x multiplier, 10 trials) and tighten plateau check to 2%-of-max`
