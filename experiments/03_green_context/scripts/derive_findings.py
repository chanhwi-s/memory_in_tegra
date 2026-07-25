#!/usr/bin/env python3
"""Derive findings.json + FINDINGS.md from results/phase3_results.csv (Phase 3 v3).

Numbers are computed from the actual measured CSV -- never hand-typed -- so this
must be re-run (not hand-edited) whenever the CSV changes. Run after run.sh.

v3 changes (prompts/03_green_context_v3.md): findings.json's SCHEMA is
unchanged from v2 (per the prompt: "Regenerate findings.json (same schema as
v2) ... from the reuse=1 sweep only"). Two purely additive FINDINGS.md-only
sections (never touch findings.json / the Phase 4 handoff):
  - "Grid alignment with Phase 2" (Change 1): lists the actual symmetric sizes
    swept, now identical to Phase 2's own grid, so the FINDINGS.md record
    states this supersedes v2's independent geometric grid.
  - "Reuse overlay" (Change 3): reads the SEPARATE, optional
    results/phase3_reuse_results.csv (scripts/sweep_reuse.py) if present, and
    summarizes whether green's delta vs shared improves with reuse_N at each
    subset size. Skipped with a note if that CSV doesn't exist yet -- this
    script must run correctly whether or not the reuse overlay has been run.

v2 changes vs the original derive_findings.py (prompts/03_green_context_v2.md):
  - `regime` is now classified from the SIZE itself (per-SM working set vs the
    192 KB/SM L1, plus Phase 1's tier_steps for the DRAM-bound tail) -- not
    from whether green happened to win at that point. The original script
    derived regime FROM delta_pct, which is circular (it can't show "green
    helps in the L1 regime" because L1-regime was *defined* as "where green
    won"). v2 separates the two: regime is a property of the size, delta_pct
    is the measured outcome, and green_helps_size_regime correlates them.
  - `per_point` covers the full widened sweep (not just 3 points).
  - `best_partition_ratios` / `configs_for_phase4` are now reported per
    (mode, regime), not collapsed to one split per mode (prompt: "do not
    collapse to a single split if it varies with size" -- Phase 4 needs this).
  - New `green_helps_size_regime`: prose + numeric range where best-green beat
    shared by > HELPS_THRESHOLD_PCT.
  - New `block_saturation_sanity_gate` (Change 1's sanity gate): the re-swept
    shared baseline at the symmetric 917504-byte anchor must be >= Phase 2's
    own measurement of that same point (143.480 GB/s, from Phase 2's local
    block search) within noise. Also records the discrepancy against the
    FIRST Phase 3 run's shared baseline at that point (135.512 GB/s), which
    was under-saturated because it held Phase 1's single-kernel/16-SM block
    count fixed instead of re-searching in context.
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
REUSE_CSV_PATH = os.path.join(PHASE_DIR, "results", "phase3_reuse_results.csv")
FINDINGS_JSON_PATH = os.path.join(PHASE_DIR, "findings.json")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")
PHASE2_FINDINGS = os.path.join(REPO_ROOT, "experiments", "02_two_kernel_size", "findings.json")

# A green config must beat shared by more than this to count as "helping"
# (prompt Verification section: green should help near L1, be neutral/negative
# when purely DRAM-bandwidth-bound -- this threshold separates noise from signal).
HELPS_THRESHOLD_PCT = 2.0

L1_BYTES_PER_SM = 192 * 1024
# Reference SM count used ONLY to classify a size's per-SM working set (Change 2:
# "for a symmetric size S per kernel on sm_k SMs, per-SM read footprint ~ 2*S/sm_k").
# Fixed at 8 (the symmetric even split) so the regime label is a property of the
# SIZE alone, not of which split the sweep happened to find best (that would be
# circular -- see module docstring).
PARTITION_SM_REF = 8

# Phase 3 v1 (pre-widened-sweep, original prompts/03_green_context.md run) shared
# baseline at the symmetric 917504-byte point, from the superseded
# experiments/03_green_context/findings.json / results/phase3_results.csv
# (row `sym_0,...,shared,...,135.512,...`; recoverable via git history). This
# constant is NOT re-derived at run time because this very run overwrites that
# CSV -- it exists only to state the Change-1 discrepancy in FINDINGS.md.
V1_SHARED_917504_GBPS = 135.512
V1_SHARED_917504_TEST_POINT_ID_NOTE = "sym_0 in the pre-v2 run (git history)"

SANITY_GATE_TOLERANCE_FRAC = 0.02  # "within noise" per the v2 prompt's sanity gate


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_phase2_onset_reference():
    """Phase 2's OWN measured shared throughput at its symmetric contention-onset
    point (917504 bytes/kernel), read from Phase 2's results CSV (path taken from
    its findings.json's source_csv). This is the Change-1 sanity-gate threshold:
    the v2 re-swept shared baseline at that same point must be >= this value."""
    phase2 = load_json(PHASE2_FINDINGS)
    if phase2 is None:
        return None
    onset = phase2.get("results", {}).get("symmetric_contention_onset", {})
    target_bytes = onset.get("per_kernel_bytes")
    csv_rel = phase2.get("source_csv")
    if target_bytes is None or not csv_rel:
        return None
    csv_path = os.path.join(REPO_ROOT, csv_rel)
    if not os.path.exists(csv_path):
        return None
    p2df = pd.read_csv(csv_path)
    match = p2df[(p2df["mode"] == "symmetric") & (p2df.k0_bytes == target_bytes) &
                 (p2df.k1_bytes == target_bytes)]
    if match.empty:
        return None
    return {"agg_GBps": float(match.agg_GBps_median.iloc[0]), "per_kernel_bytes": int(target_bytes)}


def classify_regime(per_kernel_bytes, tier_steps):
    """Regime = property of the size alone (Change 2 / Verification section):
    L1/scheduling-sensitive if the per-SM working set at PARTITION_SM_REF SMs is
    <= the 192 KB/SM L1; otherwise bucketed by Phase 1's single-kernel read-
    footprint tier_steps (L2-resident / L2+SLC-resident / DRAM-bound)."""
    per_sm_working_set = 2.0 * per_kernel_bytes / PARTITION_SM_REF
    if per_sm_working_set <= L1_BYTES_PER_SM:
        return "L1/scheduling-sensitive"

    read_footprint = 2.0 * per_kernel_bytes  # single-kernel A+B read (OVERVIEW.md: footprint = 2*S)
    tier_steps = tier_steps or {}
    l2_max = tier_steps.get("l2_resident_max_read_footprint_bytes")
    slc_max = tier_steps.get("slc_region_max_read_footprint_bytes")
    dram_min = tier_steps.get("dram_bound_min_read_footprint_bytes")
    if dram_min and read_footprint >= dram_min:
        return "DRAM-bound"
    if l2_max and read_footprint <= l2_max:
        return "L2-resident"
    if slc_max and read_footprint <= slc_max:
        return "L2+SLC-resident"
    return "DRAM-bound" if read_footprint >= 4 * 1024 * 1024 else "L2+SLC-resident"


def per_point_summary(df, tier_steps):
    df = df.copy()
    df["swept_size_bytes"] = df.apply(
        lambda r: r.k0_bytes if r["mode"] == "symmetric" else r.k1_bytes, axis=1)

    per_point = []
    for tp, sub in df.groupby("test_point_id"):
        shared_rows = sub[sub.config == "shared"]
        green_rows = sub[sub.config == "green"]
        if shared_rows.empty:
            print(f"WARNING: no shared baseline row for test point {tp!r}; skipping", file=sys.stderr)
            continue
        shared_agg = float(shared_rows.agg_GBps_median.iloc[0])
        shared_plateau = bool(int(shared_rows.plateau_reached.iloc[0]))

        if green_rows.empty:
            print(f"WARNING: no green rows for test point {tp!r}", file=sys.stderr)
            best_green_agg = None
            best_split = None
            delta_pct = None
            green_plateau = None
        else:
            best_row = green_rows.loc[green_rows.agg_GBps_median.idxmax()]
            best_green_agg = float(best_row.agg_GBps_median)
            best_split = f"{int(best_row.sm_split_k0)}:{int(best_row.sm_split_k1)}"
            delta_pct = float(best_row.delta_vs_shared_pct)
            green_plateau = bool(int(best_row.plateau_reached))

        size_bytes = int(sub.swept_size_bytes.iloc[0])
        mode = sub["mode"].iloc[0]  # bracket access: .mode collides with DataFrame.mode()
        regime = classify_regime(size_bytes, tier_steps)
        beats_shared = delta_pct is not None and delta_pct > HELPS_THRESHOLD_PCT

        per_point.append({
            "test_point_id": tp,
            "mode": mode,
            "is_anchor": "anchor" in tp,
            "swept_size_bytes": size_bytes,
            "k0_bytes": int(sub.k0_bytes.iloc[0]),
            "k1_bytes": int(sub.k1_bytes.iloc[0]),
            "shared_agg_GBps": round(shared_agg, 3),
            "shared_plateau_reached": shared_plateau,
            "best_green_agg_GBps": round(best_green_agg, 3) if best_green_agg is not None else None,
            "best_sm_split": best_split,
            "best_green_plateau_reached": green_plateau,
            "delta_pct": round(delta_pct, 3) if delta_pct is not None else None,
            "regime": regime,
            "beats_shared": beats_shared,
        })
    return sorted(per_point, key=lambda p: (p["mode"], p["swept_size_bytes"]))


def best_partition_ratios_by_regime(per_point):
    """Per (mode, regime) -- prompt: "do not collapse to a single split if it
    varies with size", since Phase 4 needs the regime-specific recommendation."""
    out = {}
    for mode in ["symmetric", "asymmetric"]:
        regimes = sorted({p["regime"] for p in per_point if p["mode"] == mode})
        out[mode] = {}
        for regime in regimes:
            candidates = [p for p in per_point
                          if p["mode"] == mode and p["regime"] == regime and p["best_sm_split"]]
            if not candidates:
                continue
            best = max(candidates, key=lambda p: p["delta_pct"] if p["delta_pct"] is not None else -1e9)
            out[mode][regime] = {"sm_split": best["best_sm_split"], "delta_pct": best["delta_pct"],
                                  "test_point_id": best["test_point_id"]}
    return out


