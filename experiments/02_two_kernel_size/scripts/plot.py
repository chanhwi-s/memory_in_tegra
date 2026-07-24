#!/usr/bin/env python3
"""Generate Phase 2 plots from results/phase2_results.csv. Runnable from anywhere."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase2_results.csv")
PLOTS_DIR = os.path.join(PHASE_DIR, "results", "plots")
PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")

L2_BYTES = 4 * 1024 * 1024
L2_SLC_BYTES = 8 * 1024 * 1024
ONSET_EFFICIENCY_THRESHOLD = 0.95  # matches derive_findings.py


def load_k_bytes():
    """Same derivation as gen_config.py: k (per-buffer bytes) = dram-bound read-footprint
    boundary / 2. Returns None if Phase 1 findings aren't available yet."""
    if not os.path.exists(PHASE1_FINDINGS):
        return None
    with open(PHASE1_FINDINGS) as f:
        findings = json.load(f)
    footprint = findings["results"]["tier_steps"]["dram_bound_min_read_footprint_bytes"]
    return footprint // 2


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    return pd.read_csv(CSV_PATH)


def plot_symmetric(df):
    # NOTE: df["mode"], not df.mode -- DataFrame.mode() is a built-in method.
    sym = df[df["mode"] == "symmetric"].sort_values("combined_read_footprint_bytes")
    if sym.empty:
        print("WARNING: no symmetric rows; skipping sym_agg_vs_footprint.png")
        return

    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(sym.combined_read_footprint_bytes, sym.agg_GBps_median, marker="o",
              color="tab:blue", label="aggregate GB/s")
    ax1.plot(sym.combined_read_footprint_bytes, sym.k0_GBps_median, marker=".",
              color="tab:cyan", linestyle="--", label="K0 GB/s")
    ax1.plot(sym.combined_read_footprint_bytes, sym.k1_GBps_median, marker=".",
              color="tab:purple", linestyle="--", label="K1 GB/s")
    ax1.set_xscale("log", base=2)
    ax1.set_xlabel("Combined read footprint, both kernels (bytes, log2)")
    ax1.set_ylabel("Achieved bandwidth (GB/s)")

    ax1.axvline(L2_BYTES, color="gray", linestyle=":", linewidth=1)
    ax1.text(L2_BYTES, ax1.get_ylim()[1], " 4MB (L2)", va="top", ha="left", fontsize=8, color="gray")
    ax1.axvline(L2_SLC_BYTES, color="gray", linestyle=":", linewidth=1)
    ax1.text(L2_SLC_BYTES, ax1.get_ylim()[1], " 8MB (L2+SLC)", va="top", ha="left", fontsize=8,
             color="gray")

    valid_eff = sym[sym.scaling_efficiency >= 0]
    onset_row = None
    if not valid_eff.empty:
        below = valid_eff[valid_eff.scaling_efficiency < ONSET_EFFICIENCY_THRESHOLD]
        if not below.empty:
            onset_row = below.iloc[0]
            ax1.axvline(onset_row.combined_read_footprint_bytes, color="firebrick", linestyle="--",
                        linewidth=1.5)
            ax1.text(onset_row.combined_read_footprint_bytes, ax1.get_ylim()[0],
                      " contention onset", va="bottom", ha="left", fontsize=8, color="firebrick")

    ax2 = ax1.twinx()
    if not valid_eff.empty:
        ax2.plot(valid_eff.combined_read_footprint_bytes, valid_eff.scaling_efficiency,
                  marker="s", color="tab:green", alpha=0.6, label="scaling efficiency")
        ax2.set_ylabel("scaling_efficiency = agg / (single_k0_ref + single_k1_ref)",
                        color="tab:green")
        ax2.axhline(1.0, color="tab:green", linestyle=":", linewidth=1, alpha=0.5)
    else:
        ax2.text(0.5, 0.5, "scaling_efficiency unavailable\n(Phase 1 refs missing)",
                  transform=ax2.transAxes, ha="center", va="center", color="tab:green", alpha=0.7)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    ax1.set_title("Phase 2a: symmetric concurrent kernels — BW & scaling efficiency vs combined footprint")
    ax1.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "sym_agg_vs_footprint.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_asymmetric(df):
    asym = df[df["mode"] == "asymmetric"].sort_values("k1_bytes")
    if asym.empty:
        print("WARNING: no asymmetric rows; skipping asym_vs_k1.png")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(asym.k1_bytes, asym.agg_GBps_median, marker="o", label="aggregate GB/s")
    ax.plot(asym.k1_bytes, asym.k0_GBps_median, marker=".", linestyle="--", label="K0 GB/s (fixed 1MB)")
    ax.plot(asym.k1_bytes, asym.k1_GBps_median, marker=".", linestyle="--", label="K1 GB/s")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("K1 size, per-buffer (bytes, log2); K0 fixed at 1 MB")
    ax.set_ylabel("Achieved bandwidth (GB/s)")

    k_bytes = load_k_bytes()
    if k_bytes is not None:
        ax.axvline(k_bytes, color="firebrick", linestyle="--", linewidth=1.5)
        ax.text(k_bytes, ax.get_ylim()[1], f" k ({k_bytes / (1024*1024):.1f} MB)", va="top",
                ha="left", fontsize=8, color="firebrick")
    else:
        print("NOTE: Phase 1 findings.json not available yet -- k not marked on asym_vs_k1.png")
    ax.set_title("Phase 2b: asymmetric concurrent kernels — BW vs K1 size")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "asym_vs_k1.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    df = load()
    plot_symmetric(df)
    plot_asymmetric(df)


if __name__ == "__main__":
    main()
