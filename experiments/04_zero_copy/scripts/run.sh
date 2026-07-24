#!/usr/bin/env bash
# One-shot Phase 4 v2 pipeline: build (if needed), lock clocks, generate the widened test-
# point sweep from upstream findings, run it (with in-context block saturation search per
# prompts/04_zero_copy_v2.md), profile L2 (if `ncu` is available), plot, derive findings,
# and log the environment. Intended to run on the Jetson AGX Orin device itself.
# Runnable from anywhere. This is the only script you need to run by hand — everything
# downstream (results/phase4_results.csv, results/plots/*.png, findings.json, FINDINGS.md)
# is produced by this one invocation. This run SUPERSEDES the first Phase 4 run in place.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase4_bench"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

if [ ! -x "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

# ---- v2 Change 1 sanity gate needs the first run's numbers to compare against. Archive
# the pre-v2 phase4_results.csv exactly once (never overwrite an existing archive, so
# re-running run.sh repeatedly during v2 doesn't clobber the true v1 baseline with v2
# numbers from a prior partial v2 run). ----
BASELINE_CSV="$PHASE_DIR/results/phase4_results_v1_baseline.csv"
CURRENT_CSV="$PHASE_DIR/results/phase4_results.csv"
if [ -f "$CURRENT_CSV" ] && [ ! -f "$BASELINE_CSV" ]; then
    cp "$CURRENT_CSV" "$BASELINE_CSV"
    echo "Archived pre-v2 results to $BASELINE_CSV (for the Change-1 sanity gate)."
fi

echo "Locking power mode / clocks (00_conventions.md #4)..."
sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"

echo "Generating test points from upstream findings.json (Phase 1/2/3)..."
python3 "$SCRIPT_DIR/gen_test_points.py"

echo "Running Phase 4 v2 sweep (widened size sweep + in-context block saturation search)..."
"$BIN" --config "$PHASE_DIR/results/test_points_config.csv" --out "$PHASE_DIR/results/phase4_results.csv" \
    --chosen-blocks "$PHASE_DIR/results/chosen_blocks.csv"

# ---- shared/env.md: written once (header), appended every run (never rewritten) ----
ENV_MD="$REPO_ROOT/shared/env.md"
if [ ! -f "$ENV_MD" ]; then
    cat > "$ENV_MD" <<'HEADER'
# Environment Log

Append-only reproducibility record. Each run below is its own timestamped block;
earlier blocks are never edited or removed.
HEADER
fi

{
    echo ""
    echo "## Run: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- phase: 04_zero_copy"
    echo "- device: $(cat /proc/device-tree/model 2>/dev/null || echo unknown)"
    echo "- L4T/JetPack: $(cat /etc/nv_tegra_release 2>/dev/null || echo unknown)"
    echo "- CUDA (nvcc): $(nvcc --version 2>/dev/null | grep -o 'release [0-9.]*' || echo unknown)"
    echo "- nvpmodel: $(sudo nvpmodel -q 2>/dev/null | tr '\n' ' ' || echo unknown)"
    echo "- jetson_clocks --show:"
    echo '```'
    sudo jetson_clocks --show 2>/dev/null || echo unknown
    echo '```'
    echo "- SoC temp (thermal_zone0): $(( $(cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null || echo 0) / 1000 )) C"
} >> "$ENV_MD"

echo "Env log appended: $ENV_MD"

echo "Profiling L2 hit rate (cached vs zerocopy)..."
if command -v ncu >/dev/null 2>&1; then
    "$SCRIPT_DIR/profile_l2.sh" || echo "WARNING: profile_l2.sh failed — continuing without L2 evidence (l2_hit_rate_* columns will stay NA)"
else
    echo "WARNING: ncu (Nsight Compute) not on PATH — skipping L2 profiling. l2_hit_rate_* columns" \
         "and l2_bypass_verified will stay NA/false until you install ncu and re-run scripts/profile_l2.sh" \
         "+ scripts/derive_findings.py."
fi

echo "Generating plots..."
python3 "$SCRIPT_DIR/plot.py"

echo "Deriving findings.json + FINDINGS.md..."
python3 "$SCRIPT_DIR/derive_findings.py"

echo "Done. Results: $PHASE_DIR/results/phase4_results.csv"
echo "Plots: $PHASE_DIR/results/plots/"
echo "Findings: $PHASE_DIR/findings.json, $PHASE_DIR/FINDINGS.md"
