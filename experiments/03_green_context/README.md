# Phase 3 v2 — Green Context (SM Partitioning), In-Context Saturation + Widened Size Sweep

See `../../OVERVIEW.md` §3 and `../../prompts/03_green_context_v2.md` for the full spec
(and `../../prompts/03_green_context.md` for the original methodology this run
**supersedes**); this README covers what changed and how to build/run this phase.

## Why this is v2

The first Phase 3 run concluded "green context never helps." That conclusion had two
methodology gaps (full rationale in `prompts/03_green_context_v2.md`):

1. **Block counts were held fixed from Phase 1's single-kernel/16-SM lookup**, never
   re-swept in context. This under-saturated the shared baseline (135.512 GB/s measured
   at the symmetric 917504-byte point, vs Phase 2's own local-search measurement of the
   *same point* at 143.480 GB/s) -- and green partitions (fewer SMs each) were even more
   likely to be under-saturated by a block count tuned for 16 SMs.
2. **The size sweep was pinned to Phase 2's 3 roofline points**, all DRAM-bound. Green
   context's predicted benefit (L1 / occupancy / scheduling isolation) shows up where the
   per-SM working set is near the 192 KB/SM L1 -- the small-size end, which the original
   sweep never entered. "Green never helps" was a foregone conclusion of point selection.

v2 fixes both:

- **Change 1 (in-context block saturation):** `phase3_bench` now runs its own local
  block-count search for every (size x config x SM split) cell -- Phase 1's lookup is only
  a seed/lower bound, and the search range scales with the *assigned* SM count (a green
  8-SM partition gets its own search, not the 16-SM value). See the file header comment in
  `src/phase3_bench.cu` for the exact algorithm. Each row now also carries a
  `plateau_reached` flag.
- **Change 2 (widened size sweep):** `scripts/sweep.py` now builds its own geometric
  per-kernel size sweep from ~64 KB to ~8 MB (symmetric: both kernels grown together;
  asymmetric: K0 fixed at 1 MB, K1 swept), spanning the L1-near-boundary, L2/SLC, and
  DRAM-bound regimes. Phase 2's 3 original roofline points are re-added as explicitly
  labeled **anchor** cells (`test_point_id` contains `anchor`, at their exact byte sizes)
  so they stay directly comparable to the original run, but the sweep is not capped to them.

## What this measures

