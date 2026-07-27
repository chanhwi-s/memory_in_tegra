#!/usr/bin/env python3
"""Additive Phase 2 plot: unify the x-axis to combined read footprint (MB, log2), per
prompts/02_two_kernel_size/02_combined_footprint_plot.md.

This does NOT modify any existing CSV, findings.json, or scripts/plot.py -- it only reads
this phase's results CSVs and writes new figures under results/plots/ with a
"_combined_footprint" suffix, so the existing sym_agg_vs_footprint.png / asym_vs_k1.png /
reuse_bw_vs_footprint.png are untouched.

Canonical x-axis (same formula as every other phase):
    combined_read_footprint_bytes = sum over active kernels of (num_input_buffers * per_buffer_bytes)
For this phase's C = A + B kernel (2 input buffers) with 2 concurrent kernels:
    combined_read_footprint_bytes = 2*k0_bytes + 2*k1_bytes
The results CSVs already carry this column (from phase2_bench.cu); it is reused as-is, not
re-derived, except as a fallback if a CSV is ever missing it.
"""
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
RESULTS_DIR = os.path.join(PHASE_DIR, "results")
PLOTS_DIR = os.path.join(RESULTS_DIR, "plots")
BASE_CSV = os.path.join(RESULTS_DIR, "phase2_results.csv")
REUSE_CSV = os.path.join(RESULTS_DIR, "phase2_reuse_results.csv")
PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")

MiB = 1024 * 1024

# Stated fallback values (per the prompt), used only if Phase 1's findings.json is unavailable.
FALLBACK_CACHE_BOUNDARY_MB = 2.0
FALLBACK_DRAM_PEAK_GBPS = 177.0


def ensure_footprint_column(df):
    if "combined_read_footprint_bytes" not in df.columns:
        df["combined_read_footprint_bytes"] = 2 * df.k0_bytes + 2 * df.k1_bytes
    return df


def load_base():
    if not os.path.exists(BASE_CSV):
        sys.exit(f"CSV not found: {BASE_CSV} (run scripts/run.sh first)")
    return ensure_footprint_column(pd.read_csv(BASE_CSV))


def load_reuse():
    if not os.path.exists(REUSE_CSV):
        print(f"NOTE: {REUSE_CSV} not found -- reuse overlay lines skipped "
              "(that's the additive reuse-sweep add-on's output; fine if it hasn't been run).",
              file=sys.stderr)
        return None
    return ensure_footprint_column(pd.read_csv(REUSE_CSV))


def load_refs():
    """Cache boundary (~2 MB) and measured DRAM peak, read from Phase 1's findings.json when
    available; else the prompt's stated fallback values, with a logged note."""
    if os.path.exists(PHASE1_FINDINGS):
        with open(PHASE1_FINDINGS, encoding="utf-8") as f:
            findings = json.load(f)
        dram_peak = float(findings["results"]["measured_dram_peak_GBps"])
        # "cache boundary" = largest read footprint still cache-served (L2+SLC), i.e. the last
        # point before DRAM-bound -- matches the prompt's stated "~2 MB" reference.
        cache_boundary_bytes = findings["results"]["tier_steps"]["slc_region_max_read_footprint_bytes"]
        cache_boundary_mb = cache_boundary_bytes / MiB
        return dram_peak, cache_boundary_mb, True
    print(f"NOTE: {PHASE1_FINDINGS} not found -- using stated fallback reference values "
          f"(cache boundary {FALLBACK_CACHE_BOUNDARY_MB} MB, DRAM peak {FALLBACK_DRAM_PEAK_GBPS} GB/s).",
          file=sys.stderr)
    return FALLBACK_DRAM_PEAK_GBPS, FALLBACK_CACHE_BOUNDARY_MB, False


