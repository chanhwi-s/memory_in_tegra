#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase4_results.csv (+ results/l2_profile.csv
if scripts/profile_l2.sh has been run). Numbers are computed from the measured CSVs -- never
hand-typed -- so re-run this (don't hand-edit) whenever any input CSV changes.

v2 (prompts/04_zero_copy_v2.md) changes vs the first run:
- Sanity gate (Change 1): compares the re-swept cached aggregate at every anchor row
  (is_anchor==1) against results/phase4_results_v1_baseline.csv (archived once by
  scripts/run.sh before the v2 sweep overwrote phase4_results.csv). Matches by the actual
  measured (config, k0_bytes, k1_bytes, reuse_N) tuple, NOT by test_point_id label -- the
  first run's gen_test_points.py had a naming bug where sym_0 and sym_1 both resolved to
  the same 917504-byte size (see "Discrepancy vs first Phase 4 run" in FINDINGS.md), so
  label-based matching would silently compare the wrong sizes for sym_0.
- per_config / headline now report the widened asymmetric large-kernel (K1) sweep as a
  function of size_regime, not a single verdict per fixed point.

Also merges l2_profile.csv into phase4_results.csv in place: every row for a given
test_point_id gets both l2_hit_rate_cached and l2_hit_rate_zc filled in (broadcast across
reuse_N -- see README.md "L2 profiling design").
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
BASELINE_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase4_results_v1_baseline.csv")
L2_PROFILE_PATH = os.path.join(PHASE_DIR, "results", "l2_profile.csv")
PROVENANCE_PATH = os.path.join(PHASE_DIR, "results", "test_points_provenance.json")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

L2_BYPASS_THRESHOLD_PCT = 10.0   # zero-copy L2 hit rate below this counts as "bypass confirmed"
DELTA_NOISE_FLOOR_PCT = 2.0      # |delta| below this counts as "no meaningful difference"
GATE_TOLERANCE_PCT = 0.5         # allow this much slack for measurement noise in the sanity gate


def fmt_bytes(n):
    n = float(n)
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f}MB"
    return f"{n / 1024:.0f}KB"


