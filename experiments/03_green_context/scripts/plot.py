#!/usr/bin/env python3
"""Generate Phase 3 plots from results/phase3_results.csv. Runnable from anywhere."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    return pd.read_csv(CSV_PATH)


def plot_green_vs_shared(df):
    """Aggregate GB/s: shared vs best-green, per test point (grouped bars)."""
    test_points = list(df.test_point_id.unique())
    shared_vals = []
    best_green_vals = []
    for tp in test_points:
        sub = df[df.test_point_id == tp]
        shared_vals.append(sub[sub.config == "shared"].agg_GBps_median.max())
        green = sub[sub.config == "green"]
        best_green_vals.append(green.agg_GBps_median.max() if not green.empty else np.nan)

    x = np.arange(len(test_points))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(x - width / 2, shared_vals, width, label="shared (baseline)")
    ax.bar(x + width / 2, best_green_vals, width, label="best green (partitioned)")
    ax.set_xticks(x)
    ax.set_xticklabels(test_points, rotation=20, ha="right")
    ax.set_ylabel("Aggregate achieved bandwidth (GB/s)")
    ax.set_title("Phase 3: shared vs best-green aggregate throughput per test point")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "green_vs_shared.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_partition_sweep(df):
    """Aggregate + per-kernel GB/s vs SM split ratio, for the onset test point."""
    onset_candidates = [tp for tp in df.test_point_id.unique() if "onset" in tp]
    tp = onset_candidates[0] if onset_candidates else df.test_point_id.iloc[0]
    sub = df[(df.test_point_id == tp) & (df.config == "green")].copy()
    if sub.empty:
        print(f"WARNING: no green rows for test point {tp!r}; skipping partition_sweep.png")
        return
    sub["split_label"] = sub.sm_split_k0.astype(str) + ":" + sub.sm_split_k1.astype(str)
    sub = sub.sort_values("sm_split_k0")

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(sub.split_label, sub.agg_GBps_median, marker="o", label="aggregate")
    ax.plot(sub.split_label, sub.k0_GBps_median, marker="s", label="K0")
    ax.plot(sub.split_label, sub.k1_GBps_median, marker="^", label="K1")
    ax.set_xlabel(f"SM split (K0:K1), test point = {tp}")
    ax.set_ylabel("Achieved bandwidth (GB/s)")
    ax.set_title(f"Phase 3: throughput vs SM partition ratio ({tp})")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "partition_sweep.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_green_vs_shared(df)
    plot_partition_sweep(df)


if __name__ == "__main__":
    main()
