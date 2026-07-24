#!/usr/bin/env python3
"""Generate results/test_points_config.csv, the input to phase4_bench, from upstream
findings.json files.

v2 (see prompts/04_zero_copy_v2.md) rewrite of the original gen_test_points.py. Two changes
vs the first Phase 4 run:

1. Block counts are no longer resolved to a fixed value here. This script only writes
   *search seeds* (seed_blocks_k0/seed_blocks_k1, from Phase 1's saturation_blocks_by_size
   nearest-neighbor) — phase4_bench.cu runs its own in-context saturation search per
   (test point x config x cached/zerocopy path) and decides the real blocks_k0/blocks_k1.
2. The size sweep is no longer 3 fixed points. The asymmetric large kernel (K1) is swept on
   a geometric grid from a small-end anchor (per-SM working set ~= L1, 192 KB/SM) up through
   the L2/SLC tiers into clearly DRAM-bound territory; the original 3 points (sym_0, sym_1,
   asym_2) are kept as labeled anchor rows for direct comparison.

Reads Phase 1/2/3 findings.json at run time; never fabricates numbers. If Phase 3's
findings.json is missing OR is still the v1-shaped file (flat configs_for_phase4 with no
per-regime info — i.e. Phase 3 v2 hasn't run yet), this script does NOT fail the build; it
falls back to config="shared" for every generated point with a loud warning, per
prompts/04_zero_copy_v2.md's "Ordering" section ("fail loudly, or fall back to shared with a
loud TODO warning"). Re-run this once Phase 3 v2's findings.json lands.
"""
import csv
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))

PHASE1_FINDINGS = os.path.join(REPO_ROOT, "experiments", "01_single_kernel_size", "findings.json")
PHASE2_FINDINGS = os.path.join(REPO_ROOT, "experiments", "02_two_kernel_size", "findings.json")
PHASE3_FINDINGS = os.path.join(REPO_ROOT, "experiments", "03_green_context", "findings.json")
OUT_CSV = os.path.join(PHASE_DIR, "results", "test_points_config.csv")
OUT_PROVENANCE = os.path.join(PHASE_DIR, "results", "test_points_provenance.json")

FIELDS = [
    "test_point_id", "mode", "config", "sm_split_k0", "sm_split_k1",
    "k0_bytes", "k1_bytes", "large_kernel_id",
    "seed_blocks_k0", "seed_blocks_k1", "threads_per_block",
    "size_regime", "is_anchor",
]

DEFAULT_TPB = 256
DEFAULT_BLOCKS = 256
LARGE_KERNEL_ID = 1  # K1 always, see module docstring
K0_FIXED_ASYMMETRIC = 1 * 1024 * 1024  # Phase 2 asymmetric definition: K0 fixed at 1 MB

SM_COUNT = 16  # OVERVIEW.md sec 0: 16 SMs, sm_87
L1_PER_SM_BYTES = 192 * 1024  # OVERVIEW.md sec 0
GEOMETRIC_RATIO = 1.75  # within the "1.5-2x" range the prompt asks for
MAX_SWEEP_POINTS = 12  # bound the sweep so on-device runtime stays reasonable
DRAM_TAIL_MULTIPLIER = 4  # keep growing until K1 clears dram_bound_min by this factor

# Fallback tier thresholds (read footprint bytes) if Phase 1 findings are unavailable,
# per OVERVIEW.md sec 0 ("Tier boundaries used throughout").
FALLBACK_TIER_STEPS = {
    "l2_resident_max_read_footprint_bytes": 4 * 1024 * 1024,
    "slc_region_max_read_footprint_bytes": 8 * 1024 * 1024,
    "dram_bound_min_read_footprint_bytes": 8 * 1024 * 1024,
}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def blocks_for(sat_blocks_by_size, size_bytes):
    """Nearest-size lookup into Phase 1's saturation_blocks_by_size. This is a SEARCH SEED
    only (prompts/04_zero_copy_v2.md Change 1) -- phase4_bench re-derives the real saturated
    block count in-context, independently per (config, cached|zerocopy path)."""
    if not sat_blocks_by_size:
        return DEFAULT_BLOCKS
    sizes = sorted(int(k) for k in sat_blocks_by_size)
    nearest = min(sizes, key=lambda s: abs(s - size_bytes))
    return int(sat_blocks_by_size[str(nearest)])


