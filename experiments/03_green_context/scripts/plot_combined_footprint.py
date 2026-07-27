#!/usr/bin/env python3
"""Phase 3 -- combined-footprint plot (additive; prompts/03_green_context/03_combined_footprint_plot.md).

Re-plots Phase 3 on the unified combined-read-footprint x-axis instead of
per-kernel size, so Phase 3 lands directly on top of Phase 2/1 where they
represent the same underlying data (worklog/2026-07-27-1015_HANDOFF.md S2.3:
Phase 2's x-axis is combined footprint, Phase 3's existing plot.py uses
per-kernel size -- same data, different axis definition).

Canonical formula (same in every phase):
    combined_read_footprint_bytes = sum over active kernels of
                                     (num_input_buffers * per_buffer_bytes)
C = A + B -> num_input_buffers = 2 (A, B; C is written, not read).
Phase 3 has 2 concurrent kernels -> combined_read_footprint_bytes =
    2 * k0_bytes + 2 * k1_bytes

Additive only: reads existing results/*.csv, writes new results/plots/*_combined_footprint.png.
Does not touch results/*.csv, findings.json, or scripts/plot.py.

symmetric/asymmetric are plotted as two side-by-side panels (same layout as
scripts/plot.py's plot_green_vs_shared) rather than merged onto one panel --
merging them onto a single combined-footprint axis was tried first but reads
worse than keeping the two-panel layout readers already know from plot.py.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")

MB = 1024 * 1024

# Fallback reference values (worklog/2026-07-27-1015_HANDOFF.md S0/S2): used only
# if experiments/01_single_kernel_size/findings.json is missing or lacks the key,
# with a note printed so the fallback is never silently mistaken for a measurement.
FALLBACK_CACHE_BOUNDARY_BYTES = 2 * MB
FALLBACK_DRAM_PEAK_GBPS = 177.0


def combined_footprint_mb(df):
    return (2 * df.k0_bytes + 2 * df.k1_bytes) / MB


def _fmt_mb(x, _pos):
    return f"{x:g}"


def _set_log2_mb_axis(ax):
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_mb))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_xlabel("combined read footprint [MB], log2")


def load_reference_lines():
    """Cache boundary (vertical) + measured DRAM peak (horizontal), read from
    Phase 1's findings.json if present; else the stated fallback with a note."""
    cache_boundary_bytes = None
    dram_peak_gbps = None
    if os.path.exists(PHASE1_FINDINGS):
        with open(PHASE1_FINDINGS) as f:
            p1 = json.load(f)
        results = p1.get("results", {})
        cache_boundary_bytes = results.get("tier_steps", {}).get("slc_region_max_read_footprint_bytes")
        dram_peak_gbps = results.get("measured_dram_peak_GBps")

    if cache_boundary_bytes is None:
        print(f"NOTE: Phase 1 findings.json missing tier_steps.slc_region_max_read_footprint_bytes -- "
              f"using fallback cache boundary {FALLBACK_CACHE_BOUNDARY_BYTES / MB:.0f} MB "
              f"(worklog/2026-07-27-1015_HANDOFF.md S2)", file=sys.stderr)
        cache_boundary_bytes = FALLBACK_CACHE_BOUNDARY_BYTES
    if dram_peak_gbps is None:
        print(f"NOTE: Phase 1 findings.json missing measured_dram_peak_GBps -- "
              f"using fallback DRAM peak {FALLBACK_DRAM_PEAK_GBPS} GB/s "
              f"(worklog/2026-07-27-1015_HANDOFF.md S0)", file=sys.stderr)
        dram_peak_gbps = FALLBACK_DRAM_PEAK_GBPS

    return cache_boundary_bytes / MB, dram_peak_gbps


def _draw_reference_lines(ax, cache_boundary_mb, dram_peak_gbps, label=True):
    ax.axvline(cache_boundary_mb, color="gray", linestyle="--", linewidth=1,
               label=f"cache boundary ~{cache_boundary_mb:g} MB" if label else None)
    ax.axhline(dram_peak_gbps, color="firebrick", linestyle=":", linewidth=1,
               label=f"DRAM peak ~{dram_peak_gbps:.0f} GB/s" if label else None)


def load_main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df = pd.read_csv(CSV_PATH)
    df["combined_footprint_mb"] = combined_footprint_mb(df)
    return df


def _point_summary(df):
    """One row per test_point_id (both modes merged -- that's the point of the
    unified x-axis): combined footprint, shared agg GB/s, best-green agg GB/s."""
    rows = []
    for tp, g in df.groupby("test_point_id"):
        shared = g[g.config == "shared"]
        green = g[g.config == "green"]
        if shared.empty:
            continue
        shared_agg = shared.agg_GBps_median.iloc[0]
        best_green_agg = green.agg_GBps_median.max() if not green.empty else np.nan
        rows.append({
            "test_point_id": tp,
            "mode": g["mode"].iloc[0],
            "combined_footprint_mb": g.combined_footprint_mb.iloc[0],
            "shared_agg_GBps": shared_agg,
            "best_green_agg_GBps": best_green_agg,
        })
    cols = ["test_point_id", "mode", "combined_footprint_mb", "shared_agg_GBps", "best_green_agg_GBps"]
    return pd.DataFrame(rows).sort_values("combined_footprint_mb") if rows else pd.DataFrame(columns=cols)


def plot_green_vs_shared_combined_footprint(df, cache_boundary_mb, dram_peak_gbps):
    """Aggregate GB/s vs combined read footprint (MB, log2), shared vs green --
    one panel per mode (symmetric, asymmetric), same two-panel layout as
    scripts/plot.py's plot_green_vs_shared, just with the combined-footprint
    x-axis instead of per-kernel size."""
    s = _point_summary(df)
    if s.empty:
        sys.exit("No shared-baseline rows found in phase3_results.csv -- nothing to plot")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, mode in zip(axes, ["symmetric", "asymmetric"]):
        g = s[s["mode"] == mode]
        if g.empty:
            ax.set_title(f"{mode} (no data)")
            continue
        ax.plot(g.combined_footprint_mb, g.shared_agg_GBps, marker="o",
                 color="tab:blue", label="shared (baseline)")
        ax.plot(g.combined_footprint_mb, g.best_green_agg_GBps, marker="s",
                 color="tab:green", label="best green (partitioned)")
        _draw_reference_lines(ax, cache_boundary_mb, dram_peak_gbps)
        _set_log2_mb_axis(ax)
        ax.set_title(f"Phase 3: {mode}")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Aggregate achieved bandwidth (GB/s)")
    fig.suptitle("Shared vs best-green aggregate throughput vs combined read footprint")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "green_vs_shared_combined_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    cache_boundary_mb, dram_peak_gbps = load_reference_lines()
    df = load_main()
    plot_green_vs_shared_combined_footprint(df, cache_boundary_mb, dram_peak_gbps)


if __name__ == "__main__":
    main()
