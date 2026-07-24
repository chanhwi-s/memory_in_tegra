#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase3_results.csv.

Numbers are computed from the actual measured CSV -- never hand-typed -- so this
must be re-run (not hand-edited) whenever the CSV changes. Run after run.sh.
"""
import datetime
import json
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_results.csv")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")
PHASE2_FINDINGS = os.path.join(REPO_ROOT, "experiments", "02_two_kernel_size", "findings.json")

# A green config must beat shared by more than this to count as "helping"
# (prompt Verification section: green should help near L1, be neutral/negative
# when purely DRAM-bandwidth-bound -- this threshold separates noise from signal).
HELPS_THRESHOLD_PCT = 2.0


def per_point_summary(df):
    per_point = []
    for tp, sub in df.groupby("test_point_id"):
        shared_rows = sub[sub.config == "shared"]
        green_rows = sub[sub.config == "green"]
        if shared_rows.empty:
            print(f"WARNING: no shared baseline row for test point {tp!r}; skipping", file=sys.stderr)
            continue
        shared_agg = float(shared_rows.agg_GBps_median.iloc[0])

        if green_rows.empty:
            print(f"WARNING: no green rows for test point {tp!r}", file=sys.stderr)
            best_green_agg = None
            best_split = None
            delta_pct = None
        else:
            best_row = green_rows.loc[green_rows.agg_GBps_median.idxmax()]
            best_green_agg = float(best_row.agg_GBps_median)
            best_split = f"{int(best_row.sm_split_k0)}:{int(best_row.sm_split_k1)}"
            delta_pct = float(best_row.delta_vs_shared_pct)

        regime = None
        if delta_pct is not None:
            regime = "L1/scheduling" if delta_pct > HELPS_THRESHOLD_PCT else "DRAM-bound"

        per_point.append({
            "test_point_id": tp,
            "mode": sub.mode.iloc[0],
            "shared_agg_GBps": round(shared_agg, 3),
            "best_green_agg_GBps": round(best_green_agg, 3) if best_green_agg is not None else None,
            "best_sm_split": best_split,
            "delta_pct": round(delta_pct, 3) if delta_pct is not None else None,
            "regime": regime,
        })
    return per_point


def best_partition_ratios(per_point):
    def pick(mode):
        candidates = [p for p in per_point if p["mode"] == mode and p["best_sm_split"] is not None]
        if not candidates:
            return None
        best = max(candidates, key=lambda p: p["delta_pct"])
        return best["best_sm_split"]
    return {"symmetric": pick("symmetric"), "asymmetric": pick("asymmetric")}


def configs_for_phase4(per_point):
    out = []
    for p in per_point:
        if p["regime"] == "L1/scheduling":
            out.append({"test_point_id": p["test_point_id"], "config": "green", "sm_split": p["best_sm_split"]})
        else:
            out.append({"test_point_id": p["test_point_id"], "config": "shared", "sm_split": "16:16"})
    return out


def green_context_helps_condition(per_point):
    helping = [p for p in per_point if p["regime"] == "L1/scheduling"]
    hurting = [p for p in per_point if p["regime"] == "DRAM-bound"]
    if not helping and not hurting:
        return "No data (results/phase3_results.csv had no comparable shared/green pairs)."
    parts = []
    if helping:
        ids = ", ".join(p["test_point_id"] for p in helping)
        parts.append(f"helped at: {ids}")
    if hurting:
        ids = ", ".join(p["test_point_id"] for p in hurting)
        parts.append(f"neutral/hurt at: {ids}")
    return "; ".join(parts) + f" (threshold: best-green delta > {HELPS_THRESHOLD_PCT}% vs shared)."


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df = pd.read_csv(CSV_PATH)

    per_point = per_point_summary(df)
    ratios = best_partition_ratios(per_point)
    configs4 = configs_for_phase4(per_point)
    helps_note = green_context_helps_condition(per_point)

    consumed = []
    if os.path.exists(PHASE1_FINDINGS):
        consumed.append(os.path.relpath(PHASE1_FINDINGS, REPO_ROOT).replace(os.sep, "/"))
    if os.path.exists(PHASE2_FINDINGS):
        consumed.append(os.path.relpath(PHASE2_FINDINGS, REPO_ROOT).replace(os.sep, "/"))

    results = {
        "per_point": per_point,
        "best_partition_ratios": ratios,
        "green_context_helps_when": helps_note,
        "configs_for_phase4": configs4,
    }

    findings = {
        "schema_version": "1.0",
        "phase": "03_green_context",
        "generated_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv": "experiments/03_green_context/results/phase3_results.csv",
        "env_ref": "shared/env.md",
        "results": results,
        "consumed": consumed,
    }

    with open(FINDINGS_JSON_PATH, "w") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    print(f"wrote {FINDINGS_JSON_PATH}")

    lines = []
    for p in per_point:
        lines.append(
            f"- **{p['test_point_id']}** ({p['mode']}): shared={p['shared_agg_GBps']} GB/s, "
            f"best green={p['best_green_agg_GBps']} GB/s at split {p['best_sm_split']} "
            f"(delta {p['delta_pct']}%), regime: {p['regime']}"
        )

    md = f"""# Phase 3 Findings — Green Context on the Two-Kernel Roofline

Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated.

Upstream consumed: {', '.join(consumed) if consumed else '(none found -- placeholder test points were used, see scripts/sweep.py WARNINGs)'}

## Per test point

{chr(10).join(lines) if lines else '(no rows)'}

## Best partition ratios

- symmetric: {ratios['symmetric']}
- asymmetric: {ratios['asymmetric']}

## When does green context help?

{helps_note}

## Configs recommended for Phase 4

{chr(10).join(f"- {c['test_point_id']}: config={c['config']}, sm_split={c['sm_split']}" for c in configs4)}

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
"""
    with open(FINDINGS_MD_PATH, "w") as f:
        f.write(md)
    print(f"wrote {FINDINGS_MD_PATH}")


if __name__ == "__main__":
    main()
