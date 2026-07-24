#!/usr/bin/env python3
"""Phase 3 v2 sweep driver: shared vs green-context, across a WIDENED per-kernel
size sweep (64 KB - 8 MB, symmetric and asymmetric) plus Phase 2's roofline
anchors, across SM partition ratios. Runnable from anywhere.

v2 changes vs the original sweep.py (prompts/03_green_context_v2.md):
  - Change 1: block counts are no longer looked up from Phase 1 and held fixed.
    This script now passes a per-size SEED (still the Phase 1 nearest-neighbor
    lookup, `nearest_saturation_blocks`) via --blocks0-seed/--blocks1-seed;
    `phase3_bench` itself runs an in-context local search from that seed and
    prints the ACTUAL saturated blocks_k0/blocks_k1 + plateau_reached in its
    CSV row. This script never decides the final block count anymore.
  - Change 2: the test-point list is no longer capped to Phase 2's 3 roofline
    points. It now includes a geometric per-kernel size sweep from ~64 KB to
    ~8 MB (symmetric: both kernels grown together; asymmetric: K0 fixed at
    1 MB, K1 swept) PLUS Phase 2's `recommended_phase3_test_points` re-added
    as explicitly-labeled "anchor" cells (id prefix `*_anchor_`) at their exact
    byte sizes, so they stay directly comparable to the original Phase 3 run.

This script owns the outer sweep (which the C++ binary does not know about);
`phase3_bench` measures exactly one cell per invocation and prints one CSV
row to stdout. This script:
  1. reads Phase 2's recommended_phase3_test_points (for anchor labeling only
     -- the sweep itself does NOT depend on Phase 2) from
     experiments/02_two_kernel_size/findings.json, and saturation-search seeds
     + tpb from experiments/01_single_kernel_size/findings.json, at RUN TIME
     -- never hard-coded (00_conventions.md #2).
  2. falls back to placeholder defaults with a loud TODO warning if either is
     absent -- it does NOT fabricate upstream numbers, it only supplies its
     own placeholder seeds so the harness is runnable standalone. The size
     sweep itself (Change 2) never needs a fallback: it is this phase's own,
     not read from upstream.
  3. invokes the built binary once per (test_point, config, sm_split) cell;
     the binary itself saturates blocks_k0/blocks_k1 in context (Change 1).
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

# ---- Change 2: Phase 3's OWN widened per-kernel size sweep ----
# ~1.5-2x geometric grid from ~64 KB (per-SM working set approaches the 192 KB/SM
# L1 once partitioned) up to ~8 MB (clearly DRAM-bound), per
# prompts/03_green_context_v2.md "Change 2". Not capped to Phase 2's 3 points.
SWEEP_SIZE_LO_BYTES = 64 * 1024
SWEEP_SIZE_HI_BYTES = 8 * 1024 * 1024
SWEEP_SIZE_RATIO = 1.8
ASYMMETRIC_K0_FIXED_BYTES = 1 * 1024 * 1024


def geometric_size_sweep(lo, hi, ratio):
    sizes = []
    s = float(lo)
    while s < hi * (1 - 1e-9):
        sizes.append(int(round(s)))
        s *= ratio
    sizes.append(int(hi))
    return sizes


SWEEP_SIZES = geometric_size_sweep(SWEEP_SIZE_LO_BYTES, SWEEP_SIZE_HI_BYTES, SWEEP_SIZE_RATIO)


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
    """Change 2: Phase 3's own size sweep, independent of Phase 2, plus Phase 2's
    recommended_phase3_test_points re-added as explicitly labeled anchor points
    at their EXACT byte sizes (not snapped to the nearest sweep-grid point) so
    they stay directly comparable to the original Phase 3 run."""
    warnings = []
    points = []

    for s in SWEEP_SIZES:
        points.append({
            "mode": "symmetric", "test_point_id": f"sym_{s}",
            "k0_bytes": s, "k1_bytes": s, "is_anchor": False,
        })
    for s in SWEEP_SIZES:
        points.append({
            "mode": "asymmetric", "test_point_id": f"asym_{s}",
            "k0_bytes": ASYMMETRIC_K0_FIXED_BYTES, "k1_bytes": s, "is_anchor": False,
        })

    if phase2 is None:
        warnings.append(
            "TODO(read from phase2 findings): experiments/02_two_kernel_size/findings.json "
            "not found -- the widened size sweep (Change 2) runs regardless, but no "
            "Phase 2 roofline anchors are labeled in this run. Re-run once Phase 2 exists "
            "so results stay comparable to the original Phase 3 run."
        )
    else:
        results = phase2.get("results", {})
        recommended = results.get("recommended_phase3_test_points")
        if not recommended:
            sys.exit("FATAL: experiments/02_two_kernel_size/findings.json is present but missing "
                     "required key results.recommended_phase3_test_points (00_conventions.md #2: "
                     "fail loudly, do not substitute a guess).")
        for i, tp in enumerate(recommended):
            mode = tp["mode"]
            if mode == "symmetric":
                sz = int(tp["per_kernel_bytes"])
                points.append({
                    "mode": "symmetric", "test_point_id": f"sym_anchor_{i}_{sz}",
                    "k0_bytes": sz, "k1_bytes": sz, "is_anchor": True,
                })
            else:
                k0 = int(tp.get("k0_bytes", ASYMMETRIC_K0_FIXED_BYTES))
                k1 = int(tp["k1_bytes"])
                points.append({
                    "mode": "asymmetric", "test_point_id": f"asym_anchor_{i}_{k1}",
                    "k0_bytes": k0, "k1_bytes": k1, "is_anchor": True,
                })

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
        print(f"Planned {len(cells)} cells ({n_anchor} at Phase 2 anchor sizes, "
              f"{len(SWEEP_SIZES)} sizes/mode in the widened sweep, "
              f"per-kernel size range {SWEEP_SIZE_LO_BYTES}-{SWEEP_SIZE_HI_BYTES} bytes, "
              f"ratio {SWEEP_SIZE_RATIO}x):")
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
