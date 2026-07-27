# Work Prompt — Phase 3: combined-footprint plot (additive)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`.
**Additive only:** do NOT modify existing CSVs, `findings.json`, or `scripts/plot.py`. Add one new
script + new plot images under `experiments/03_green_context/`.

## Goal
Re-plot Phase 3 on the unified **combined read footprint** x-axis (currently per-kernel size). This
makes Phase 3 land directly on top of Phase 2 where they represent the same data (handoff §2.3) and
aligns the ~2 MB boundary across phases.

## Canonical x-axis (same formula in every phase)
```
combined_read_footprint_bytes = sum over active kernels of (num_input_buffers * per_buffer_bytes)
```
`C = A + B` → `num_input_buffers = 2` (A, B; C excluded). Phase 3 has 2 kernels →
`combined_read_footprint = 2 * k0_bytes + 2 * k1_bytes`.
Plot x-axis in **MB, log2 scale**.

## Deliverable
`experiments/03_green_context/scripts/plot_combined_footprint.py` that:
1. Reads only this phase's results CSV(s) from `results/` (including reuse-overlay data if present).
2. Computes `combined_read_footprint_bytes` per the definition above.
3. Plots **aggregate GB/s vs combined footprint (MB, log2), shared vs green** (and one line per
   reuse_N if the reuse overlay exists).
4. Draws the same reference annotations: **cache boundary ≈ 2 MB** (vertical) and **DRAM peak
   ≈ 177 GB/s** (horizontal), read from `experiments/01_single_kernel_size/findings.json` if available, else
   the stated values with a logged note.
5. Writes figures to `results/plots/` with a `_combined_footprint` suffix (never overwrite existing).
   Clear labels (`combined read footprint [MB], log2`) + legend.

## Verification
Confirm the ~2 MB boundary line lands at the same x-position as in the Phase 1/2 combined-footprint
figures, and that Phase 3 shared overlaps Phase 2 where they are the same data.

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
