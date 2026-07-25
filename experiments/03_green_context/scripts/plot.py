#!/usr/bin/env python3
"""Generate Phase 3 v3 plots from results/phase3_results.csv (+ the optional
reuse overlay CSV). Runnable from anywhere.

v2 changes vs the original plot.py (prompts/03_green_context_v2.md "Metrics / CSV / plots"):
  - green_vs_shared.png is now a function of per-kernel size (the widened sweep),
    not 3 bar-chart test points, with Phase 2's roofline anchors marked.
  - partition_sweep.png now contrasts TWO regimes side by side: a small-size point
    (L1/scheduling-sensitive) and the roofline anchor point (DRAM-bound), instead
    of a single "onset" point.
  - delta_vs_size.png is new: green's aggregate-throughput delta (%) vs shared,
    plotted against per-kernel size, with the zero line marked.

v3 changes (prompts/03_green_context_v3.md):
  - Change 2: every size x-axis (green_vs_shared.png, delta_vs_size.png) is now
    log BASE 2 with power-of-two tick labels (256K, 512K, 1M, ...) instead of
    matplotlib's default log10 -- these are byte sizes, base-2 is the natural
    axis. partition_sweep.png's x-axis is untouched (it's the categorical SM
    split, e.g. "8:8", not a size).
  - Change 3: new plot_reuse_overlay() -> results/plots/reuse_green_vs_shared.png,
    read from the SEPARATE results/phase3_reuse_results.csv (written by
    scripts/sweep_reuse.py). Purely additive: if that CSV doesn't exist yet
    (the reuse overlay hasn't been run), this step is skipped with a note --
    it never blocks the reuse=1 plots above.
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
REUSE_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_reuse_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")


def _fmt_bytes(x, _pos):
    for unit, div in (("M", 1024 * 1024), ("K", 1024)):
        if x >= div:
            v = x / div
            return f"{v:.0f}{unit}" if v == int(v) else f"{v:.2f}{unit}"
    return f"{int(x)}"


def _set_log2_bytes_axis(ax):
    """v3 Change 2: power-of-2 x-axis for byte-size axes (not the categorical
    SM-split axis in partition_sweep.png)."""
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_bytes))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df = pd.read_csv(CSV_PATH)
    df["is_anchor"] = df.test_point_id.str.contains("anchor")
    # per-kernel size swept: symmetric -> k0_bytes (== k1_bytes); asymmetric -> k1_bytes (K0 fixed).
    df["swept_size_bytes"] = np.where(df["mode"] == "symmetric", df.k0_bytes, df.k1_bytes)
    return df


def _point_summary(df, mode):
    """One row per test_point_id for the given mode: swept size, shared agg GB/s,
    best-green agg GB/s + split, is_anchor."""
    sub = df[df["mode"] == mode]
    rows = []
    for tp, g in sub.groupby("test_point_id"):
        shared = g[g.config == "shared"]
        green = g[g.config == "green"]
        if shared.empty:
            continue
        shared_agg = shared.agg_GBps_median.iloc[0]
        best_green_agg = green.agg_GBps_median.max() if not green.empty else np.nan
        rows.append({
            "test_point_id": tp,
            "size": g.swept_size_bytes.iloc[0],
            "is_anchor": bool(g.is_anchor.iloc[0]),
            "shared_agg_GBps": shared_agg,
            "best_green_agg_GBps": best_green_agg,
            "delta_pct": (best_green_agg - shared_agg) / shared_agg * 100.0 if shared_agg else np.nan,
        })
    return pd.DataFrame(rows).sort_values("size") if rows else pd.DataFrame(
        columns=["test_point_id", "size", "is_anchor", "shared_agg_GBps", "best_green_agg_GBps", "delta_pct"])


def plot_green_vs_shared(df):
    """Aggregate GB/s, shared vs best-green, as a function of per-kernel size,
    one panel per mode; roofline anchors marked with a star."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, mode in zip(axes, ["symmetric", "asymmetric"]):
        s = _point_summary(df, mode)
        if s.empty:
            ax.set_title(f"{mode} (no data)")
            continue
        ax.plot(s["size"], s["shared_agg_GBps"], marker="o", label="shared (baseline)")
        ax.plot(s["size"], s["best_green_agg_GBps"], marker="s", label="best green (partitioned)")
        anchors = s[s.is_anchor]
        if not anchors.empty:
            ax.scatter(anchors["size"], anchors["shared_agg_GBps"], marker="*", s=200,
                       color="black", zorder=5, label="Phase 2 anchor")
            ax.scatter(anchors["size"], anchors["best_green_agg_GBps"], marker="*", s=200,
                       color="black", zorder=5)
        _set_log2_bytes_axis(ax)
        xlabel = "per-kernel size (bytes, log2)" if mode == "symmetric" else "K1 size (bytes, log2; K0 fixed 1 MB)"
        ax.set_xlabel(xlabel)
        ax.set_title(f"Phase 3 v3: {mode}")
        ax.grid(True, alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("Aggregate achieved bandwidth (GB/s)")
    fig.suptitle("Shared vs best-green aggregate throughput across the widened size sweep")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "green_vs_shared.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def _pick_contrast_points(df):
    """Pick a small-size (L1/scheduling-sensitive) symmetric point and the
    roofline anchor symmetric point, so partition_sweep.png contrasts the two
    regimes side by side (prompt: "at a small-size point AND at the roofline
    point"). The roofline anchor is the LARGEST-size symmetric anchor (Phase 2's
    contention-onset point, 917504 B, is bigger than its ninety_pct point,
    786432 B) -- anchor ids are `sym_anchor_<bytes>`, not name-tagged
    "onset", so size order is how we pick it."""
    sym = df[df["mode"] == "symmetric"].copy()
    if sym.empty:
        return None, None
    sizes_by_tp = sym.groupby("test_point_id").swept_size_bytes.first()

    anchor_tps = sym[sym.is_anchor].test_point_id.unique()
    if len(anchor_tps):
        roofline_tp = sizes_by_tp[anchor_tps].idxmax()
    else:
        roofline_tp = sizes_by_tp.idxmax()

    non_anchor_tps = sym[~sym.is_anchor].test_point_id.unique()
    if len(non_anchor_tps):
        small_tp = sizes_by_tp[non_anchor_tps].idxmin()
    else:
        small_tp = sizes_by_tp.idxmin()

    return small_tp, roofline_tp


def _plot_split_panel(ax, df, tp):
    sub = df[(df.test_point_id == tp) & (df.config == "green")].copy()
    if sub.empty:
        ax.set_title(f"{tp} (no green rows)")
        return
    sub["split_label"] = sub.sm_split_k0.astype(str) + ":" + sub.sm_split_k1.astype(str)
    sub = sub.sort_values("sm_split_k0")
    ax.plot(sub.split_label, sub.agg_GBps_median, marker="o", label="aggregate")
    ax.plot(sub.split_label, sub.k0_GBps_median, marker="s", label="K0")
    ax.plot(sub.split_label, sub.k1_GBps_median, marker="^", label="K1")
    size_bytes = int(sub.k0_bytes.iloc[0])
    ax.set_xlabel(f"SM split (K0:K1) -- {tp} (per-kernel size {size_bytes:,} B)")
    ax.set_ylabel("Achieved bandwidth (GB/s)")
    ax.grid(True, alpha=0.3)
    ax.legend()


def plot_partition_sweep(df):
    """Aggregate + per-kernel GB/s vs SM split ratio, contrasting a small-size
    (L1/scheduling) point and the roofline (DRAM-bound) anchor point."""
    small_tp, roofline_tp = _pick_contrast_points(df)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if small_tp:
        _plot_split_panel(axes[0], df, small_tp)
        axes[0].set_title(f"Small-size point: {small_tp}")
    else:
        axes[0].set_title("(no small-size point)")
    if roofline_tp:
        _plot_split_panel(axes[1], df, roofline_tp)
        axes[1].set_title(f"Roofline anchor: {roofline_tp}")
    else:
        axes[1].set_title("(no roofline anchor)")
    fig.suptitle("Phase 3 v3: throughput vs SM partition ratio -- small vs roofline regime")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "partition_sweep.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_delta_vs_size(df):
    """Green delta (%) vs per-kernel size, zero line marked -- shows any
    crossover into 'green helps' across the sweep."""
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = {"symmetric": "tab:blue", "asymmetric": "tab:orange"}
    for mode in ["symmetric", "asymmetric"]:
        s = _point_summary(df, mode)
        if s.empty:
            continue
        ax.plot(s["size"], s["delta_pct"], marker="o", label=mode, color=colors[mode])
        anchors = s[s.is_anchor]
        if not anchors.empty:
            ax.scatter(anchors["size"], anchors["delta_pct"], marker="*", s=200,
                       color="black", zorder=5)
    ax.axhline(0, color="gray", linestyle="--", linewidth=1, label="shared baseline (0%)")
    _set_log2_bytes_axis(ax)
    ax.set_xlabel("swept per-kernel size (bytes, log2; symmetric=per-kernel, asymmetric=K1)")
    ax.set_ylabel("best-green delta vs shared (%)")
    ax.set_title("Phase 3 v3: green-context delta vs shared across the size sweep")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "delta_vs_size.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def _load_dram_peak_GBps():
    if not os.path.exists(PHASE1_FINDINGS):
        return None
    with open(PHASE1_FINDINGS) as f:
        d = json.load(f)
    return d.get("results", {}).get("measured_dram_peak_GBps")


def plot_reuse_overlay():
    """v3 Change 3: one panel per reuse-overlay subset size, aggregate GB/s vs
    reuse_N (log base 2), shared vs best-green, DRAM-peak reference line.
    Purely additive -- skips cleanly if the overlay CSV hasn't been generated
    yet (scripts/sweep_reuse.py), never blocks the reuse=1 plots above."""
    if not os.path.exists(REUSE_CSV_PATH):
        print(f"NOTE: {REUSE_CSV_PATH} not found -- skipping reuse_green_vs_shared.png "
              f"(run scripts/sweep_reuse.py to generate the reuse overlay; this does not "
              f"affect the reuse=1 plots above).", file=sys.stderr)
        return

    df = pd.read_csv(REUSE_CSV_PATH)
    dram_peak = _load_dram_peak_GBps()

    tp_size = df.groupby("test_point_id").k0_bytes.first().sort_values()
    test_points = list(tp_size.index)
    n = max(len(test_points), 1)

    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5), squeeze=False)
    axes = axes[0]
    for ax, tp in zip(axes, test_points):
        sub = df[df.test_point_id == tp]
        for config, marker in (("shared", "o"), ("green", "s")):
            csub = sub[sub.config == config].sort_values("reuse_N")
            if csub.empty:
                continue
            ax.plot(csub.reuse_N, csub.agg_GBps_median, marker=marker, label=config)
        if dram_peak:
            ax.axhline(dram_peak, color="gray", linestyle=":", linewidth=1,
                       label=f"DRAM peak ({dram_peak:.1f} GB/s)")
        ax.set_xscale("log", base=2)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _pos: f"{int(round(x))}"))
        ax.xaxis.set_minor_formatter(mticker.NullFormatter())
        ax.set_xlabel(f"reuse_N (log2) -- {tp} ({_fmt_bytes(int(tp_size[tp]), None)}/kernel)")
        ax.set_ylabel("Aggregate achieved bandwidth (GB/s)")
        ax.set_title(tp)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Phase 3 v3 reuse overlay: aggregate GB/s vs reuse_N, shared vs best-green "
                 "(blocks held fixed across N)")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "reuse_green_vs_shared.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_green_vs_shared(df)
    plot_partition_sweep(df)
    plot_delta_vs_size(df)
    plot_reuse_overlay()


if __name__ == "__main__":
    main()