def draw_reference_lines(ax1, ax2, dram_peak, cache_boundary_mb, from_findings):
    fallback_tag = "" if from_findings else " (fallback)"
    ax1.axvline(cache_boundary_mb, color="gray", linestyle=":", linewidth=1)
    ax1.text(cache_boundary_mb, ax1.get_ylim()[1], f" cache boundary ~{cache_boundary_mb:.2g} MB{fallback_tag}",
              va="top", ha="left", fontsize=8, color="gray")
    ax1.axhline(dram_peak, color="firebrick", linestyle=":", linewidth=1)
    ax1.text(ax1.get_xlim()[0], dram_peak, f" DRAM peak ~{dram_peak:.0f} GB/s{fallback_tag}",
              va="bottom", ha="left", fontsize=8, color="firebrick")


def plot_mode(mode, base_df, reuse_df, dram_peak, cache_boundary_mb, from_findings):
    out = os.path.join(PLOTS_DIR, f"{'sym' if mode == 'symmetric' else 'asym'}_vs_combined_footprint.png")
    if os.path.exists(out):
        print(f"NOTE: {out} already exists -- not overwriting (additive-only per prompt; "
              "delete it manually first if you want to regenerate).", file=sys.stderr)
        return

    base = base_df[base_df["mode"] == mode].sort_values("combined_read_footprint_bytes").copy()
    if base.empty:
        print(f"WARNING: no {mode} rows in {BASE_CSV}; skipping {mode} combined-footprint plot")
        return
    base["footprint_mb"] = base.combined_read_footprint_bytes / MiB

    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(base.footprint_mb, base.agg_GBps_median, marker="o", color="tab:blue", linewidth=2,
              label="aggregate GB/s (reuse N=1)")
    ax1.plot(base.footprint_mb, base.k0_GBps_median, marker=".", color="tab:cyan", linestyle="--",
              label="K0 GB/s (reuse N=1)")
    ax1.plot(base.footprint_mb, base.k1_GBps_median, marker=".", color="tab:purple", linestyle="--",
              label="K1 GB/s (reuse N=1)")

    if reuse_df is not None:
        reuse_mode = reuse_df[reuse_df["mode"] == mode].copy()
        reuse_ns = sorted(n for n in reuse_mode.reuse_N.unique() if n != 1)
        cmap = plt.get_cmap("viridis")
        for i, n in enumerate(reuse_ns):
            sub = reuse_mode[reuse_mode.reuse_N == n].copy()
            sub["footprint_mb"] = sub.combined_read_footprint_bytes / MiB
            sub = sub.sort_values("footprint_mb")
            color = cmap(i / max(1, len(reuse_ns) - 1))
            ax1.plot(sub.footprint_mb, sub.agg_GBps_median, marker="x", linestyle="-", linewidth=1,
                      color=color, alpha=0.8, label=f"aggregate GB/s (reuse N={n})")

    ax1.set_xscale("log", base=2)
    ax1.set_xlabel("Combined read footprint [MB], log2")
    ax1.set_ylabel("Achieved bandwidth (GB/s)")
    ax1.set_title(f"Phase 2{'a' if mode == 'symmetric' else 'b'}: {mode} concurrent kernels — "
                   "BW vs combined read footprint (unified axis)")
    ax1.grid(True, which="both", alpha=0.3)

    valid_eff = base[base.scaling_efficiency >= 0]
    ax2 = ax1.twinx()
    if not valid_eff.empty:
        ax2.plot(valid_eff.footprint_mb, valid_eff.scaling_efficiency, marker="s", color="tab:green",
                  alpha=0.6, label="scaling efficiency (reuse N=1)")
        ax2.set_ylabel("scaling_efficiency = agg / (single_k0_ref + single_k1_ref)", color="tab:green")
        ax2.axhline(1.0, color="tab:green", linestyle=":", linewidth=1, alpha=0.5)
    else:
        ax2.text(0.5, 0.5, "scaling_efficiency unavailable", transform=ax2.transAxes, ha="center",
                  va="center", color="tab:green", alpha=0.7)

    draw_reference_lines(ax1, ax2, dram_peak, cache_boundary_mb, from_findings)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=7)
    fig.tight_layout()

    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    base_df = load_base()
    reuse_df = load_reuse()
    dram_peak, cache_boundary_mb, from_findings = load_refs()

    for mode in ("symmetric", "asymmetric"):
        plot_mode(mode, base_df, reuse_df, dram_peak, cache_boundary_mb, from_findings)


if __name__ == "__main__":
    main()
