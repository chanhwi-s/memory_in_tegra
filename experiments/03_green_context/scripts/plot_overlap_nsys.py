#!/usr/bin/env python3
"""Plot + tabulate Phase 3's nsys overlap verification
(prompts/03_green_context/03_verify_overlap_nsys.md; cell selection + plot
rewritten by prompts/05_unified_size_grid_and_plots.md Change 6).

Reads results/overlap_nsys.csv (written by scripts/run_overlap_nsys.py) --
now 3 test points per mode (the cache-bound local peak + its two grid
neighbours, not just the single peak) x {shared, green} = up to 12 rows --
and produces:
  - results/plots/overlap_ratio_vs_footprint_combined_footprint.png: a real
    LINE plot, overlap_ratio (%) vs combined read footprint (MB, log2), one
    panel per mode, shared vs green. With only 1 point per mode (the old
    global-argmax selection) a "line" carried no trend information, so this
    used to be a grouped bar chart instead (Change 6: now that there are 3
    points per mode, it can finally be a real curve).
  - results/overlap_nsys_table.md: the same numbers as a small markdown table
    (test point, mode, config, overlap %, kernel instances in window, distinct
    GreenCtx count, K0/K1 size, SM split, block counts, threads/block,
    failure reason), for reading without opening the PNG.

Each point/row also carries the EXACT configuration it was profiled at (K0/K1
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
import matplotlib.ticker as mticker
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
CONFIG_MARKER = {"shared": "o", "green": "s"}
CONFIG_LABEL = {"shared": "shared", "green": "green (best-green split)"}

# Per-cell configuration columns added after the initial nsys-CSV schema; a
# CSV from before this feature (or from the older sqlite-based prototype)
# won't have them -- degrade gracefully (skip the annotation / table columns
# with a note) rather than crashing on an older results/overlap_nsys.csv.
CONFIG_COLS = ["sm_split_k0", "sm_split_k1", "blocks_k0", "blocks_k1", "threads_per_block"]
# failure_reason (Change 6) is newer still -- an even older CSV may lack it too.
FAILURE_COL = "failure_reason"


def _fmt_mb(x, _pos):
    return f"{x:g}"


def _set_log2_mb_axis(ax):
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_mb))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_xlabel("combined read footprint [MB], log2")


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


def _point_config_label(row):
    """SM split + block counts for this specific (test point, config) cell --
    these DO differ between shared (always 16:16) and green (the SM split
    found best for this size)."""
    sm = f"SM {int(row.sm_split_k0)}:{int(row.sm_split_k1)}"
    blocks = f"blocks {int(row.blocks_k0)}:{int(row.blocks_k1)}"
    tpb = f"{int(row.threads_per_block)} thr/blk"
    return f"{sm}\n{blocks}\n{tpb}"


def plot_overlap_vs_footprint(df):
    """Change 6: real line plot, overlap_ratio (%) vs combined read footprint
    (MB, log2) -- one panel per mode, shared vs green. Each mode now has 3
    points (the cache-bound peak + its two grid neighbours,
    scripts/run_overlap_nsys.py), which is what makes a line meaningful here
    (with the old 1-point-per-mode selection a "line" carried no trend
    information, hence the old grouped bar chart)."""
    modes = _mode_order(df)
    if not modes:
        sys.exit("No usable rows in overlap_nsys.csv -- nothing to plot")

    has_config_cols = all(c in df.columns for c in CONFIG_COLS)
    if not has_config_cols:
        print(f"NOTE: overlap_nsys.csv is missing {CONFIG_COLS} (an older run, before this "
              f"column was added) -- skipping the per-point SM-split/block-count annotation. "
              f"Re-run scripts/run_overlap_nsys.py to include it.", file=sys.stderr)

    fig, axes = plt.subplots(1, len(modes), figsize=(7 * len(modes), 6), squeeze=False)
    axes = axes[0]
    for ax, mode in zip(axes, modes):
        msub = df[df["mode"] == mode].copy()
        msub = msub.sort_values("combined_read_footprint_bytes")
        all_footprints_mb = (msub.combined_read_footprint_bytes / MB).tolist()
        # shared's annotations stack ABOVE its point, green's stack BELOW its point --
        # keeps them from colliding even when the two configs' overlap_ratio (and
        # therefore marker y-position) are close, which is common (small deltas).
        ANNOTATE_DIRECTION = {"shared": 1, "green": -1}
        for config in ("shared", "green"):
            csub = msub[msub.config == config]
            if csub.empty:
                continue
            direction = ANNOTATE_DIRECTION.get(config, 1)
            va = "bottom" if direction > 0 else "top"
            footprint_mb = csub.combined_read_footprint_bytes / MB
            pct = csub.overlap_ratio * 100.0
            ax.plot(footprint_mb, pct, marker=CONFIG_MARKER.get(config, "o"),
                     color=CONFIG_COLOR.get(config, None),
                     label=CONFIG_LABEL.get(config, config))
            for fp_mb, h, (_, row) in zip(footprint_mb, pct, csub.iterrows()):
                if pd.notna(h):
                    ax.annotate(f"{h:.0f}%", (fp_mb, h), xytext=(0, direction * 6),
                                textcoords="offset points", ha="center", va=va,
                                fontsize=9, fontweight="bold", color=CONFIG_COLOR.get(config))
                    label_anchor_y = h
                else:
                    reason = row.get(FAILURE_COL, "") if hasattr(row, "get") else ""
                    label = f"N/A ({reason})" if reason else "N/A"
                    ax.annotate(label, (fp_mb, 0), xytext=(0, direction * 6),
                                textcoords="offset points", ha="center", va=va,
                                fontsize=8, color="gray")
                    label_anchor_y = 0
                if has_config_cols:
                    ax.annotate(_point_config_label(row), (fp_mb, label_anchor_y),
                                xytext=(0, direction * 22), textcoords="offset points",
                                ha="center", va=va, fontsize=7, color="dimgray",
                                linespacing=1.3)
        ax.axhline(100, color="gray", linestyle="--", linewidth=1,
                   label="100% (full concurrency)")
        _set_log2_mb_axis(ax)
        # A degenerate single-x-value panel (e.g. an older CSV from before Change 6, with
        # only 1 test point for this mode) makes matplotlib's default log-scale autoscale
        # margin push the lower bound to/below 0 -- explicit padding avoids that crash and
        # still renders sensibly once there really are 3 distinct footprints.
        if all_footprints_mb:
            lo, hi = min(all_footprints_mb), max(all_footprints_mb)
            if lo == hi:
                ax.set_xlim(lo * 0.7, hi * 1.4)
            else:
                pad = (hi / lo) ** 0.15
                ax.set_xlim(lo / pad, hi * pad)
        ax.set_ylim(-35, 145)
        ax.set_yticks(range(0, 101, 20))
        ax.set_title(f"Phase 3 nsys verification: {mode}")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8, loc="upper center")
    axes[0].set_ylabel("Kernel-overlap ratio (%) = concurrent_time / union_busy_time")
    fig.suptitle("Overlap ratio vs combined read footprint: cache-bound peak + neighbours, shared vs green")
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

    has_failure_col = FAILURE_COL in df.columns
    if not has_failure_col:
        print(f"NOTE: overlap_nsys.csv is missing '{FAILURE_COL}' (an older run, before "
              f"Change 6 added it) -- failed cells show a generic N/A instead of the specific "
              f"reason. Re-run scripts/run_overlap_nsys.py to include it.", file=sys.stderr)

    cols = base_cols + (["k0_bytes", "k1_bytes"] + CONFIG_COLS if has_config_cols else [])
    cols += ["combined_read_footprint_bytes"]
    if has_failure_col:
        cols += [FAILURE_COL]
    rows = df.sort_values(["mode", "config"])[cols].copy()

    header_cells = ["Test point", "Mode", "Config", "Overlap %", "Kernels in window", "Distinct GreenCtx"]
    if has_config_cols:
        header_cells += ["K0 size", "K1 size", "SM split (K0:K1)", "Blocks (K0:K1)", "Threads/block"]
    header_cells += ["Combined footprint (MB)"]
    if has_failure_col:
        header_cells += ["Failure reason"]

    lines = [
        "# Phase 3 nsys overlap verification -- summary table",
        "",
        "One row per (mode, config) at that mode's cache-bound local peak + its two grid "
        "neighbours (scripts/run_overlap_nsys.py, 05_unified_size_grid_and_plots.md Change 6). "
        "Verification-only -- not throughput." +
        (" K0/K1/SM-split/blocks/threads-per-block are the EXACT configuration "
         "that cell was profiled at (reconstructed via --fixed-blocks0/1 from "
         "the matching results/phase3_results.csv row)." if has_config_cols else "") +
        (" \"Failure reason\" distinguishes an nsys timeout from a parse failure -- both used "
         "to show as an undifferentiated N/A." if has_failure_col else ""),
        "",
        "| " + " | ".join(header_cells) + " |",
        "|" + "---|" * len(header_cells),
    ]
    for _, r in rows.iterrows():
        reason = str(r[FAILURE_COL]) if has_failure_col and pd.notna(r[FAILURE_COL]) and r[FAILURE_COL] != "" else ""
        if pd.notna(r.overlap_ratio):
            overlap_pct = f"{r.overlap_ratio * 100:.1f}%"
        else:
            overlap_pct = f"N/A ({reason})" if reason else "N/A (timeout/parse failure)"
        kiw = "" if pd.isna(r.kernel_instances_in_window) else int(r.kernel_instances_in_window)
        dgc = "" if pd.isna(r.distinct_greenctx) else int(r.distinct_greenctx)
        footprint_mb = r.combined_read_footprint_bytes / MB
        cells = [str(r.test_point_id), r["mode"], r.config, overlap_pct, str(kiw), str(dgc)]
        if has_config_cols:
            cells += [_fmt_bytes(r.k0_bytes), _fmt_bytes(r.k1_bytes),
                      f"{int(r.sm_split_k0)}:{int(r.sm_split_k1)}",
                      f"{int(r.blocks_k0)}:{int(r.blocks_k1)}", str(int(r.threads_per_block))]
        cells.append(f"{footprint_mb:.3f}")
        if has_failure_col:
            cells.append(reason)
        lines.append("| " + " | ".join(cells) + " |")

    with open(TABLE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {TABLE_PATH}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_overlap_vs_footprint(df)
    write_table(df)


if __name__ == "__main__":
    main()
