#!/usr/bin/env bash
# Verify the zero-copy bypass is real: profile L2 hit rate for the large kernel, cached vs
# zerocopy, for every test point in results/test_points_config.csv (prompts/04_zero_copy.md
# Verification section — "do not assume", report the evidence).
#
# Requires Nsight Compute (`ncu`) on PATH. Runs phase4_bench in --profile-one mode (a single
# test point, single path, reuse_N=1, trials=1) so ncu's kernel-replay overhead stays small;
# this measures the intrinsic per-launch L2 behavior of the two allocation paths, which is
# what config=green/shared and reuse_N do NOT change (zero-copy bypasses L2 on every launch
# regardless of N; see README.md for the reasoning).
#
# v2: --profile-one reuses the block counts the main sweep's in-context saturation search
# already found (results/chosen_blocks.csv), instead of re-running that search under ncu's
# replay overhead. Run scripts/run.sh (the main sweep) at least once before this script so
# chosen_blocks.csv exists -- otherwise phase4_bench falls back to unsaturated seed blocks
# for the profiling launch only, with a stderr warning.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
BIN="$PHASE_DIR/build/phase4_bench"
CFG="$PHASE_DIR/results/test_points_config.csv"
RAW_DIR="$PHASE_DIR/results/l2_raw"

if ! command -v ncu >/dev/null 2>&1; then
    echo "ERROR: ncu (Nsight Compute) not found on PATH. Install it or run this on-device." >&2
    exit 1
fi
if [ ! -f "$CFG" ]; then
    echo "ERROR: $CFG not found — run scripts/gen_test_points.py (or scripts/run.sh) first." >&2
    exit 1
fi
if [ ! -x "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

mkdir -p "$RAW_DIR"

METRIC="lts__t_sector_hit_rate.pct"

# Column order in test_points_config.csv: test_point_id is field 1.
tail -n +2 "$CFG" | cut -d',' -f1 | while IFS= read -r tpid; do
    [ -z "$tpid" ] && continue
    for path in cached zerocopy; do
        echo "Profiling test_point=$tpid path=$path ..."
        ncu --metrics "$METRIC" --csv --page raw \
            "$BIN" --config "$CFG" --out /dev/null \
            --chosen-blocks "$PHASE_DIR/results/chosen_blocks.csv" \
            --profile-one "$tpid" --profile-path "$path" --profile-reuse 1 --trials 1 \
            > "$RAW_DIR/${tpid}__${path}.csv" \
            || echo "WARNING: ncu run failed for $tpid/$path (see $RAW_DIR/${tpid}__${path}.csv)"
    done
done

echo "Parsing raw ncu output into results/l2_profile.csv ..."
python3 "$SCRIPT_DIR/parse_l2_profile.py"

echo "Done. See results/l2_profile.csv, then re-run scripts/derive_findings.py to merge it."
