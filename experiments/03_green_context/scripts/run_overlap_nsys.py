#!/usr/bin/env python3
"""Phase 3 -- verify concurrent overlap with nsys, restricted to the cache-bound
local peak (+ its two neighbours) per mode (symmetric, asymmetric) -- not every
size. Profiling the whole grid was excessive for a concurrency SANITY check.

Cell selection rewritten by prompts/05_unified_size_grid_and_plots.md Change 6:
the OLD selection (global argmax of agg_GBps_median over ALL configs) is broken
for the symmetric sweep -- after the cache-bound dip, aggregate bandwidth rises
monotonically toward the DRAM asymptote, so the global max is always simply the
LARGEST size in the grid (a point whose green delta is ~-1%, the least
informative cell in the phase), and it's fragile (the cache-region local peak
and the DRAM asymptote are only ~4% apart, so re-measurement noise can flip
which one "wins"). The new selection:
  1. `shared` rows ONLY (the old code took the max over all configs, which let
     a green row decide the selection).
  2. Sort by swept size ascending (symmetric: k0_bytes; asymmetric: k1_bytes,
     K0 fixed).
  3. Find the FIRST local maximum: smallest index i with agg[i] > agg[i-1] and
     agg[i] > agg[i+1] -- the cache-bound peak.
  4. Select test points {i-1, i, i+1} -- the peak plus one neighbour each
     side. Clamped at grid ends with a WARNING if clamping occurred.
  5. If no local maximum exists, fall back to the old global-argmax behaviour
     with a loud WARNING (so a silently-degenerate curve doesn't go unnoticed).
Within each selected test point, the existing per-cell selection is unchanged:
the `shared` row + the `green` row with max agg_GBps_median -- same selection
scripts/plot.py / scripts/plot_combined_footprint.py use. Result: 3 test
points x 2 configs x 2 modes = 12 cells (was 4: 1 test point x ~2 configs x 2
modes). Runnable from anywhere.

Cells are selected directly from the already-measured results/phase3_results.csv
(never re-enumerated via scripts/sweep.py's build_plan). Each selected cell's
EXACT phase3_bench invocation is reconstructed from that CSV row using
--fixed-blocks0/--fixed-blocks1 (skips the in-context block-count search
entirely and measures at exactly the given block counts) -- this guarantees
nsys traces the identical configuration that produced the plotted throughput
number, and is far cheaper than re-running the search per cell.

Each cell is profiled under `nsys profile -t cuda,nvtx --sample=none
--cpuctxsw=none` (CPU sampling / context-switch tracing off -- the CUDA+NVTX
trace is all we need, and this also sidesteps a known nsys hang on
Jetson/aarch64), wrapped in a per-cell `timeout` so one stuck cell can't hang
the whole run. Extraction uses `nsys stats --report {cuda_gpu_trace,
nvtx_pushpop_trace} --format csv` -- NEVER `nsys export --type=sqlite`, which
produces an EMPTY database (0 tables) on this project's nsys version
(2025.6.3) -- confirmed on-device; see scripts/parse_nsys_csv.py. The overlap
metric is computed only within the NVTX "measure" window that
src/phase3_bench.cu now marks around its final measured-trial loop (excludes
warmup and the in-context block-saturation search, which otherwise dilute the
ratio badly -- an earlier unwindowed run measured green~=0.10, shared~=0.01,
both dominated by sequential search launches).

A cell whose `nsys profile` call times out is recorded with overlap_ratio =
NaN and a note -- NOT dropped (that measured configuration still exists and
was already profiled in the throughput sweep; only nsys itself failed to
finish tracing it). An invalid SM ratio (rc=4, rejected by the driver) IS
dropped -- that configuration was never actually measured, so there is
nothing to report.

VERIFICATION ONLY. nsys tracing adds overhead; do not read timings out of
these traces as throughput -- that stays in results/phase3_results.csv from
the untraced sweep. Traces are written to a temp dir and deleted (.nsys-rep +
both stats CSVs) immediately after each cell is parsed (disk hygiene).

Use --dry-run to print the selected cells (cache-bound peak + neighbours per mode,
Change 6 above) without needing nsys, `timeout`, or a CUDA device.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
BIN_PATH = os.path.join(PHASE_DIR, "build", "phase3_bench")
RESULTS_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_results.csv")
CSV_PATH = os.path.join(PHASE_DIR, "results", "overlap_nsys.csv")

sys.path.insert(0, SCRIPT_DIR)
import parse_nsys_csv  # noqa: E402

# Column order for the new CSV (prompts/03_green_context/03_verify_overlap_nsys.md
# columns first, in the order it specifies; sm_split_k0..threads_per_block appended
# at the end -- user request: make each of the 4 cells' exact configuration
# (kernel sizes, block counts, SM split) visible without cross-referencing
# results/phase3_results.csv by hand).
# failure_reason (Change 6): profile_cell() records an empty-metrics row for TWO
# different failures -- nsys profile timeout, and parse_nsys_csv raising -- but until
# this column existed the CSV couldn't distinguish them (both just showed up as blank
# overlap_ratio, which is why overlap_nsys_table.md said "N/A (timeout/parse failure)").
# Empty string on success; "timeout" or "parse_error: <message>" otherwise.
CSV_FIELDS = [
    "test_point_id", "mode", "config", "k0_bytes", "k1_bytes",
    "combined_read_footprint_bytes",
    "kernel_instances_in_window", "distinct_greenctx",
    "union_busy_ms", "concurrent_ms", "overlap_ratio", "failure_reason",
    "gpu_clock_mhz", "power_mode", "soc_temp_c", "cuda_version", "driver_version",
    "sm_split_k0", "sm_split_k1", "blocks_k0", "blocks_k1", "threads_per_block",
]
CSV_HEADER = ",".join(CSV_FIELDS)

PROFILE_TIMEOUT_SEC = 180
NSYS_TIMEOUT_RC = 124  # GNU coreutils `timeout`: process was killed for exceeding the limit


def check_tools_available():
    if shutil.which("nsys") is None:
        sys.exit("FATAL: `nsys` not found on PATH -- this verification step requires the "
                 "NVIDIA Nsight Systems CLI (ships with JetPack/CUDA on the Jetson). Report "
                 "this in the worklog rather than skipping verification silently.")
    if shutil.which("timeout") is None:
        sys.exit("FATAL: `timeout` (coreutils) not found on PATH -- required to bound each "
                 "nsys profile call (prompts/03_green_context/03_verify_overlap_nsys.md).")


def _swept_size_bytes(row):
    """symmetric -> k0_bytes (== k1_bytes); asymmetric -> k1_bytes (K0 fixed).
    Same convention as scripts/plot.py's swept_size_bytes column."""
    return row.k0_bytes if row["mode"] == "symmetric" else row.k1_bytes


