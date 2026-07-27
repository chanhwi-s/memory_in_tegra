# Work Prompt — Phase 2: combined-footprint plot (additive)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`.
**Additive only:** do NOT modify existing CSVs, `findings.json`, or `scripts/plot.py`. Add one new
script + new plot images under `experiments/02_two_kernel_size/`.

## Goal
Re-plot Phase 2 on the unified **combined read footprint** x-axis so Phases 1–3 share one cache-
pressure axis and the ~2 MB boundary aligns.

## Canonical x-axis (same formula in every phase)
```
combined_read_footprint_bytes = sum over active kernels of (num_input_buffers * per_buffer_bytes)
```
`C = A + B` → `num_input_buffers = 2` (A, B; C excluded). Phase 2 has 2 kernels →
`combined_read_footprint = 2 * k0_bytes + 2 * k1_bytes`.
If the CSV already carries a `combined_read_footprint_bytes` column, reuse it; else derive it.
Plot x-axis in **MB, log2 scale**.

## Deliverable
`experiments/02_two_kernel_size/scripts/plot_combined_footprint.py` that:
1. Reads only this phase's results CSV(s) from `results/` (including the reuse-overlay CSV if present).
2. Computes `combined_read_footprint_bytes` per the definition above.
3. Plots **aggregate GB/s and per-kernel GB/s, plus scaling_efficiency, vs combined footprint
   (MB, log2)**. If reuse-overlay data exists, draw one aggregate line per reuse_N.
4. Draws the same reference annotations: **cache boundary ≈ 2 MB** (vertical) and **DRAM peak
   ≈ 177 GB/s** (horizontal), read from `experiments/01_single_kernel_size/findings.json` if available, else
   the stated values with a logged note.
5. Writes figures to `results/plots/` with a `_combined_footprint` suffix (never overwrite existing).
   Clear labels (`combined read footprint [MB], log2`) + legend.

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