def configs_for_phase4(per_point):
    out = []
    for p in per_point:
        if p["beats_shared"]:
            out.append({"test_point_id": p["test_point_id"], "mode": p["mode"], "regime": p["regime"],
                        "config": "green", "sm_split": p["best_sm_split"]})
        else:
            out.append({"test_point_id": p["test_point_id"], "mode": p["mode"], "regime": p["regime"],
                        "config": "shared", "sm_split": "16:16"})
    return out


def green_helps_size_regime(per_point):
    helping = [p for p in per_point if p["beats_shared"]]
    if not helping:
        return {
            "helps": False,
            "prose": f"None across the 64KB-8MB/kernel sweep: best-green never beat shared by "
                     f"more than {HELPS_THRESHOLD_PCT}% at any measured point (symmetric or asymmetric).",
            "qualifying_points": [],
        }
    sizes = [p["swept_size_bytes"] for p in helping]
    regimes = sorted({p["regime"] for p in helping})
    return {
        "helps": True,
        "prose": (f"Green beat shared by >{HELPS_THRESHOLD_PCT}% at {len(helping)} point(s) "
                  f"(regimes: {', '.join(regimes)}), swept-size range "
                  f"{min(sizes):,}-{max(sizes):,} bytes."),
        "qualifying_points": [
            {"test_point_id": p["test_point_id"], "mode": p["mode"], "swept_size_bytes": p["swept_size_bytes"],
             "delta_pct": p["delta_pct"], "regime": p["regime"], "best_sm_split": p["best_sm_split"]}
            for p in helping
        ],
    }


