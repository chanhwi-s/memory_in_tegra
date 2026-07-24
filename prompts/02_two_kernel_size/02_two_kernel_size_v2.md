# Work Prompt — Phase 2 (add-on): reuse-sweep overlay plot for two concurrent kernels

**Prerequisites:** read `../OVERVIEW.md`, `00_conventions.md`, and the original
`prompts/02_two_kernel_size.md` first. Standard phase layout, worklog, and findings rules apply.
**Scope: Phase 2 ONLY** (`experiments/02_two_kernel_size/`). Do **not** touch any other phase
directory. This is **purely additive** — keep the existing reuse=1 sweep, `phase2_results.csv`,
`findings.json`, `FINDINGS.md`, and both existing plots (`sym_agg_vs_footprint.png`,
`asym_vs_k1.png`) **exactly as they are**. Add one reuse axis and one new plot.

> **Why this add-on exists.** Phase 1 swept reuse (N = 1,2,4,8,16,32) for a *single* kernel and
> produced `bw_vs_footprint.png` — the plot that shows reuse lifting achieved BW above DRAM peak in
> the cache-resident region and collapsing onto DRAM peak once the footprint overflows cache. Phase 2
> currently runs at reuse N=1 only, so we have no two-kernel analog of that plot. We want to see how
> reuse changes the **two-kernel concurrent** picture — where the aggregate gets a cache boost, where
> the reuse lines collapse, and how that compares to the single-kernel Phase 1 story.

## What to add

- **Reuse axis:** `reuse_N ∈ {1, 2, 4, 8, 16, 32}` — both kernels launched N times over the identical
  buffers (inter-launch, full-buffer reuse; same definition as Phase 1 and Phase 4). This requires
  adding a `--reuse-n` flag + an N-iteration launch loop to `phase2_bench` (mirror Phase 4's
  `phase4_bench` reuse loop; both streams launch N times per timed trial) and multiplying moved bytes
  by N in the throughput calc. Config stays **shared** (no green context — that is Phase 3); zero
  copy stays OFF.
- **Size grid:** reuse the existing Phase 2 grid exactly (`symmetric_sizes_bytes()` and
  `asymmetric_k1_sizes_bytes(k)` in `scripts/gen_config.py`) — do not invent new sizes, so the reuse
  overlay lines up with the existing reuse=1 curves and with Phase 1/Phase 3.
- **Block counts:** reuse Phase 2's existing per-cell block-count handling (its local `{1,2,4}×`
  saturation search). Determine the saturated block counts at **reuse N=1** and **hold them fixed**
  across the reuse sweep (verify stable at one extra N), so cost stays ~6× the reuse=1 run rather
  than 6× a fresh search per N.
- **Separate output CSV:** write `results/phase2_reuse_results.csv` with a `reuse_N` column (same
  other columns as `phase2_results.csv`). **Do not** modify `phase2_results.csv` or `findings.json`
  — the reuse=1 handoff to Phases 3/4 must stay byte-for-byte intact. This overlay is diagnostic.

## New plot — `results/plots/reuse_bw_vs_footprint.png`

Mirror Phase 1's `bw_vs_footprint.png`, but for two concurrent kernels. Two panels:

1. **Symmetric:** x-axis = **combined read footprint** (bytes), y-axis = **aggregate GB/s**. One line
   per `reuse_N` (6 lines overlaid, labeled `reuse N=1 … 32`).
2. **Asymmetric:** x-axis = **K1 size** (bytes; K0 fixed 1 MiB), y-axis = aggregate GB/s. One line per
   `reuse_N`.

Both panels:
- x-axis on **log base 2** with power-of-2 tick labels (256K, 512K, 1M, 2M, …) — note this is not
  automatic; matplotlib's `set_xscale("log")` defaults to base 10, so use
  `ax.set_xscale("log", base=2)` + a `FuncFormatter` for human-readable K/M labels.
- Draw the measured DRAM-peak reference (from Phase 1 `findings.json`,
  `measured_dram_peak_GBps`) as a horizontal dotted line, labeled.

**Purpose / what to read off it:** in the cache-resident region (small combined footprint) higher
reuse_N should lift the aggregate **above** DRAM peak (cache hits); once the combined footprint
overflows the effective cache, all reuse_N lines should collapse together onto DRAM peak (no reuse
gain — DRAM-bound). This is the two-kernel analog of Phase 1's plot; call out in `FINDINGS.md` where
the two-kernel collapse point sits versus Phase 1's single-kernel collapse (~4 MB read footprint).

## Verification
- Correctness sample-check both kernels at a couple of reuse_N values (still `C == 3.0`).
- Behavioral sanity (no profiler): at the largest combined footprint all reuse_N lines coincide and
  sit at ~DRAM peak; at a small cache-resident footprint the high-N lines rise above DRAM peak. If a
  high-reuse line does **not** rise in the cache region, the reuse loop isn't re-reading the buffers
  — fix before trusting the plot.
- Flag any cell with stddev/median > 5% (00_conventions §4).

## Findings handoff
Do **not** regenerate or alter `findings.json` (the reuse=1 machine handoff is frozen). Add a
"Reuse overlay" prose section to `FINDINGS.md` describing the new plot and where the two-kernel
reuse collapse sits. Write a new `worklog/YYYY-MM-DD-HHMM_phase2-reuse-overlay.md` and print a
suggested one-line git commit message. Do not commit automatically.
