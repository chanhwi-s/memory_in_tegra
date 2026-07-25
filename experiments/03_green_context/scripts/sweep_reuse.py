#!/usr/bin/env python3
"""Phase 3 v3 Change 3: reuse_N overlay -- a SEPARATE, additive diagnostic sweep
on top of the reuse=1 main sweep (scripts/sweep.py). Runnable from anywhere.

Why this exists (prompts/03_green_context_v3.md Change 3): the reuse=1 sweep can
only see green context's scheduling/occupancy isolation, not its predicted MAIN
benefit -- stabilizing L1 *inter-launch* reuse, which only exists at reuse_N>1
(OVERVIEW.md §1). This script re-measures a small representative SUBSET of
symmetric sizes across reuse_N in {1,2,4,8,16,32}: shared vs the best-green
split that scripts/sweep.py's reuse=1 run already found for that size (read
back from results/phase3_results.csv -- this script never re-sweeps SM splits).

Cost control: full 18-size x 6-split x 6-reuse_N would be enormous, so this is
capped to ~4-5 sizes x 2 configs x 6 reuse_N. Block counts are NOT re-searched
per reuse_N (that would multiply the cost further and isn't the point of this
overlay): the reuse=1 saturated blocks are read back from results/phase3_results.csv,
verified stable at one additional check N (=4, mirroring Phase 4's
searchAndVerifyStable -- element-wise max + a stderr NOTE if they disagree), and
then held fixed via phase3_bench's --fixed-blocks0/1 --reuse-overlay flags for
every reuse_N in the sweep (re-measuring N=1 and the check N too, at the final
verified blocks, so every point on the reuse curve is measured with IDENTICAL
block counts -- self-consistency over the tiny extra cost of a few re-runs).

Writes results/phase3_reuse_results.csv (own schema, with a reuse_N column).
Does NOT touch results/phase3_results.csv or findings.json (the Phase 4 handoff)
-- this overlay is diagnostic only, per the prompt.

Use --dry-run to print the planned measurement calls without needing a built
binary, a CUDA device, or even results/phase3_results.csv from a real run
(a synthetic df can't be dry-run without the main CSV existing, though --
--dry-run still requires the main sweep's CSV so it can show the real subset
sizes / blocks / splits it would use).
"""
import argparse
import os
import subprocess
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import sweep as sw  # reuse BIN_PATH, CSV_PATH, CSV_HEADER (v3: needs sweep.py's own path setup)

PHASE_DIR = sw.PHASE_DIR
REUSE_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_reuse_results.csv")

REUSE_NS = [1, 2, 4, 8, 16, 32]
CHECK_N = 4  # stability-check N, mirrors Phase 4's searchAndVerifyStable
DRAM_BOUND_TARGET_BYTES = 4 * 1024 * 1024

REUSE_CSV_HEADER = (
    "test_point_id,mode,k0_bytes,k1_bytes,config,sm_split_k0,sm_split_k1,"
    "blocks_k0,blocks_k1,threads_per_block,trials,reuse_N,wall_ms_median,"
    "agg_GBps_median,k0_GBps_median,k1_GBps_median,gpu_clock_mhz,power_mode,"
    "soc_temp_c,cuda_version,driver_version"
)


def select_subset_sizes(df):
    """~4-5 symmetric sizes: the smallest (L1/small), the size closest to 4 MiB
    (clearly DRAM-bound), and Phase 2's anchor sizes (786432, 917504) -- read
    dynamically from the just-completed v3 main sweep rather than hardcoded, so
    this still works if the grid changes upstream."""
    sym = df[df["mode"] == "symmetric"]
    if sym.empty:
        sys.exit("FATAL: no symmetric rows in results/phase3_results.csv -- run scripts/sweep.py first.")
    small = int(sym.k0_bytes.min())
    dram_bound = int(min(sym.k0_bytes.unique(), key=lambda s: abs(s - DRAM_BOUND_TARGET_BYTES)))
    anchor_sizes = sorted(int(s) for s in sym[sym.test_point_id.str.contains("anchor")].k0_bytes.unique())
    return sorted(set([small, dram_bound] + anchor_sizes))


def find_configs_for_size(df, size_bytes):
    """From the main sweep's CSV: the shared row's blocks, and the best-green
    row's split + blocks, for this symmetric size. Returns a dict per config."""
    sub = df[(df["mode"] == "symmetric") & (df.k0_bytes == size_bytes) & (df.k1_bytes == size_bytes)]
    shared = sub[sub.config == "shared"]
    green = sub[sub.config == "green"]
    if shared.empty:
        sys.exit(f"FATAL: no shared row for symmetric size {size_bytes} in results/phase3_results.csv.")
    tpb = int(shared.threads_per_block.iloc[0])
    out = {
        "shared": {"sm0": 16, "sm1": 16, "blocks0": int(shared.blocks_k0.iloc[0]),
                   "blocks1": int(shared.blocks_k1.iloc[0]), "tpb": tpb},
    }
    if not green.empty:
        best = green.loc[green.agg_GBps_median.idxmax()]
        out["green"] = {"sm0": int(best.sm_split_k0), "sm1": int(best.sm_split_k1),
                        "blocks0": int(best.blocks_k0), "blocks1": int(best.blocks_k1), "tpb": tpb}
    else:
        print(f"WARNING: no green rows for symmetric size {size_bytes} -- reuse overlay will "
              f"only cover shared for this size.", file=sys.stderr)
    return out


def run_bench(args_list):
    proc = subprocess.run([sw.BIN_PATH] + args_list, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"phase3_bench failed (rc={proc.returncode}): {' '.join(args_list)}\n{proc.stderr}")
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.stdout.strip().splitlines()[-1]