def block_saturation_sanity_gate(per_point):
    """Change 1's sanity gate: re-swept shared 917504 must be >= Phase 2's own
    143.480 GB/s measurement of that point (within noise), and must have improved
    over the v1 (under-saturated) 135.512 GB/s."""
    p2ref = load_phase2_onset_reference()
    sym_917504 = [p for p in per_point
                  if p["mode"] == "symmetric" and p["swept_size_bytes"] == 917504]
    v2_shared = sym_917504[0]["shared_agg_GBps"] if sym_917504 else None

    gate_passed = None
    if v2_shared is not None and p2ref is not None:
        gate_passed = v2_shared >= p2ref["agg_GBps"] * (1.0 - SANITY_GATE_TOLERANCE_FRAC)

    return {
        "phase2_reference_agg_GBps": p2ref["agg_GBps"] if p2ref else None,
        "phase2_reference_per_kernel_bytes": p2ref["per_kernel_bytes"] if p2ref else None,
        "v1_shared_917504_agg_GBps": V1_SHARED_917504_GBPS,
        "v1_shared_917504_source": V1_SHARED_917504_TEST_POINT_ID_NOTE,
        "v2_shared_917504_agg_GBps": v2_shared,
        "gate_passed": gate_passed,
        "note": ("gate_passed is null if Phase 2 findings/CSV or this run's 917504 anchor row "
                 "are missing -- treat as UNVERIFIED, not passed, until both are present."),
    }