def select_peak_bandwidth_test_points(df):
    """Change 6 (05_unified_size_grid_and_plots.md): per mode, `shared` rows
    ONLY (a green row must never decide this selection), sorted by swept size
    ascending, then the FIRST local maximum of agg_GBps_median -- the
    cache-bound peak. Falls back to the old global-argmax-over-shared-rows
    behaviour with a loud WARNING if no local maximum exists (e.g. a
    monotonic or too-short grid), so a degenerate curve is never silently
    mistaken for a resolved peak.

    Why not global argmax (the old behaviour): for the symmetric sweep,
    aggregate bandwidth climbs monotonically toward the DRAM asymptote after
    the cache-bound dip, so the global max is always simply the LARGEST size
    in the grid -- a point whose green delta is ~-1%, the least informative
    cell in the phase, and fragile (the cache-region local peak and the DRAM
    asymptote are only ~4% apart, so re-measurement noise can flip which one
    "wins"). Computed fresh every time from results/phase3_results.csv, never
    hardcoded, so it tracks wherever the peak actually lands after any
    re-sweep (grid changes, re-measurement, noise, etc.).

    Returns {mode: [test_point_id, ...]} -- 3 test points per mode when a
    local max is found (peak - 1, peak, peak + 1, clamped at grid ends), 1
    when falling back to global argmax."""
    result = {}
    for mode, g in df.groupby("mode"):
        shared = g[g.config == "shared"].copy()
        if shared.empty:
            print(f"WARNING: no shared rows for mode={mode} -- cannot select a peak test point",
                  file=sys.stderr)
            continue
        shared["swept_size_bytes"] = shared.apply(_swept_size_bytes, axis=1)
        shared = shared.sort_values("swept_size_bytes").reset_index(drop=True)
        agg = shared.agg_GBps_median.to_numpy()
        n = len(agg)

        peak_idx = None
        for i in range(1, n - 1):
            if agg[i] > agg[i - 1] and agg[i] > agg[i + 1]:
                peak_idx = i
                break

        if peak_idx is None:
            peak_idx = int(agg.argmax())
            print(f"WARNING: no local maximum found for mode={mode} (n={n} shared rows) -- "
                  f"falling back to the global-argmax test point "
                  f"({shared.iloc[peak_idx].test_point_id!r}). This may be the largest/smallest "
                  f"grid size rather than a resolved cache-bound peak -- treat with caution.",
                  file=sys.stderr)
            indices = [peak_idx]
        else:
            lo, hi = peak_idx - 1, peak_idx + 1
            clamped_lo, clamped_hi = max(0, lo), min(n - 1, hi)
            if clamped_lo != lo or clamped_hi != hi:
                print(f"WARNING: peak-neighbour selection clamped at grid edge for mode={mode} "
                      f"(peak_idx={peak_idx}, n={n}, requested [{lo},{hi}], clamped "
                      f"[{clamped_lo},{clamped_hi}])", file=sys.stderr)
            indices = sorted(set([clamped_lo, peak_idx, clamped_hi]))

        result[mode] = [shared.iloc[idx].test_point_id for idx in indices]
    return result


