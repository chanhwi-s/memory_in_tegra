#!/usr/bin/env python3
"""Generate results/phase2_config.csv: the list of (mode, k0_bytes, k1_bytes) cells for
phase2_bench to measure, plus per-cell block-count hints and single-kernel reference
throughput.

Per prompts/02_two_kernel_size.md ("Dependency") and 00_conventions.md #2, Phase 2 must
read its sweep parameters and reference numbers from Phase 1's *measured* output at run
time -- never fabricate them. This script:
  - reads experiments/01_single_kernel_size/findings.json for tier_steps (to pick the
    asymmetric crossover `k`) and saturation_blocks_by_size / recommended_threads_per_block
    (as block-count hints),
  - reads experiments/01_single_kernel_size/results/phase1_results.csv for the per-size
    single-kernel achieved_GBps_median (the `single_k0_GBps_ref` / `single_k1_GBps_ref`
    columns; findings.json itself only carries summary tier numbers, not a full curve).

If either is missing (Phase 1 not yet run on hardware), it falls back to the placeholder
defaults below -- clearly marked TODO -- and single_k*_GBps_ref is written as -1 (sentinel
"unknown"; phase2_bench.cu then writes scaling_efficiency = -1 rather than inventing a value).
Re-run this script once Phase 1 has real results.
"""
import bisect
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
PHASE1_DIR = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size")
PHASE1_FINDINGS = os.path.join(PHASE1_DIR, "findings.json")
PHASE1_CSV = os.path.join(PHASE1_DIR, "results", "phase1_results.csv")
CONFIG_OUT = os.path.join(PHASE_DIR, "results", "phase2_config.csv")

DEFAULT_TPB = 256
DEFAULT_BLOCKS_HINT = 256
# TODO(read from phase1 findings): placeholders per OVERVIEW.md tier boundaries, used only
# if experiments/01_single_kernel_size/findings.json does not exist yet.
FALLBACK_DRAM_BOUND_MIN_READ_FOOTPRINT_BYTES = 16 * 1024 * 1024

MiB = 1024 * 1024


def load_phase1_findings():
    if not os.path.exists(PHASE1_FINDINGS):
        print(f"NOTE: {PHASE1_FINDINGS} not found -- using fallback defaults (TODO).",
              file=sys.stderr)
        return None
    with open(PHASE1_FINDINGS) as f:
        return json.load(f)


def load_phase1_csv():
    if not os.path.exists(PHASE1_CSV):
        print(f"NOTE: {PHASE1_CSV} not found -- single_k*_GBps_ref will be -1 (unknown).",
              file=sys.stderr)
        return None
    import pandas as pd
    return pd.read_csv(PHASE1_CSV)


def nearest_saturation_blocks(findings, size_bytes):
    if not findings:
        return DEFAULT_BLOCKS_HINT
    table = findings.get("results", {}).get("saturation_blocks_by_size", {})
    if not table:
        return DEFAULT_BLOCKS_HINT
    sizes = sorted(int(k) for k in table.keys())
    idx = bisect.bisect_left(sizes, size_bytes)
    if idx == 0:
        nearest = sizes[0]
    elif idx == len(sizes):
        nearest = sizes[-1]
    else:
        before, after = sizes[idx - 1], sizes[idx]
        nearest = before if (size_bytes - before) <= (after - size_bytes) else after
    return int(table[str(nearest)])


def single_kernel_ref_GBps(df, size_bytes):
    """Nearest-size, reuse_N=1, saturated-row achieved_GBps_median from Phase 1's raw CSV."""
    if df is None:
        return -1.0
    sub = df[(df.reuse_N == 1) & (df.saturated == 1)]
    if sub.empty:
        return -1.0
    sizes = sorted(sub.size_per_buffer_bytes.unique())
    idx = bisect.bisect_left(sizes, size_bytes)
    if idx == 0:
        nearest = sizes[0]
    elif idx == len(sizes):
        nearest = sizes[-1]
    else:
        before, after = sizes[idx - 1], sizes[idx]
        nearest = before if (size_bytes - before) <= (after - size_bytes) else after
    rows = sub[sub.size_per_buffer_bytes == nearest]
    return float(rows.achieved_GBps_median.max())


