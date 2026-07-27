# Work Prompt — Phase 3: clean nsys overlap verification (NVTX-windowed, plotted cells)

**Prerequisites (paths relative to repo root):** read `OVERVIEW.md`, `prompts/00_conventions.md`, and
`worklog/2026-07-27-1015_HANDOFF.md`. Modifies Phase 3's own directory only. This supersedes any earlier
overlap-verification attempt — implement it as the single clean version.

## Goal
Measure how much the two Phase 3 kernels actually run **concurrently on the GPU**, for `green` (disjoint
SM partitions) vs `shared`, so we can confirm green context yields real overlap. Environment already
validated: **NVIDIA Jetson AGX Orin 64GB, nsys 2025.6.3, CUDA 13.2.** Two facts learned the hard way,
which this spec must respect:
- `nsys export --type=sqlite` produces an **empty database (0 tables)** on this version. Do NOT use it.
  Extract the GPU trace via `nsys stats ... --output <file>` and parse the CSV file.
- The bench runs a **block-saturation search + warmup + measured trials** in one process. Counting all
  launches dilutes overlap badly (a raw whole-trace run gave green≈0.10, shared≈0.01, both polluted by
  the sequential search launches). We must isolate the **measured-trial window** with an NVTX range.

## Change 1 — mark the measured window with NVTX in `src/phase3_bench.cu`
- `#include <nvtx3/nvToolsExt.h>` (link with `-lnvToolsExt` if the build needs it).
- Wrap **only the final measured-trial loop** (the timed trials at the chosen/held block counts — NOT the
  block-saturation search, NOT warmup) in:
  ```cpp
  nvtxRangePush("measure");
  /* ... measured trials: both kernels launched, reuse loop, the timed region ... */
  nvtxRangePop();
  ```
- Keep everything else unchanged; this is additive instrumentation.

## Change 2 — new overlap script + parser (do not touch existing CSV/findings/plot.py)
Create `experiments/03_green_context/scripts/verify_overlap_nsys.sh` (+ parser). Steps:

**Cell selection — peak-bandwidth point per mode only (NOT all sizes; superseded 2026-07-27).** From
the existing `results/phase3_results.csv`, per mode (`symmetric`, `asymmetric`) find the single
`test_point_id` whose row (any config) has the max `agg_GBps_median` (the roofline point) — computed
fresh from the CSV every run, never hardcoded. For each of those 2 test points, select the `shared` row
and the single **best-green** row (max `agg_GBps_median` among that size's green rows — the exact
selection `plot.py`'s `green_vs_shared` uses). Reconstruct each cell's `phase3_bench` args from that row.
Result = 4 cells (2 modes x {shared, best-green}) — profiling every size (~58 cells) was excessive for a
concurrency sanity check; the peak/roofline point per mode is the single most informative place to
confirm the two kernels overlap.

**Profile each selected cell** (per-cell `timeout`, CPU sampling off, NVTX enabled):
```
timeout 180 nsys profile -t cuda,nvtx --sample=none --cpuctxsw=none \
    --force-overwrite=true -o <tmp>/cell ./build/phase3_bench <cell args>
```

**Extract to files** (never `nsys export --type=sqlite`; never pipe nsys stats stdout):
```
nsys stats --report cuda_gpu_trace     --format csv --force-export=true --output <tmp>/cell <tmp>/cell.nsys-rep
nsys stats --report nvtx_pushpop_trace --format csv --force-export=true --output <tmp>/cell <tmp>/cell.nsys-rep
```
This writes `<tmp>/cell_cuda_gpu_trace.csv` and `<tmp>/cell_nvtx_pushpop_trace.csv`.
**GOTCHA: `nsys stats --output` skips regeneration if the target CSV already exists** (`SKIPPED:
output file exists`) — use a **unique temp base per cell** (or delete the old CSVs first), otherwise the
parser reads a stale previous cell's trace and metrics come out wrong/empty.

**Parse (all timestamps share one global ns timebase):**
1. From the NVTX CSV (`nvtx_pushpop_trace`), find the measure range using its `Start (ns)` / `End (ns)`
   columns. **GOTCHA: the `Name` is reported as `:measure` (leading colon from the RangeStack), not
   `measure`** — match by substring (`'measure' in Name`), never by exact equality, or you get 0 rows.
2. From the GPU-trace CSV, keep only `addKernel(...)` rows (exclude `fillKernel` init) whose interval
   `[Start, Start+Duration]` falls inside the `measure` window.
3. Label-free overlap via sweep line over those intervals:
   ```
   union_busy = total time with >= 1 kernel active
   concurrent = total time with >= 2 kernels active
   overlap_ratio = concurrent / union_busy
   ```
   `overlap_ratio = 1` ⇒ whenever the GPU was busy in the measured window, both kernels ran together.
   Also record `kernel_instances_in_window`, `union_busy_ms`, `concurrent_ms`, and the distinct
   `GreenCtx` values seen (for green, expect two distinct contexts).
4. If a cell times out or the `measure` range is missing, write `overlap_ratio = NaN` with a note and
   continue.

## Output
- New CSV `results/overlap_nsys.csv`, one row per selected cell:
  ```
  test_point_id, mode, config, k0_bytes, k1_bytes, combined_read_footprint_bytes,
  kernel_instances_in_window, distinct_greenctx, union_busy_ms, concurrent_ms, overlap_ratio,
  gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version
  ```
  (`combined_read_footprint_bytes = 2*k0_bytes + 2*k1_bytes`.)
- New plot `results/plots/overlap_ratio_vs_footprint_combined_footprint.png`: `overlap_ratio` vs combined
  read footprint (MB, log2), **shared vs green** as two lines, with a reference line at `overlap_ratio = 1`.

## Robustness / hygiene
- Lock clocks first (MAXN + `jetson_clocks`).
- Write traces to a temp dir; **delete each `.nsys-rep`, `.sqlite`, and `.csv` temp right after parsing**.
- Verification-only: do NOT use nsys timings as throughput; the real throughput stays in the normal
  sweep CSV.
- Add `--skip-nsys` passthrough so `run.sh` can skip this stage.

## Interpretation to record (worklog, not overwriting findings.json)
- Expect **green overlap ≫ shared overlap** (disjoint SMs → genuine concurrency; shared tends to
  serialize). If green ≈ 1, green context is delivering real concurrency; if green stays low despite the
  confirmed disjoint SM split, note it and flag for investigation (e.g. launch-latency-bound at tiny
  sizes). Report the shared value alongside for contrast.

## Wrap-up
End with a `worklog/` entry and a suggested one-line commit message.
