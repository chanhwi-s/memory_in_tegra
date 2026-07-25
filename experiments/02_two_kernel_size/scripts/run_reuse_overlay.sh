#!/usr/bin/env bash
# v2 add-on (prompts/02_two_kernel_size_v2.md): build (if needed), lock clocks, run the
# reuse-sweep overlay (--reuse-out), plot it, and append the "Reuse overlay" FINDINGS.md
# section. Purely additive -- this script never touches phase2_config.csv generation,
# phase2_results.csv, findings.json, or scripts/run.sh's own output; it only reads the
# already-committed results/phase2_config.csv (same cells as the reuse=1 sweep) and writes
# results/phase2_reuse_results.csv + results/plots/reuse_bw_vs_footprint.png.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase2_bench"
CONFIG="$PHASE_DIR/results/phase2_config.csv"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

if [ ! -x "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

if [ ! -f "$CONFIG" ]; then
    echo "Config missing, generating from Phase 1 findings (scripts/gen_config.py)..."
    python3 "$SCRIPT_DIR/gen_config.py"
fi

echo "Locking power mode / clocks (00_conventions.md #4)..."
sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"

echo "Running Phase 2 reuse-sweep overlay (reuse_N in {1,2,4,8,16,32})..."
"$BIN" --config "$CONFIG" --reuse-out "$PHASE_DIR/results/phase2_reuse_results.csv"

echo "Generating reuse overlay plot (scripts/plot_reuse.py)..."
python3 "$SCRIPT_DIR/plot_reuse.py"

echo "Appending 'Reuse overlay' section to FINDINGS.md (scripts/append_reuse_findings.py)..."
python3 "$SCRIPT_DIR/append_reuse_findings.py"

# ---- shared/env.md: append-only, same convention as run.sh ----
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
    echo "- phase: 02_two_kernel_size (reuse overlay add-on)"
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

echo "Done. Results: $PHASE_DIR/results/phase2_reuse_results.csv"
echo "Plot: $PHASE_DIR/results/plots/reuse_bw_vs_footprint.png"
echo "phase2_results.csv / findings.json were NOT touched by this script."
echo "Env log appended: $ENV_MD"
