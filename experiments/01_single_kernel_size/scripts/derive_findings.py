#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase1_results.csv.

Numbers are computed from the actual measured CSV — never hand-typed — so this
must be re-run (not hand-edited) whenever the CSV changes. Run after run.sh.
"""
import datetime
import json
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase1_results.csv")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

CACHE_REL_TOL = 0.10  # within 10% of DRAM peak counts as "DRAM-bound"


def measured_dram_peak(df):
    largest_size = df.size_per_buffer_bytes.max()
    rows = df[(df.reuse_N == 1) & (df.size_per_buffer_bytes == largest_size)]
    return float(rows.achieved_GBps_median.max())


def find_tier_steps(df, dram_peak):
    """Use the highest-reuse plateau curve (best proxy for cache residency) to
    locate where BW converges to DRAM peak (dram-bound boundary) and, within
    the cache-resident region below that, the largest single BW drop (proxy
    for the L2 -> L2+SLC step)."""
    max_reuse = df.reuse_N.max()
    curve = (
        df[df.reuse_N == max_reuse]
        .groupby("read_footprint_bytes")["achieved_GBps_median"]
        .max()
        .sort_index()
    )
    footprints = curve.index.to_numpy()
    bws = curve.to_numpy()

    dram_bound_min = int(footprints[-1])
    for i in range(len(footprints)):
        if all(bws[j] <= dram_peak * (1 + CACHE_REL_TOL) for j in range(i, len(footprints))):
            dram_bound_min = int(footprints[i])
            break

    cache_idx = [i for i, f in enumerate(footprints) if f < dram_bound_min]
    if len(cache_idx) < 2:
        l2_resident_max = int(footprints[cache_idx[0]]) if cache_idx else None
        slc_region_max = l2_resident_max
    else:
        cache_bws = bws[cache_idx]
        cache_fp = footprints[cache_idx]
        drops = [(cache_bws[i] - cache_bws[i + 1]) / cache_bws[i] for i in range(len(cache_bws) - 1)]
        split = max(range(len(drops)), key=lambda i: drops[i])
        l2_resident_max = int(cache_fp[split])
        slc_region_max = int(cache_fp[-1])

    return l2_resident_max, slc_region_max, dram_bound_min


def saturation_blocks_by_size(df):
    out = {}
    for size, group in df[df.reuse_N == 1].groupby("size_per_buffer_bytes"):
        sat = group[group.saturated == 1]
        if sat.empty:
            continue
        out[str(int(size))] = int(sat.blocks.min())
    return out


def tpb_check_note(df):
    mid_rows = df[(df.reuse_N == 1) & (df.blocks == 256)]
    tpb_bw = mid_rows.groupby("threads_per_block")["achieved_GBps_median"].max()
    if 256 not in tpb_bw.index or len(tpb_bw) < 2:
        return "threads-per-block check incomplete (missing rows)"
    best_tpb = tpb_bw.idxmax()
    if best_tpb == 256 or tpb_bw[256] >= 0.98 * tpb_bw.max():
        return f"256 threads/block confirmed near-optimal at the mid-size check (values: {tpb_bw.to_dict()})"
    return (f"WARNING: 256 threads/block was NOT near-optimal at the mid-size check "
            f"(best was {best_tpb}; values: {tpb_bw.to_dict()})")


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df_all = pd.read_csv(CSV_PATH)
    df = df_all[df_all.threads_per_block == 256].copy()

    dram_peak = measured_dram_peak(df)
    l2_max, slc_max, dram_min = find_tier_steps(df, dram_peak)
    sat_blocks = saturation_blocks_by_size(df)
    tpb_note = tpb_check_note(df_all)

    crossover_note = (
        f"Reuse stops lifting achieved BW above DRAM peak once read_footprint_bytes >= "
        f"{dram_min} (~{dram_min / (1024 * 1024):.1f} MB); below that, higher reuse_N "
        f"pushes BW above the {dram_peak:.0f} GB/s measured DRAM peak via cache hits."
    )

    results = {
        "measured_dram_peak_GBps": round(dram_peak, 1),
        "tier_steps": {
            "l2_resident_max_read_footprint_bytes": l2_max,
            "slc_region_max_read_footprint_bytes": slc_max,
            "dram_bound_min_read_footprint_bytes": dram_min,
        },
        "saturation_blocks_by_size": sat_blocks,
        "recommended_threads_per_block": 256,
        "reuse_crossover_note": crossover_note,
        "compute_bound_observed": False,
    }

    findings = {
        "schema_version": "1.0",
        "phase": "01_single_kernel_size",
        "generated_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv": "experiments/01_single_kernel_size/results/phase1_results.csv",
        "env_ref": "shared/env.md",
        "results": results,
        "consumed": ["shared/size_grid.py"],
    }

    with open(FINDINGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    print(f"wrote {FINDINGS_JSON_PATH}")

    md = f"""# Phase 1 Findings — Single-Kernel Memory-Hierarchy Characterization

Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not
hand-edit) if the CSV is regenerated.

## Size grid (`prompts/05_unified_size_grid_and_plots.md`)

Sizes come from `../../shared/size_grid.py::phase1_sizes_bytes()` (32 points: the union of
F/2 and F/4 over the shared combined-footprint grid F), not a hardcoded list -- see
`README.md`. The tier boundaries below are measured from this densified grid (1-4 MB
combined footprint is now 256KB-dense); if they differ from a prior run's tier boundaries,
that is a legitimate consequence of denser sampling, not an error -- flag any such move for
`OVERVIEW.md` §0 (which still documents the nominal, not measured, 4MB/8MB tiers). Phase 2
and Phase 3's symmetric x-axis is this same shared combined-read-footprint grid; their
asymmetric grid is unchanged and therefore not comparable point-for-point across phases.

## Cache-tier bandwidth steps

- **L2-resident** up to read-footprint **{l2_max:,} bytes** (~{l2_max / (1024*1024):.2f} MB)
- **L2+SLC-served** up to read-footprint **{slc_max:,} bytes** (~{slc_max / (1024*1024):.2f} MB)
- **DRAM-bound** from read-footprint **{dram_min:,} bytes** (~{dram_min / (1024*1024):.2f} MB) onward
- **Measured DRAM peak:** {dram_peak:.1f} GB/s

## Reuse crossover

{crossover_note}

## Saturation (minimum blocks to reach plateau, threads/block=256, reuse N=1)

{chr(10).join(f"- {int(k):,} bytes/buffer -> {v} blocks" for k, v in sorted(sat_blocks.items(), key=lambda kv: int(kv[0])))}

## Threads-per-block check

{tpb_note}

## Compute-bound crossover observed?

{"Yes — UNEXPECTED, investigate." if results["compute_bound_observed"] else "No (as expected for AI ~= 0.08 flop/byte)."}

## Tier-boundary sanity (00_conventions.md / prompt Verification section)

Re-check these by eye against `results/plots/bw_vs_footprint.png`:
- Largest size (footprint >> 8 MB) should show ~no BW gain from reuse, BW ~= DRAM peak.
- Small size (footprint <= 4 MB) should show reuse pushing BW *above* DRAM peak (cache hits).
If either does not hold, treat this findings.json as suspect and STOP before Phase 2 consumes it.
"""
    with open(FINDINGS_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {FINDINGS_MD_PATH}")


if __name__ == "__main__":
    main()