def classify_regime(k1_bytes, tier_steps):
    """Classify the large kernel's own size against the L1 per-SM heuristic and Phase 1's
    measured tier steps (OVERVIEW.md sec 0: L1 192KB/SM, L2 <=4MB, L2+SLC <=8MB, DRAM >8MB)."""
    per_sm_footprint = 2.0 * k1_bytes / SM_COUNT
    if per_sm_footprint <= L1_PER_SM_BYTES:
        return "l1"
    footprint = 2 * k1_bytes
    if footprint <= tier_steps["l2_resident_max_read_footprint_bytes"]:
        return "l2"
    if footprint <= tier_steps["slc_region_max_read_footprint_bytes"]:
        return "slc"
    return "dram"


def build_asymmetric_k1_grid(tier_steps, anchor_k1_bytes):
    """Geometric grid for the large kernel K1, per Change 2: small end ~= per-SM L1 working
    set, growing ~1.75x per step through L2/SLC and into clearly DRAM-bound (> dram_bound_min
    by DRAM_TAIL_MULTIPLIER), capped at MAX_SWEEP_POINTS. The original asym_2 anchor
    (Phase 2's asymmetric_k_used_bytes) is inserted into the grid (nearest slot) and labeled.
    """
    small_end = int(round(L1_PER_SM_BYTES * SM_COUNT / 2.0))
    dram_min = tier_steps["dram_bound_min_read_footprint_bytes"]
    tail_target = dram_min * DRAM_TAIL_MULTIPLIER

    sizes = [small_end]
    while sizes[-1] < tail_target and len(sizes) < MAX_SWEEP_POINTS:
        sizes.append(int(round(sizes[-1] * GEOMETRIC_RATIO)))

    anchor_idx = None
    if anchor_k1_bytes:
        nearest_idx = min(range(len(sizes)), key=lambda i: abs(sizes[i] - anchor_k1_bytes))
        if abs(sizes[nearest_idx] - anchor_k1_bytes) / anchor_k1_bytes < 0.10:
            sizes[nearest_idx] = anchor_k1_bytes  # snap onto the exact anchor value
            anchor_idx = nearest_idx
        else:
            sizes.append(anchor_k1_bytes)
            sizes.sort()
            anchor_idx = sizes.index(anchor_k1_bytes)
    return sizes, anchor_idx


def load_phase3_regime_configs(phase3, warnings):
    """Returns (regime_map or None, is_v2_shaped: bool). regime_map maps a regime name
    ("l1"|"l2"|"slc"|"dram") to a {"config":..., "sm_split":...} dict. Phase 3 v2
    (prompts/03_green_context_v2.md) is expected to report configs_for_phase4 *per size
    regime*, since a single fixed split no longer applies once the sweep spans L1->DRAM.
    If Phase 3's findings.json is still the v1-shaped flat list (no regime field anywhere),
    this is NOT usable for regime-aware config selection -- treat as absent."""
    if not phase3:
        warnings.append(
            "Phase 3 findings.json not found -- Phase 3 v2 has not run yet. Falling back to "
            "config='shared' for every generated test point (TODO: re-run this script once "
            "experiments/03_green_context/findings.json exists from the v2 re-sweep)."
        )
        return None, False

    entries = phase3.get("results", {}).get("configs_for_phase4", [])
    if not entries:
        warnings.append(
            "Phase 3 findings.json has no 'configs_for_phase4' entries -- falling back to "
            "config='shared' for every generated test point."
        )
        return None, False

    has_regime = any(("regime" in e) or ("size_regime" in e) for e in entries)
    if not has_regime:
        warnings.append(
            "Phase 3 findings.json's configs_for_phase4 has NO per-regime field -- this looks "
            "like the STALE v1 Phase 3 run (flat 3-point list), not the v2 re-sweep that "
            "prompts/04_zero_copy_v2.md requires ('Ordering: run this after Phase 3 v2'). "
            "Falling back to config='shared' for every generated test point rather than "
            "trusting stale per-test-point configs. Re-run scripts/gen_test_points.py once "
            "Phase 3 v2 (widened, regime-aware configs_for_phase4) has actually run."
        )
        return None, False

    regime_map = {}
    for e in entries:
        r = e.get("regime") or e.get("size_regime")
        if r and r not in regime_map:
            regime_map[r] = {"config": e.get("config", "shared"), "sm_split": e.get("sm_split", "16:16")}
    return regime_map, True


def parse_sm_split(s):
    a, b = s.split(":")
    return int(a), int(b)


