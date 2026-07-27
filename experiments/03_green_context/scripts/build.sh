#!/usr/bin/env bash
# Build phase3_bench. Runnable from anywhere; paths are resolved relative to this script.
# Needs -lcuda (driver API, for the green context calls). NVTX (<nvtx3/nvToolsExt.h>,
# used to mark the measured-trial window for the nsys overlap verification) is the
# newer header-only NVTX3 API and normally needs no separate link flag (it dlopen()s
# the injection library at runtime, no-op if no profiler is attached) -- if the build
# ever fails with undefined NVTX symbols on a given toolkit, add -lnvToolsExt here.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$PHASE_DIR/build"
nvcc -O3 -arch=sm_87 -o "$PHASE_DIR/build/phase3_bench" "$PHASE_DIR/src/phase3_bench.cu" -lcuda

echo "Built $PHASE_DIR/build/phase3_bench"
