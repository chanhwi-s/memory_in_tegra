#!/usr/bin/env bash
# Build phase3_bench. Runnable from anywhere; paths are resolved relative to this script.
# Needs -lcuda (driver API, for the green context calls).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$PHASE_DIR/build"
nvcc -O3 -arch=sm_87 -o "$PHASE_DIR/build/phase3_bench" "$PHASE_DIR/src/phase3_bench.cu" -lcuda

echo "Built $PHASE_DIR/build/phase3_bench"