def grid_alignment_note(per_point):
    """v3 Change 1, FINDINGS.md-only: list the actual symmetric sizes swept (now
    Phase 2's own grid + the small-end extension) so the record states this run
    is directly overlayable with Phase 2, superseding v2's independent 1.8x
    geometric grid."""
    sym_sizes = sorted({p["swept_size_bytes"] for p in per_point if p["mode"] == "symmetric"})
    if not sym_sizes:
        return "(no symmetric points in this run -- grid alignment cannot be confirmed)"
    size_list = ", ".join(f"{s:,}" for s in sym_sizes)
    return (f"This run's symmetric per-kernel size grid ({len(sym_sizes)} sizes) is Phase 2's own "
            f"grid (`experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`) "
            f"plus a small-end extension (32 KiB, 64 KiB) for the L1/scheduling regime, imported "
            f"directly rather than re-derived -- so Phase 1/2/3 curves now sit at the SAME x "
            f"positions and are directly overlayable. This supersedes v2's independent 1.8x "
            f"geometric grid (65536, 117965, 212337, ...), which only coincided with Phase 2 at the "
            f"3 anchor points. Sizes (bytes): {size_list}.")


def reuse_overlay_summary():
    """v3 Change 3, FINDINGS.md-only: does green's delta vs shared improve with
    reuse_N? Reads the SEPARATE, optional results/phase3_reuse_results.csv
    (scripts/sweep_reuse.py) -- never touches findings.json (the Phase 4
    handoff stays reuse=1-only, per the prompt). Skips cleanly if that CSV
    doesn't exist yet."""
    if not os.path.exists(REUSE_CSV_PATH):
        return ("Not run this session -- `results/phase3_reuse_results.csv` does not exist. "
                "Run `scripts/sweep_reuse.py` (after `scripts/sweep.py`) to generate the reuse_N "
                "overlay and re-run this script to fill in this section.")

    rdf = pd.read_csv(REUSE_CSV_PATH)
    lines = []
    any_improves = False
    for tp, sub in rdf.groupby("test_point_id"):
        size_bytes = int(sub.k0_bytes.iloc[0])
        shared = sub[sub.config == "shared"].sort_values("reuse_N")
        green = sub[sub.config == "green"].sort_values("reuse_N")
        if shared.empty or green.empty:
            lines.append(f"- **{tp}** ({size_bytes:,} B): incomplete (missing shared or green rows)")
            continue
        merged = pd.merge(shared[["reuse_N", "agg_GBps_median"]], green[["reuse_N", "agg_GBps_median"]],
                          on="reuse_N", suffixes=("_shared", "_green"))
        merged["delta_pct"] = ((merged.agg_GBps_median_green - merged.agg_GBps_median_shared)
                               / merged.agg_GBps_median_shared * 100.0)
        delta_n1 = merged[merged.reuse_N == 1].delta_pct
        delta_nmax = merged[merged.reuse_N == merged.reuse_N.max()].delta_pct
        if delta_n1.empty or delta_nmax.empty:
            lines.append(f"- **{tp}** ({size_bytes:,} B): incomplete reuse_N coverage")
            continue
        d1, dmax = float(delta_n1.iloc[0]), float(delta_nmax.iloc[0])
        nmax = int(merged.reuse_N.max())
        improved = dmax > d1 + HELPS_THRESHOLD_PCT / 2  # meaningfully rising, not just noise
        crossed = d1 <= 0 < dmax
        if improved:
            any_improves = True
        verdict = ("CROSSES into green-helps at higher reuse" if crossed else
                  "delta improves with reuse (still not a win)" if improved else
                  "flat/no improvement with reuse")
        lines.append(f"- **{tp}** ({size_bytes:,} B/kernel): delta @ reuse_N=1 = {d1:+.2f}%, "
                    f"@ reuse_N={nmax} = {dmax:+.2f}% -- {verdict}")

    header = ("At least one subset size shows green's delta improving with reuse_N "
             "(the predicted L1 inter-launch-reuse benefit)." if any_improves else
             "No subset size shows green's delta meaningfully improving with reuse_N up to 32 -- "
             "green context's benefit did not show up via inter-launch L1 reuse in this run either.")
    return header + "\n\n" + "\n".join(lines)


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run.sh first)")
    df = pd.read_csv(CSV_PATH)

    phase1 = load_json(PHASE1_FINDINGS)
    tier_steps = phase1.get("results", {}).get("tier_steps") if phase1 else None
    if tier_steps is None:
        print("WARNING: no Phase 1 tier_steps available -- DRAM-bound/L2/SLC sub-labels fall back "
              "to a hardcoded 4 MB read-footprint threshold; only the L1/scheduling-sensitive label "
              "(which needs no upstream data) is fully trustworthy until Phase 1 findings.json exists.",
              file=sys.stderr)

    per_point = per_point_summary(df, tier_steps)
    ratios = best_partition_ratios_by_regime(per_point)
    configs4 = configs_for_phase4(per_point)
    ghsr = green_helps_size_regime(per_point)
    gate = block_saturation_sanity_gate(per_point)

    n_not_plateaued = sum(1 for p in per_point if p["shared_plateau_reached"] is False or
                          p["best_green_plateau_reached"] is False)

    consumed = []
    if os.path.exists(PHASE1_FINDINGS):
        consumed.append(os.path.relpath(PHASE1_FINDINGS, REPO_ROOT).replace(os.sep, "/"))
    if os.path.exists(PHASE2_FINDINGS):
        consumed.append(os.path.relpath(PHASE2_FINDINGS, REPO_ROOT).replace(os.sep, "/"))

    results = {
        "per_point": per_point,
        "best_partition_ratios": ratios,
        "green_context_helps_when": ghsr["prose"],
        "green_helps_size_regime": ghsr,
        "configs_for_phase4": configs4,
        "block_saturation_sanity_gate": gate,
        "cells_not_plateaued": n_not_plateaued,
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

    with open(FINDINGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    print(f"wrote {FINDINGS_JSON_PATH}")

    lines = []
    for p in per_point:
        anchor_tag = " [ANCHOR]" if p["is_anchor"] else ""
        lines.append(
            f"- **{p['test_point_id']}**{anchor_tag} ({p['mode']}, {p['swept_size_bytes']:,} B, "
            f"regime: {p['regime']}): shared={p['shared_agg_GBps']} GB/s "
            f"(plateau={p['shared_plateau_reached']}), "
            f"best green={p['best_green_agg_GBps']} GB/s at split {p['best_sm_split']} "
            f"(plateau={p['best_green_plateau_reached']}, delta {p['delta_pct']}%)"
        )

    ratio_lines = []
    for mode, regimes in ratios.items():
        if not regimes:
            ratio_lines.append(f"- {mode}: (no data)")
            continue
        for regime, info in regimes.items():
            ratio_lines.append(f"- {mode} / {regime}: {info['sm_split']} "
                               f"(delta {info['delta_pct']}% at {info['test_point_id']})")

    gate_line = (
        f"v2 re-swept shared @ 917504 B/kernel = {gate['v2_shared_917504_agg_GBps']} GB/s "
        f"vs Phase 2's own measurement {gate['phase2_reference_agg_GBps']} GB/s "
        f"(gate_passed={gate['gate_passed']}); v1 (pre-widened-sweep) shared @ the same point was "
        f"{gate['v1_shared_917504_agg_GBps']} GB/s ({gate['v1_shared_917504_source']})."
        if gate["v2_shared_917504_agg_GBps"] is not None
        else "UNVERIFIED -- the 917504 B/kernel symmetric anchor row is missing from this run's CSV "
             "(re-run scripts/sweep.py so the Phase 2 anchor is included)."
    )

    grid_note = grid_alignment_note(per_point)
    reuse_note = reuse_overlay_summary()

    md = f"""# Phase 3 v3 Findings — Green Context, In-Context Saturation + Phase-2-Aligned Size Sweep

Generated {findings['generated_utc']} from `{findings['source_csv']}`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` -- re-run it (do not
hand-edit) if the CSV is regenerated. See `prompts/03_green_context_v3.md` (building on
`_v2.md`) for the full methodology; this supersedes the original Phase 3 run
(`prompts/03_green_context.md`) and v2's independently-gridded re-run.

Upstream consumed: {', '.join(consumed) if consumed else '(none found -- placeholder seeds/anchors were used, see scripts/sweep.py WARNINGs)'}

## Grid alignment with Phase 2 (v3 Change 1)

{grid_note}

## Change 1 sanity gate (block-count saturation)

{gate_line}

If `gate_passed` is not `true`, the in-context saturation search is still under-resolving the
shared baseline -- do not trust any green delta in this run until it passes.

## Per test point ({len(per_point)} points: widened sweep + Phase 2 anchors)

{chr(10).join(lines) if lines else '(no rows)'}

{f"**{n_not_plateaued} point(s) had a shared or best-green cell that did not reach the block-count "
 f"plateau within the search cap** -- their throughput is a lower bound; see run-time WARNINGs / "
 f"`scripts/sweep.py` stderr log for which cells." if n_not_plateaued else
 "All measured cells reached the block-count plateau within the search cap."}

## Best partition ratios (per mode x regime -- Phase 4 must NOT collapse this to one split per mode)

{chr(10).join(ratio_lines) if ratio_lines else '(no data)'}

## When does green context help?

{ghsr['prose']}

## Configs recommended for Phase 4

{chr(10).join(f"- {c['test_point_id']} ({c['mode']}, {c['regime']}): config={c['config']}, sm_split={c['sm_split']}" for c in configs4)}

## Discrepancy vs the first Phase 3 run (00_conventions.md #2: do not overwrite upstream, record discrepancies)

The original Phase 3 run (`prompts/03_green_context.md`, now superseded) held block counts fixed
from Phase 1's single-kernel/16-SM `saturation_blocks_by_size` lookup instead of re-searching them
in context. At the symmetric 917504-byte anchor point this measured an under-saturated shared
baseline of **{V1_SHARED_917504_GBPS} GB/s**, versus Phase 2's own local-search measurement of the
*same point* at **{gate['phase2_reference_agg_GBps']} GB/s** -- a gap the original run's `FINDINGS.md`
did not catch. This v2 run's re-swept shared baseline at that point is
**{gate['v2_shared_917504_agg_GBps']} GB/s** (see sanity gate above). The v1 numbers remain
recoverable via git history (the commit that introduced `experiments/03_green_context/findings.json`
before this revision); they are superseded, not deleted from provenance.

## Reuse overlay (v3 Change 3 -- diagnostic only, does NOT feed findings.json / Phase 4)

{reuse_note}

## Verification (00_conventions.md / prompt Verification section)

See `results/partition_verification.txt` for the %smid-based evidence that each
partition's blocks only ran on their assigned SMs (disjoint smid sets expected).
If that file reports overlap, treat this findings.json as suspect and STOP before
Phase 4 consumes it.
"""
    with open(FINDINGS_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {FINDINGS_MD_PATH}")


if __name__ == "__main__":
    main()
