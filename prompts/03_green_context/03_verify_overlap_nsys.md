# Work Prompt — Phase 3: verify concurrent overlap with nsys (all sizes, averaged)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`.
**Additive only:** do NOT modify existing CSVs, `findings.json`, `scripts/plot.py`, or the throughput
numbers. Add one new script + one new CSV + one new plot under `experiments/03_green_context/`.

## Goal
Confirm, on the actual execution timeline, that the two kernels really run **concurrently** in Phase 3
— **only for the cells that actually appear in the `green_vs_shared` plot** (NOT all 149 sweep cells).
`plot.py`'s `green_vs_shared.png` shows, per size (`test_point_id`), just two points: the `shared`
cell and the single **best-green** cell = the SM split with the maximum `agg_GBps_median` among that
size's green rows (`green.agg_GBps_median.max()`). The other green split ratios are swept but never
plotted, so tracing them wastes time. Restrict nsys to exactly that plotted set — `{shared}` plus the
`{best-green split}` per size.

The timing heuristic `wall < serial_sum` cannot distinguish "did not overlap" from "overlapped but bandwidth-
shared"; nsys records the real timeline and resolves this. (nsys does NOT serialize kernels — unlike
ncu — so it is the correct tool here.)

## Metric — label-free overlap ratio (this is the "average aggregation")
For a traced cell run, take all GPU kernel execution intervals `[start, end]` (nanoseconds) from the
trace and compute:
```
union_busy_time  = total time during which >= 1 kernel is executing   (union of intervals)
concurrent_time  = total time during which >= 2 kernels execute simultaneously
overlap_ratio    = concurrent_time / union_busy_time
```
`overlap_ratio = 1` ⇒ whenever the GPU was busy, both kernels were running together (full overlap).
This is inherently a time-weighted average over the whole cell run (all reuse-N launch pairs), so no
per-pair labeling of K0 vs K1 is needed. Also report `concurrent_time`, `union_busy_time`, and the
kernel-instance count for transparency.

## Deliverable — `experiments/03_green_context/scripts/verify_overlap_nsys.sh` (+ a small parser)
1. **Select only the plotted cells** from the existing Phase 3 results CSV, reusing the SAME best-green
   selection as `plot.py` (`_summary_table` / `plot_green_vs_shared`): for each `test_point_id`, take
   the `shared` row, and the `green` row whose `agg_GBps_median` is the max for that `test_point_id`
   (its `sm_split_k0:sm_split_k1`). Reconstruct each selected cell's exact `phase3_bench` arguments
   from that CSV row (do not re-enumerate the whole sweep). Result ≈ (number of sizes) × 2 cells.
2. For each selected cell, run its `build/phase3_bench` invocation under nsys, wrapped in a per-cell
   `timeout` so one stuck cell can't hang the whole run, and with CPU sampling off (CUDA trace is all
   we need — this also avoids a known nsys-hang on Jetson/aarch64):
   ```
   timeout 180 nsys profile -t cuda --sample=none --cpuctxsw=none \
       --force-overwrite=true -o <tmp>/cell ./build/phase3_bench <cell args>
   nsys export --type=sqlite --force-overwrite=true <tmp>/cell.nsys-rep
   ```
   Parse `CUPTI_ACTIVITY_KIND_KERNEL` (`start`, `end`) from the sqlite to compute the metric above. If
   a cell times out, record `overlap_ratio` as NaN with a `timeout` note and continue.
3. Append one row per cell to a **new** CSV `results/overlap_nsys.csv`:
   ```
   test_point_id, mode, config, k0_bytes, k1_bytes, combined_read_footprint_bytes, reuse_N,
   kernel_instances, union_busy_ms, concurrent_ms, overlap_ratio,
   gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
   ```
   (`combined_read_footprint_bytes = 2*k0_bytes + 2*k1_bytes`, matching the unified axis.)
4. Emit a plot `results/plots/overlap_ratio_vs_footprint_combined_footprint.png`: `overlap_ratio` vs
   combined read footprint (MB, log2), **shared vs green** as two lines. Draw a reference line at
   `overlap_ratio = 1`.

## Practical constraints
- Lock clocks first (MAXN + `jetson_clocks`), same as every phase.
- **Disk hygiene:** write traces to a temp dir and **delete each `.nsys-rep` and `.sqlite` right after
  parsing** — running all sizes × both configs produces many traces; do not let them accumulate.
- This nsys run is **verification-only**. Do NOT use its timings as throughput — the real throughput
  stays in the normal (non-nsys) sweep CSV. nsys tracing adds overhead but preserves the concurrency
  we are measuring.
- If a cell's `phase3_bench` invocation differs from the standard sweep (e.g. green needs SM-split
  args), reuse exactly the argument construction from `sweep.py` so overlap is measured on the same
  configuration the throughput sweep used.

## Interpretation to record in FINDINGS-style note (in the worklog, not overwriting findings.json)
- `overlap_ratio ≈ 1` for green confirms the SM-partitioned kernels truly run concurrently. If green
  shows high overlap yet no throughput gain (from the main sweep), that pins the cause on shared
  DRAM/cache bandwidth, not lack of concurrency — a key mechanistic conclusion.
- Compare shared vs green overlap across sizes: note where either drops below ~1 (serialization onset).

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
