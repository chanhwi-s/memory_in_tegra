#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase4_results.csv (+ results/l2_profile.csv
if scripts/profile_l2.sh has been run). Numbers are computed from the measured CSVs — never
hand-typed — so re-run this (don't hand-edit) whenever either CSV changes.

Also merges l2_profile.csv into phase4_results.csv in place: every row for a given
test_point_id gets both l2_hit_rate_cached and l2_hit_rate_zc filled in (broadcast across
reuse_N and path — see README.md "L2 profiling design" for why one profiled pair per test
point is treated as representative of all reuse_N for that point).
"""
import csv
import datetime
import json
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase4_results.csv")
L2_PROFILE_PATH = os.path.join(PHASE_DIR, "results", "l2_profile.csv")
PROVENANCE_PATH = os.path.join(PHASE_DIR, "results", "test_points_provenance.json")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

L2_BYPASS_THRESHOLD_PCT = 10.0   # zero-copy L2 hit rate below this counts as "bypass confirmed"
DELTA_NOISE_FLOOR_PCT = 2.0      # |delta| below this counts as "no meaningful difference"


def merge_l2_profile():
    if not os.path.exists(L2_PROFILE_PATH):
        print(f"NOTE: {L2_PROFILE_PATH} not found — l2_hit_rate columns stay 'NA' "
              f"(run scripts/profile_l2.sh to fill them in).", file=sys.stderr)
        return
    profile = {}
    with open(L2_PROFILE_PATH, newline="") as f:
        for row in csv.DictReader(f):
            profile[row["test_point_id"]] = (row["l2_hit_rate_cached"], row["l2_hit_rate_zc"])

    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = rows[0].keys() if rows else []
    changed = 0
    for row in rows:
        tpid = row["test_point_id"]
        if tpid in profile:
            cached_val, zc_val = profile[tpid]
            if row.get("l2_hit_rate_cached") == "NA" and cached_val != "NA":
                row["l2_hit_rate_cached"] = cached_val
                changed += 1
            if row.get("l2_hit_rate_zc") == "NA" and zc_val != "NA":
                row["l2_hit_rate_zc"] = zc_val
                changed += 1
    if changed:
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"merged l2_profile.csv into {CSV_PATH} ({changed} cells filled)")


def find_crossover(df_point):
    """df_point: rows for one (test_point_id, config) at path=='zerocopy', sorted by reuse_N.
    Returns (crossover_reuse_N, note). crossover_reuse_N == 0 means "not observed in the
    swept range 1..32" (delta stayed the same sign throughout)."""
    sub = df_point.sort_values("reuse_N")
    sign_at_n1 = None
    for _, row in sub.iterrows():
        d = row["delta_vs_cached_pct"]
        if pd.isna(d):
            continue
        sign_at_n1 = d
        break
    if sign_at_n1 is None:
        return 0, "no valid delta_vs_cached_pct rows"

    prev_sign = sign_at_n1 >= 0
    for _, row in sub.iterrows():
        d = row["delta_vs_cached_pct"]
        if pd.isna(d):
            continue
        cur_sign = d >= 0
        if cur_sign != prev_sign:
            return int(row["reuse_N"]), f"delta flipped sign at reuse_N={int(row['reuse_N'])}"
        prev_sign = cur_sign
    return 0, "delta sign never flipped across swept reuse_N (1..32)"


def bound_conclusion_for(delta_at_n1, crossover_n):
    if abs(delta_at_n1) <= DELTA_NOISE_FLOOR_PCT and crossover_n == 0:
        return "dram-bound-throughout"
    if delta_at_n1 > DELTA_NOISE_FLOOR_PCT:
        return "memory-bound"
    return "compute-bound"


def l2_bypass_verified_for(df_point):
    zc_rows = df_point[df_point.large_kernel_path == "zerocopy"]
    if zc_rows.empty:
        return False, "no zerocopy rows"
    zc_hit = zc_rows["l2_hit_rate_zc"].iloc[0]
    if zc_hit == "NA" or pd.isna(zc_hit):
        return False, "l2_hit_rate_zc not profiled yet (run scripts/profile_l2.sh)"
    try:
        zc_hit = float(zc_hit)
    except (TypeError, ValueError):
        return False, f"unparseable l2_hit_rate_zc={zc_hit!r}"
    return zc_hit <= L2_BYPASS_THRESHOLD_PCT, f"l2_hit_rate_zc={zc_hit:.2f}%"


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")

    merge_l2_profile()
    df = pd.read_csv(CSV_PATH, na_values=["NA"])

    consumed = []
    if os.path.exists(PROVENANCE_PATH):
        with open(PROVENANCE_PATH) as f:
            consumed = json.load(f).get("consumed", [])

    per_config = []
    for (tpid, config), group in df.groupby(["test_point_id", "config"]):
        zc = group[group.large_kernel_path == "zerocopy"].sort_values("reuse_N")
        if zc.empty:
            continue
        crossover_n, note = find_crossover(zc)
        n1_rows = zc[zc.reuse_N == zc.reuse_N.min()]
        delta_at_n1 = float(n1_rows["delta_vs_cached_pct"].iloc[0]) if not n1_rows.empty and \
            not pd.isna(n1_rows["delta_vs_cached_pct"].iloc[0]) else 0.0
        bound = bound_conclusion_for(delta_at_n1, crossover_n)
        verified, verify_note = l2_bypass_verified_for(group)

        per_config.append({
            "test_point_id": str(tpid),
            "config": str(config),
            "crossover_reuse_N": crossover_n,
            "crossover_note": note,
            "zc_delta_at_N1_pct": round(delta_at_n1, 2),
            "bound_conclusion": bound,
            "l2_bypass_verified": bool(verified),
            "l2_bypass_note": verify_note,
        })

    if per_config:
        mem_bound = [p for p in per_config if p["bound_conclusion"] == "memory-bound"]
        if mem_bound:
            best = max(mem_bound, key=lambda p: p["zc_delta_at_N1_pct"])
            headline = (
                f"Zero copy helped most at '{best['test_point_id']}' ({best['config']}): "
                f"+{best['zc_delta_at_N1_pct']:.1f}% aggregate throughput at reuse N=1, "
                f"crossing over to cache-favored around reuse N={best['crossover_reuse_N'] or '>32'} "
                f"— evidence the bottleneck there was L2/SLC contention, not compute."
            )
        else:
            headline = (
                "Zero copy showed no meaningful throughput benefit at any tested point "
                "(deltas within noise floor at reuse N=1) — the workload was DRAM-bandwidth-"
                "bound throughout the tested range, consistent with the low arithmetic "
                "intensity kernel having little cache reuse to lose."
            )
    else:
        headline = "No test points produced usable results (see warnings)."

    results = {
        "per_config": per_config,
        "headline": headline,
    }

    findings = {
        "schema_version": "1.0",
        "phase": "04_zero_copy",
        "generated_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv": "experiments/04_zero_copy/results/phase4_results.csv",
        "env_ref": "shared/env.md",
        "results": results,
        "consumed": consumed,
    }

    with open(FINDINGS_JSON_PATH, "w") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    print(f"wrote {FINDINGS_JSON_PATH}")

    lines = [
        "# Phase 4 Findings — Zero Copy + Reuse Crossover",
        "",
        f"Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers "
        "below are computed directly from that CSV (and `results/l2_profile.csv` if present) "
        "by `scripts/derive_findings.py` — re-run it (do not hand-edit) if either CSV changes.",
        "",
        "## Headline",
        "",
        headline,
        "",
        "## Per test point / config",
        "",
        "| test_point_id | config | zc delta @ N=1 | crossover N | bound conclusion | L2 bypass verified |",
        "|---|---|---|---|---|---|",
    ]
    for p in per_config:
        lines.append(
            f"| {p['test_point_id']} | {p['config']} | {p['zc_delta_at_N1_pct']:+.1f}% | "
            f"{p['crossover_reuse_N'] or 'none in 1..32'} | {p['bound_conclusion']} | "
            f"{'yes' if p['l2_bypass_verified'] else 'NO — ' + p['l2_bypass_note']} |"
        )
    lines += [
        "",
        "## L2 bypass verification",
        "",
        "Each row's `l2_bypass_verified` comes from `results/l2_profile.csv` "
        f"(threshold: zero-copy L2 hit rate <= {L2_BYPASS_THRESHOLD_PCT}%). If it says NO, "
        "the profiler either hasn't been run yet (`scripts/profile_l2.sh`) or the bypass did "
        "not show the expected near-zero L2 hit rate — investigate before trusting the "
        "bound_conclusion for that row.",
        "",
        "## Consumed upstream findings",
        "",
    ]
    if consumed:
        lines.extend(f"- {c}" for c in consumed)
    else:
        lines.append("- none (placeholders were used; see `results/test_points_provenance.json`)")

    with open(FINDINGS_MD_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {FINDINGS_MD_PATH}")


if __name__ == "__main__":
    main()
