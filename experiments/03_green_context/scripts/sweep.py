#!/usr/bin/env python3
"""Phase 3 sweep driver: shared vs green-context, at Phase 2's roofline test
points, across SM partition ratios. Runnable from anywhere.

This script owns the outer sweep (which the C++ binary does not know about);
`phase3_bench` measures exactly one cell per invocation and prints one CSV
row to stdout. This script:
  1. reads test-point sizes from experiments/02_two_kernel_size/findings.json
     and saturation/tpb from experiments/01_single_kernel_size/findings.json,
     at RUN TIME -- never hard-coded (00_conventions.md #2).
  2. falls back to placeholder defaults with a loud TODO warning if either is
     absent (per prompts/03_green_context.md "Dependency" section) --
     it does NOT fabricate upstream numbers, it only supplies its own
     placeholder test points so the harness is runnable standalone.
  3. invokes the built binary once per (test_point, config, sm_split) cell.
  4. joins each green row back to its test point's shared baseline to fill
     delta_vs_shared_pct, and writes results/phase3_results.csv.

Use --dry-run to print the planned cells without needing a built binary or
a CUDA device (useful for reviewing the sweep plan off-device).
"""
import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
BIN_PATH = os.path.join(PHASE_DIR, "build", "phase3_bench")
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_results.csv")

PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")
PHASE2_FINDINGS = os.path.join(REPO_ROOT, "experiments", "02_two_kernel_size", "findings.json")

CSV_HEADER = (
    "test_point_id,mode,k0_bytes,k1_bytes,config,sm_split_k0,sm_split_k1,"
    "blocks_k0,blocks_k1,threads_per_block,trials,wall_ms_median,agg_GBps_median,"
    "k0_GBps_median,k1_GBps_median,delta_vs_shared_pct,gpu_clock_mhz,power_mode,"
    "soc_temp_c,cuda_version,driver_version"
)

# Fallback placeholders, only used if experiments/02_two_kernel_size/findings.json
# is absent. TODO(read from phase2 findings): replace by reading the real
# recommended_phase3_test_points once Phase 2 has been run.
DEFAULT_TEST_POINTS = [
    {"mode": "symmetric", "test_point_id": "sym_onset", "k0_bytes": 4 * 1024 * 1024, "k1_bytes": 4 * 1024 * 1024},
    {"mode": "symmetric", "test_point_id": "sym_ninety_pct", "k0_bytes": int(3.6 * 1024 * 1024), "k1_bytes": int(3.6 * 1024 * 1024)},
    {"mode": "asymmetric", "test_point_id": "asym_at_k", "k0_bytes": 1 * 1024 * 1024, "k1_bytes": 8 * 1024 * 1024},
]

# TODO(read from phase1 findings): replaced by saturation_blocks_by_size /
# recommended_threads_per_block once Phase 1 has been run.
DEFAULT_TPB = 256
DEFAULT_BLOCKS = 256

SYMMETRIC_SPLITS = [(4, 12), (6, 10), (8, 8), (10, 6), (12, 4)]
NUM_SMS = 16


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def nearest_saturation_blocks(sat_blocks_by_size, size_bytes):
    if not sat_blocks_by_size:
        return DEFAULT_BLOCKS
    keys = sorted(int(k) for k in sat_blocks_by_size.keys())
    nearest = min(keys, key=lambda k: abs(k - size_bytes))
    return int(sat_blocks_by_size[str(nearest)])


def asymmetric_splits(k0_bytes, k1_bytes):
    total = k0_bytes + k1_bytes
    target0 = round(NUM_SMS * k0_bytes / total)
    target0 = max(2, min(NUM_SMS - 2, target0))
    candidates = sorted({max(2, min(NUM_SMS - 2, target0 + d)) for d in (-2, 0, 2)})
    return [(c, NUM_SMS - c) for c in candidates]