def pick_config_for_regime(regime, regime_map):
    if not regime_map:
        return "shared", (0, 0)
    entry = regime_map.get(regime)
    if entry is None:
        # nearest regime in tier order as a reasonable fallback (documented, not silent)
        order = ["l1", "l2", "slc", "dram"]
        if regime in order:
            idx = order.index(regime)
            for d in range(1, len(order)):
                for cand in (idx - d, idx + d):
                    if 0 <= cand < len(order) and order[cand] in regime_map:
                        entry = regime_map[order[cand]]
                        break
                if entry:
                    break
    if entry is None:
        return "shared", (0, 0)
    config = entry.get("config", "shared")
    sm_split = entry.get("sm_split", "16:16")
    sm_k0, sm_k1 = parse_sm_split(sm_split) if config == "green" else (0, 0)
    return config, (sm_k0, sm_k1)


def main():
    warnings = []
    consumed = []

    phase1 = load_json(PHASE1_FINDINGS)
    if phase1:
        consumed.append(os.path.relpath(PHASE1_FINDINGS, REPO_ROOT).replace("\\", "/"))
        tpb = int(phase1["results"].get("recommended_threads_per_block", DEFAULT_TPB))
        sat_blocks_by_size = phase1["results"].get("saturation_blocks_by_size", {})
        tier_steps = phase1["results"].get("tier_steps", FALLBACK_TIER_STEPS)
    else:
        warnings.append(
            f"{PHASE1_FINDINGS} not found -- using placeholder threads_per_block="
            f"{DEFAULT_TPB}, blocks seed={DEFAULT_BLOCKS}, and OVERVIEW.md fallback tier "
            f"steps (TODO: read from Phase 1 findings once run)"
        )
        tpb = DEFAULT_TPB
        sat_blocks_by_size = {}
        tier_steps = FALLBACK_TIER_STEPS

    phase2 = load_json(PHASE2_FINDINGS)
    phase3 = load_json(PHASE3_FINDINGS)

    rows = []

    if phase2:
        consumed.append(os.path.relpath(PHASE2_FINDINGS, REPO_ROOT).replace("\\", "/"))
        p2r = phase2["results"]

        sym_roofline = p2r.get("symmetric_roofline_points", {})
        sym_90pct_bytes = sym_roofline.get("ninety_pct", {}).get("per_kernel_bytes")
        sym_onset_bytes = sym_roofline.get("onset", {}).get("per_kernel_bytes")
        asym_k1_bytes = p2r.get("asymmetric_k_used_bytes")

        if not (sym_90pct_bytes and sym_onset_bytes and asym_k1_bytes):
            warnings.append(
                "Phase 2 findings.json is missing one of symmetric_roofline_points."
                "{ninety_pct,onset} or asymmetric_k_used_bytes -- cannot build the anchor "
                "rows faithfully. TODO: re-run once Phase 2 findings are complete."
            )
        else:
            if phase3 is None:
                warnings.append(
                    f"{PHASE3_FINDINGS} not found -- Phase 3 v2 has not run yet."
                )
            regime_map, is_v2 = load_phase3_regime_configs(phase3, warnings)

            # ---- Change 2: widened asymmetric K1 sweep (the primary, "large kernel" story) ----
            k1_grid, anchor_idx = build_asymmetric_k1_grid(tier_steps, asym_k1_bytes)
            for i, k1_bytes in enumerate(k1_grid):
                regime = classify_regime(k1_bytes, tier_steps)
                config, (sm_k0, sm_k1) = pick_config_for_regime(regime, regime_map)
                is_anchor = (i == anchor_idx)
                tpid = "asym_2" if is_anchor else f"asym_{i:02d}"
                rows.append({
                    "test_point_id": tpid,
                    "mode": "asymmetric",
                    "config": config,
                    "sm_split_k0": sm_k0,
                    "sm_split_k1": sm_k1,
                    "k0_bytes": K0_FIXED_ASYMMETRIC,
                    "k1_bytes": k1_bytes,
                    "large_kernel_id": LARGE_KERNEL_ID,
                    "seed_blocks_k0": blocks_for(sat_blocks_by_size, K0_FIXED_ASYMMETRIC),
                    "seed_blocks_k1": blocks_for(sat_blocks_by_size, k1_bytes),
                    "threads_per_block": tpb,
                    "size_regime": regime,
                    "is_anchor": 1 if is_anchor else 0,
                })

            # ---- Change 2: symmetric anchors, kept for continuity (secondary, not the
            # headline "large kernel" story -- both kernels are the same size here) ----
            sym_points = [
                ("sym_0", sym_90pct_bytes, True),
                ("sym_1", sym_onset_bytes, True),
            ]
            # optional context extension: a small (L1-ish) and a clearly DRAM-bound symmetric
            # point, so the symmetric story has more than 2 near-identical anchors -- these
            # are NOT anchors and NOT the headline result (Change 2 says the headline must
            # come from the asymmetric sweep).
            small_ctx = k1_grid[0]
            large_ctx = k1_grid[-1]
            if abs(small_ctx - sym_90pct_bytes) / sym_90pct_bytes > 0.10:
                sym_points.append(("sym_ctx_small", small_ctx, False))
            if abs(large_ctx - sym_onset_bytes) / sym_onset_bytes > 0.10:
                sym_points.append(("sym_ctx_large", large_ctx, False))

            for tpid, s_bytes, is_anchor in sym_points:
                regime = classify_regime(s_bytes, tier_steps)
                config, (sm_k0, sm_k1) = pick_config_for_regime(regime, regime_map)
                rows.append({
                    "test_point_id": tpid,
                    "mode": "symmetric",
                    "config": config,
                    "sm_split_k0": sm_k0,
                    "sm_split_k1": sm_k1,
                    "k0_bytes": s_bytes,
                    "k1_bytes": s_bytes,
                    "large_kernel_id": LARGE_KERNEL_ID,
                    "seed_blocks_k0": blocks_for(sat_blocks_by_size, s_bytes),
                    "seed_blocks_k1": blocks_for(sat_blocks_by_size, s_bytes),
                    "threads_per_block": tpb,
                    "size_regime": regime,
                    "is_anchor": 1 if is_anchor else 0,
                })

            if not is_v2:
                warnings.append(
                    "NOTE: because Phase 3 v2 regime-aware configs were unavailable, EVERY "
                    "row above uses config='shared' regardless of its size_regime. This is a "
                    "safe fallback (shared is always a valid baseline) but it means no "
                    "config='green' rows will be measured until Phase 3 v2 lands and this "
                    "script is re-run."
                )

    if not rows:
        warnings.append(
            "Phase 2 findings.json missing or unusable -- using PLACEHOLDER test points "
            "bracketing the tier boundaries from OVERVIEW.md (4 MB L2 / 8 MB L2+SLC). "
            "TODO: re-run this script once experiments/02_two_kernel_size/findings.json "
            "exists, and do not trust phase4_results.csv produced from these placeholders "
            "as a real finding."
        )
        rows = [
            {
                "test_point_id": "sym_0_PLACEHOLDER",
                "mode": "symmetric", "config": "shared",
                "sm_split_k0": 0, "sm_split_k1": 0,
                "k0_bytes": 786432, "k1_bytes": 786432,
                "large_kernel_id": LARGE_KERNEL_ID,
                "seed_blocks_k0": blocks_for(sat_blocks_by_size, 786432),
                "seed_blocks_k1": blocks_for(sat_blocks_by_size, 786432),
                "threads_per_block": tpb,
                "size_regime": classify_regime(786432, tier_steps), "is_anchor": 1,
            },
            {
                "test_point_id": "sym_1_PLACEHOLDER",
                "mode": "symmetric", "config": "shared",
                "sm_split_k0": 0, "sm_split_k1": 0,
                "k0_bytes": 917504, "k1_bytes": 917504,
                "large_kernel_id": LARGE_KERNEL_ID,
                "seed_blocks_k0": blocks_for(sat_blocks_by_size, 917504),
                "seed_blocks_k1": blocks_for(sat_blocks_by_size, 917504),
                "threads_per_block": tpb,
                "size_regime": classify_regime(917504, tier_steps), "is_anchor": 1,
            },
            {
                "test_point_id": "asym_2_PLACEHOLDER",
                "mode": "asymmetric", "config": "shared",
                "sm_split_k0": 0, "sm_split_k1": 0,
                "k0_bytes": K0_FIXED_ASYMMETRIC, "k1_bytes": 8 * 1024 * 1024,
                "large_kernel_id": LARGE_KERNEL_ID,
                "seed_blocks_k0": blocks_for(sat_blocks_by_size, K0_FIXED_ASYMMETRIC),
                "seed_blocks_k1": blocks_for(sat_blocks_by_size, 8 * 1024 * 1024),
                "threads_per_block": tpb,
                "size_regime": classify_regime(8 * 1024 * 1024, tier_steps), "is_anchor": 1,
            },
        ]

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {OUT_CSV} ({len(rows)} test points)")

    provenance = {"consumed": consumed, "warnings": warnings}
    with open(OUT_PROVENANCE, "w") as f:
        json.dump(provenance, f, indent=2)
        f.write("\n")
    print(f"wrote {OUT_PROVENANCE}")

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
