#!/usr/bin/env bash
# One-shot Phase 1 pipeline: build (if needed), lock clocks, run the sweep, plot, derive
# findings, and log the environment. Intended to run on the Jetson AGX Orin device itself.
# Runnable from anywhere. This is the only script you need to run by hand — everything
# downstream (results/phase1_results.csv, results/plots/*.png, findings.json, FINDINGS.md)
# is produced by this one invocation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase1_bench"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

if [ ! -x "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

echo "Locking power mode / clocks (00_conventions.md #4)..."
sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"

echo "Running Phase 1 sweep..."
SIZES="$(python3 "$SCRIPT_DIR/gen_sizes.py")"
"$BIN" --out "$PHASE_DIR/results/phase1_results.csv" --sizes "$SIZES"

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
    echo "- phase: 01_single_kernel_size"
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

echo "Generating plots..."
python3 "$SCRIPT_DIR/plot.py"

echo "Deriving findings.json + FINDINGS.md..."
python3 "$SCRIPT_DIR/derive_findings.py"

echo "Done. Results: $PHASE_DIR/results/phase1_results.csv"
echo "Plots: $PHASE_DIR/results/plots/"
echo "Findings: $PHASE_DIR/findings.json, $PHASE_DIR/FINDINGS.md"
