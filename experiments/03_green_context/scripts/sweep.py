#!/usr/bin/env python3
"""Phase 3 v3 sweep driver: shared vs green-context, across a per-kernel size
sweep ALIGNED to Phase 2's own grid (plus a small-end extension), across SM
partition ratios. Runnable from anywhere.

v3 changes vs v2 (prompts/03_green_context_v3.md Change 1 -- Changes 2/3 live in
scripts/plot.py and scripts/sweep_reuse.py respectively):
  - The v2 sweep used its own 1.8x geometric grid (65536, 117965, 212337, ...),
    which didn't line up with Phase 2's sizes -- only the 3 anchors coincided,
    so Phase 1/2/3 curves couldn't be overlaid at the same x positions. v3
    instead LITERALLY REUSES Phase 2's own `symmetric_sizes_bytes()` /
    `asymmetric_k1_sizes_bytes(k)` functions (imported directly from
    experiments/02_two_kernel_size/scripts/gen_config.py, not re-derived) so
    the two phases' grids can never drift apart again, prepending a small-end
    extension so the green-context L1/scheduling regime is still covered.
  - Phase 2's 3 roofline anchors (786432, 917504 symmetric; 2097152 asymmetric)
    now fall EXACTLY on grid points at this resolution, so anchor tagging is an
    exact-match snap onto an EXISTING grid cell (is_anchor=True set in place),
    not a separate duplicate cell like v2's `*_anchor_<i>_<bytes>` rows.

v2 behavior kept as-is: block counts are only a SEED (`--blocks0-seed`/
`--blocks1-seed`) for phase3_bench's in-context local search, which prints the
ACTUAL saturated blocks_k0/blocks_k1 + plateau_reached; this script never
decides the final block count.

This script owns the outer sweep (which the C++ binary does not know about);
`phase3_bench` measures exactly one cell per invocation and prints one CSV
row to stdout. This script:
  1. reads Phase 2's recommended_phase3_test_points and asymmetric_k_used_bytes
     (for grid alignment + anchor labeling) from
     experiments/02_two_kernel_size/findings.json, and saturation-search seeds
     + tpb from experiments/01_single_kernel_size/findings.json, at RUN TIME
     -- never hard-coded (00_conventions.md #2). Phase 2's grid-generating
     FUNCTIONS (symmetric_sizes_bytes/asymmetric_k1_sizes_bytes) are imported
     directly from its scripts/gen_config.py -- these need no upstream run,
     they're pure size-list generators, so the sweep itself never depends on
     Phase 2 having been executed, only the anchor labels and exact `k` do.
  2. falls back to placeholder defaults with a loud TODO warning if either
     upstream findings.json is absent -- it does NOT fabricate upstream
     numbers, it only supplies its own placeholder seeds/k so the harness is
     runnable standalone.
  3. invokes the built binary once per (test_point, config, sm_split) cell;
     the binary itself saturates blocks_k0/blocks_k1 in context (v2 Change 1).
  4. joins each green row back to its test point's shared baseline to fill
     delta_vs_shared_pct, and writes results/phase3_results.csv.

Use --dry-run to print the planned cells (and the per-SM working-set context
for each size) without needing a built binary or a CUDA device.
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

# Column order MUST match phase3_bench.cu's final printf exactly.
CSV_HEADER = (
    "test_point_id,mode,k0_bytes,k1_bytes,config,sm_split_k0,sm_split_k1,"
    "blocks_k0,blocks_k1,threads_per_block,trials,plateau_reached,wall_ms_median,"
    "agg_GBps_median,k0_GBps_median,k1_GBps_median,delta_vs_shared_pct,gpu_clock_mhz,"
    "power_mode,soc_temp_c,cuda_version,driver_version"
)

# TODO(read from phase1 findings): replaced by saturation_blocks_by_size /
# recommended_threads_per_block once Phase 1 has been run.
DEFAULT_TPB = 256
DEFAULT_BLOCKS_SEED = 64

SYMMETRIC_SPLITS = [(4, 12), (6, 10), (8, 8), (10, 6), (12, 4)]
NUM_SMS = 16
L1_BYTES_PER_SM = 192 * 1024

# ---- v3 Change 1: reuse Phase 2's exact size-grid functions (never re-derive
# with a different ratio -- that is what caused the v2/Phase-2 x-axis mismatch
# this patch fixes). ----
PHASE2_SCRIPTS_DIR = os.path.join(REPO_ROOT, "experiments", "02_two_kernel_size", "scripts")
sys.path.insert(0, PHASE2_SCRIPTS_DIR)
import gen_config as phase2_gen_config  # noqa: E402 (import after sys.path.insert by design)

MiB = 1024 * 1024
# Small-end extension (prompts/03_green_context_v3.md Change 1): Phase 2's grids
# start at 0.125 MiB (symmetric) / 0.125*k (asymmetric), which never reaches the
# green-context L1/scheduling regime (per-SM working set near 192 KB/SM). Prepend
# these so that regime is still resolved; everything above is Phase 2's own list,
# untouched.
SMALL_END_SYMMETRIC_MIB = [0.03125, 0.0625]          # 32 KiB, 64 KiB
SMALL_END_ASYMMETRIC_K1_FRACS = [0.03125, 0.0625]    # same fractions, applied to k

ASYMMETRIC_K0_FIXED_BYTES = 1 * 1024 * 1024
# TODO(read from phase2 findings): fallback asymmetric crossover k (Phase 2's
# `asymmetric_k_used_bytes`) if experiments/02_two_kernel_size/findings.json is
# missing -- 2 MiB matches Phase 2's own DEFAULT/measured k so the grid is right
# even before Phase 2 has been run for real.
DEFAULT_ASYMMETRIC_K_BYTES = 2 * 1024 * 1024


def build_symmetric_sweep_sizes():
    """Phase 2's exact symmetric per-kernel size grid
    (`gen_config.symmetric_sizes_bytes()`) plus the small-end extension."""
    small = [int(round(x * MiB)) for x in SMALL_END_SYMMETRIC_MIB]
    return small + phase2_gen_config.symmetric_sizes_bytes()


def build_asymmetric_k1_sizes(k_bytes):
    """Phase 2's exact asymmetric K1 grid (`gen_config.asymmetric_k1_sizes_bytes`,
    fractions of the crossover k) plus the small-end extension (also fractions
    of k, so it scales with whatever k this run actually has)."""
    small = [int(round(f * k_bytes)) for f in SMALL_END_ASYMMETRIC_K1_FRACS if int(round(f * k_bytes)) > 0]
    return sorted(set(small + phase2_gen_config.asymmetric_k1_sizes_bytes(k_bytes)))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def nearest_saturation_blocks(sat_blocks_by_size, size_bytes):
    if not sat_blocks_by_size:
        return DEFAULT_BLOCKS_SEED
    keys = sorted(int(k) for k in sat_blocks_by_size.keys())
    nearest = min(keys, key=lambda k: abs(k - size_bytes))
    return int(sat_blocks_by_size[str(nearest)])


def asymmetric_splits(k0_bytes, k1_bytes):
    # Tegra green-context rule: the split's minCount (K0's share) must be a
    # multiple of 2, so round the size-proportional target to the nearest even
    # SM count before sweeping its +/-2 neighbors.
    total = k0_bytes + k1_bytes
    target0 = round(NUM_SMS * k0_bytes / total / 2) * 2
    target0 = max(2, min(NUM_SMS - 2, target0))
    candidates = sorted({max(2, min(NUM_SMS - 2, target0 + d)) for d in (-2, 0, 2)})
    return [(c, NUM_SMS - c) for c in candidates]


def per_sm_working_set_bytes(per_kernel_bytes, sm_count):
    """~2*S/sm_k (OVERVIEW.md: read footprint = 2*S; Change 2's per-SM working
    set context). Used only for --dry-run annotation / README-style reporting,
    not for the actual green-split sweep."""
    return 2.0 * per_kernel_bytes / max(sm_count, 1)


def build_test_points(phase2):
    """v3 Change 1: sizes come from Phase 2's own grid functions, so this grid
    lines up with Phase 2's (and Phase 1's) x positions exactly. Phase 2's
    recommended_phase3_test_points anchors now fall EXACTLY on existing grid
    points at this resolution (0.75/0.875 MiB symmetric; k itself asymmetric),
    so each anchor is snapped onto its matching grid cell in place
    (is_anchor=True, test_point_id renamed to include "anchor") rather than
    added as a separate duplicate cell -- prompt: "verify each anchor still
    appears exactly once"."""
    warnings = []

    if phase2 is None:
        warnings.append(
            "TODO(read from phase2 findings): experiments/02_two_kernel_size/findings.json "
            "not found -- using the fallback asymmetric crossover k="
            f"{DEFAULT_ASYMMETRIC_K_BYTES} bytes and no anchor labels this run. Re-run once "
            "Phase 2 exists so the grid uses the real k and anchors are labeled."
        )
        k_bytes = DEFAULT_ASYMMETRIC_K_BYTES
        anchors = []
    else:
        results = phase2.get("results", {})
        recommended = results.get("recommended_phase3_test_points")
        if not recommended:
            sys.exit("FATAL: experiments/02_two_kernel_size/findings.json is present but missing "
                     "required key results.recommended_phase3_test_points (00_conventions.md #2: "
                     "fail loudly, do not substitute a guess).")
        k_bytes = int(results.get("asymmetric_k_used_bytes", DEFAULT_ASYMMETRIC_K_BYTES))
        anchors = recommended

    sym_sizes = build_symmetric_sweep_sizes()
    asym_sizes = build_asymmetric_k1_sizes(k_bytes)

    points = []
    for s in sym_sizes:
        points.append({
            "mode": "symmetric", "test_point_id": f"sym_{s}",
            "k0_bytes": s, "k1_bytes": s, "is_anchor": False,
        })
    for s in asym_sizes:
        points.append({
            "mode": "asymmetric", "test_point_id": f"asym_{s}",
            "k0_bytes": ASYMMETRIC_K0_FIXED_BYTES, "k1_bytes": s, "is_anchor": False,
        })

    by_key = {(p["mode"], p["k0_bytes"], p["k1_bytes"]): p for p in points}
    for tp in anchors:
        mode = tp["mode"]
        if mode == "symmetric":
            sz = int(tp["per_kernel_bytes"])
            key = ("symmetric", sz, sz)
            size_tag = sz
        else:
            k0 = int(tp.get("k0_bytes", ASYMMETRIC_K0_FIXED_BYTES))
            k1 = int(tp["k1_bytes"])
            key = ("asymmetric", k0, k1)
            size_tag = k1
        match = by_key.get(key)
        if match is None:
            sys.exit(f"FATAL: Phase 2 anchor {tp} does not land on an exact Phase 3 v3 grid "
                     f"point (key={key}). The v3 prompt requires exact grid alignment (Change 1) "
                     f"-- this means build_symmetric_sweep_sizes/build_asymmetric_k1_sizes have "
                     f"drifted from Phase 2's gen_config.py functions. Fix the drift; do not "
                     f"silently snap to a nearby point.")
        match["is_anchor"] = True
        match["test_point_id"] = f"{'sym' if mode == 'symmetric' else 'asym'}_anchor_{size_tag}"

    return points, warnings


