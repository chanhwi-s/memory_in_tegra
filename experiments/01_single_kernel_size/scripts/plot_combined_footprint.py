#!/usr/bin/env python3
"""Additive Phase 1 plot: achieved BW vs combined read footprint (see
prompts/01_single_kernel_size/01_combined_footprint_plot.md).

Does NOT touch results/phase1_results.csv, findings.json, or scripts/plot.py.
Unifies the x-axis definition with Phases 2-3 so cache boundaries line up:

    combined_read_footprint_bytes = sum over active kernels of (num_input_buffers * per_buffer_bytes)

Phase 1 is a single `C = A + B` kernel (num_input_buffers=2), so combined_read_footprint
== the existing `read_footprint_bytes` CSV column; reused directly rather than recomputed.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase1_results.csv")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
OUT_PATH = os.path.join(PLOTS_DIR, "bw_vs_footprint_combined_footprint.png")

MB = 1024 * 1024
FALLBACK_CACHE_BOUNDARY_BYTES = 2 * MB
FALLBACK_DRAM_PEAK_GBPS = 177.0


def load_reference_lines():
    """Cache boundary + DRAM peak, from findings.json if present, else the
    prompt's stated fallback values (logs a note either way)."""
    if not os.path.exists(FINDINGS_JSON_PATH):
        print(f"NOTE: {FINDINGS_JSON_PATH} not found; using stated fallback reference values "
              f"(cache boundary {FALLBACK_CACHE_BOUNDARY_BYTES / MB:.0f} MB, "
              f"DRAM peak {FALLBACK_DRAM_PEAK_GBPS:.0f} GB/s).")
        return FALLBACK_CACHE_BOUNDARY_BYTES, FALLBACK_DRAM_PEAK_GBPS

    with open(FINDINGS_JSON_PATH) as f:
        findings = json.load(f)
    results = findings.get("results", {})

    cache_boundary = results.get("tier_steps", {}).get("slc_region_max_read_footprint_bytes")
    if cache_boundary is None:
        print(f"NOTE: findings.json missing tier_steps.slc_region_max_read_footprint_bytes; "
              f"falling back to stated {FALLBACK_CACHE_BOUNDARY_BYTES / MB:.0f} MB.")
        cache_boundary = FALLBACK_CACHE_BOUNDARY_BYTES

    dram_peak = results.get("measured_dram_peak_GBps")
    if dram_peak is None:
        print(f"NOTE: findings.json missing measured_dram_peak_GBps; "
              f"falling back to stated {FALLBACK_DRAM_PEAK_GBPS:.0f} GB/s.")
        dram_peak = FALLBACK_DRAM_PEAK_GBPS

    return cache_boundary, dram_peak


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    os.makedirs(PLOTS_DIR, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    df = df[df.threads_per_block == 256].copy()
    df["combined_read_footprint_bytes"] = df["read_footprint_bytes"]  # num_input_buffers=2, see module docstring

    cache_boundary_bytes, dram_peak_gbps = load_reference_lines()

    fig, ax = plt.subplots(figsize=(9, 6))
    for reuse_n, group in sorted(df.groupby("reuse_N")):
        plateau = (
            group.groupby("combined_read_footprint_bytes")["achieved_GBps_median"]
            .max()
            .sort_index()
        )
        x_mb = plateau.index.to_numpy() / MB
        ax.plot(x_mb, plateau.values, marker="o", label=f"reuse N={reuse_n}")

    ax.set_xscale("log", base=2)
    ax.set_xlabel("combined read footprint [MB], log2")
    ax.set_ylabel("Achieved bandwidth (GB/s)")
    ax.set_title("Phase 1: achieved BW vs combined read footprint (plateau, threads/block=256)")

    cache_boundary_mb = cache_boundary_bytes / MB
    ax.axvline(cache_boundary_mb, color="gray", linestyle="--", linewidth=1)
    ax.text(cache_boundary_mb, ax.get_ylim()[1], f" measured cache boundary ~{cache_boundary_mb:.1f} MB",
            va="top", ha="left", fontsize=8, color="gray")

    ax.axhline(dram_peak_gbps, color="firebrick", linestyle=":", linewidth=1)
    ax.text(ax.get_xlim()[0], dram_peak_gbps, f" measured DRAM peak ~{dram_peak_gbps:.0f} GB/s",
            va="bottom", ha="left", fontsize=8, color="firebrick")

    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()

    if os.path.exists(OUT_PATH):
        sys.exit(f"Refusing to overwrite existing plot: {OUT_PATH}")
    fig.savefig(OUT_PATH, dpi=150)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
