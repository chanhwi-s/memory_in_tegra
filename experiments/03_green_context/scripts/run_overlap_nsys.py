#!/usr/bin/env python3
"""Phase 3 -- verify concurrent overlap with nsys, averaged across each run
(prompts/03_green_context/03_verify_overlap_nsys.md). Runnable from anywhere.

For every cell the throughput sweep measures (scripts/sweep.py: build_plan +
build_binary_args -- imported here, never re-derived, so the exact same sizes
and shared/green configs are covered), profiles that same phase3_bench
invocation under `nsys profile -t cuda`, exports the trace to sqlite, and
computes the label-free overlap metric (scripts/parse_nsys_sqlite.py):

    union_busy_time  = total time >= 1 kernel executing
    concurrent_time  = total time >= 2 kernels executing simultaneously
    overlap_ratio    = concurrent_time / union_busy_time

VERIFICATION ONLY. nsys tracing adds overhead; do not read timings out of
these traces as throughput -- that stays in results/phase3_results.csv from
the untraced sweep. Traces are written to a temp dir and deleted (.nsys-rep
+ .sqlite) immediately after each cell is parsed (disk hygiene: profiling
every cell x both configs produces a lot of them).

Use --dry-run to print the planned cells (same as scripts/sweep.py --dry-run)
without needing nsys or a CUDA device.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
BIN_PATH = os.path.join(PHASE_DIR, "build", "phase3_bench")
CSV_PATH = os.path.join(PHASE_DIR, "results", "overlap_nsys.csv")

sys.path.insert(0, SCRIPT_DIR)
import sweep  # noqa: E402 -- reuse build_plan/build_binary_args, never re-derive the cell list
import parse_nsys_sqlite  # noqa: E402

# Column order for the new CSV (prompts/03_green_context/03_verify_overlap_nsys.md).
CSV_HEADER = (
    "test_point_id,mode,config,k0_bytes,k1_bytes,combined_read_footprint_bytes,reuse_N,"
    "kernel_instances,union_busy_ms,concurrent_ms,overlap_ratio,"
    "gpu_clock_mhz,power_mode,soc_temp_c,cuda_version,driver_version"
)

# sweep.py's build_binary_args() never passes --reuse-n for the cells it
# generates, so phase3_bench's default (reuseN=1) applies to every cell
# profiled here -- this is the actual parameter used, not a placeholder.
REUSE_N = 1

SWEEP_ROW_IDX = {name: i for i, name in enumerate(sweep.CSV_HEADER.split(","))}


def check_nsys_available():
    if shutil.which("nsys") is None:
        sys.exit("FATAL: `nsys` not found on PATH -- this verification step requires the "
                 "NVIDIA Nsight Systems CLI (ships with JetPack/CUDA on the Jetson). Report "
                 "this in the worklog rather than skipping verification silently.")


def profile_cell(cell, trials, tmp_dir):
    """Run this cell's phase3_bench invocation under `nsys profile`, export to
    sqlite, compute the overlap metric, and return a CSV row (or None to skip
    -- invalid SM ratio, same convention as scripts/sweep.py's run_cell)."""
    base = os.path.join(tmp_dir, "cell")
    rep_path = base + ".nsys-rep"
    sqlite_path = base + ".sqlite"
    for p in (rep_path, sqlite_path):
        if os.path.exists(p):
            os.remove(p)

    bin_args = sweep.build_binary_args(cell, trials)
    profile_cmd = ["nsys", "profile", "-t", "cuda", "--force-overwrite=true", "-o", base] + bin_args
    proc = subprocess.run(profile_cmd, capture_output=True, text=True)

    if proc.returncode == 4:
        print(f"WARNING: skipping cell (SM ratio {cell['sm0']}:{cell['sm1']} rejected): "
              f"{proc.stderr.strip()}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        # Verification-only tool: warn and skip rather than aborting the whole
        # (expensive, trace-heavy) run over one bad cell.
        print(f"WARNING: nsys profile failed for cell {cell['test_point_id']} "
              f"config={cell['config']} (rc={proc.returncode}) -- skipping. stderr:\n"
              f"{proc.stderr.strip()}", file=sys.stderr)
        return None

    stdout_lines = proc.stdout.strip().splitlines()
    if not stdout_lines:
        print(f"WARNING: no stdout from traced phase3_bench for cell {cell['test_point_id']} "
              f"config={cell['config']} -- cannot recover env fields, skipping", file=sys.stderr)
        return None
    sweep_row = stdout_lines[-1].split(",")

    if not os.path.exists(rep_path):
        print(f"WARNING: nsys profile did not produce {rep_path} for cell "
              f"{cell['test_point_id']} config={cell['config']} -- skipping", file=sys.stderr)
        return None

    export_cmd = ["nsys", "export", "--type=sqlite", "--force-overwrite=true", rep_path]
    proc = subprocess.run(export_cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(sqlite_path):
        print(f"WARNING: nsys export failed for cell {cell['test_point_id']} "
              f"config={cell['config']} -- skipping. stderr:\n{proc.stderr.strip()}", file=sys.stderr)
        os.remove(rep_path)
        return None

    try:
        metrics = parse_nsys_sqlite.compute_overlap(sqlite_path)
        if not metrics["name_filtered"]:
            print(f"NOTE: cell {cell['test_point_id']} config={cell['config']}: could not resolve "
                  f"kernel names in this nsys sqlite export -- overlap computed over ALL kernel "
                  f"intervals (fillKernel init included, negligible for >=10 trials)", file=sys.stderr)
    finally:
        # Disk hygiene (prompt: do not let traces accumulate across the sweep).
        os.remove(rep_path)
        os.remove(sqlite_path)

    k0_bytes = int(sweep_row[SWEEP_ROW_IDX["k0_bytes"]])
    k1_bytes = int(sweep_row[SWEEP_ROW_IDX["k1_bytes"]])
    combined_footprint = 2 * k0_bytes + 2 * k1_bytes

    return [
        cell["test_point_id"], cell["mode"], cell["config"],
        str(k0_bytes), str(k1_bytes), str(combined_footprint), str(REUSE_N),
        str(metrics["kernel_instances"]), f"{metrics['union_busy_ms']:.6f}",
        f"{metrics['concurrent_ms']:.6f}", f"{metrics['overlap_ratio']:.4f}",
        sweep_row[SWEEP_ROW_IDX["gpu_clock_mhz"]], sweep_row[SWEEP_ROW_IDX["power_mode"]],
        sweep_row[SWEEP_ROW_IDX["soc_temp_c"]], sweep_row[SWEEP_ROW_IDX["cuda_version"]],
        sweep_row[SWEEP_ROW_IDX["driver_version"]],
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="print planned cells, profile nothing")
    args = ap.parse_args()

    phase1 = sweep.load_json(sweep.PHASE1_FINDINGS)
    phase2 = sweep.load_json(sweep.PHASE2_FINDINGS)
    cells, warnings = sweep.build_plan(phase1, phase2)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if args.dry_run:
        print(f"Planned {len(cells)} cells to profile with nsys (same cells as scripts/sweep.py):")
        for c in cells:
            print(f"  {c}")
        return

    check_nsys_available()
    if not os.path.exists(BIN_PATH):
        sys.exit(f"Binary not found: {BIN_PATH} (run scripts/build.sh first)")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    rows = []
    skipped = 0
    tmp_dir = tempfile.mkdtemp(prefix="phase3_nsys_")
    try:
        for i, cell in enumerate(cells):
            print(f"[{i + 1}/{len(cells)}] nsys profile: {cell['test_point_id']} "
                  f"config={cell['config']} sm={cell['sm0']}:{cell['sm1']}", file=sys.stderr)
            row = profile_cell(cell, args.trials, tmp_dir)
            if row is None:
                skipped += 1
                continue
            rows.append(row)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    with open(CSV_PATH, "w") as f:
        f.write(CSV_HEADER + "\n")
        for r in rows:
            f.write(",".join(r) + "\n")

    print(f"wrote {CSV_PATH}")
    if skipped:
        print(f"NOTE: {skipped} cell(s) skipped -- see WARNINGs above", file=sys.stderr)
    if warnings:
        print("Reminder: this run used placeholder upstream values (see WARNINGs above) -- "
              "re-run once the missing findings.json exists.", file=sys.stderr)


if __name__ == "__main__":
    main()