def symmetric_sizes_bytes():
    """Per-kernel size S; combined read footprint for symmetric mode is 4*S (2*S per kernel,
    two kernels). Densified so 4*S lands near L2=4MB and L2+SLC=8MB, i.e. S near 1MB and 2MB
    (prompt: "Sweep S across the same tiers as Phase 1 ... per combined footprint of both
    kernels")."""
    return [
        int(x * MiB) for x in
        [0.125, 0.25, 0.5, 0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 3.0, 4.0, 6.0, 12.0, 24.0]
    ]


def asymmetric_k1_sizes_bytes(k_bytes):
    """K1 sizes swept up to and past the crossover point k (per-buffer bytes)."""
    fracs = [0.125, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
    return sorted(set(int(f * k_bytes) for f in fracs if int(f * k_bytes) > 0))


def main():
    findings = load_phase1_findings()
    df = load_phase1_csv()

    if findings:
        dram_bound_min_footprint = findings["results"]["tier_steps"]["dram_bound_min_read_footprint_bytes"]
        recommended_tpb = findings["results"].get("recommended_threads_per_block", DEFAULT_TPB)
        consumed_note = f"consumed {os.path.relpath(PHASE1_FINDINGS, REPO_ROOT)}"
    else:
        dram_bound_min_footprint = FALLBACK_DRAM_BOUND_MIN_READ_FOOTPRINT_BYTES
        recommended_tpb = DEFAULT_TPB
        consumed_note = "TODO(read from phase1 findings): phase1 findings.json missing, using fallback"

    # k = per-buffer size at the cache-overflow / bound-crossover point (read-footprint -> per-buffer).
    k_bytes = dram_bound_min_footprint // 2
    print(f"asymmetric k (per-buffer bytes) = {k_bytes} ({consumed_note})", file=sys.stderr)

    rows = []  # mode, k0_bytes, k1_bytes, blocks_k0_hint, blocks_k1_hint, tpb, ref0, ref1

    for s in symmetric_sizes_bytes():
        blocks_hint = nearest_saturation_blocks(findings, s)
        ref = single_kernel_ref_GBps(df, s)
        rows.append(("symmetric", s, s, blocks_hint, blocks_hint, recommended_tpb, ref, ref))

    k0_fixed = 1 * MiB
    blocks_k0_hint = nearest_saturation_blocks(findings, k0_fixed)
    ref_k0 = single_kernel_ref_GBps(df, k0_fixed)
    for k1 in asymmetric_k1_sizes_bytes(k_bytes):
        blocks_k1_hint = nearest_saturation_blocks(findings, k1)
        ref_k1 = single_kernel_ref_GBps(df, k1)
        rows.append(("asymmetric", k0_fixed, k1, blocks_k0_hint, blocks_k1_hint, recommended_tpb,
                     ref_k0, ref_k1))

    os.makedirs(os.path.dirname(CONFIG_OUT), exist_ok=True)
    with open(CONFIG_OUT, "w", encoding="utf-8") as f:
        f.write("mode,k0_bytes,k1_bytes,blocks_k0_hint,blocks_k1_hint,threads_per_block,"
                "single_k0_GBps_ref,single_k1_GBps_ref\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]:.6f},{r[7]:.6f}\n")

    print(f"wrote {CONFIG_OUT} ({len(rows)} cells: "
          f"{sum(1 for r in rows if r[0]=='symmetric')} symmetric, "
          f"{sum(1 for r in rows if r[0]=='asymmetric')} asymmetric)")
    if findings is None or df is None:
        print("WARNING: Phase 1 findings/CSV not (fully) available -- this config uses "
              "fallback defaults and/or -1 reference throughput. Record this in the worklog; "
              "re-run gen_config.py once Phase 1 has real results.", file=sys.stderr)


if __name__ == "__main__":
    main()
