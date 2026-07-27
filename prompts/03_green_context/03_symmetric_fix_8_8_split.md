# Work Prompt — Phase 3: fix symmetric green split to 8:8, drop symmetric partition sweep

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`. Modifies Phase 3's own directory only.

## Rationale
For **symmetric** two-kernel cells (equal size, equal work), the only meaningful SM partition is an
even **8:8** split. Sweeping asymmetric SM ratios (4:12, 6:10, …) for a symmetric workload just
handicaps one kernel and adds noise/cells with no research value. Asymmetric cells still need the
ratio sweep (kernels differ in size, so the optimal split is not necessarily proportional).

## Changes

1. **Sweep / config generation (`scripts/sweep.py` and any config CSV it emits):**
   - For `mode=symmetric` + `config=green`, emit **only** the `sm_split = 8:8` cell. Remove all other
     symmetric green split ratios.
   - Leave `mode=symmetric` + `config=shared` (16:16) unchanged.
   - Leave all **asymmetric** cells (shared and the full green ratio sweep) unchanged.

2. **Plots (`scripts/plot.py`):**
   - `partition_sweep.png` should cover **asymmetric only**. Remove the symmetric case from it (a
     symmetric partition sweep is now a single 8:8 point and carries no information). If the current
     `roofline_tp` selection can land on a symmetric test point, restrict it to asymmetric test points.
   - `green_vs_shared.png` and `delta_vs_size.png` are unaffected in logic: for symmetric sizes the
     "best-green" is now trivially the single 8:8 cell.

3. **Findings (`scripts/derive_findings.py`):**
   - `best_partition_ratios.symmetric` is now always `"8:8"`. Keep the asymmetric best-ratio logic.

## Re-run and validate
- Rebuild/re-run Phase 3 (`bash scripts/run.sh`, clocks locked). The symmetric green cell count drops
  to one split per size, so total cells shrink.
- Confirm `green_vs_shared.png` still renders for symmetric sizes (using the 8:8 green point) and that
  `partition_sweep.png` now shows only asymmetric ratios.
- Re-derive `findings.json` / `FINDINGS.md`.

## Downstream note
This is consistent with `03_verify_overlap_nsys.md`: its best-green selection for symmetric sizes now
resolves to the 8:8 cell automatically (only one green row exists per symmetric size).

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
