#!/usr/bin/env python3
"""v2 add-on (prompts/02_two_kernel_size_v2.md): generate the reuse-sweep overlay plot from
results/phase2_reuse_results.csv. Runnable from anywhere. Purely additive -- does not read or
touch phase2_results.csv, findings.json, or scripts/plot.py's outputs.

Two-kernel analog of Phase 1's bw_vs_footprint.png: one aggregate-GB/s line per reuse_N,
overlaid, for both the symmetric (vs combined footprint) and asymmetric (vs K1 size) sweeps.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase2_reuse_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run_reuse_overlay.sh first)")
    return pd.read_csv(CSV_PATH)


def load_dram_peak():
    if not os.path.exists(PHASE1_FINDINGS):
        return None
    with open(PHASE1_FINDINGS) as f:
        findings = json.load(f)
    return findings.get("results", {}).get("measured_dram_peak_GBps")


def bytes_formatter(x, _pos):
    """Human-readable power-of-2 byte label (256K, 512K, 1M, 2M, ...). matplotlib's
    set_xscale("log", base=2) does not itself relabel ticks in K/M, so this FuncFormatter is
    required (prompts/02_two_kernel_size_v2.md)."""
    if x <= 0:
        return ""
    if x >= 1024 * 1024:
        v = x / (1024 * 1024)
        return f"{v:g}M"
    if x >= 1024:
        v = x / 1024
        return f"{v:g}K"
    return f"{x:g}"


def style_log2_axis(ax):
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(FuncFormatter(bytes_formatter))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda x, pos: ""))


def draw_dram_peak(ax, dram_peak):
    if dram_peak is None:
        print("NOTE: Phase 1 findings.json unavailable -- DRAM peak reference line omitted.")
        return
    ax.axhline(dram_peak, color="firebrick", linestyle=":", linewidth=1.5)
    ax.text(ax.get_xlim()[0], dram_peak, f" measured DRAM peak ~{dram_peak:.0f} GB/s", va="bottom",
            ha="left", fontsize=8, color="firebrick")


def plot_panel(ax, df, x_col, title, xlabel, dram_peak):
    if df.empty:
        ax.text(0.5, 0.5, "no rows", transform=ax.transAxes, ha="center", va="center")
        return
    for reuse_n, group in sorted(df.groupby("reuse_N")):
        g = group.sort_values(x_col)
        ax.plot(g[x_col], g.agg_GBps_median, marker="o", markersize=4, label=f"reuse N={reuse_n}")
    style_log2_axis(ax)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Aggregate achieved bandwidth (GB/s)")
    ax.set_title(title)
    draw_dram_peak(ax, dram_peak)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    dram_peak = load_dram_peak()

    sym = df[df["mode"] == "symmetric"].copy()
    asym = df[df["mode"] == "asymmetric"].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    plot_panel(ax1, sym, "combined_read_footprint_bytes",
               "Phase 2 reuse overlay (symmetric): aggregate BW vs combined footprint",
               "Combined read footprint, both kernels (bytes, log2)", dram_peak)
    plot_panel(ax2, asym, "k1_bytes",
               "Phase 2 reuse overlay (asymmetric): aggregate BW vs K1 size",
               "K1 size, per-buffer (bytes, log2); K0 fixed at 1 MB", dram_peak)

    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "reuse_bw_vs_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
