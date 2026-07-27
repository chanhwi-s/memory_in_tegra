#!/usr/bin/env python3
"""Phase 3 -- verify concurrent overlap with nsys, restricted to the single
peak-bandwidth test point per mode (symmetric, asymmetric) -- not every size.
Profiling all 29 sizes (58 cells) was excessive for a concurrency SANITY
check: the peak-bandwidth point per mode is the roofline/contention-onset
point, the single most informative place to confirm the two kernels actually
overlap. For each of those 2 test points: the `shared` row plus the single
best-green row (max agg_GBps_median among that size's green rows) -- same
selection scripts/plot.py's green_vs_shared.png uses, just narrowed to one
size per mode instead of all of them. Runnable from anywhere.

Cells are selected directly from the already-measured results/phase3_results.csv
(never re-enumerated via scripts/sweep.py's build_plan). Each selected cell's
EXACT phase3_bench invocation is reconstructed from that CSV row using
--fixed-blocks0/--fixed-blocks1 (skips the in-context block-count search
entirely and measures at exactly the given block counts) -- this guarantees
nsys traces the identical configuration that produced the plotted throughput
number, and is far cheaper than re-running the search per cell.

Each cell is profiled under `nsys profile -t cuda --sample=none --cpuctxsw=none`
(CPU sampling / context-switch tracing off -- the CUDA trace is all we need,
and this also sidesteps a known nsys hang on Jetson/aarch64), wrapped in a
per-cell `timeout` so one stuck cell can't hang the whole run. A cell whose
`nsys profile` call times out is recorded with overlap_ratio = NaN and a note
-- NOT dropped (that measured configuration still exists and was already
profiled in the throughput sweep; only nsys itself failed to finish tracing
it). An invalid SM ratio (rc=4, rejected by the driver) IS dropped -- that
configuration was never actually measured, so there is nothing to report.

VERIFICATION ONLY. nsys tracing adds overhead; do not read timings out of
these traces as throughput -- that stays in results/phase3_results.csv from
the untraced sweep. Traces are written to a temp dir and deleted (.nsys-rep +
.sqlite) immediately after each cell is parsed (disk hygiene).

Use --dry-run to print the selected cells (same selection scripts/plot.py's
green_vs_shared.png uses) without needing nsys, `timeout`, or a CUDA device.
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
import parse_nsys_sqlite  # noqa: E402

# Column order for the new CSV (prompts/03_green_context/03_verify_overlap_nsys.md).
CSV_FIELDS = [
    "test_point_id", "mode", "config", "k0_bytes", "k1_bytes",
    "combined_read_footprint_bytes", "reuse_N",
    "kernel_instances", "union_busy_ms", "concurrent_ms", "overlap_ratio",
    "gpu_clock_mhz", "power_mode", "soc_temp_c", "cuda_version", "driver_version",
]
CSV_HEADER = ",".join(CSV_FIELDS)

PROFILE_TIMEOUT_SEC = 180
NSYS_TIMEOUT_RC = 124  # GNU coreutils `timeout`: process was killed for exceeding the limit
# Every row in phase3_results.csv is a reuse_N=1 measurement (the main sweep
# never passes --reuse-n); this is the real parameter used, not a placeholder.
REUSE_N = 1


def check_tools_available():
    if shutil.which("nsys") is None:
        sys.exit("FATAL: `nsys` not found on PATH -- this verification step requires the "
                 "NVIDIA Nsight Systems CLI (ships with JetPack/CUDA on the Jetson). Report "
                 "this in the worklog rather than skipping verification silently.")
    if shutil.which("timeout") is None:
        sys.exit("FATAL: `timeout` (coreutils) not found on PATH -- required to bound each "
                 "nsys profile call (prompts/03_green_context/03_verify_overlap_nsys.md).")


def select_peak_bandwidth_test_points(df):
    """Per mode, the test_point_id whose row (any config) has the max
    agg_GBps_median in THIS run's CSV -- computed fresh every time from
    results/phase3_results.csv, never hardcoded, so it tracks wherever the
    peak actually lands after any re-sweep (grid changes, re-measurement,
    noise, etc.)."""
    return {mode: g.loc[g.agg_GBps_median.idxmax(), "test_point_id"]
            for mode, g in df.groupby("mode")}


def select_plotted_cells(df):
    """Restricted to the single peak-bandwidth test point per mode
    (select_peak_bandwidth_test_points, computed above). Within each selected
    test point, uses the SAME best-green selection scripts/plot.py's
    plot_green_vs_shared / _point_summary uses: the shared row + the green
    row with the max agg_GBps_median. Reimplemented here rather than imported
    -- plot.py is off-limits for edits (prompt: additive only, do NOT modify
    it) -- but this is the identical few-line selection, so it cannot drift
    in any way that matters."""
    peak_tp_by_mode = select_peak_bandwidth_test_points(df)
    print(f"Peak-bandwidth test point per mode (computed from this CSV, not hardcoded): "
          f"{peak_tp_by_mode}", file=sys.stderr)

    cells = []
    for mode, tp in peak_tp_by_mode.items():
        g = df[df.test_point_id == tp]

        shared = g[g.config == "shared"]
        if shared.empty:
            print(f"WARNING: no shared row for peak test point {tp!r} ({mode}) -- skipping",
                  file=sys.stderr)
        else:
            cells.append(shared.iloc[0])

        green = g[g.config == "green"]
        if green.empty:
            print(f"NOTE: no green rows for peak test point {tp!r} ({mode}) -- only shared "
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
    SM ratio -- rc=4). A timeout returns a row with the overlap metrics set to
    empty (-> NaN on CSV read), per the prompt: record and continue, don't drop."""
    base = os.path.join(tmp_dir, "cell")
    rep_path = base + ".nsys-rep"
    sqlite_path = base + ".sqlite"
    for p in (rep_path, sqlite_path):
        if os.path.exists(p):
            os.remove(p)

    k0_bytes = int(row.k0_bytes)
    k1_bytes = int(row.k1_bytes)
    out = {
        "test_point_id": row.test_point_id, "mode": row["mode"], "config": row.config,
        "k0_bytes": k0_bytes, "k1_bytes": k1_bytes,
        "combined_read_footprint_bytes": 2 * k0_bytes + 2 * k1_bytes, "reuse_N": REUSE_N,
        "gpu_clock_mhz": row.gpu_clock_mhz, "power_mode": row.power_mode,
        "soc_temp_c": row.soc_temp_c, "cuda_version": row.cuda_version,
        "driver_version": row.driver_version,
    }

    profile_cmd = (
        ["timeout", str(PROFILE_TIMEOUT_SEC), "nsys", "profile", "-t", "cuda",
         "--sample=none", "--cpuctxsw=none", "--force-overwrite=true", "-o", base]
        + cell_args(row)
    )
    proc = subprocess.run(profile_cmd, capture_output=True, text=True)

    if proc.returncode == NSYS_TIMEOUT_RC:
        print(f"WARNING: nsys profile TIMED OUT ({PROFILE_TIMEOUT_SEC}s) for cell "
              f"{row.test_point_id} config={row.config} -- recording overlap_ratio=NaN, "
              f"continuing", file=sys.stderr)
        for p in (rep_path, sqlite_path):
            if os.path.exists(p):
                os.remove(p)
        out.update(kernel_instances="", union_busy_ms="", concurrent_ms="", overlap_ratio="")
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

    export_cmd = ["nsys", "export", "--type=sqlite", "--force-overwrite=true", rep_path]
    proc = subprocess.run(export_cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(sqlite_path):
        print(f"WARNING: nsys export failed for cell {row.test_point_id} config={row.config} "
              f"-- dropping. stderr:\n{proc.stderr.strip()}", file=sys.stderr)
        os.remove(rep_path)
        return None

    try:
        metrics = parse_nsys_sqlite.compute_overlap(sqlite_path)
        if not metrics["name_filtered"]:
            print(f"NOTE: cell {row.test_point_id} config={row.config}: could not resolve kernel "
                  f"names in this nsys sqlite export -- overlap computed over ALL kernel intervals "
                  f"(fillKernel init included, negligible for >=10 trials)", file=sys.stderr)
    finally:
        # Disk hygiene (prompt: do not let traces accumulate across the run).
        os.remove(rep_path)
        os.remove(sqlite_path)

    out.update(
        kernel_instances=metrics["kernel_instances"],
        union_busy_ms=f"{metrics['union_busy_ms']:.6f}",
        concurrent_ms=f"{metrics['concurrent_ms']:.6f}",
        overlap_ratio=f"{metrics['overlap_ratio']:.4f}",
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
              f"peak-bandwidth test point per mode, computed from this CSV):")
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
        print(f"NOTE: {timed_out} cell(s) timed out (overlap_ratio recorded as NaN) -- "
              f"see WARNINGs above", file=sys.stderr)


if __name__ == "__main__":
    main()
