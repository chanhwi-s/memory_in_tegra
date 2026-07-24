#!/usr/bin/env python3
"""Generate results/test_points_config.csv, the input to phase4_bench, from upstream
findings.json files.

Per prompts/04_zero_copy.md: read the actual test points / SM splits / reuse ranges from
Phase 1-3 findings.json at run time; if a phase hasn't produced its findings.json yet,
fall back to clearly-marked PLACEHOLDER test points and TODO notes instead of fabricating
measured numbers. Re-run this whenever an upstream findings.json changes.

Convention adopted here (documented in README.md): the "large / streaming" kernel that
gets the zero-copy treatment is always K1 (large_kernel_id=1) — this matches Phase 2's
asymmetric definition (K0 fixed 1 MB, K1 grown) and is an arbitrary-but-fixed choice for
the symmetric case, where both kernels are the same size.
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
    "k0_bytes", "k1_bytes", "large_kernel_id", "blocks_k0", "blocks_k1", "threads_per_block",
]

DEFAULT_TPB = 256
DEFAULT_BLOCKS = 256
LARGE_KERNEL_ID = 1  # K1 always, see module docstring


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def blocks_for(sat_blocks_by_size, size_bytes):
    if not sat_blocks_by_size:
        return DEFAULT_BLOCKS
    sizes = sorted(int(k) for k in sat_blocks_by_size)
    nearest = min(sizes, key=lambda s: abs(s - size_bytes))
    return int(sat_blocks_by_size[str(nearest)])


def parse_sm_split(s):
    # "8:8" -> (8, 8)
    a, b = s.split(":")
    return int(a), int(b)


def main():
    warnings = []
    consumed = []

    phase1 = load_json(PHASE1_FINDINGS)
    if phase1:
        consumed.append(os.path.relpath(PHASE1_FINDINGS, REPO_ROOT).replace("\\", "/"))
        tpb = int(phase1["results"].get("recommended_threads_per_block", DEFAULT_TPB))
        sat_blocks_by_size = phase1["results"].get("saturation_blocks_by_size", {})
    else:
        warnings.append(
            f"{PHASE1_FINDINGS} not found — using placeholder threads_per_block="
            f"{DEFAULT_TPB} and blocks={DEFAULT_BLOCKS} (TODO: read from Phase 1 findings once run)"
        )
        tpb = DEFAULT_TPB
        sat_blocks_by_size = {}

    phase2 = load_json(PHASE2_FINDINGS)
    phase3 = load_json(PHASE3_FINDINGS)

    rows = []

    if phase2 and phase3:
        consumed.append(os.path.relpath(PHASE2_FINDINGS, REPO_ROOT).replace("\\", "/"))
        consumed.append(os.path.relpath(PHASE3_FINDINGS, REPO_ROOT).replace("\\", "/"))

        p2r = phase2["results"]
        p3r = phase3["results"]
        configs_for_phase4 = p3r.get("configs_for_phase4", [])
        if not configs_for_phase4:
            warnings.append(
                "phase3 findings.json has no 'configs_for_phase4' entries — "
                "falling back to placeholder test points"
            )
        for entry in configs_for_phase4:
            tpid = entry.get("test_point_id")
            config = entry.get("config", "shared")
            sm_split = entry.get("sm_split", "8:8")
            sm_k0, sm_k1 = parse_sm_split(sm_split) if config == "green" else (0, 0)

            # Match this test_point_id back to Phase 2's sizes via naming convention.
            k0_bytes = k1_bytes = None
            mode = "symmetric" if tpid and tpid.startswith("sym") else "asymmetric"
            if mode == "symmetric":
                roofline = p2r.get("symmetric_roofline_points", {})
                if tpid and "90" in tpid:
                    pt = roofline.get("ninety_pct", {})
                else:
                    pt = roofline.get("onset", {})
                per_kernel = pt.get("per_kernel_bytes")
                if per_kernel:
                    k0_bytes = k1_bytes = int(per_kernel)
            else:
                k1_bytes = p2r.get("asymmetric_k_used_bytes")
                k0_bytes = 1 * 1024 * 1024  # fixed per Phase 2 asymmetric definition
                if k1_bytes:
                    k1_bytes = int(k1_bytes)

            if not k0_bytes or not k1_bytes:
                warnings.append(
                    f"could not resolve sizes for test_point_id='{tpid}' from Phase 2 findings "
                    f"— skipping this Phase 3 config entry (TODO: reconcile IDs once Phase 2/3 "
                    f"naming is finalized)"
                )
                continue

            rows.append({
                "test_point_id": tpid or "unknown",
                "mode": mode,
                "config": config,
                "sm_split_k0": sm_k0,
                "sm_split_k1": sm_k1,
                "k0_bytes": k0_bytes,
                "k1_bytes": k1_bytes,
                "large_kernel_id": LARGE_KERNEL_ID,
                "blocks_k0": blocks_for(sat_blocks_by_size, k0_bytes),
                "blocks_k1": blocks_for(sat_blocks_by_size, k1_bytes),
                "threads_per_block": tpb,
            })

    if not rows:
        warnings.append(
            "Phase 2 and/or Phase 3 findings.json missing or unusable — using PLACEHOLDER "
            "test points bracketing the tier boundaries from OVERVIEW.md (4 MB L2 / 8 MB "
            "L2+SLC). TODO: re-run this script once experiments/02_two_kernel_size/findings.json "
            "and experiments/03_green_context/findings.json exist, and do not trust "
            "phase4_results.csv produced from these placeholders as a real finding."
        )
        rows = [
            {
                "test_point_id": "sym_onset_PLACEHOLDER",
                "mode": "symmetric", "config": "shared",
                "sm_split_k0": 0, "sm_split_k1": 0,
                "k0_bytes": 2 * 1024 * 1024, "k1_bytes": 2 * 1024 * 1024,
                "large_kernel_id": LARGE_KERNEL_ID,
                "blocks_k0": blocks_for(sat_blocks_by_size, 2 * 1024 * 1024),
                "blocks_k1": blocks_for(sat_blocks_by_size, 2 * 1024 * 1024),
                "threads_per_block": tpb,
            },
            {
                "test_point_id": "sym_onset_PLACEHOLDER_green",
                "mode": "symmetric", "config": "green",
                "sm_split_k0": 8, "sm_split_k1": 8,
                "k0_bytes": 2 * 1024 * 1024, "k1_bytes": 2 * 1024 * 1024,
                "large_kernel_id": LARGE_KERNEL_ID,
                "blocks_k0": blocks_for(sat_blocks_by_size, 2 * 1024 * 1024),
                "blocks_k1": blocks_for(sat_blocks_by_size, 2 * 1024 * 1024),
                "threads_per_block": tpb,
            },
            {
                "test_point_id": "asym_k_PLACEHOLDER",
                "mode": "asymmetric", "config": "shared",
                "sm_split_k0": 0, "sm_split_k1": 0,
                "k0_bytes": 1 * 1024 * 1024, "k1_bytes": 8 * 1024 * 1024,
                "large_kernel_id": LARGE_KERNEL_ID,
                "blocks_k0": blocks_for(sat_blocks_by_size, 1 * 1024 * 1024),
                "blocks_k1": blocks_for(sat_blocks_by_size, 8 * 1024 * 1024),
                "threads_per_block": tpb,
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
