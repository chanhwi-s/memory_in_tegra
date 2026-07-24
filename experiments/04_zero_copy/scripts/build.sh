#!/usr/bin/env bash
# Build phase4_bench. Runnable from anywhere; paths are resolved relative to this script.
# Links against the CUDA driver API (-lcuda) for green-context support (config=green rows);
# if the toolkit predates CUDA 12.4, green-context code compiles out to a stub that skips
# those rows at runtime (see src/phase4_bench.cu).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$PHASE_DIR/build"
nvcc -O3 -arch=sm_87 -o "$PHASE_DIR/build/phase4_bench" "$PHASE_DIR/src/phase4_bench.cu" -lcuda

echo "Built $PHASE_DIR/build/phase4_bench"
