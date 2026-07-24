#!/usr/bin/env bash
# Build (if needed), lock clocks, run the Phase 3 sweep, and log the environment.
# Intended to run on the Jetson AGX Orin device itself. Runnable from anywhere.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase3_bench"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

if [ ! -x "$BIN" ]; then
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

echo "Done. Results: $PHASE_DIR/results/phase3_results.csv"
echo "Env log appended: $ENV_MD"