Two concurrent `C = A + B` kernels (K0, K1) across the widened size sweep, comparing
**shared SMs** (both kernels on all 16 SMs) vs **green-context partitioned SMs** (each
kernel gets a disjoint SM set). Zero copy stays OFF this phase. Swept: per-kernel size
(~64 KB - 8 MB, symmetric + asymmetric) x SM partition ratio (symmetric: 4:12..12:4 around
8:8; asymmetric: ratios near the kernels' size ratio) x config (shared|green), with block
counts saturated in context for every cell.

## Layout

```
src/phase3_bench.cu     CUDA/driver-API benchmark: for ONE cell (size x config x sm split),
                        runs the in-context block-count saturation search (Change 1), then
                        measures and prints one CSV row. Also has --verify (%smid probe)
                        and --check-api (green context availability check) modes.
scripts/build.sh        nvcc build -> build/phase3_bench (gitignored), links -lcuda
scripts/sweep.py        outer driver: builds the widened size sweep (Change 2) + Phase 2
                        anchor cells x partition-ratio cell list, reads Phase 1's
                        saturation_blocks_by_size as SEEDS ONLY (not final blocks), invokes
                        the binary per cell, joins delta_vs_shared_pct, writes
                        results/phase3_results.csv
scripts/run.sh          locks clocks, runs sweep.py, runs partition verification, appends
                        shared/env.md
scripts/plot.py         results/phase3_results.csv -> results/plots/*.png (3 plots, see below)
scripts/derive_findings.py  results/phase3_results.csv -> findings.json + FINDINGS.md;
                        classifies each point's regime from its SIZE (per-SM working set vs
                        L1, Phase 1 tier_steps), not from whether green won there
results/                CSV + plots + partition_verification.txt (committed)
```

## Dependency on upstream findings (00_conventions.md #2)

This phase reads, **at run time**:
- `experiments/01_single_kernel_size/findings.json` -- `recommended_threads_per_block` and
  `saturation_blocks_by_size`, used only as **search seeds** for `phase3_bench`'s in-context
  block saturation (never as the final block count -- see Change 1 above).
- `experiments/02_two_kernel_size/findings.json` -- `recommended_phase3_test_points`, used
  only to **label anchor cells** in the sweep (Change 2). The widened size sweep itself does
  **not** depend on Phase 2 and runs regardless of whether that file exists.
- `experiments/02_two_kernel_size/results/*.csv` (path read from that phase's
  `findings.json`'s `source_csv`) -- for the Change-1 sanity gate, since Phase 2's
  `findings.json` doesn't itself store the raw GB/s of its `symmetric_contention_onset`
  point.

If Phase 1 or Phase 2's `findings.json` is missing, `scripts/sweep.py` falls back to its own
placeholder seeds/tpb with a loud `TODO(read from phase{1,2} findings)` warning on stderr and
runs the sweep anyway (the size sweep needs no upstream data) -- it never fabricates the
missing upstream numbers. Re-run once those files exist so seeds and anchor labels are real.

Sanity-check the plan without a CUDA device:
```bash
python3 scripts/sweep.py --dry-run
```
This prints every planned cell plus its per-SM working set (`per_sm_working_set_k0`), tagged
`<=L1/SM` where it's at or below the 192 KB/SM L1 -- useful for confirming the widened sweep
actually resolves the small-size regime before spending device time on it.

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh
```

Single entry point: build (if needed) -> lock clocks -> `--check-api` -> sweep
(`results/phase3_results.csv`) -> `--verify` (`results/partition_verification.txt`) -> plots
(`results/plots/green_vs_shared.png`, `partition_sweep.png`, `delta_vs_size.png`) -> findings
(`findings.json`, `FINDINGS.md`) -> append `shared/env.md`.

`run.sh`, `build.sh`, and `sweep.py` all resolve their own paths, so they can be invoked from
any working directory. The plot/findings steps need `pandas` + `matplotlib`; run
`scripts/plot.py` / `scripts/derive_findings.py` directly only if you want to regenerate just
those from an existing `results/phase3_results.csv` without re-running the sweep.

**This run is noticeably slower than the original Phase 3 run**: the widened sweep alone is
~5x more test points, and every cell now runs an in-context block-count search (2 axes x up
to 4 candidates x `kSearchTrials`=3, plus the final `--trials`=10 measurement) instead of a
single fixed-block measurement. Budget accordingly; use `--dry-run` first to see the cell count.

## Status

**v2 harness implemented and unit-tested off-device (dry-run cell planning + `plot.py` /
`derive_findings.py` exercised against synthetic CSV data matching the new schema); not yet
re-run on the Jetson.** Development happens on a machine with no CUDA toolchain (no `nvcc`),
so `phase3_bench.cu` itself is not compile-checked until built on the Jetson. **The
`results/`, `findings.json`, and `FINDINGS.md` currently committed in this directory are
still the v1 (original-methodology) numbers** -- they are superseded by this prompt's
methodology but have not yet been replaced by a real v2 measurement. Running `scripts/run.sh`
on-device will overwrite them with v2 numbers (that is expected; the v1 numbers remain
recoverable via git history, and `FINDINGS.md`'s "Discrepancy vs the first Phase 3 run"
section will record the before/after once regenerated).

Before trusting a v2 run on real hardware:
- Run `phase3_bench --check-api` and confirm it reports the API as available before trusting
  any `green`-config row.
- Run `phase3_bench --verify` (or `scripts/run.sh`, which does this automatically) and confirm
  `results/partition_verification.txt` reports disjoint smid sets between the two partitions.
- **Check the Change-1 sanity gate** in the generated `findings.json`'s
  `results.block_saturation_sanity_gate`: `v2_shared_917504_agg_GBps` must be `>=`
  `phase2_reference_agg_GBps` (Phase 2's own 143.480 GB/s measurement at that point) within
  ~2% noise. If `gate_passed` is not `true`, the in-context search is still under-resolving
  and no green delta in the run should be trusted.
- Check `results/phase3_results.csv`'s `plateau_reached` column and the stderr warnings
  `scripts/sweep.py` prints for any cell that didn't reach a plateau within the search cap
  (1024 blocks) -- that cell's throughput is a lower bound, not a saturated measurement.

## Design notes

- **In-context block saturation search** (Change 1, `src/phase3_bench.cu`): for each cell,
  candidates = `{1,2,4,8} x max(phase1_seed, 4 * assigned_sm_count)`, clamped to 1024. A
  phase2_bench-style two-pass local search (sweep K0 with K1 fixed, then K1 with K0 fixed at
  its winner) picks the best (highest aggregate GB/s == lowest wall time, since bytes moved
  are fixed for the cell). `plateau_reached` is true iff, on both axes, the top candidate's
  gain over the previous one was < 2%. The search uses `kSearchTrials`=3 (cheap); the final
  reported measurement re-runs at the chosen block counts with the full `--trials` (10).
- **Widened size sweep** (Change 2, `scripts/sweep.py`): geometric grid, ratio 1.8x, from
  65536 to 8388608 bytes/kernel (10 points), symmetric and asymmetric (K0 fixed 1 MB), plus
  Phase 2's `recommended_phase3_test_points` re-added at their exact byte sizes as
  `*_anchor_*`-prefixed cells. Regular sweep points and anchors can be numerically close
  (some redundancy is accepted deliberately, since anchors must run at their *exact* size to
  stay comparable to the original run -- they are not snapped onto the nearest grid point).
- **Regime classification** (`scripts/derive_findings.py`): a point's regime
  (L1/scheduling-sensitive vs L2-resident vs L2+SLC-resident vs DRAM-bound) is computed from
  its **size alone** -- per-SM working set `2*S / PARTITION_SM_REF` (fixed reference of 8
  SMs) against the 192 KB/SM L1, then Phase 1's `tier_steps` for the DRAM-bound tail. This is
  deliberately independent of whether green happened to win at that point in this run (the
  original derive_findings.py derived regime FROM the measured delta, which is circular --
  it could never show "green helps in the L1 regime" because the L1 regime was *defined* as
  "where green won"). `green_helps_size_regime` then correlates the two after the fact.
- **Timing across two streams / SM split notation / single-split-call requirement /
  green-context-per-cell lifecycle / correctness check / asymmetric-ratio proportional
  sweep:** unchanged from the original Phase 3 implementation; see `prompts/03_green_context.md`
  and the original harness for the underlying rationale (still valid in v2).
- `delta_vs_shared_pct` still can't be computed inside a single `phase3_bench` invocation (it
  needs the sibling shared-baseline row for the same test point), so the binary prints `0.0`
  for that column and `scripts/sweep.py` fills in the real value after collecting all cells
  for a test point -- unchanged from v1.