def merge_l2_profile():
    if not os.path.exists(L2_PROFILE_PATH):
        print(f"NOTE: {L2_PROFILE_PATH} not found -- l2_hit_rate columns stay 'NA' "
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


def run_sanity_gate(df):
    """Change 1 sanity gate: the re-swept cached aggregate at each anchor point should be >=
    the first Phase 4 run's cached number for the SAME (config, k0_bytes, k1_bytes, reuse_N).
    Matches by measured size, not by test_point_id label (see module docstring -- v1's
    sym_0/sym_1 naming bug makes label-based matching unsafe)."""
    if not os.path.exists(BASELINE_CSV_PATH):
        return {
            "ran": False,
            "note": f"{os.path.relpath(BASELINE_CSV_PATH, REPO_ROOT)} not found -- "
                    "scripts/run.sh archives the pre-v2 phase4_results.csv there on first "
                    "v2 run. Cannot check the sanity gate until that archive exists.",
            "checks": [],
        }

    base = pd.read_csv(BASELINE_CSV_PATH, na_values=["NA"])
    base_cached = base[base.large_kernel_path == "cached"]

    anchors = df[(df.is_anchor == 1) & (df.large_kernel_path == "cached")]
    checks = []
    for tpid, group in anchors.groupby("test_point_id"):
        config = group.config.iloc[0]
        k0 = int(group.k0_bytes.iloc[0])
        k1 = int(group.k1_bytes.iloc[0])
        match = base_cached[(base_cached.config == config) & (base_cached.k0_bytes == k0) &
                             (base_cached.k1_bytes == k1)]
        if match.empty:
            checks.append({
                "test_point_id": str(tpid), "config": str(config),
                "k0_bytes": k0, "k1_bytes": k1, "status": "no_baseline_match",
                "note": "no v1 baseline row at this exact (config, k0_bytes, k1_bytes) -- "
                        "likely because v1's gen_test_points.py resolved this label to a "
                        "different size (see FINDINGS.md discrepancy note).",
            })
            continue
        for _, new_row in group.iterrows():
            reuse_n = int(new_row.reuse_N)
            base_row = match[match.reuse_N == reuse_n]
            if base_row.empty:
                continue
            new_agg = float(new_row.agg_GBps_median)
            base_agg = float(base_row.agg_GBps_median.iloc[0])
            passed = new_agg >= base_agg * (1 - GATE_TOLERANCE_PCT / 100.0)
            checks.append({
                "test_point_id": str(tpid), "config": str(config), "reuse_N": reuse_n,
                "k0_bytes": k0, "k1_bytes": k1,
                "v1_cached_GBps": round(base_agg, 3), "v2_cached_GBps": round(new_agg, 3),
                "status": "pass" if passed else "FAIL",
            })

    any_fail = any(c["status"] == "FAIL" for c in checks)
    any_checked = any(c["status"] in ("pass", "FAIL") for c in checks)
    return {
        "ran": True,
        "note": "all checked anchor points re-saturated to >= the v1 cached aggregate"
                if any_checked and not any_fail else
                ("SANITY GATE FAILED -- re-swept cached aggregate is LOWER than v1 at one or "
                 "more anchor points; the block-saturation search is too narrow, do not trust "
                 "the zero-copy delta until this is fixed" if any_fail else
                 "no directly comparable v1 baseline rows found (see per-check notes)"),
        "checks": checks,
    }


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")

    merge_l2_profile()
    df = pd.read_csv(CSV_PATH, na_values=["NA"])

    consumed = []
    if os.path.exists(PROVENANCE_PATH):
        with open(PROVENANCE_PATH) as f:
            consumed = json.load(f).get("consumed", [])

    gate = run_sanity_gate(df)

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
            "mode": str(group["mode"].iloc[0]),
            "config": str(config),
            "size_regime": str(group.size_regime.iloc[0]) if "size_regime" in group.columns else "unknown",
            "is_anchor": bool(group.is_anchor.iloc[0]) if "is_anchor" in group.columns else False,
            "k1_bytes": int(group.k1_bytes.iloc[0]),
            "plateau_reached": bool(group.plateau_reached.mode().iloc[0]) if "plateau_reached" in group.columns and not group.plateau_reached.empty else None,
            "crossover_reuse_N": crossover_n,
            "crossover_note": note,
            "zc_delta_at_N1_pct": round(delta_at_n1, 2),
            "bound_conclusion": bound,
            "l2_bypass_verified": bool(verified),
            "l2_bypass_note": verify_note,
        })

    asym = [p for p in per_config if p["mode"] == "asymmetric"]
    sym = [p for p in per_config if p["mode"] == "symmetric"]
    asym_sorted = sorted(asym, key=lambda p: p["k1_bytes"])

    if asym_sorted:
        helping = [p for p in asym_sorted if p["bound_conclusion"] == "memory-bound"]
        hurting = [p for p in asym_sorted if p["bound_conclusion"] == "compute-bound"]
        if helping:
            lo = fmt_bytes(min(p["k1_bytes"] for p in helping))
            hi = fmt_bytes(max(p["k1_bytes"] for p in helping))
            best = max(helping, key=lambda p: p["zc_delta_at_N1_pct"])
            headline = (
                f"Across the widened asymmetric K1 sweep ({fmt_bytes(asym_sorted[0]['k1_bytes'])}"
                f" -> {fmt_bytes(asym_sorted[-1]['k1_bytes'])}), zero copy helps (memory-bound) "
                f"in the {lo}-{hi} range, peaking at {best['test_point_id']} "
                f"({best['size_regime']} regime): +{best['zc_delta_at_N1_pct']:.1f}% at reuse "
                f"N=1, crossing over around reuse N="
                f"{best['crossover_reuse_N'] or '>32'}."
            )
            if hurting:
                lo2 = fmt_bytes(min(p["k1_bytes"] for p in hurting))
                hi2 = fmt_bytes(max(p["k1_bytes"] for p in hurting))
                headline += (
                    f" Beyond that ({lo2}-{hi2}), the workload is DRAM/compute-limited enough "
                    "that bypassing cache costs throughput instead (zero copy loses)."
                )
        else:
            headline = (
                "Zero copy showed no meaningful throughput benefit anywhere in the widened "
                "asymmetric K1 sweep (all regimes within the noise floor or negative at "
                "reuse N=1) -- the large kernel was DRAM-bandwidth-bound at every tested "
                "size, consistent with the low arithmetic intensity kernel having little "
                "cache reuse to lose regardless of size."
            )
    else:
        headline = "No asymmetric (large-kernel) test points produced usable results (see warnings)."

    results = {
        "per_config": per_config,
        "asymmetric_large_kernel_sweep": asym_sorted,
        "symmetric_anchors_secondary": sym,
        "saturation_sanity_gate": gate,
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
        "# Phase 4 v2 Findings -- Zero Copy + Reuse Crossover (widened sweep, re-saturated blocks)",
        "",
        f"Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers "
        "below are computed directly from that CSV (and `results/l2_profile.csv` if present) "
        "by `scripts/derive_findings.py` -- re-run it (do not hand-edit) if either CSV changes. "
        "This run **supersedes** the first Phase 4 run per `prompts/04_zero_copy_v2.md`.",
        "",
        "## Headline",
        "",
        headline,
        "",
        "## Sanity gate (Change 1: block saturation must not regress vs the first run)",
        "",
        gate["note"],
        "",
    ]
    if gate["checks"]:
        lines += [
            "| test_point_id | config | reuse_N | v1 cached GB/s | v2 cached GB/s | status |",
            "|---|---|---|---|---|---|",
        ]
        for c in gate["checks"]:
            if c["status"] == "no_baseline_match":
                lines.append(f"| {c['test_point_id']} | {c['config']} | - | - | - | "
                              f"no v1 baseline match ({c['note']}) |")
            else:
                lines.append(f"| {c['test_point_id']} | {c['config']} | {c['reuse_N']} | "
                              f"{c['v1_cached_GBps']:.1f} | {c['v2_cached_GBps']:.1f} | "
                              f"{c['status']} |")
        lines.append("")

    lines += [
        "## Asymmetric large-kernel (K1) sweep -- the headline story",
        "",
        "| test_point_id | regime | k1_bytes | zc delta @ N=1 | crossover N | bound conclusion | plateau reached | L2 bypass verified |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in asym_sorted:
        lines.append(
            f"| {p['test_point_id']} | {p['size_regime']} | {fmt_bytes(p['k1_bytes'])} | "
            f"{p['zc_delta_at_N1_pct']:+.1f}% | {p['crossover_reuse_N'] or 'none in 1..32'} | "
            f"{p['bound_conclusion']} | {p['plateau_reached']} | "
            f"{'yes' if p['l2_bypass_verified'] else 'NO -- ' + p['l2_bypass_note']} |"
        )

    lines += [
        "",
        "## Symmetric anchors (secondary -- NOT the large-kernel story, kept for continuity)",
        "",
        "Both kernels are the same size here, so this is a contention point, not a "
        "large/streaming-kernel test (prompts/04_zero_copy_v2.md Change 2). See the "
        "discrepancy note below for why v1's sym_0/sym_1 rows are not directly comparable.",
        "",
        "| test_point_id | k_bytes | zc delta @ N=1 | crossover N | bound conclusion |",
        "|---|---|---|---|---|",
    ]
    for p in sym:
        lines.append(
            f"| {p['test_point_id']} | {fmt_bytes(p['k1_bytes'])} | "
            f"{p['zc_delta_at_N1_pct']:+.1f}% | {p['crossover_reuse_N'] or 'none in 1..32'} | "
            f"{p['bound_conclusion']} |"
        )

    lines += [
        "",
        "## Discrepancy vs first Phase 4 run",
        "",
        "- **sym_0 / sym_1 were NOT distinct sizes in the first run.** The v1 "
        "`gen_test_points.py` matched Phase 3's `test_point_id` strings to Phase 2 sizes via "
        "a `\"90\" in tpid` substring check; since neither `sym_0` nor `sym_1` contained "
        "`\"90\"`, BOTH resolved to the `onset` size (917504 bytes) -- `results/"
        "test_points_config.csv` from the first run shows both rows with `k0_bytes=k1_bytes="
        "917504`. So the first run's headline (\"zero copy helps most at sym_0\") was really "
        "just two measurements of the *same* symmetric point, not the two distinct roofline "
        "sizes Phase 2 recommended. v2 fixes this by reading Phase 2's "
        "`symmetric_roofline_points.{ninety_pct,onset}` directly (sym_0=786432, "
        "sym_1=917504) instead of matching through Phase 3's id strings.",
        "- **Block counts were fixed, not saturated.** v1 held `blocks_k0`/`blocks_k1` fixed "
        "from Phase 1's single-kernel nearest-neighbor lookup for both the cached and "
        "zero-copy paths. v2 runs an independent in-context search per (test point, config, "
        "cached|zerocopy path) -- see the sanity gate above for whether this actually raised "
        "the cached baseline.",
        "- **The size sweep was 3 points, 2 of them not actually \"large\".** v1's headline "
        "used `sym_0` as the \"large kernel\" evidence, but symmetric points have no large "
        "kernel by definition. v2's headline is drawn from the widened asymmetric K1 sweep "
        "above instead.",
        "",
        "## L2 bypass verification",
        "",
        "Each row's `l2_bypass_verified` comes from `results/l2_profile.csv` "
        f"(threshold: zero-copy L2 hit rate <= {L2_BYPASS_THRESHOLD_PCT}%). If it says NO, "
        "the profiler either hasn't been run yet (`scripts/profile_l2.sh`) or the bypass did "
        "not show the expected near-zero L2 hit rate -- investigate before trusting the "
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