def build_plan(phase1, phase2):
    warnings = []

    if phase2 is None:
        warnings.append(
            "TODO(read from phase2 findings): experiments/02_two_kernel_size/findings.json "
            "not found -- using placeholder test points (DEFAULT_TEST_POINTS in sweep.py). "
            "Do not trust these results as final; re-run once Phase 2 exists."
        )
        test_points = DEFAULT_TEST_POINTS
    else:
        results = phase2.get("results", {})
        recommended = results.get("recommended_phase3_test_points")
        if not recommended:
            sys.exit("FATAL: experiments/02_two_kernel_size/findings.json is present but missing "
                     "required key results.recommended_phase3_test_points (00_conventions.md #2: "
                     "fail loudly, do not substitute a guess).")
        test_points = []
        for i, tp in enumerate(recommended):
            mode = tp["mode"]
            if mode == "symmetric":
                k0 = k1 = int(tp["per_kernel_bytes"])
                tp_id = tp.get("test_point_id", f"sym_{i}")
            else:
                k0 = int(tp.get("k0_bytes", 1 * 1024 * 1024))
                k1 = int(tp["k1_bytes"])
                tp_id = tp.get("test_point_id", f"asym_{i}")
            test_points.append({"mode": mode, "test_point_id": tp_id, "k0_bytes": k0, "k1_bytes": k1})

    if phase1 is None:
        warnings.append(
            "TODO(read from phase1 findings): experiments/01_single_kernel_size/findings.json "
            "not found -- using placeholder tpb=256 / blocks=256 (DEFAULT_TPB/DEFAULT_BLOCKS in "
            "sweep.py). Do not trust these results as final; re-run once Phase 1 exists."
        )
        tpb = DEFAULT_TPB
        sat_blocks = {}
    else:
        results = phase1.get("results", {})
        tpb = int(results.get("recommended_threads_per_block", DEFAULT_TPB))
        sat_blocks = results.get("saturation_blocks_by_size", {})

    cells = []
    for tp in test_points:
        blocks0 = nearest_saturation_blocks(sat_blocks, tp["k0_bytes"])
        blocks1 = nearest_saturation_blocks(sat_blocks, tp["k1_bytes"])

        cells.append({
            "test_point_id": tp["test_point_id"], "mode": tp["mode"],
            "k0_bytes": tp["k0_bytes"], "k1_bytes": tp["k1_bytes"],
            "config": "shared", "sm0": NUM_SMS, "sm1": NUM_SMS,
            "blocks0": blocks0, "blocks1": blocks1, "tpb": tpb,
        })

        splits = SYMMETRIC_SPLITS if tp["mode"] == "symmetric" else asymmetric_splits(tp["k0_bytes"], tp["k1_bytes"])
        for sm0, sm1 in splits:
            cells.append({
                "test_point_id": tp["test_point_id"], "mode": tp["mode"],
                "k0_bytes": tp["k0_bytes"], "k1_bytes": tp["k1_bytes"],
                "config": "green", "sm0": sm0, "sm1": sm1,
                "blocks0": blocks0, "blocks1": blocks1, "tpb": tpb,
            })

    return cells, warnings


def run_cell(cell, trials):
    args = [
        BIN_PATH,
        "--test-point-id", cell["test_point_id"],
        "--mode", cell["mode"],
        "--config", cell["config"],
        "--k0-bytes", str(cell["k0_bytes"]),
        "--k1-bytes", str(cell["k1_bytes"]),
        "--sm0", str(cell["sm0"]),
        "--sm1", str(cell["sm1"]),
        "--blocks0", str(cell["blocks0"]),
        "--blocks1", str(cell["blocks1"]),
        "--tpb", str(cell["tpb"]),
        "--trials", str(trials),
    ]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"phase3_bench failed for cell {cell}: rc={proc.returncode}\n{proc.stderr}")
    line = proc.stdout.strip().splitlines()[-1]
    return line


def fill_deltas(rows):
    """rows: list of CSV field-lists (matches CSV_HEADER order). Fills the
    delta_vs_shared_pct column (index 15) by joining each row's test_point_id
    to that test point's shared-config row."""
    idx = {name: i for i, name in enumerate(CSV_HEADER.split(","))}
    shared_agg = {}
    for r in rows:
        if r[idx["config"]] == "shared":
            shared_agg[r[idx["test_point_id"]]] = float(r[idx["agg_GBps_median"]])

    out = []
    for r in rows:
        r = list(r)
        base = shared_agg.get(r[idx["test_point_id"]])
        agg = float(r[idx["agg_GBps_median"]])
        if base is None or base == 0:
            r[idx["delta_vs_shared_pct"]] = "0.0"
        else:
            r[idx["delta_vs_shared_pct"]] = f"{(agg - base) / base * 100.0:.3f}"
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="print planned cells, run nothing")
    args = ap.parse_args()

    phase1 = load_json(PHASE1_FINDINGS)
    phase2 = load_json(PHASE2_FINDINGS)
    cells, warnings = build_plan(phase1, phase2)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if args.dry_run:
        print(f"Planned {len(cells)} cells:")
        for c in cells:
            print(f"  {c}")
        return

    if not os.path.exists(BIN_PATH):
        sys.exit(f"Binary not found: {BIN_PATH} (run scripts/build.sh first)")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    raw_rows = []
    for i, cell in enumerate(cells):
        print(f"[{i + 1}/{len(cells)}] {cell['test_point_id']} config={cell['config']} "
              f"sm={cell['sm0']}:{cell['sm1']}", file=sys.stderr)
        line = run_cell(cell, args.trials)
        raw_rows.append(line.split(","))

    final_rows = fill_deltas(raw_rows)
    with open(CSV_PATH, "w") as f:
        f.write(CSV_HEADER + "\n")
        for r in final_rows:
            f.write(",".join(r) + "\n")

    print(f"wrote {CSV_PATH}")
    if warnings:
        print("Reminder: this run used placeholder upstream values (see WARNINGs above) -- "
              "re-run once the missing findings.json exists.", file=sys.stderr)


if __name__ == "__main__":
    main()
