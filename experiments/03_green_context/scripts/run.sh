#!/usr/bin/env bash
# Build (if needed), lock clocks, run the Phase 3 v3 sweep END TO END -- reuse=1 main
# sweep, the reuse_N overlay, plots, findings -- and log the environment. Single entry
# point, no separate plot.py / derive_findings.py / sweep_reuse.py invocation needed.
# Intended to run on the Jetson AGX Orin device itself. Runnable from anywhere. Needs
# pandas + matplotlib for the plot/findings steps.
#
# v2 (prompts/03_green_context_v2.md): the sweep is a widened per-kernel size sweep
# instead of 3 fixed points, and EACH cell runs an in-context block-count saturation
# search inside phase3_bench (not a single fixed-block measurement) -- this run takes
# noticeably longer than the original Phase 3 run.
# v3 (prompts/03_green_context_v3.md): the size grid is now Phase 2's own grid (+ a
# small-end extension), so this script's output is directly x-axis-comparable to
# Phase 2's. This script now ALSO runs the reuse_N overlay (Change 3,
# scripts/sweep_reuse.py) right after the main sweep, then plots both. Pass
# --skip-reuse to run the reuse=1 main sweep only (the overlay is diagnostic-only and
# adds ~48 extra measurements; see scripts/sweep.py / scripts/sweep_reuse.py --dry-run
# to preview cell counts before running for real).
# nsys overlap verification (prompts/03_green_context/03_verify_overlap_nsys.md): runs
# after the main sweep, profiling just the peak-bandwidth cell per mode (4 cells total
# -- cheap enough to run every time) to confirm the two kernels genuinely overlap on
# the real execution timeline. Pass --skip-nsys to skip it (e.g. on a device without
# nsys installed); a missing `nsys`/`timeout` is a non-fatal WARNING either way, same
# as the sudo/reuse-overlay steps below, so it never aborts the rest of the run.
set -euo pipefail

RUN_REUSE_OVERLAY=1
RUN_NSYS_OVERLAP=1
for arg in "$@"; do
    case "$arg" in
        --skip-reuse) RUN_REUSE_OVERLAY=0 ;;
        --skip-nsys) RUN_NSYS_OVERLAP=0 ;;
        *) echo "Unknown arg: $arg (supported: --skip-reuse, --skip-nsys)" >&2; exit 2 ;;
    esac
done

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

if [ "$RUN_REUSE_OVERLAY" -eq 1 ]; then
    echo "Running Phase 3 reuse_N overlay (v3 Change 3; pass --skip-reuse to skip this)..."
    python3 "$SCRIPT_DIR/sweep_reuse.py" \
        || echo "WARNING: sweep_reuse.py failed -- reuse overlay is diagnostic-only, continuing without it (results/findings above are unaffected)"
else
    echo "Skipping reuse_N overlay (--skip-reuse)."
fi

if [ "$RUN_NSYS_OVERLAP" -eq 1 ]; then
    if command -v nsys >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
        echo "Verifying concurrent overlap with nsys (peak-bandwidth cell per mode; pass --skip-nsys to skip this)..."
        python3 "$SCRIPT_DIR/run_overlap_nsys.py" \
            || echo "WARNING: run_overlap_nsys.py failed -- this is verification-only, continuing without it (results/findings above are unaffected)"
    else
        echo "WARNING: \`nsys\` or \`timeout\` not on PATH -- skipping nsys overlap verification (pass --skip-nsys to silence this)"
    fi
else
    echo "Skipping nsys overlap verification (--skip-nsys)."
fi

echo "Generating plots..."
python3 "$SCRIPT_DIR/plot.py"
if [ -f "$PHASE_DIR/results/overlap_nsys.csv" ]; then
    python3 "$SCRIPT_DIR/plot_overlap_nsys.py" \
        || echo "WARNING: plot_overlap_nsys.py failed -- continuing"
fi

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
echo "  CSV:           $PHASE_DIR/results/phase3_results.csv"
if [ "$RUN_REUSE_OVERLAY" -eq 1 ]; then
    echo "  Reuse CSV:     $PHASE_DIR/results/phase3_reuse_results.csv (diagnostic-only; see --skip-reuse)"
fi
if [ -f "$PHASE_DIR/results/overlap_nsys.csv" ]; then
    echo "  nsys overlap:  $PHASE_DIR/results/overlap_nsys.csv (verification-only; see --skip-nsys)"
fi
echo "  Plots:         $PHASE_DIR/results/plots/"
echo "  Findings:      $PHASE_DIR/findings.json, $PHASE_DIR/FINDINGS.md"
echo "  Env log appended: $ENV_MD"
