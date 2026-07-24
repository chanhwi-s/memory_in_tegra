#!/usr/bin/env python3
"""Generate Phase 4 plots from results/phase4_results.csv. Runnable from anywhere."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase4_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    return pd.read_csv(CSV_PATH, na_values=["NA"])


def plot_zc_vs_cached_reuse(df):
    points = sorted(df.groupby(["test_point_id", "config"]).groups.keys())
    n = len(points)
    if n == 0:
        print("WARNING: no test points to plot")
        return
    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)

    for idx, (tpid, config) in enumerate(points):
        ax = axes[idx // ncols][idx % ncols]
        sub = df[(df.test_point_id == tpid) & (df.config == config)]
        for path, marker in [("cached", "o"), ("zerocopy", "s")]:
            line = sub[sub.large_kernel_path == path].sort_values("reuse_N")
            if line.empty:
                continue
            ax.plot(line.reuse_N, line.agg_GBps_median, marker=marker, label=path)

        # mark crossover: smallest reuse_N where delta_vs_cached_pct changes sign
        zc = sub[sub.large_kernel_path == "zerocopy"].sort_values("reuse_N")
        prev = None
        for _, row in zc.iterrows():
            d = row.get("delta_vs_cached_pct")
            if pd.isna(d):
                continue
            cur = d >= 0
            if prev is not None and cur != prev:
                ax.axvline(row.reuse_N, color="gray", linestyle="--", linewidth=1)
                ax.text(row.reuse_N, ax.get_ylim()[1], f" N={int(row.reuse_N)}",
                        va="top", fontsize=8, color="gray")
                break
            prev = cur

        ax.set_xscale("log", base=2)
        ax.set_xlabel("reuse N")
        ax.set_ylabel("aggregate GB/s")
        ax.set_title(f"{tpid} ({config})", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.3)

    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].axis("off")

    fig.suptitle("Phase 4: aggregate GB/s vs reuse N, cached vs zero-copy")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "zc_vs_cached_reuse.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_zc_benefit_map(df):
    zc = df[df.large_kernel_path == "zerocopy"].copy()
    if zc.empty:
        print("WARNING: no zerocopy rows to plot")
        return
    zc["point_label"] = zc.test_point_id + " (" + zc.config + ")"
    pivot = zc.pivot_table(index="point_label", columns="reuse_N", values="delta_vs_cached_pct")
    pivot = pivot.sort_index(axis=1)

    fig, ax = plt.subplots(figsize=(8, 0.6 * len(pivot) + 2))
    vmax = np.nanmax(np.abs(pivot.values)) if pivot.size else 1.0
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xlabel("reuse N")
    ax.set_title("Phase 4: zero-copy delta vs cached (%) by test point x reuse N")
    fig.colorbar(im, ax=ax, label="delta_vs_cached_pct")

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7)

    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "zc_benefit_map.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_zc_vs_cached_reuse(df)
    plot_zc_benefit_map(df)


if __name__ == "__main__":
    main()
