#!/usr/bin/env python3
"""Phase 3 -- full-grid reuse_N=32 overlay (prompts/05_unified_size_grid_and_plots.md
Change 5). Runnable from anywhere.

Why this exists: `green_vs_shared_combined_footprint.png` (scripts/plot_combined_footprint.py)
was drawn from the reuse_N=1 main sweep (results/phase3_results.csv), where the aggregate
curve is dominated by cold-miss DRAM traffic and green loses at every point -- reuse_N=1 can
never show green's intended mechanism (stabilized inter-launch L1 residency), which only
exists when there IS inter-launch reuse. The existing 4-point N-sweep
(results/phase3_reuse_results.csv, scripts/sweep_reuse.py) showed green's only win
(+33.5% at sym_32768) and worst loss (-26.0% at sym_917504) at N=32, but only at 4 points --
not enough to draw the full curve. This script re-measures the FULL symmetric grid at a
single fixed N=32.

Cost control (do NOT sweep every SM split at N=32 -- each cell is 32x the work of an N=1
cell): for each symmetric size, only two cells are measured -- `shared`, and the single
green SM split that scripts/sweep.py's reuse=1 run already found best for that size (the
max agg_GBps_median green row in results/phase3_results.csv -- the SAME selection
scripts/plot.py / scripts/plot_combined_footprint.py already use for their "best green"
series). That split is NOT re-searched here; this is therefore a *conditional* comparison
(N=1-optimal split, not necessarily N=32-optimal) -- label it as such wherever it's shown.
Block counts are held fixed across N exactly like the existing reuse overlay
(--fixed-blocks0/1 --reuse-overlay), reusing scripts/sweep_reuse.py's
find_configs_for_size() (same selection, so this and the 4-point overlay agree at their
shared sizes) and verify_stable_and_fix_blocks() (one stability check at CHECK_N=4, element-
wise max on disagreement).

Writes results/phase3_reuse32_results.csv (own file). Does NOT touch
results/phase3_results.csv, results/phase3_reuse_results.csv, or findings.json.

Use --dry-run to print the planned cells without needing a built binary or CUDA device
(skips the stability-check search, same contract as scripts/sweep_reuse.py --dry-run).
"""
import argparse
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import sweep as sw  # noqa: E402
import sweep_reuse as sr  # noqa: E402 -- reuse find_configs_for_size / verify_stable_and_fix_blocks

PHASE_DIR = sw.PHASE_DIR
REUSE32_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_reuse32_results.csv")
FIXED_REUSE_N = 32

REUSE32_CSV_HEADER = sr.REUSE_CSV_HEADER  # identical schema to the 4-point overlay


def all_symmetric_sizes(df):
    sym = df[df["mode"] == "symmetric"]
    if sym.empty:
        sys.exit("FATAL: no symmetric rows in results/phase3_results.csv -- run scripts/sweep.py first.")
    return sorted(int(s) for s in sym.k0_bytes.unique())


def build_plan(df, trials, verify_stability=True):
    sizes = all_symmetric_sizes(df)
    plan = []
    for size_bytes in sizes:
        configs = sr.find_configs_for_size(df, size_bytes)
        for config, cfg in configs.items():
            if verify_stability:
                fixed0, fixed1 = sr.verify_stable_and_fix_blocks(size_bytes, config, cfg)
                stability_note = "verified"
            else:
                fixed0, fixed1 = cfg["blocks0"], cfg["blocks1"]
                stability_note = "UNVERIFIED (dry-run: reuse=1 blocks shown as-is, no device call)"
            plan.append({
                "test_point_id": f"reuse32_sym_{size_bytes}", "mode": "symmetric",
                "k0_bytes": size_bytes, "k1_bytes": size_bytes, "config": config,
                "sm0": cfg["sm0"], "sm1": cfg["sm1"], "tpb": cfg["tpb"],
                "blocks0": fixed0, "blocks1": fixed1, "reuse_n": FIXED_REUSE_N, "trials": trials,
                "stability": stability_note,
            })
    return plan, sizes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(sw.CSV_PATH):
        sys.exit(f"FATAL: {sw.CSV_PATH} not found -- run scripts/sweep.py first "
                 f"(this reads back its reuse=1 saturated blocks + best-green splits).")
    df = pd.read_csv(sw.CSV_PATH)

    if not os.path.exists(sw.BIN_PATH) and not args.dry_run:
        sys.exit(f"Binary not found: {sw.BIN_PATH} (run scripts/build.sh first)")

    plan, sizes = build_plan(df, args.trials, verify_stability=not args.dry_run)
    print(f"Reuse32 overlay sizes (symmetric, ALL {len(sizes)} bytes/kernel in the grid): {sizes}",
          file=sys.stderr)

    if args.dry_run:
        print(f"Planned {len(plan)} cells at reuse_N={FIXED_REUSE_N} "
              f"({len(sizes)} sizes x 2 configs [shared + N=1-optimal green split]):")
        for c in plan:
            print(f"  {c}")
        return

    rows = []
    for i, c in enumerate(plan):
        print(f"[{i + 1}/{len(plan)}] {c['test_point_id']} config={c['config']} "
              f"reuse_N={c['reuse_n']}", file=sys.stderr)
        line = sr.run_bench([
            "--test-point-id", c["test_point_id"], "--mode", c["mode"], "--config", c["config"],
            "--k0-bytes", str(c["k0_bytes"]), "--k1-bytes", str(c["k1_bytes"]),
            "--sm0", str(c["sm0"]), "--sm1", str(c["sm1"]),
            "--fixed-blocks0", str(c["blocks0"]), "--fixed-blocks1", str(c["blocks1"]),
            "--tpb", str(c["tpb"]), "--trials", str(c["trials"]),
            "--reuse-n", str(c["reuse_n"]), "--reuse-overlay",
        ])
        rows.append(line)

    os.makedirs(os.path.dirname(REUSE32_CSV_PATH), exist_ok=True)
    with open(REUSE32_CSV_PATH, "w") as f:
        f.write(REUSE32_CSV_HEADER + "\n")
        for r in rows:
            f.write(r + "\n")
    print(f"wrote {REUSE32_CSV_PATH}")
    print("Reminder: results/phase3_results.csv, results/phase3_reuse_results.csv, and "
          "findings.json are untouched by this script. Green splits here are the N=1-optimal "
          "split (read back from phase3_results.csv, NOT re-searched at N=32) -- a conditional "
          "comparison, labeled as such on green_vs_shared_combined_footprint_n32.png. Run "
          "scripts/plot_combined_footprint.py to regenerate that figure from this CSV.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
