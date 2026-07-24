#!/usr/bin/env bash
# Build (if needed), lock clocks, run the Phase 3 v2 sweep, plot, derive findings, and log
# the environment -- a single end-to-end entry point (no separate plot.py /
# derive_findings.py invocation needed). Intended to run on the Jetson AGX Orin device
# itself. Runnable from anywhere. Needs pandas + matplotlib for the plot/findings steps.
#
# v2 (prompts/03_green_context_v2.md): the sweep is now a widened per-kernel size
# sweep (~64 KB - 8 MB, symmetric + asymmetric) instead of 3 fixed points, and
# EACH cell runs an in-context block-count saturation search inside phase3_bench
# (not a single fixed-block measurement) -- this run takes noticeably longer than
# the original Phase 3 run. See scripts/sweep.py --dry-run to preview cell count.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase3_bench"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

# Rebuild if the binary is missing OR the source is newer than the binary --
# a stale binary here once silently ran pre-fix code and wasted a debug cycle.
if [ ! -x "$BIN" ] || [ "$PHASE_DIR/src/phase3_bench.cu" -nt "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

echo "Locking power mode / clocks (00_conventions.md #4)..."
sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"

echo "Checking green context API availability..."
"$BIN" --check-api || echo "WARNING: green context API check failed — green-config cells will error out below"

echo "Running Phase 3 sweep (reads Phase 1/2 findings.json if present; see scripts/sweep.py)..."
python3 "$SCRIPT_DIR/sweep.py"

echo "Verifying SM partitioning took effect (8:8 split, prompt Verification section)..."
"$BIN" --verify --sm0 8 --sm1 8 --blocks0 256 --blocks1 256 --tpb 256 \
    > "$PHASE_DIR/results/partition_verification.txt" 2>&1 \
    || echo "WARNING: partition verification failed, see $PHASE_DIR/results/partition_verification.txt"
cat "$PHASE_DIR/results/partition_verification.txt"

echo "Generating plots..."
python3 "$SCRIPT_DIR/plot.py"

echo "Deriving findings.json / FINDINGS.md..."
python3 "$SCRIPT_DIR/derive_findings.py"

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
    echo "- phase: 03_green_context"
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

echo "Done."
echo "  CSV:      $PHASE_DIR/results/phase3_results.csv"
echo "  Plots:    $PHASE_DIR/results/plots/"
echo "  Findings: $PHASE_DIR/findings.json, $PHASE_DIR/FINDINGS.md"
echo "  Env log appended: $ENV_MD"
