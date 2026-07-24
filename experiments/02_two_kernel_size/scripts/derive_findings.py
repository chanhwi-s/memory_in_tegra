#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase2_results.csv.

Numbers are computed from the actual measured CSV — never hand-typed — so this must be
re-run (not hand-edited) whenever the CSV changes. Run after run.sh.
"""
import datetime
import json
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase2_results.csv")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")
PHASE1_FINDINGS_PATH = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size",
                                     "findings.json")
PHASE1_FINDINGS_REL = "experiments/01_single_kernel_size/findings.json"

ONSET_EFFICIENCY_THRESHOLD = 0.95  # scaling_efficiency below this = "contention onset"


def contention_onset(sym):
    """First (smallest-footprint) symmetric row whose scaling_efficiency drops below the
    threshold. Returns None if no row has a valid ref (all scaling_efficiency == -1) or
    none drops below threshold within the measured range."""
    valid = sym[sym.scaling_efficiency >= 0].sort_values("combined_read_footprint_bytes")
    if valid.empty:
        return None
    below = valid[valid.scaling_efficiency < ONSET_EFFICIENCY_THRESHOLD]
    if below.empty:
        return None
    return below.iloc[0]


def ninety_pct_point(sym, onset_row):
    """Largest symmetric per-kernel size strictly below the onset point (prompt: "a point
    ~90% below it" for Phase 3/4 to also test)."""
    below_onset = sym[sym.k0_bytes < onset_row.k0_bytes].sort_values("k0_bytes")
    if below_onset.empty:
        return None
    return below_onset.iloc[-1]


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/gen_config.py + the built binary first)")
    df = pd.read_csv(CSV_PATH)

    # NOTE: use df["mode"], not df.mode -- DataFrame.mode() is a built-in method, so
    # attribute access here would silently return the method object, not the column.
    sym = df[df["mode"] == "symmetric"].copy()
    asym = df[df["mode"] == "asymmetric"].copy()

    consumed = []
    if os.path.exists(PHASE1_FINDINGS_PATH):
        consumed.append(PHASE1_FINDINGS_REL)

    results = {}
    warnings = []

    onset_row = contention_onset(sym) if not sym.empty else None
    if onset_row is not None:
        results["symmetric_contention_onset"] = {
            "per_kernel_bytes": int(onset_row.k0_bytes),
            "combined_footprint_bytes": int(onset_row.combined_read_footprint_bytes),
            "scaling_efficiency": round(float(onset_row.scaling_efficiency), 4),
        }
        ninety_row = ninety_pct_point(sym, onset_row)
        results["symmetric_roofline_points"] = {
            "onset": {"per_kernel_bytes": int(onset_row.k0_bytes)},
            "ninety_pct": {"per_kernel_bytes": int(ninety_row.k0_bytes) if ninety_row is not None
                           else None},
        }
    else:
        warnings.append("No symmetric contention onset found (scaling_efficiency stayed >= "
                         f"{ONSET_EFFICIENCY_THRESHOLD} across the measured range, or refs were "
                         "unavailable/-1 because Phase 1 hasn't been run). Re-check once Phase 1 "
                         "findings are real and/or extend the symmetric size sweep.")
        results["symmetric_contention_onset"] = None
        results["symmetric_roofline_points"] = None

    # asymmetric_k_used_bytes: the crossover point Phase 1 findings pointed at, i.e. the
    # k1_bytes value closest to Phase 1's dram_bound_min_read_footprint_bytes / 2 among the
    # cells actually measured.
    k_used_bytes = None
    if not asym.empty and os.path.exists(PHASE1_FINDINGS_PATH):
        with open(PHASE1_FINDINGS_PATH) as f:
            phase1 = json.load(f)
        k_target = phase1["results"]["tier_steps"]["dram_bound_min_read_footprint_bytes"] // 2
        idx = (asym.k1_bytes - k_target).abs().idxmin()
        k_used_bytes = int(asym.loc[idx, "k1_bytes"])
        row_at_k = asym.loc[idx]
    elif not asym.empty:
        warnings.append("Phase 1 findings.json unavailable -- asymmetric_k_used_bytes reports "
                         "the largest measured K1 size as a placeholder rather than the true "
                         "cache-crossover k. Re-run gen_config.py + this script once Phase 1 "
                         "has real results.")
        row_at_k = asym.sort_values("k1_bytes").iloc[-1]
        k_used_bytes = int(row_at_k.k1_bytes)

    if k_used_bytes is not None:
        results["asymmetric_k_used_bytes"] = k_used_bytes
        results["asymmetric_result_at_k"] = {
            "agg_GBps": round(float(row_at_k.agg_GBps_median), 3),
            "k0_GBps": round(float(row_at_k.k0_GBps_median), 3),
            "k1_GBps": round(float(row_at_k.k1_GBps_median), 3),
        }
    else:
        results["asymmetric_k_used_bytes"] = None
        results["asymmetric_result_at_k"] = None
        warnings.append("No asymmetric rows in CSV.")

    recommended_points = []
    if onset_row is not None:
        recommended_points.append({"mode": "symmetric", "per_kernel_bytes": int(onset_row.k0_bytes)})
        ninety_row = ninety_pct_point(sym, onset_row)
        if ninety_row is not None:
            recommended_points.append({"mode": "symmetric",
                                        "per_kernel_bytes": int(ninety_row.k0_bytes)})
    if k_used_bytes is not None:
        recommended_points.append({"mode": "asymmetric", "k1_bytes": k_used_bytes})
    results["recommended_phase3_test_points"] = recommended_points

    findings = {
        "schema_version": "1.0",
        "phase": "02_two_kernel_size",
        "generated_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv": "experiments/02_two_kernel_size/results/phase2_results.csv",
        "env_ref": "shared/env.md",
        "results": results,
        "consumed": consumed,
    }

    with open(FINDINGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    print(f"wrote {FINDINGS_JSON_PATH}")

    onset_md = (
        f"- **Per-kernel size:** {results['symmetric_contention_onset']['per_kernel_bytes']:,} bytes "
        f"(~{results['symmetric_contention_onset']['per_kernel_bytes'] / (1024*1024):.2f} MB)\n"
        f"- **Combined read footprint:** {results['symmetric_contention_onset']['combined_footprint_bytes']:,} bytes\n"
        f"- **scaling_efficiency at onset:** {results['symmetric_contention_onset']['scaling_efficiency']}"
        if results["symmetric_contention_onset"] else "Not found in the measured range — see warnings below."
    )

    asym_md = (
        f"- **k (per-buffer bytes):** {results['asymmetric_k_used_bytes']:,}\n"
        f"- **aggregate GB/s at k:** {results['asymmetric_result_at_k']['agg_GBps']}\n"
        f"- **K0 GB/s at k:** {results['asymmetric_result_at_k']['k0_GBps']}\n"
        f"- **K1 GB/s at k:** {results['asymmetric_result_at_k']['k1_GBps']}"
        if results["asymmetric_result_at_k"] else "No asymmetric rows measured."
    )

    warnings_md = ("\n".join(f"- {w}" for w in warnings) if warnings else "None.")

    md = f"""# Phase 2 Findings — Two-Kernel Size Sweep

Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers below are
computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not hand-edit)
if the CSV is regenerated. Consumed upstream: {', '.join(consumed) if consumed else 'none (Phase 1 findings.json not available yet)'}.

## 2a — Symmetric contention onset

{onset_md}

`symmetric_roofline_points` (onset + ~90%-below point, for Phase 3/4): see `findings.json`.

## 2b — Asymmetric result at k

{asym_md}

## Recommended Phase 3 test points

{chr(10).join(f"- {p}" for p in results["recommended_phase3_test_points"]) if results["recommended_phase3_test_points"] else "None derivable yet."}

## Warnings / caveats

{warnings_md}

## Verification (00_conventions.md / prompt Verification section)

Re-check by eye against `results/plots/sym_agg_vs_footprint.png` and `results/plots/asym_vs_k1.png`:
- Symmetric: scaling_efficiency should be ~1 well below L2 (4 MB combined) and drop as combined
  footprint exceeds cache.
- The benchmark binary itself (`src/phase2_bench.cu`) prints a `WARNING` to stderr for any cell
  where `wall_ms_median >= serial_sum_ms` (no measured overlap) or a correctness mismatch — check
  the run log for these before trusting this file.
"""
    with open(FINDINGS_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {FINDINGS_MD_PATH}")


if __name__ == "__main__":
    main()