def select_plotted_cells(df):
    """Restricted to the cache-bound peak + its two neighbours per mode
    (select_peak_bandwidth_test_points, computed above -- 3 test points x 2
    modes when a local max is found, so up to 3 x 2 x 2 = 12 cells). Within
    each selected test point, uses the SAME best-green selection
    scripts/plot.py / scripts/plot_combined_footprint.py use: the shared row
    + the green row with the max agg_GBps_median. Reimplemented here (not
    imported) since it's the identical few-line selection and this script
    must not depend on plot.py's internals."""
    peak_tps_by_mode = select_peak_bandwidth_test_points(df)
    print(f"Peak + neighbour test points per mode (computed from this CSV, not hardcoded): "
          f"{peak_tps_by_mode}", file=sys.stderr)

    cells = []
    for mode, tps in peak_tps_by_mode.items():
        for tp in tps:
            g = df[df.test_point_id == tp]

            shared = g[g.config == "shared"]
            if shared.empty:
                print(f"WARNING: no shared row for test point {tp!r} ({mode}) -- skipping",
                      file=sys.stderr)
            else:
                cells.append(shared.iloc[0])

            green = g[g.config == "green"]
            if green.empty:
                print(f"NOTE: no green rows for test point {tp!r} ({mode}) -- only shared "
                      f"will be profiled", file=sys.stderr)
                continue
            cells.append(green.loc[green.agg_GBps_median.idxmax()])
    return cells


def cell_args(row):
    """Reconstruct the exact phase3_bench invocation for this already-measured
    row, using --fixed-blocks0/1 so the binary skips its in-context block
    search and reproduces exactly the configuration that produced this row's
    agg_GBps_median -- not a fresh (possibly different) search result."""
    return [
        BIN_PATH,
        "--test-point-id", str(row.test_point_id),
        "--mode", str(row["mode"]),  # bracket access: .mode collides with Series.mode()
        "--config", str(row.config),
        "--k0-bytes", str(int(row.k0_bytes)),
        "--k1-bytes", str(int(row.k1_bytes)),
        "--sm0", str(int(row.sm_split_k0)),
        "--sm1", str(int(row.sm_split_k1)),
        "--fixed-blocks0", str(int(row.blocks_k0)),
        "--fixed-blocks1", str(int(row.blocks_k1)),
        "--tpb", str(int(row.threads_per_block)),
        "--trials", str(int(row.trials)),
    ]


