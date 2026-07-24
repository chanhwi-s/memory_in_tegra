#!/usr/bin/env bash
# Build phase1_bench. Runnable from anywhere; paths are resolved relative to this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$PHASE_DIR/build"
nvcc -O3 -arch=sm_87 -o "$PHASE_DIR/build/phase1_bench" "$PHASE_DIR/src/phase1_bench.cu"

echo "Built $PHASE_DIR/build/phase1_bench"
