#!/usr/bin/env python3
"""Plot + tabulate Phase 3's nsys overlap verification
(prompts/03_green_context/03_verify_overlap_nsys.md).

Reads results/overlap_nsys.csv (written by scripts/run_overlap_nsys.py) --
exactly 2 test points (the single peak-bandwidth size per mode) x {shared,
green} -- and produces:
  - results/plots/overlap_ratio_vs_footprint_combined_footprint.png: a grouped
    bar chart (mode x config), overlap_ratio shown as a PERCENTAGE with the
    value labeled directly on each bar, plus a 100% reference line. A line
    plot doesn't suit this: there are only 2 x-positions (one per mode), so a
    "line" between two points carries no trend information -- magnitude
    comparison across a handful of categories is a bar-chart job.
  - results/overlap_nsys_table.md: the same numbers as a small markdown table
    (test point, mode, config, overlap %, kernel instances in window, distinct
    GreenCtx count, K0/K1 size, SM split, block counts, threads/block), for
    reading without opening the PNG.

Each bar/row also carries the EXACT configuration it was profiled at (K0/K1
size, SM split, block counts) -- read straight from the CSV's
sm_split_k0/sm_split_k1/blocks_k0/blocks_k1/threads_per_block columns
(scripts/run_overlap_nsys.py copies these from the phase3_results.csv row
cell_args() reconstructed the invocation from), so nothing here needs a
manual cross-reference back to that CSV to see what was actually measured.

Additive-only: does not touch results/phase3_results.csv, findings.json, or
scripts/plot.py.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "overlap_nsys.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
TABLE_PATH = os.path.join(PHASE_DIR, "results", "overlap_nsys_table.md")

MB = 1024 * 1024
# Fixed categorical color assignment (shared vs green), matching every other
# plot in this phase (scripts/plot.py, scripts/plot_combined_footprint.py) --
# color identifies the config, never a re-cycled/ranked hue.
CONFIG_COLOR = {"shared": "tab:blue", "green": "tab:green"}
CONFIG_LABEL = {"shared": "shared", "green": "green (best-green split)"}

# Per-cell configuration columns added after the initial nsys-CSV schema; a
# CSV from before this feature (or from the older sqlite-based prototype)
# won't have them -- degrade gracefully (skip the annotation / table columns
# with a note) rather than crashing on an older results/overlap_nsys.csv.
CONFIG_COLS = ["sm_split_k0", "sm_split_k1", "blocks_k0", "blocks_k1", "threads_per_block"]


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/verify_overlap_nsys.sh first)")
    return pd.read_csv(CSV_PATH)


def _mode_order(df):
    # Fixed, readable order regardless of row order in the CSV.
    present = list(df["mode"].unique())
    return [m for m in ("symmetric", "asymmetric") if m in present] + \
           [m for m in present if m not in ("symmetric", "asymmetric")]


def _fmt_bytes(n):
    n = int(n)
    for unit, div in (("MB", MB), ("KB", 1024)):
        if n >= div:
            v = n / div
            return f"{v:.0f}{unit}" if v == int(v) else f"{v:.1f}{unit}"
    return f"{n}B"


def _mode_xtick_label(df, mode):
    """K0/K1 size for this mode (identical across its shared/green rows --
    same test point, just different config), so it's shown once per mode
    rather than repeated per bar."""
    sub = df[df["mode"] == mode]
    if sub.empty:
        return mode
    k0, k1 = int(sub.k0_bytes.iloc[0]), int(sub.k1_bytes.iloc[0])
    if mode == "symmetric":
        return f"{mode}\n(K0=K1={_fmt_bytes(k0)})"
    return f"{mode}\n(K0={_fmt_bytes(k0)}, K1={_fmt_bytes(k1)})"


def _bar_config_label(row):
    """SM split + block counts for this specific (mode, config) cell -- these
    DO differ between shared (always 16:16) and green (the SM split found
    best for this size)."""
    sm = f"SM {int(row.sm_split_k0)}:{int(row.sm_split_k1)}"
    blocks = f"blocks {int(row.blocks_k0)}:{int(row.blocks_k1)}"
    tpb = f"{int(row.threads_per_block)} thr/blk"
    return f"{sm}\n{blocks}\n{tpb}"


def plot_overlap_bar_chart(df):
    modes = _mode_order(df)
    configs = [c for c in ("shared", "green") if c in df.config.unique()]
    if not modes or not configs:
        sys.exit("No usable rows in overlap_nsys.csv -- nothing to plot")

    has_config_cols = all(c in df.columns for c in CONFIG_COLS)
    if not has_config_cols:
        print(f"NOTE: overlap_nsys.csv is missing {CONFIG_COLS} (an older run, before this "
              f"column was added) -- skipping the per-bar SM-split/block-count annotation. "
              f"Re-run scripts/run_overlap_nsys.py to include it.", file=sys.stderr)

    x = np.arange(len(modes))
    width = 0.35 if len(configs) > 1 else 0.5

    fig, ax = plt.subplots(figsize=(9, 7.5))
    for i, config in enumerate(configs):
        offset = (i - (len(configs) - 1) / 2) * width
        heights = []
        rows_by_mode = {}
        for mode in modes:
            sub = df[(df["mode"] == mode) & (df.config == config)]
            rows_by_mode[mode] = sub.iloc[0] if not sub.empty else None
            ratio = sub.overlap_ratio.mean() if not sub.empty else np.nan
            heights.append(ratio * 100.0 if pd.notna(ratio) else np.nan)
        bars = ax.bar(x + offset, heights, width, color=CONFIG_COLOR.get(config, None),
                       label=CONFIG_LABEL.get(config, config))
        for bar, h, mode in zip(bars, heights, modes):
            base_y = h if pd.notna(h) else 0
            if pd.notna(h):
                ax.annotate(f"{h:.0f}%", (bar.get_x() + bar.get_width() / 2, base_y),
                            xytext=(0, 4), textcoords="offset points",
                            ha="center", va="bottom", fontsize=11, fontweight="bold")
            else:
                ax.annotate("N/A", (bar.get_x() + bar.get_width() / 2, base_y),
                            xytext=(0, 4), textcoords="offset points",
                            ha="center", va="bottom", fontsize=9, color="gray")
            # Exact configuration this bar was profiled at (SM split, block
            # counts, threads/block) -- stacked in the open space ABOVE the
            # bar (never on top of the colored fill, which reads poorly
            # regardless of text color) so it's visible without opening the
            # table, whatever the bar's height.
            row = rows_by_mode[mode]
            if row is not None and has_config_cols:
                ax.annotate(_bar_config_label(row), (bar.get_x() + bar.get_width() / 2, base_y),
                            xytext=(0, 20), textcoords="offset points",
                            ha="center", va="bottom", fontsize=7.5, color="dimgray", linespacing=1.4)

    ax.axhline(100, color="gray", linestyle="--", linewidth=1,
               label="100% (full concurrency)")
    ax.set_xticks(x)
    ax.set_xticklabels([_mode_xtick_label(df, m) for m in modes])
    ax.set_ylabel("Kernel-overlap ratio (%) = concurrent_time / union_busy_time")
    ax.set_ylim(0, 132)
    ax.set_yticks(range(0, 101, 20))
    ax.set_title("Phase 3 nsys verification: overlap at the peak-bandwidth point per mode")
    ax.grid(True, axis="y", alpha=0.3)
    # Centered between the two mode groups (the one column with no bars or
    # annotations above it), so it never collides with the per-bar config text.
    ax.legend(fontsize=9, loc="upper center")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "overlap_ratio_vs_footprint_combined_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def write_table(df):
    base_cols = ["test_point_id", "mode", "config", "overlap_ratio",
                 "kernel_instances_in_window", "distinct_greenctx"]
    missing_base = [c for c in base_cols if c not in df.columns]
    if missing_base:
        sys.exit(f"overlap_nsys.csv missing required column(s) {missing_base} -- "
                  f"re-run scripts/run_overlap_nsys.py")

    has_config_cols = all(c in df.columns for c in CONFIG_COLS)
    if not has_config_cols:
        print(f"NOTE: overlap_nsys.csv is missing {CONFIG_COLS} (an older run, before this "
              f"column was added) -- table omits the K0/K1/SM-split/blocks columns. "
              f"Re-run scripts/run_overlap_nsys.py to include them.", file=sys.stderr)

    cols = base_cols + (["k0_bytes", "k1_bytes"] + CONFIG_COLS if has_config_cols else [])
    cols += ["combined_read_footprint_bytes"]
    rows = df.sort_values(["mode", "config"])[cols].copy()

    header_cells = ["Test point", "Mode", "Config", "Overlap %", "Kernels in window", "Distinct GreenCtx"]
    if has_config_cols:
        header_cells += ["K0 size", "K1 size", "SM split (K0:K1)", "Blocks (K0:K1)", "Threads/block"]
    header_cells += ["Combined footprint (MB)"]

    lines = [
        "# Phase 3 nsys overlap verification -- summary table",
        "",
        "One row per (mode, config) at that mode's peak-bandwidth test point "
        "(scripts/run_overlap_nsys.py). Verification-only -- not throughput." +
        (" K0/K1/SM-split/blocks/threads-per-block are the EXACT configuration "
         "that cell was profiled at (reconstructed via --fixed-blocks0/1 from "
         "the matching results/phase3_results.csv row)." if has_config_cols else ""),
        "",
        "| " + " | ".join(header_cells) + " |",
        "|" + "---|" * len(header_cells),
    ]
    for _, r in rows.iterrows():
        overlap_pct = f"{r.overlap_ratio * 100:.1f}%" if pd.notna(r.overlap_ratio) else "N/A (timeout/parse failure)"
        kiw = "" if pd.isna(r.kernel_instances_in_window) else int(r.kernel_instances_in_window)
        dgc = "" if pd.isna(r.distinct_greenctx) else int(r.distinct_greenctx)
        footprint_mb = r.combined_read_footprint_bytes / MB
        cells = [str(r.test_point_id), r["mode"], r.config, overlap_pct, str(kiw), str(dgc)]
        if has_config_cols:
            cells += [_fmt_bytes(r.k0_bytes), _fmt_bytes(r.k1_bytes),
                      f"{int(r.sm_split_k0)}:{int(r.sm_split_k1)}",
                      f"{int(r.blocks_k0)}:{int(r.blocks_k1)}", str(int(r.threads_per_block))]
        cells.append(f"{footprint_mb:.3f}")
        lines.append("| " + " | ".join(cells) + " |")

    with open(TABLE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {TABLE_PATH}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_overlap_bar_chart(df)
    write_table(df)


if __name__ == "__main__":
    main()
