#!/usr/bin/env python3
"""Generate Phase 4 v2 plots from results/phase4_results.csv. Runnable from anywhere.

v2 (prompts/04_zero_copy_v2.md) changes vs the first run:
- zc_vs_cached_reuse.png: panels now ordered by mode then by large-kernel size (k1_bytes)
  ascending, so the widened asymmetric sweep reads left-to-right as the large kernel grows.
- zc_benefit_map.png: heatmap is now (large-kernel size) x (reuse N) restricted to the
  asymmetric sweep -- the "large kernel" story lives there, not in the symmetric points
  (Change 2). Anchor rows (is_anchor==1) are marked with a leading '*' in the row label.
- crossover_vs_size.png: new. crossover reuse N vs large-kernel (K1) size, one line per
  config, log-x. Points where no crossover was observed in 1..32 are plotted as open
  markers above the axis (not at y=0, which would misleadingly read as "crosses over
  immediately").
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
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase4_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")

NO_CROSSOVER_SENTINEL = 48  # plotting position for "never crossed over in 1..32"


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    return pd.read_csv(CSV_PATH, na_values=["NA"])


def fmt_bytes(n):
    n = float(n)
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f}MB"
    return f"{n / 1024:.0f}KB"


def find_crossover(zc_sorted_by_reuse):
    """zc_sorted_by_reuse: DataFrame of zerocopy rows for one (test_point_id, config), sorted
    by reuse_N. Returns 0 if the delta sign never flips across the swept range."""
    prev_sign = None
    first = True
    for _, row in zc_sorted_by_reuse.iterrows():
        d = row.get("delta_vs_cached_pct")
        if pd.isna(d):
            continue
        cur_sign = d >= 0
        if first:
            prev_sign = cur_sign
            first = False
            continue
        if cur_sign != prev_sign:
            return int(row["reuse_N"])
        prev_sign = cur_sign
    return 0


def sort_key(tpid_config, df):
    tpid, config = tpid_config
    sub = df[(df.test_point_id == tpid) & (df.config == config)]
    mode = sub["mode"].iloc[0] if not sub.empty else "zzz"
    k1 = sub.k1_bytes.iloc[0] if not sub.empty else 0
    return (0 if mode == "asymmetric" else 1, k1, config)


def plot_zc_vs_cached_reuse(df):
    points = list(df.groupby(["test_point_id", "config"]).groups.keys())
    points.sort(key=lambda p: sort_key(p, df))
    n = len(points)
    if n == 0:
        print("WARNING: no test points to plot")
        return
    ncols = min(4, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.5 * nrows), squeeze=False)

    for idx, (tpid, config) in enumerate(points):
        ax = axes[idx // ncols][idx % ncols]
        sub = df[(df.test_point_id == tpid) & (df.config == config)]
        is_anchor = bool(sub.is_anchor.iloc[0]) if "is_anchor" in sub.columns and not sub.empty else False
        k1_label = fmt_bytes(sub.k1_bytes.iloc[0]) if not sub.empty else "?"
        for path, marker in [("cached", "o"), ("zerocopy", "s")]:
            line = sub[sub.large_kernel_path == path].sort_values("reuse_N")
            if line.empty:
                continue
            ax.plot(line.reuse_N, line.agg_GBps_median, marker=marker, label=path)

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
        anchor_mark = " [anchor]" if is_anchor else ""
        ax.set_title(f"{tpid} ({config}) k1={k1_label}{anchor_mark}", fontsize=8)
        ax.legend(fontsize=7)
        ax.grid(True, which="both", alpha=0.3)

    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].axis("off")

    fig.suptitle("Phase 4 v2: aggregate GB/s vs reuse N, cached vs zero-copy "
                 "(ordered: asymmetric by K1 size, then symmetric)")
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "zc_vs_cached_reuse.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def plot_zc_benefit_map(df):
    """Heatmap of zero-copy delta_pct over (large-kernel size) x (reuse N), restricted to
    the asymmetric sweep -- prompts/04_zero_copy_v2.md Change 2: this is the "payoff figure"
    mapping the crossover surface across cache tiers for the large/streaming kernel."""
    zc = df[(df.large_kernel_path == "zerocopy") & (df["mode"] == "asymmetric")].copy()
    if zc.empty:
        print("WARNING: no asymmetric zerocopy rows to plot (falling back to all modes)")
        zc = df[df.large_kernel_path == "zerocopy"].copy()
        if zc.empty:
            print("WARNING: no zerocopy rows to plot at all")
            return

    zc["size_label"] = zc.apply(
        lambda r: ("* " if bool(r.get("is_anchor", False)) else "") + fmt_bytes(r.k1_bytes) +
                  f" ({r.config})",
        axis=1,
    )
    zc = zc.sort_values("k1_bytes")
    pivot = zc.pivot_table(index="size_label", columns="reuse_N", values="delta_vs_cached_pct",
                            aggfunc="mean", sort=False)
    pivot = pivot.reindex(zc.drop_duplicates("size_label").sort_values("k1_bytes")["size_label"])
    pivot = pivot[sorted(pivot.columns)]

    fig, ax = plt.subplots(figsize=(8, 0.5 * len(pivot) + 2))
    vmax = np.nanmax(np.abs(pivot.values)) if pivot.size and np.isfinite(pivot.values).any() else 1.0
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xlabel("reuse N")
    ax.set_title("Phase 4 v2: zero-copy delta vs cached (%) over large-kernel (K1) size x reuse N\n"
                  "('*' = original Phase-4-v1 anchor point)")
    fig.colorbar(im, ax=ax, label="delta_vs_cached_pct")

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7)

    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "zc_benefit_map.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def plot_crossover_vs_size(df):
    """New in v2: crossover reuse N vs large-kernel size, one line per config. Points with
    no observed crossover in 1..32 are drawn as open markers at NO_CROSSOVER_SENTINEL with
    an annotation, rather than at y=0 (which would misleadingly mean "crosses over
    immediately")."""
    zc = df[(df.large_kernel_path == "zerocopy") & (df["mode"] == "asymmetric")].copy()
    if zc.empty:
        print("WARNING: no asymmetric zerocopy rows for crossover_vs_size.png")
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    for config, group in zc.groupby("config"):
        xs, ys, never = [], [], []
        for (tpid,), sub in group.groupby(["test_point_id"]):
            sub = sub.sort_values("reuse_N")
            crossover_n = find_crossover(sub)
            k1 = sub.k1_bytes.iloc[0]
            xs.append(k1)
            if crossover_n == 0:
                ys.append(NO_CROSSOVER_SENTINEL)
                never.append(True)
            else:
                ys.append(crossover_n)
                never.append(False)
        order = np.argsort(xs)
        xs = np.array(xs)[order]
        ys = np.array(ys)[order]
        never = np.array(never)[order]

        ax.plot(xs, ys, "-", label=config, alpha=0.6, zorder=1)
        solid = ~never
        if solid.any():
            ax.scatter(xs[solid], ys[solid], marker="o", zorder=2)
        if never.any():
            ax.scatter(xs[never], ys[never], marker="^", facecolors="none",
                       edgecolors="C0", zorder=2, s=80)

    ax.axhline(NO_CROSSOVER_SENTINEL, color="gray", linestyle=":", linewidth=1)
    ax.text(ax.get_xlim()[0], NO_CROSSOVER_SENTINEL, " never crossed (1..32)", fontsize=8,
            va="bottom", color="gray")
    ax.set_xscale("log")
    ax.set_yscale("log", base=2)
    ax.set_xlabel("large-kernel (K1) size, bytes")
    ax.set_ylabel("crossover reuse N (zero-copy stops winning)")
    ax.set_title("Phase 4 v2: crossover reuse N vs large-kernel size")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "crossover_vs_size.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_zc_vs_cached_reuse(df)
    plot_zc_benefit_map(df)
    plot_crossover_vs_size(df)


if __name__ == "__main__":
    main()