def profile_cell(row, tmp_dir):
    """Returns a dict of CSV_FIELDS -> value, or None to drop the cell (invalid
    SM ratio -- rc=4). A timeout, or a missing/unparseable 'measure' NVTX
    window, returns a row with the overlap metrics left empty (-> NaN on CSV
    read), per the prompt: record and continue, don't drop."""
    base = os.path.join(tmp_dir, "cell")
    rep_path = base + ".nsys-rep"
    gpu_csv_path = base + "_cuda_gpu_trace.csv"
    nvtx_csv_path = base + "_nvtx_pushpop_trace.csv"
    temp_paths = (rep_path, gpu_csv_path, nvtx_csv_path)
    for p in temp_paths:
        if os.path.exists(p):
            os.remove(p)

    k0_bytes = int(row.k0_bytes)
    k1_bytes = int(row.k1_bytes)
    out = {
        "test_point_id": row.test_point_id, "mode": row["mode"], "config": row.config,
        "k0_bytes": k0_bytes, "k1_bytes": k1_bytes,
        "combined_read_footprint_bytes": 2 * k0_bytes + 2 * k1_bytes,
        "gpu_clock_mhz": row.gpu_clock_mhz, "power_mode": row.power_mode,
        "soc_temp_c": row.soc_temp_c, "cuda_version": row.cuda_version,
        "driver_version": row.driver_version,
        # Exact configuration this cell was profiled at (straight from the
        # phase3_results.csv row cell_args() reconstructed the invocation
        # from) -- so the CSV/table/chart never need a manual cross-reference
        # back to phase3_results.csv to see what was actually measured.
        "sm_split_k0": int(row.sm_split_k0), "sm_split_k1": int(row.sm_split_k1),
        "blocks_k0": int(row.blocks_k0), "blocks_k1": int(row.blocks_k1),
        "threads_per_block": int(row.threads_per_block),
    }
    empty_metrics = dict(kernel_instances_in_window="", distinct_greenctx="",
                          union_busy_ms="", concurrent_ms="", overlap_ratio="")

    profile_cmd = (
        ["timeout", str(PROFILE_TIMEOUT_SEC), "nsys", "profile", "-t", "cuda,nvtx",
         "--sample=none", "--cpuctxsw=none", "--force-overwrite=true", "-o", base]
        + cell_args(row)
    )
    proc = subprocess.run(profile_cmd, capture_output=True, text=True)

    if proc.returncode == NSYS_TIMEOUT_RC:
        print(f"WARNING: nsys profile TIMED OUT ({PROFILE_TIMEOUT_SEC}s) for cell "
              f"{row.test_point_id} config={row.config} -- recording overlap_ratio=NaN, "
              f"continuing", file=sys.stderr)
        for p in temp_paths:
            if os.path.exists(p):
                os.remove(p)
        out.update(empty_metrics)
        out["failure_reason"] = "timeout"
        return out

    if proc.returncode == 4:
        print(f"WARNING: dropping cell (SM ratio {int(row.sm_split_k0)}:{int(row.sm_split_k1)} "
              f"rejected): {proc.stderr.strip()}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"WARNING: nsys profile failed for cell {row.test_point_id} config={row.config} "
              f"(rc={proc.returncode}) -- dropping. stderr:\n{proc.stderr.strip()}", file=sys.stderr)
        return None

    if not os.path.exists(rep_path):
        print(f"WARNING: nsys profile did not produce {rep_path} for cell {row.test_point_id} "
              f"config={row.config} -- dropping", file=sys.stderr)
        return None

    # NEVER `nsys export --type=sqlite` -- confirmed to produce an empty (0-table)
    # database on this project's nsys version. `nsys stats --format csv` is the
    # working extraction path (prompts/03_green_context/03_verify_overlap_nsys.md).
    for report, out_csv in (("cuda_gpu_trace", gpu_csv_path), ("nvtx_pushpop_trace", nvtx_csv_path)):
        stats_cmd = ["nsys", "stats", "--report", report, "--format", "csv",
                     "--force-export=true", "--output", base, rep_path]
        proc = subprocess.run(stats_cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(out_csv):
            print(f"WARNING: `nsys stats --report {report}` failed for cell {row.test_point_id} "
                  f"config={row.config} -- dropping. stderr:\n{proc.stderr.strip()}", file=sys.stderr)
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            return None

    try:
        metrics = parse_nsys_csv.compute_overlap_in_window(gpu_csv_path, nvtx_csv_path)
    except RuntimeError as e:
        print(f"WARNING: could not parse nsys CSVs for cell {row.test_point_id} "
              f"config={row.config} -- recording overlap_ratio=NaN, continuing. Error: {e}",
              file=sys.stderr)
        for p in temp_paths:
            if os.path.exists(p):
                os.remove(p)
        out.update(empty_metrics)
        # CSV_FIELDS are written with a naive comma-join (no quoting), so scrub any
        # commas/newlines out of the exception text -- it can legitimately contain
        # them (e.g. a Python list repr in the message).
        reason = str(e).replace(",", ";").replace("\n", " ")
        out["failure_reason"] = f"parse_error: {reason}"
        return out

    # Disk hygiene (prompt: do not let traces/CSVs accumulate across the run).
    for p in temp_paths:
        if os.path.exists(p):
            os.remove(p)

    out.update(
        kernel_instances_in_window=metrics["kernel_instances_in_window"],
        distinct_greenctx=metrics["distinct_greenctx"],
        union_busy_ms=f"{metrics['union_busy_ms']:.6f}",
        concurrent_ms=f"{metrics['concurrent_ms']:.6f}",
        overlap_ratio=f"{metrics['overlap_ratio']:.4f}",
        failure_reason="",
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print selected cells, profile nothing")
    args = ap.parse_args()

    if not os.path.exists(RESULTS_CSV_PATH):
        sys.exit(f"FATAL: {RESULTS_CSV_PATH} not found -- run scripts/sweep.py (or scripts/run.sh) "
                 f"first; this script selects cells FROM that CSV, it does not re-sweep.")
    df = pd.read_csv(RESULTS_CSV_PATH)
    cells = select_plotted_cells(df)

    if args.dry_run:
        print(f"Selected {len(cells)} cells to profile with nsys (shared + best-green at the "
              f"cache-bound peak + its two neighbours, per mode, computed from this CSV):")
        for row in cells:
            print(f"  {row.test_point_id} mode={row['mode']} config={row.config} "
                  f"sm={int(row.sm_split_k0)}:{int(row.sm_split_k1)} "
                  f"blocks={int(row.blocks_k0)}:{int(row.blocks_k1)} agg_GBps={row.agg_GBps_median}")
        return

    check_tools_available()
    if not os.path.exists(BIN_PATH):
        sys.exit(f"Binary not found: {BIN_PATH} (run scripts/build.sh first)")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    rows = []
    dropped = 0
    timed_out = 0
    tmp_dir = tempfile.mkdtemp(prefix="phase3_nsys_")
    try:
        for i, row in enumerate(cells):
            print(f"[{i + 1}/{len(cells)}] nsys profile: {row.test_point_id} config={row.config} "
                  f"sm={int(row.sm_split_k0)}:{int(row.sm_split_k1)}", file=sys.stderr)
            result = profile_cell(row, tmp_dir)
            if result is None:
                dropped += 1
                continue
            if result["overlap_ratio"] == "":
                timed_out += 1
            rows.append(result)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    with open(CSV_PATH, "w") as f:
        f.write(CSV_HEADER + "\n")
        for r in rows:
            f.write(",".join(str(r[k]) for k in CSV_FIELDS) + "\n")

    print(f"wrote {CSV_PATH}")
    if dropped:
        print(f"NOTE: {dropped} cell(s) dropped (invalid SM ratio or nsys failure) -- "
              f"see WARNINGs above", file=sys.stderr)
    if timed_out:
        print(f"NOTE: {timed_out} cell(s) timed out or had an unparseable 'measure' NVTX window "
              f"(overlap_ratio recorded as NaN) -- see WARNINGs above", file=sys.stderr)


if __name__ == "__main__":
    main()
