#!/usr/bin/env bash
# Phase 3 -- verify concurrent overlap with nsys (prompts/03_green_context/03_verify_overlap_nsys.md).
# VERIFICATION ONLY: confirms the two kernels really run concurrently, on the actual
# execution timeline, for the cells that appear in scripts/plot.py's green_vs_shared.png
# (shared + best-green, at the single peak-bandwidth test point per mode -- read from the
# already-measured results/phase3_results.csv, NOT the full sweep; see
# scripts/run_overlap_nsys.py). Needs results/phase3_results.csv
# and the built binary to already exist (run scripts/run.sh first).
# Does NOT touch results/phase3_results.csv, findings.json, or scripts/plot.py -- writes
# only results/overlap_nsys.csv and results/plots/overlap_ratio_vs_footprint_combined_footprint.png.
# Intended to run on the Jetson AGX Orin device itself. Runnable from anywhere.
#
# Pass --dry-run to preview the selected cells without nsys, `timeout`, or a CUDA device.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"
BIN="$PHASE_DIR/build/phase3_bench"

DRY_RUN=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=(--dry-run) ;;
        *) echo "Unknown arg: $arg (supported: --dry-run)" >&2; exit 2 ;;
    esac
done

if [ ${#DRY_RUN[@]} -eq 0 ]; then
    if ! command -v nsys >/dev/null 2>&1; then
        echo "FATAL: \`nsys\` not found on PATH -- this verification step requires the NVIDIA" >&2
        echo "Nsight Systems CLI (ships with JetPack/CUDA on the Jetson). Install it or run on" >&2
        echo "a machine that has it; report this in the worklog rather than skipping silently." >&2
        exit 1
    fi

    mkdir -p "$PHASE_DIR/results/plots"

    # Rebuild if the binary is missing OR the source is newer than the binary,
    # same staleness guard as scripts/run.sh.
    if [ ! -x "$BIN" ] || [ "$PHASE_DIR/src/phase3_bench.cu" -nt "$BIN" ]; then
        "$SCRIPT_DIR/build.sh"
    fi

    echo "Locking power mode / clocks (00_conventions.md #4)..."
    sudo nvpmodel -m 0 || echo "WARNING: nvpmodel -m 0 failed (not on Jetson, or no sudo) — continuing"
    sudo jetson_clocks || echo "WARNING: jetson_clocks failed (not on Jetson, or no sudo) — continuing"
fi

echo "Running nsys overlap verification (shared + best-green at the peak-bandwidth point per mode)..."
python3 "$SCRIPT_DIR/run_overlap_nsys.py" "${DRY_RUN[@]}"

if [ ${#DRY_RUN[@]} -eq 0 ]; then
    echo "Plotting overlap_ratio vs combined read footprint..."
    python3 "$SCRIPT_DIR/plot_overlap_nsys.py"

    echo "Done."
    echo "  CSV:  $PHASE_DIR/results/overlap_nsys.csv"
    echo "  Plot: $PHASE_DIR/results/plots/overlap_ratio_vs_footprint_combined_footprint.png"
    echo "Remember: these traces are VERIFICATION ONLY -- do not read throughput out of them."
fi