def search_blocks_at_reuse_n(size_bytes, config, sm0, sm1, tpb, reuse_n, seed0, seed1, trials=3):
    """Normal (non-overlay) phase3_bench invocation: runs the FULL in-context
    search (v2 Change 1) at the given reuse_N, seeded from the reuse=1 blocks.
    Used only for the stability check (v3 Change 3), never for the final
    reuse-sweep measurements (those use --fixed-blocks/--reuse-overlay)."""
    line = run_bench([
        "--test-point-id", "reuse_stability_check", "--mode", "symmetric", "--config", config,
        "--k0-bytes", str(size_bytes), "--k1-bytes", str(size_bytes),
        "--sm0", str(sm0), "--sm1", str(sm1),
        "--blocks0-seed", str(seed0), "--blocks1-seed", str(seed1),
        "--tpb", str(tpb), "--trials", str(trials), "--reuse-n", str(reuse_n),
    ])
    idx = {name: i for i, name in enumerate(sw.CSV_HEADER.split(","))}
    fields = line.split(",")
    return int(fields[idx["blocks_k0"]]), int(fields[idx["blocks_k1"]])


def verify_stable_and_fix_blocks(size_bytes, config, cfg):
    """v3 Change 3: 'verify the plateau block count is stable across a couple of
    N values, then hold it' (mirrors Phase 4's searchAndVerifyStable). Searches
    once more at CHECK_N; if it disagrees with the reuse=1 blocks, takes the
    element-wise max (never under-provisions) and logs the discrepancy."""
    b0_1, b1_1 = cfg["blocks0"], cfg["blocks1"]
    b0_n, b1_n = search_blocks_at_reuse_n(size_bytes, config, cfg["sm0"], cfg["sm1"], cfg["tpb"],
                                           CHECK_N, b0_1, b1_1)
    if b0_n == b0_1 and b1_n == b1_1:
        return b0_1, b1_1
    fixed0, fixed1 = max(b0_1, b0_n), max(b1_1, b1_n)
    print(f"NOTE: block saturation search NOT stable across reuse_N at size={size_bytes} "
          f"config={config} (N=1 -> {b0_1},{b1_1} ; N={CHECK_N} -> {b0_n},{b1_n}). Using the "
          f"element-wise max ({fixed0},{fixed1}) and holding it across the full reuse sweep.",
          file=sys.stderr)
    return fixed0, fixed1


def build_plan(df, trials, verify_stability=True):
    """verify_stability=False (--dry-run only) skips the stability-check search
    (it needs the built binary + a CUDA device) and previews the plan using the
    raw reuse=1 blocks, clearly labeled unverified -- matches sweep.py's
    --dry-run contract of never touching the device."""
    sizes = select_subset_sizes(df)
    plan = []
    for size_bytes in sizes:
        configs = find_configs_for_size(df, size_bytes)
        for config, cfg in configs.items():
            if verify_stability:
                fixed0, fixed1 = verify_stable_and_fix_blocks(size_bytes, config, cfg)
                stability_note = "verified"
            else:
                fixed0, fixed1 = cfg["blocks0"], cfg["blocks1"]
                stability_note = "UNVERIFIED (dry-run: reuse=1 blocks shown as-is, no device call)"
            for reuse_n in REUSE_NS:
                plan.append({
                    "test_point_id": f"reuse_sym_{size_bytes}", "mode": "symmetric",
                    "k0_bytes": size_bytes, "k1_bytes": size_bytes, "config": config,
                    "sm0": cfg["sm0"], "sm1": cfg["sm1"], "tpb": cfg["tpb"],
                    "blocks0": fixed0, "blocks1": fixed1, "reuse_n": reuse_n, "trials": trials,
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
                 f"(the reuse overlay reads back its reuse=1 saturated blocks + best-green splits).")
    df = pd.read_csv(sw.CSV_PATH)

    if not os.path.exists(sw.BIN_PATH) and not args.dry_run:
        sys.exit(f"Binary not found: {sw.BIN_PATH} (run scripts/build.sh first)")

    plan, sizes = build_plan(df, args.trials, verify_stability=not args.dry_run)
    print(f"Reuse overlay subset sizes (symmetric, bytes/kernel): {sizes}", file=sys.stderr)

    if args.dry_run:
        print(f"Planned {len(plan)} reuse-overlay cells:")
        for c in plan:
            print(f"  {c}")
        return

    rows = []
    for i, c in enumerate(plan):
        print(f"[{i + 1}/{len(plan)}] {c['test_point_id']} config={c['config']} "
              f"reuse_N={c['reuse_n']}", file=sys.stderr)
        line = run_bench([
            "--test-point-id", c["test_point_id"], "--mode", c["mode"], "--config", c["config"],
            "--k0-bytes", str(c["k0_bytes"]), "--k1-bytes", str(c["k1_bytes"]),
            "--sm0", str(c["sm0"]), "--sm1", str(c["sm1"]),
            "--fixed-blocks0", str(c["blocks0"]), "--fixed-blocks1", str(c["blocks1"]),
            "--tpb", str(c["tpb"]), "--trials", str(c["trials"]),
            "--reuse-n", str(c["reuse_n"]), "--reuse-overlay",
        ])
        rows.append(line)

    os.makedirs(os.path.dirname(REUSE_CSV_PATH), exist_ok=True)
    with open(REUSE_CSV_PATH, "w") as f:
        f.write(REUSE_CSV_HEADER + "\n")
        for r in rows:
            f.write(r + "\n")
    print(f"wrote {REUSE_CSV_PATH}")
    print("Reminder: results/phase3_results.csv and findings.json are untouched by this script "
          "(the reuse overlay is additive/diagnostic-only, per prompts/03_green_context_v3.md "
          "Change 3). Run scripts/plot.py to regenerate reuse_green_vs_shared.png from this CSV.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
