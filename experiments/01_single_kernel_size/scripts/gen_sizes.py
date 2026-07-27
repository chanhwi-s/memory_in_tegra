#!/usr/bin/env python3
"""Print the shared-grid Phase 1 size list (shared/size_grid.py::phase1_sizes_bytes()) as a
comma-separated byte list, for `phase1_bench --sizes $(python3 gen_sizes.py)`.
See prompts/05_unified_size_grid_and_plots.md Change 1.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(PHASE_DIR))
sys.path.insert(0, os.path.join(REPO_ROOT, "shared"))
import size_grid  # noqa: E402

if __name__ == "__main__":
    print(",".join(str(s) for s in size_grid.phase1_sizes_bytes()))
