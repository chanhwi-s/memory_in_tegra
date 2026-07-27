#!/usr/bin/env python3
"""Parse nsys `stats --report cuda_gpu_trace/nvtx_pushpop_trace --format csv`
output and compute the label-free concurrent-overlap metric for Phase 3's nsys
verification (prompts/03_green_context/03_verify_overlap_nsys.md), restricted
to the NVTX "measure" window.

NOT `nsys export --type=sqlite`: on this project's nsys version (2025.6.3,
Jetson AGX Orin / CUDA 13.2) that export produces an empty database (0
tables) -- confirmed on-device. `nsys stats --report ... --format csv
--force-export=true --output <file> <rep>` is the working extraction path,
writing `<file>_<report>.csv`.

Why the NVTX window matters: phase3_bench runs an in-context block-saturation
search, then warmup, then the final measured trials, all in one process.
Counting every kernel launch in the whole trace dilutes the overlap ratio
badly (observed green~=0.10, shared~=0.01 on an unwindowed run -- both
swamped by the sequential search launches). src/phase3_bench.cu now wraps
ONLY the final measured-trial loop in an `nvtxRangePush("measure")` /
`nvtxRangePop()` pair (tagMeasuredTrials=true, passed only at the final-cell
call sites, never during the block-search calls) -- this parser finds that
NVTX range's [start, end] and keeps only `addKernel(...)` GPU-trace rows
(excluding the one-time `fillKernel` init) whose interval falls inside it.

    union_busy_ms     = total time (inside the window) >= 1 kernel executing
    concurrent_ms     = total time (inside the window) >= 2 kernels executing
    overlap_ratio     = concurrent_ms / union_busy_ms
    distinct_greenctx = number of distinct GreenCtx ids among the kept rows
                        (green config: expect 2, confirming the SM split
                        created two separate green contexts; shared: expect
                        0 or 1, since it never partitions SMs)

Standalone use (debug one cell's pair of CSVs):
    python3 parse_nsys_csv.py <cell>_cuda_gpu_trace.csv <cell>_nvtx_pushpop_trace.csv
prints the computed metrics as JSON to stdout.

Column names are resolved defensively (a short candidate list per column) since
nsys's stats CSV schema has shifted across releases; raises a clear error
listing the actual columns found if none of the candidates match, rather than
silently guessing.
"""
import csv
import json
import sys


def _read_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _resolve_column(fieldnames, candidates, csv_path):
    for c in candidates:
        if c in fieldnames:
            return c
    raise RuntimeError(f"{csv_path}: none of {candidates} found in columns {list(fieldnames)}")


def _nvtx_name_matches(raw_name, range_name):
    """True if an nsys NVTX row names `range_name`.

    nsys renders NVTX ranges as "<domain>:<name>"; a range pushed with plain
    nvtxRangePush (no domain) comes out as ":measure", NOT "measure" -- an
    exact-equality test therefore never matched and every cell was recorded as
    a parse failure (all 4 rows of results/overlap_nsys.csv were empty). Accept
    the bare name, the empty-domain form, and any explicit domain prefix.
    """
    s = raw_name.strip()
    return s == range_name or s.rsplit(":", 1)[-1] == range_name


def find_measure_window(nvtx_csv_path, range_name="measure"):
    """Returns (start_ns, end_ns) for the NVTX range named `range_name`."""
    rows = _read_csv_rows(nvtx_csv_path)
    if not rows:
        raise RuntimeError(f"{nvtx_csv_path}: empty NVTX trace (no rows) -- was the "
                            f"'measure' NVTX range ever entered? nsys profile must include "
                            f"'-t cuda,nvtx' for this file to be non-empty.")
    fieldnames = rows[0].keys()
    name_col = _resolve_column(fieldnames, ["Name", "Text"], nvtx_csv_path)
    start_col = _resolve_column(fieldnames, ["Start (ns)", "Start"], nvtx_csv_path)

    end_col = next((c for c in ("End (ns)", "End") if c in fieldnames), None)
    dur_col = next((c for c in ("Duration (ns)", "Duration") if c in fieldnames), None)
    if end_col is None and dur_col is None:
        raise RuntimeError(f"{nvtx_csv_path}: no End or Duration column found in "
                            f"{list(fieldnames)}")

    matches = [r for r in rows if _nvtx_name_matches(r[name_col], range_name)]
    if not matches:
        # Report names EXACTLY as nsys wrote them (no .strip()) -- the previous
        # message normalized them and hid the ":measure" domain prefix that was
        # the actual mismatch.
        raise RuntimeError(f"{nvtx_csv_path}: no NVTX range named {range_name!r} found "
                            f"(available names, verbatim: {sorted({r[name_col] for r in rows})})")
    row = matches[0]
    start_ns = int(float(row[start_col]))
    end_ns = int(float(row[end_col])) if end_col else start_ns + int(float(row[dur_col]))
    return start_ns, end_ns