def build_plan(phase1, phase2):
    test_points, warnings = build_test_points(phase2)

    if phase1 is None:
        warnings.append(
            "TODO(read from phase1 findings): experiments/01_single_kernel_size/findings.json "
            "not found -- using placeholder tpb=256 / block-search seed=64 (DEFAULT_TPB / "
            "DEFAULT_BLOCKS_SEED in sweep.py). These are only SEEDS for phase3_bench's in-context "
            "saturation search (Change 1), so the measured plateau is unaffected in principle, but "
            "re-run once Phase 1 exists so the search starts from a real lower bound."
        )
        tpb = DEFAULT_TPB
        sat_blocks = {}
    else:
        results = phase1.get("results", {})
        tpb = int(results.get("recommended_threads_per_block", DEFAULT_TPB))
        sat_blocks = results.get("saturation_blocks_by_size", {})

    cells = []
    for tp in test_points:
        seed0 = nearest_saturation_blocks(sat_blocks, tp["k0_bytes"])
        seed1 = nearest_saturation_blocks(sat_blocks, tp["k1_bytes"])

        cells.append({
            "test_point_id": tp["test_point_id"], "mode": tp["mode"], "is_anchor": tp["is_anchor"],
            "k0_bytes": tp["k0_bytes"], "k1_bytes": tp["k1_bytes"],
            "config": "shared", "sm0": NUM_SMS, "sm1": NUM_SMS,
            "blocks0_seed": seed0, "blocks1_seed": seed1, "tpb": tpb,
        })

        splits = SYMMETRIC_SPLITS if tp["mode"] == "symmetric" else asymmetric_splits(tp["k0_bytes"], tp["k1_bytes"])
        for sm0, sm1 in splits:
            cells.append({
                "test_point_id": tp["test_point_id"], "mode": tp["mode"], "is_anchor": tp["is_anchor"],
                "k0_bytes": tp["k0_bytes"], "k1_bytes": tp["k1_bytes"],
                "config": "green", "sm0": sm0, "sm1": sm1,
                "blocks0_seed": seed0, "blocks1_seed": seed1, "tpb": tpb,
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
        "--blocks0-seed", str(cell["blocks0_seed"]),
        "--blocks1-seed", str(cell["blocks1_seed"]),
        "--tpb", str(cell["tpb"]),
        "--trials", str(trials),
    ]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode == 4:
        # phase3_bench: this SM ratio was invalid, or was rejected by the driver
        # (possibly discovered mid in-context block search). Skip the cell with
        # a warning instead of hard-failing the sweep.
        print(f"WARNING: skipping cell (SM ratio {cell['sm0']}:{cell['sm1']} rejected): "
              f"{proc.stderr.strip()}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        sys.exit(f"phase3_bench failed for cell {cell}: rc={proc.returncode}\n{proc.stderr}")
    if proc.stderr.strip():
        # e.g. "block search did not plateau" warnings -- surface them, not fatal.
        print(proc.stderr.strip(), file=sys.stderr)
    line = proc.stdout.strip().splitlines()[-1]
    return line


def fill_deltas(rows):
    """rows: list of CSV field-lists (matches CSV_HEADER order). Fills the
    delta_vs_shared_pct column by joining each row's test_point_id
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
        n_anchor = sum(1 for c in cells if c["is_anchor"])
        n_sym = len({c["k0_bytes"] for c in cells if c["mode"] == "symmetric"})
        n_asym = len({c["k1_bytes"] for c in cells if c["mode"] == "asymmetric"})
        print(f"Planned {len(cells)} cells ({n_anchor} at Phase 2 anchor sizes, "
              f"{n_sym} symmetric sizes, {n_asym} asymmetric K1 sizes -- grid aligned to "
              f"Phase 2's gen_config.py, v3 Change 1):")
        for c in cells:
            ws0 = per_sm_working_set_bytes(c["k0_bytes"], c["sm0"])
            near_l1 = " <=L1/SM" if ws0 <= L1_BYTES_PER_SM else ""
            print(f"  {c}  per_sm_working_set_k0={ws0:.0f}B{near_l1}")
        return

    if not os.path.exists(BIN_PATH):
        sys.exit(f"Binary not found: {BIN_PATH} (run scripts/build.sh first)")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    raw_rows = []
    skipped = 0
    for i, cell in enumerate(cells):
        print(f"[{i + 1}/{len(cells)}] {cell['test_point_id']} config={cell['config']} "
              f"sm={cell['sm0']}:{cell['sm1']}", file=sys.stderr)
        line = run_cell(cell, args.trials)
        if line is None:
            skipped += 1
            continue
        raw_rows.append(line.split(","))

    final_rows = fill_deltas(raw_rows)
    with open(CSV_PATH, "w") as f:
        f.write(CSV_HEADER + "\n")
        for r in final_rows:
            f.write(",".join(r) + "\n")

    idx = {name: i for i, name in enumerate(CSV_HEADER.split(","))}
    n_not_plateaued = sum(1 for r in final_rows if r[idx["plateau_reached"]] == "0")

    print(f"wrote {CSV_PATH}")
    if skipped:
        print(f"NOTE: {skipped} cell(s) skipped (invalid/rejected SM ratios -- see WARNINGs above)",
              file=sys.stderr)
    if n_not_plateaued:
        print(f"NOTE: {n_not_plateaued} cell(s) did not reach a block-count plateau within the cap "
              f"-- see WARNINGs above; treat those rows' throughput as a lower bound.", file=sys.stderr)
    if warnings:
        print("Reminder: this run used placeholder upstream values (see WARNINGs above) -- "
              "re-run once the missing findings.json exists.", file=sys.stderr)


if __name__ == "__main__":
    main()
