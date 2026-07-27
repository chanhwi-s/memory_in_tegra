"""Canonical size grid — single source of truth for Phases 1-3's symmetric size sweeps.

Read-only input to every phase (unlike shared/env.md, which is append-only output).
No phase may edit this file as part of a normal run.

Defines the grid in terms of the physically meaningful axis -- combined read
footprint F -- and derives each phase's per-buffer size from it, so a given F
means the same amount of cache pressure in every phase:

    phase              kernels  buffers read/kernel  read footprint  per-buffer size
    1                  1        A, B                 2*S             S = F/2
    2 / 3 symmetric    2        A, B each             4*S             S = F/4

Grid rationale (see prompts/05_unified_size_grid_and_plots.md Change 0):
  - Coarse below 1MB (latency/L1 regime).
  - 256KB-dense from 1MB to 4MB: brackets the *measured* effective cache boundary
    (2MB combined footprint, experiments/01_single_kernel_size/findings.json
    tier_steps.slc_region_max_read_footprint_bytes) AND the nominal 4MB L2 size
    (OVERVIEW.md Sec.0). This is where the interesting structure lives (local peak,
    dip, climb to DRAM asymptote).
  - Coarse above 4MB (DRAM-bound asymptote, sparse sampling is enough).

Only the symmetric grid (this module) and Phase 1's single-kernel grid change.
The asymmetric grids (gen_config.py::asymmetric_k1_sizes_bytes(),
sweep.py::build_asymmetric_k1_sizes()) are out of scope and untouched.
"""

MiB = 1024 * 1024

_F_COARSE_BELOW_1MB_MIB = [0.125, 0.25, 0.5]
_F_DENSE_1MB_4MB_MIB = [
    1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0,
]
_F_COARSE_ABOVE_4MB_MIB = [5, 6, 8, 12, 16, 24, 48, 96]


def combined_footprint_grid_bytes() -> list[int]:
    """Canonical x-axis: combined READ footprint F, in bytes. Coarse below 1MB
    (latency/L1 regime), 256KB-dense from 1MB to 4MB (brackets the measured 2MB
    effective cache boundary AND the nominal 4MB L2), coarse above."""
    mib_values = (
        _F_COARSE_BELOW_1MB_MIB + _F_DENSE_1MB_4MB_MIB + _F_COARSE_ABOVE_4MB_MIB
    )
    return [round(v * MiB) for v in mib_values]


def symmetric_per_kernel_sizes_bytes() -> list[int]:
    """Per-buffer size S = F/4 for the two-kernel symmetric sweep (Phases 2 and 3)."""
    return [f // 4 for f in combined_footprint_grid_bytes()]


def phase1_sizes_bytes() -> list[int]:
    """Union of F/2 (aligns Phase 1's own combined-footprint x-axis with Phases 2/3)
    and F/4 (gives Phase 1's saturation_blocks_by_size an exact entry for every
    per-kernel size Phases 2/3/4 will look up, instead of nearest-neighbour)."""
    grid = combined_footprint_grid_bytes()
    halves = {f // 2 for f in grid}
    quarters = {f // 4 for f in grid}
    return sorted(halves | quarters)


if __name__ == "__main__":
    grid = combined_footprint_grid_bytes()
    assert len(grid) == 24, f"expected 24 F points, got {len(grid)}"
    for f in grid:
        assert f % 4 == 0, f"F={f} not divisible by 4"
        assert f % 131072 == 0, f"F={f} not divisible by 128 KiB"
    sym = symmetric_per_kernel_sizes_bytes()
    for s in sym:
        assert s > 0 and s % 4 == 0, f"symmetric per-buffer size {s} invalid"
    p1 = phase1_sizes_bytes()
    assert len(p1) == 32, f"expected 32 phase1 sizes, got {len(p1)}"
    for s in p1:
        assert s > 0 and s % 4 == 0, f"phase1 size {s} invalid"
    print(f"combined_footprint_grid_bytes(): {len(grid)} points")
    print(f"symmetric_per_kernel_sizes_bytes(): {len(sym)} points")
    print(f"phase1_sizes_bytes(): {len(p1)} points")
