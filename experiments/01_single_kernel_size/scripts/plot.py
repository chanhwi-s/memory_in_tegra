#!/usr/bin/env python3
"""Generate Phase 1 plots from results/phase1_results.csv. Runnable from anywhere."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase1_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")

L2_BYTES = 4 * 1024 * 1024
L2_SLC_BYTES = 8 * 1024 * 1024

# Representative sizes for the saturation plot (bytes per buffer):
# L2-resident, SLC-region, DRAM-bound (see OVERVIEW.md tier boundaries).
SAT_SIZES = {
    "L2-resident (1 MB/buf)": 1 * 1024 * 1024,
    "SLC-region (3 MB/buf)": 3 * 1024 * 1024,
    "DRAM-bound (48 MB/buf)": 48 * 1024 * 1024,
}


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df = pd.read_csv(CSV_PATH)
    return df[df.threads_per_block == 256].copy()


def plot_bw_vs_footprint(df):
    fig, ax = plt.subplots(figsize=(9, 6))
    for reuse_n, group in sorted(df.groupby("reuse_N")):
        plateau = group.groupby("read_footprint_bytes")["achieved_GBps_median"].max().sort_index()
        ax.plot(plateau.index, plateau.values, marker="o", label=f"reuse N={reuse_n}")

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Read footprint (bytes, log2)")
    ax.set_ylabel("Achieved bandwidth (GB/s)")
    ax.set_title("Phase 1: achieved BW vs read footprint (plateau, threads/block=256)")

    ax.axvline(L2_BYTES, color="gray", linestyle="--", linewidth=1)
    ax.text(L2_BYTES, ax.get_ylim()[1], " 4MB (L2)", va="top", ha="left", fontsize=8, color="gray")
    ax.axvline(L2_SLC_BYTES, color="gray", linestyle="--", linewidth=1)
    ax.text(L2_SLC_BYTES, ax.get_ylim()[1], " 8MB (L2+SLC)", va="top", ha="left", fontsize=8, color="gray")

    dram_rows = df[(df.reuse_N == 1) & (df.size_per_buffer_bytes == df.size_per_buffer_bytes.max())]
    if not dram_rows.empty:
        dram_peak = dram_rows["achieved_GBps_median"].max()
        ax.axhline(dram_peak, color="firebrick", linestyle=":", linewidth=1)
        ax.text(ax.get_xlim()[0], dram_peak, f" measured DRAM peak ~{dram_peak:.0f} GB/s",
                va="bottom", ha="left", fontsize=8, color="firebrick")

    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "bw_vs_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_saturation(df):
    fig, ax = plt.subplots(figsize=(9, 6))
    for label, size_bytes in SAT_SIZES.items():
        sub = df[(df.reuse_N == 1) & (df.size_per_buffer_bytes == size_bytes)].sort_values("blocks")
        if sub.empty:
            print(f"WARNING: no rows for {label} ({size_bytes} bytes); skipping")
            continue
        ax.plot(sub.blocks, sub.achieved_GBps_median, marker="o", label=label)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Block count (log2)")
    ax.set_ylabel("Achieved bandwidth (GB/s)")
    ax.set_title("Phase 1: saturation vs block count (reuse N=1, threads/block=256)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "saturation.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_bw_vs_footprint(df)
    plot_saturation(df)


if __name__ == "__main__":
    main()
