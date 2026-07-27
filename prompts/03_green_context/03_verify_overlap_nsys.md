# Work Prompt — Phase 3: verify concurrent overlap with nsys (all sizes, averaged)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`.
**Additive only:** do NOT modify existing CSVs, `findings.json`, `scripts/plot.py`, or the throughput
numbers. Add one new script + one new CSV + one new plot under `experiments/03_green_context/`.

## Goal
Confirm, on the actual execution timeline, that the two kernels really run **concurrently** in Phase 3
— for **every** sweep cell (all kernel sizes), in **both** `shared` and `green` configs. The timing
heuristic `wall < serial_sum` cannot distinguish "did not overlap" from "overlapped but bandwidth-
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
1. Enumerate **the same cells the Phase 3 sweep uses** (reuse `scripts/sweep.py` / the sweep config
   CSV so sizes and configs match exactly — all sizes, both `shared` and `green`).
2. For each cell, run the existing per-cell `build/phase3_bench` invocation under nsys:
   ```
   nsys profile -t cuda --force-overwrite=true -o <tmp>/cell ./build/phase3_bench <cell args>
   nsys export --type=sqlite --force-overwrite=true <tmp>/cell.nsys-rep
   ```
   Parse `CUPTI_ACTIVITY_KIND_KERNEL` (`start`, `end`) from the sqlite to compute the metric above.
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