def load_kernel_intervals_in_window(gpu_trace_csv_path, window, name_filter="addKernel"):
    """Returns (intervals, greenctx_values) for `name_filter`-matching rows
    whose [start, start+duration] interval falls entirely within `window`."""
    rows = _read_csv_rows(gpu_trace_csv_path)
    if not rows:
        return [], set()
    fieldnames = rows[0].keys()
    start_col = _resolve_column(fieldnames, ["Start (ns)", "Start"], gpu_trace_csv_path)
    dur_col = _resolve_column(fieldnames, ["Duration (ns)", "Duration"], gpu_trace_csv_path)
    name_col = _resolve_column(fieldnames, ["Name"], gpu_trace_csv_path)
    greenctx_col = next((c for c in ("GreenCtx", "Green Ctx", "GreenContext") if c in fieldnames), None)

    win_start, win_end = window
    intervals = []
    greenctx_values = set()
    for r in rows:
        if name_filter not in r[name_col]:
            continue
        start = int(float(r[start_col]))
        end = start + int(float(r[dur_col]))
        if start < win_start or end > win_end:
            continue
        intervals.append((start, end))
        if greenctx_col:
            val = r[greenctx_col].strip()
            if val and val not in ("0", "N/A"):
                greenctx_values.add(val)
    return intervals, greenctx_values


def compute_overlap_in_window(gpu_trace_csv_path, nvtx_csv_path, range_name="measure",
                               name_filter="addKernel"):
    window = find_measure_window(nvtx_csv_path, range_name)
    intervals, greenctx_values = load_kernel_intervals_in_window(gpu_trace_csv_path, window, name_filter)

    if not intervals:
        return {
            "kernel_instances_in_window": 0, "distinct_greenctx": len(greenctx_values),
            "union_busy_ms": 0.0, "concurrent_ms": 0.0, "overlap_ratio": 0.0,
        }

    # Sweep-line over start(+1)/end(-1) events, same algorithm as the earlier
    # sqlite-based prototype (scripts/parse_nsys_sqlite.py, now superseded):
    # depth = kernels concurrently executing; accumulate time at depth>=1
    # (union) and depth>=2 (concurrent).
    events = []
    for s, e in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort()

    union_ns = 0
    concurrent_ns = 0
    depth = 0
    prev_t = events[0][0]
    for t, delta in events:
        dt = t - prev_t
        if dt > 0:
            if depth >= 1:
                union_ns += dt
            if depth >= 2:
                concurrent_ns += dt
        depth += delta
        prev_t = t

    union_ms = union_ns / 1e6
    concurrent_ms = concurrent_ns / 1e6
    overlap_ratio = (concurrent_ms / union_ms) if union_ms > 0 else 0.0

    return {
        "kernel_instances_in_window": len(intervals),
        "distinct_greenctx": len(greenctx_values),
        "union_busy_ms": union_ms,
        "concurrent_ms": concurrent_ms,
        "overlap_ratio": overlap_ratio,
    }


def main():
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <cuda_gpu_trace>.csv <nvtx_pushpop_trace>.csv")
    print(json.dumps(compute_overlap_in_window(sys.argv[1], sys.argv[2]), indent=2))


if __name__ == "__main__":
    main()
