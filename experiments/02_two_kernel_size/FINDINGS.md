# Phase 2 Findings — Two-Kernel Size Sweep

Generated 2026-07-24T08:11:58Z from `experiments/02_two_kernel_size/results/phase2_results.csv`. All numbers below are
computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not hand-edit)
if the CSV is regenerated. Consumed upstream: experiments/01_single_kernel_size/findings.json.

## 2a — Symmetric contention onset

- **Per-kernel size:** 131,072 bytes (~0.12 MB)
- **Combined read footprint:** 524,288 bytes
- **scaling_efficiency at onset:** 0.5016

`symmetric_roofline_points` (onset + ~90%-below point, for Phase 3/4): see `findings.json`.

## 2b — Asymmetric result at k

- **k (per-buffer bytes):** 2,097,152
- **aggregate GB/s at k:** 158.172
- **K0 GB/s at k:** 81.852
- **K1 GB/s at k:** 105.448

## Recommended Phase 3 test points

- {'mode': 'symmetric', 'per_kernel_bytes': 131072}
- {'mode': 'asymmetric', 'k1_bytes': 2097152}

## Warnings / caveats

None.

## Verification (00_conventions.md / prompt Verification section)

Re-check by eye against `results/plots/sym_agg_vs_footprint.png` and `results/plots/asym_vs_k1.png`:
- Symmetric: scaling_efficiency should be ~1 well below L2 (4 MB combined) and drop as combined
  footprint exceeds cache.
- The benchmark binary itself (`src/phase2_bench.cu`) prints a `WARNING` to stderr for any cell
  where `wall_ms_median >= serial_sum_ms` (no measured overlap) or a correctness mismatch — check
  the run log for these before trusting this file.
