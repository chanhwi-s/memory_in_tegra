# Work Prompt — Phase 1: combined-footprint plot (additive)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`.
**Additive only:** do NOT modify existing CSVs, `findings.json`, or `scripts/plot.py`. Add one new
script + new plot images under `experiments/01_single_kernel_size/`.

## Goal
Re-plot Phase 1 on the unified **combined read footprint** x-axis so it is directly comparable to
Phases 2–3 and the ~2 MB cache boundary lines up across phases.

## Canonical x-axis (same formula in every phase)
```
combined_read_footprint_bytes = sum over active kernels of (num_input_buffers * per_buffer_bytes)
```
`C = A + B` has `num_input_buffers = 2` (A, B; write buffer C excluded — matches existing "read
footprint" convention). Phase 1 has 1 kernel → `combined_read_footprint = 2 * S`.
If the results CSV already has `read_footprint_bytes`, that equals this value for Phase 1 — reuse it.
Plot x-axis in **MB, log2 scale**.

## Deliverable
`experiments/01_single_kernel_size/scripts/plot_combined_footprint.py` that:
1. Reads only this phase's results CSV from `results/`.
2. Computes `combined_read_footprint_bytes` per the definition above.
3. Plots **achieved_GBps vs combined footprint (MB, log2), one line per reuse_N**.
4. Draws reference annotations on the figure: **measured cache boundary ≈ 2 MB** (vertical line) and
   **measured DRAM peak ≈ 177 GB/s** (horizontal line). Read these from
   `findings.json` if present; otherwise use the stated values and log a note.
5. Writes figures to `results/plots/` with a `_combined_footprint` suffix (never overwrite existing
   plots). Clear axis labels (`combined read footprint [MB], log2`) + legend.

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
