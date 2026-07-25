#!/usr/bin/env bash
# Build (if needed), generate the sweep config from Phase 1's findings, lock clocks, run the
# Phase 2 sweep, plot, derive findings, and then the v2 reuse-sweep overlay add-on
# (prompts/02_two_kernel_size_v2.md). Intended to run on the Jetson AGX Orin device itself.
# Runnable from anywhere. This is the single entry point -- no separate manual plot.py /
# derive_findings.py / run_reuse_overlay.sh invocation needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
BIN="$PHASE_DIR/build/phase2_bench"

mkdir -p "$PHASE_DIR/results/plots" "$REPO_ROOT/shared"

if [ ! -x "$BIN" ]; then
    "$SCRIPT_DIR/build.sh"
fi

echo "Generating sweep config from Phase 1 findings (scripts/gen_config.py)..."
python3 "$SCRIPT_DIR/gen_config.py"

echo "Locking power mode / clocks (00_conventions.md #4)..."
sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"

echo "Running Phase 2 sweep..."
"$BIN" --config "$PHASE_DIR/results/phase2_config.csv" --out "$PHASE_DIR/results/phase2_results.csv"

echo "Generating plots (scripts/plot.py)..."
python3 "$SCRIPT_DIR/plot.py"

echo "Deriving findings (scripts/derive_findings.py)..."
python3 "$SCRIPT_DIR/derive_findings.py"

# ---- v2 add-on: reuse-sweep overlay (prompts/02_two_kernel_size_v2.md) ----
# Must run after derive_findings.py above: derive_findings.py rewrites FINDINGS.md from
# scratch, which would silently drop the "Reuse overlay" section appended below. Reuses the
# same config/binary/clock-lock from the main sweep -- does not touch phase2_results.csv or
# findings.json (see src/phase2_bench.cu's --reuse-out handling).
echo "Running Phase 2 reuse-sweep overlay (reuse_N in {1,2,4,8,16,32})..."
"$BIN" --config "$PHASE_DIR/results/phase2_config.csv" \
       --reuse-out "$PHASE_DIR/results/phase2_reuse_results.csv"

echo "Generating reuse overlay plot (scripts/plot_reuse.py)..."
python3 "$SCRIPT_DIR/plot_reuse.py"

echo "Appending 'Reuse overlay' section to FINDINGS.md (scripts/append_reuse_findings.py)..."
python3 "$SCRIPT_DIR/append_reuse_findings.py"

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
    echo "- phase: 02_two_kernel_size"
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

echo "Done. Results: $PHASE_DIR/results/phase2_results.csv, $PHASE_DIR/results/phase2_reuse_results.csv"
echo "Plots: $PHASE_DIR/results/plots/"
echo "Findings: $PHASE_DIR/findings.json, $PHASE_DIR/FINDINGS.md"
echo "Env log appended: $ENV_MD"
