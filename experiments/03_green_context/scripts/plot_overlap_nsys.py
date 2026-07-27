#!/usr/bin/env python3
"""Plot Phase 3's nsys overlap verification (prompts/03_green_context/03_verify_overlap_nsys.md).

Reads results/overlap_nsys.csv (written by scripts/run_overlap_nsys.py) and plots
overlap_ratio vs combined read footprint (MB, log2), shared vs green, with a
reference line at overlap_ratio = 1 (full concurrency: whenever the GPU was
busy, both kernels were running together).

Additive-only: does not touch results/phase3_results.csv, findings.json, or
scripts/plot.py. Reuses the log2/MB axis helper from scripts/plot_combined_footprint.py
so this figure is visually consistent with that one (same phase, same x quantity).

A test point's `green` config has several SM-partition-ratio cells in the
underlying sweep (scripts/sweep.py sweeps a handful of splits per size); this
plot summarizes them as the MEAN overlap_ratio across splits per test point --
concurrency (unlike throughput) is not expected to vary much by split, so one
representative "green" line is more readable than one line per split.
"""
import importlib.util
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "overlap_nsys.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")

_spec = importlib.util.spec_from_file_location(
    "plot_combined_footprint", os.path.join(SCRIPT_DIR, "plot_combined_footprint.py"))
_pcf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pcf)
MB = _pcf.MB
_set_log2_mb_axis = _pcf._set_log2_mb_axis


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/verify_overlap_nsys.sh first)")
    return pd.read_csv(CSV_PATH)


def _series_by_config(df, config):
    sub = df[df.config == config]
    if sub.empty:
        return pd.DataFrame(columns=["combined_footprint_mb", "overlap_ratio"])
    g = (
        sub.groupby("test_point_id")
        .agg(combined_footprint_mb=("combined_read_footprint_bytes", lambda s: s.iloc[0] / MB),
             overlap_ratio=("overlap_ratio", "mean"))
        .sort_values("combined_footprint_mb")
    )
    return g


def plot_overlap_ratio(df):
    fig, ax = plt.subplots(figsize=(10, 6.5))

    shared = _series_by_config(df, "shared")
    green = _series_by_config(df, "green")
    if shared.empty and green.empty:
        sys.exit("No shared or green rows in overlap_nsys.csv -- nothing to plot")

    if not shared.empty:
        ax.plot(shared.combined_footprint_mb, shared.overlap_ratio, marker="o",
                color="tab:blue", label="shared")
    if not green.empty:
        ax.plot(green.combined_footprint_mb, green.overlap_ratio, marker="s",
                color="tab:green", label="green (mean over SM splits)")

    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="overlap_ratio = 1 (full concurrency)")
    _set_log2_mb_axis(ax)
    ax.set_ylabel("overlap_ratio = concurrent_time / union_busy_time")
    ax.set_title("Phase 3 nsys verification: kernel-overlap ratio vs combined read footprint")
    ax.set_ylim(bottom=0)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "overlap_ratio_vs_footprint_combined_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_overlap_ratio(df)


if __name__ == "__main__":
    main()
