# Phase 3 v3 — Green Context (SM Partitioning): Phase-2-Aligned Grid + Reuse Overlay

See `../../OVERVIEW.md` §3 and `../../prompts/03_green_context_v3.md` for the full spec
(building on `../../prompts/03_green_context_v2.md`, and `../../prompts/03_green_context.md`
for the original methodology this run **supersedes**); this README covers what changed and
how to build/run this phase.

## Why this is v3

v2 fixed two methodology gaps in the original run (in-context block saturation; a widened
size sweep reaching the L1/scheduling regime) and was actually run on-device. Its real
`FINDINGS.md` sanity gate passed (re-swept shared @ 917504 B/kernel = 148.24 GB/s vs Phase 2's
own 143.599 GB/s), but it surfaced a new gap: v2's size sweep used its own 1.8x geometric grid
(65536, 117965, 212337, ...), which only coincided with Phase 2's sizes at the 3 anchor
points — so Phase 1/2/3 curves couldn't be overlaid at the same x positions. v2's result was
also reuse_N=1 only, so it could see green context's scheduling/occupancy isolation but not
its predicted *main* benefit: stabilizing L1 **inter-launch** reuse, which only exists at
reuse_N>1 (`OVERVIEW.md` §1).

v3 is a **patch on top of v2** (keeps everything: in-context saturation, findings schema,
%smid verification, anchors, discrepancy notes) that changes/adds exactly three things:

- **Change 1 (grid alignment):** `scripts/sweep.py` no longer generates its own geometric
  size grid. It now **imports Phase 2's own grid-generating functions directly**
  (`experiments/02_two_kernel_size/scripts/gen_config.py`: `symmetric_sizes_bytes()` /
  `asymmetric_k1_sizes_bytes(k)`), prepending a small-end extension (32 KiB, 64 KiB /
  the same fractions of `k`) so the L1/scheduling regime is still covered. Phase 2's 3
  anchors now fall **exactly** on existing grid points at this resolution, so they're
  snapped in place (`is_anchor=True`, one cell, not a duplicate row like v2) instead of
  added as separate cells.
- **Change 2 (power-of-2 axes):** every byte-size x-axis (`green_vs_shared.png`,
  `delta_vs_size.png`) is now log **base 2** with human-readable power-of-two tick labels
  (256K, 512K, 1M, ...) instead of matplotlib's default log10. `partition_sweep.png`'s
  x-axis (the categorical SM split, e.g. "8:8") is untouched.
- **Change 3 (reuse overlay, new + additive):** `scripts/sweep_reuse.py` re-measures a small
  representative subset of symmetric sizes (~4-5: the smallest/L1 point, both Phase 2
  anchors, one clearly DRAM-bound point) across `reuse_N ∈ {1,2,4,8,16,32}`, shared vs the
  best-green split the reuse=1 sweep already found for that size. Block counts are **not**
  re-searched per `reuse_N` — read back from the reuse=1 CSV, verified stable at one check N
  (=4, mirroring Phase 4's `searchAndVerifyStable`: element-wise max + a stderr note if they
  disagree), then held fixed. Writes a **separate** `results/phase3_reuse_results.csv`;
  never touches `results/phase3_results.csv` or `findings.json` (the Phase 4 handoff stays
  reuse=1-only, diagnostic overlay only).

## What this measures

Two concurrent `C = A + B` kernels (K0, K1) across a size sweep now numerically aligned with
Phase 2's, comparing **shared SMs** (both kernels on all 16 SMs) vs **green-context
partitioned SMs** (each kernel gets a disjoint SM set). Zero copy stays OFF this phase. Swept:
per-kernel size (32 KiB up to 24 MiB, symmetric + asymmetric) x SM partition ratio (symmetric:
4:12..12:4 around 8:8; asymmetric: ratios near the kernels' size ratio) x config
(shared|green), with block counts saturated in context for every cell. Plus the optional
reuse_N overlay described above.

## Layout

```
src/phase3_bench.cu     CUDA/driver-API benchmark: for ONE cell (size x config x sm split
                        [x reuse_N]), runs the in-context block-count saturation search
                        (v2 Change 1) unless --fixed-blocks0/1 are given (v3 Change 3), then
                        measures and prints one CSV row. --reuse-overlay switches to the
                        separate reuse-CSV row format. Also has --verify (%smid probe) and
                        --check-api (green context availability check) modes.
scripts/build.sh        nvcc build -> build/phase3_bench (gitignored), links -lcuda
scripts/sweep.py        outer driver for the reuse=1 main sweep: imports Phase 2's own size-
                        grid functions (v3 Change 1), snaps Phase 2's anchors onto exact grid
                        points, reads Phase 1's saturation_blocks_by_size as SEEDS ONLY
                        (never final blocks), invokes the binary per cell, joins
                        delta_vs_shared_pct, writes results/phase3_results.csv
scripts/sweep_reuse.py  (v3 Change 3, new) reuse_N overlay driver: reads back reuse=1 blocks/
                        splits from results/phase3_results.csv, verifies block-count stability
                        at one check N, measures the subset x reuse_N grid, writes the
                        SEPARATE results/phase3_reuse_results.csv. Run manually AFTER sweep.py.
scripts/run.sh          locks clocks, runs sweep.py (reuse=1 only), runs partition
                        verification, appends shared/env.md
scripts/plot.py         results/phase3_results.csv -> results/plots/*.png (green_vs_shared,
                        partition_sweep, delta_vs_size); ALSO reads the optional
                        results/phase3_reuse_results.csv -> reuse_green_vs_shared.png if
                        present (skips cleanly with a note if sweep_reuse.py hasn't run yet)
scripts/derive_findings.py  results/phase3_results.csv -> findings.json + FINDINGS.md (v2
                        schema, unchanged); FINDINGS.md gets two new v3-only prose sections
                        ("Grid alignment with Phase 2", "Reuse overlay") that never touch
                        findings.json
results/                CSV(s) + plots + partition_verification.txt (committed)
```

## Dependency on upstream findings (00_conventions.md #2)

This phase reads, **at run time**:
- `experiments/01_single_kernel_size/findings.json` -- `recommended_threads_per_block` and
  `saturation_blocks_by_size`, used only as **search seeds** for `phase3_bench`'s in-context
  block saturation (never as the final block count), and `measured_dram_peak_GBps` for the
  reuse-overlay plot's reference line.
- `experiments/02_two_kernel_size/findings.json` -- `recommended_phase3_test_points` (anchor
  labeling) and `asymmetric_k_used_bytes` (the crossover `k` the asymmetric grid is built
  from). **The size grid itself** comes from Phase 2's `scripts/gen_config.py` functions,
  imported directly (v3 Change 1) -- these need no Phase 2 *run*, only the file to exist.
- `experiments/02_two_kernel_size/results/*.csv` (path read from that phase's
  `findings.json`'s `source_csv`) -- for the Change-1 sanity gate, since Phase 2's
  `findings.json` doesn't itself store the raw GB/s of its `symmetric_contention_onset`
  point.

If Phase 1 or Phase 2's `findings.json` is missing, `scripts/sweep.py` falls back to its own
placeholder seeds/`k`/tpb with a loud `TODO(read from phase{1,2} findings)` warning on stderr
and runs the sweep anyway -- it never fabricates the missing upstream numbers. Re-run once
those files exist so seeds, `k`, and anchor labels are real.

Sanity-check the plan without a CUDA device:
```bash
python3 scripts/sweep.py --dry-run
```
This prints every planned cell plus its per-SM working set (`per_sm_working_set_k0`), tagged
`<=L1/SM` where it's at or below the 192 KB/SM L1, and a summary of how many symmetric /
asymmetric sizes and Phase 2 anchors are in the plan.

`scripts/sweep_reuse.py --dry-run` requires `results/phase3_results.csv` to already exist
(it reads back the reuse=1 sweep's blocks/splits) but still makes **no device/binary calls**
in dry-run mode -- the block-count stability check is skipped and the raw reuse=1 blocks are
shown labeled `UNVERIFIED`.

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh                 # reuse=1 main sweep (mandatory)
scripts/sweep_reuse.py         # reuse_N overlay (optional, additive, run after the above)
scripts/plot.py                # re-run to pick up reuse_green_vs_shared.png
```

`scripts/run.sh` is the single entry point for the reuse=1 sweep: build (if needed) -> lock
clocks -> `--check-api` -> sweep (`results/phase3_results.csv`) -> `--verify`
(`results/partition_verification.txt`) -> plots (`results/plots/green_vs_shared.png`,
`partition_sweep.png`, `delta_vs_size.png`) -> findings (`findings.json`, `FINDINGS.md`) ->
append `shared/env.md`.

All scripts resolve their own paths, so they can be invoked from any working directory. The
plot/findings steps need `pandas` + `matplotlib`; run `scripts/plot.py` /
`scripts/derive_findings.py` directly only if you want to regenerate just those from an
existing CSV without re-running the sweep.

**This run is noticeably slower than the original Phase 3 run**: the widened/aligned sweep
alone is ~5x more test points, and every cell runs an in-context block-count search (2 axes x
up to 4 candidates x `kSearchTrials`=3, plus the final `--trials`=10 measurement) instead of a
single fixed-block measurement. The reuse overlay adds another ~48 measurements (4-5 sizes x
2 configs x 6 `reuse_N` values, each preceded by one stability-check search). Budget
accordingly; use `--dry-run` on both scripts first to see the cell counts.

## Status

**v2 was actually run on-device; results/`findings.json`/`FINDINGS.md` currently committed
in this directory are real v2 measurements** (sanity gate passed: re-swept shared @ 917504
B/kernel = 148.24 GB/s ≥ Phase 2's 143.599 GB/s; best-green result: green only beat shared
at the smallest asymmetric point, +8.5%, everywhere else neutral/negative — see the committed
`FINDINGS.md` for the full per-point breakdown).

**v3's code changes (this revision) are implemented and unit-tested off-device** (grid
generation verified via `--dry-run` against Phase 2's actual grid — 18 symmetric / 11
asymmetric sizes, anchors snapped exactly once each at 786432/917504/2097152; `plot.py` and
`derive_findings.py` exercised end-to-end against synthetic CSV data matching the new grid +
reuse-overlay schema) **but not yet re-run on the Jetson.** Development happens on a machine
with no CUDA toolchain (no `nvcc`), so `phase3_bench.cu`'s reuse/fixed-blocks plumbing is not
compile-checked until built on the Jetson. Running `scripts/run.sh` on-device will overwrite
the committed v2 results with v3 numbers (expected; `FINDINGS.md`'s "Grid alignment with
Phase 2" section will state the supersession, and the existing "Discrepancy vs the first Phase
3 run" section is unaffected since it's about saturation methodology, not the grid).

Before trusting a v3 run on real hardware:
- Run `phase3_bench --check-api` and confirm it reports the API as available before trusting
  any `green`-config row.
- Run `phase3_bench --verify` (or `scripts/run.sh`, which does this automatically) and confirm
  `results/partition_verification.txt` reports disjoint smid sets between the two partitions.
- **Check the Change-1 sanity gate** in the generated `findings.json`'s
  `results.block_saturation_sanity_gate`: the re-swept shared baseline at 917504 B/kernel
  must be `>=` Phase 2's own ~143.6 GB/s measurement at that point within ~2% noise. If
  `gate_passed` is not `true`, the in-context search is still under-resolving and no green
  delta in the run should be trusted.
- Check `results/phase3_results.csv`'s `plateau_reached` column and the stderr warnings
  `scripts/sweep.py` prints for any cell that didn't reach a plateau within the search cap
  (1024 blocks) -- that cell's throughput is a lower bound, not a saturated measurement.
- For the reuse overlay: check `scripts/sweep_reuse.py`'s stderr for `NOTE: block saturation
  search NOT stable across reuse_N` -- if printed, the element-wise-max fallback was used;
  not fatal, but worth a second look if the overlay's shape looks off. Sanity-check
  `reuse_green_vs_shared.png` per the prompt: a large DRAM-bound size should be ~flat across
  `reuse_N` (nothing to cache-hit); a small/L1 size's *shared* line should visibly rise with
  `reuse_N` (cache hits) -- if neither line moves anywhere, the reuse launch loop isn't
  re-reading the buffers.

## Design notes

- **In-context block saturation search** (v2 Change 1, `src/phase3_bench.cu`): for each cell,
  candidates = `{1,2,4,8} x max(phase1_seed, 4 * assigned_sm_count)`, clamped to 1024. A
  phase2_bench-style two-pass local search (sweep K0 with K1 fixed, then K1 with K0 fixed at
  its winner) picks the best (highest aggregate GB/s == lowest wall time, since bytes moved
  are fixed for the cell). `plateau_reached` is true iff, on both axes, the top candidate's
  gain over the previous one was < 2%. The search uses `kSearchTrials`=3 (cheap); the final
  reported measurement re-runs at the chosen block counts with the full `--trials` (10).
  `--fixed-blocks0/1` (v3) skip this entirely and measure directly at the given counts --
  used by the reuse overlay so it never re-searches per `reuse_N`.
- **Phase-2-aligned size grid** (v3 Change 1, `scripts/sweep.py`): `symmetric_sizes_bytes()`
  and `asymmetric_k1_sizes_bytes(k)` are imported directly from
  `experiments/02_two_kernel_size/scripts/gen_config.py` (never re-derived with a different
  ratio), prepended with a small-end extension (`[0.03125, 0.0625]` MiB / same fractions of
  `k`). Phase 2's anchors are matched to their exact `(mode, k0_bytes, k1_bytes)` grid key and
  tagged `is_anchor=True` **in place** -- if an anchor doesn't land on an exact grid point,
  `sweep.py` exits loudly rather than silently snapping (that would indicate the grid
  functions have drifted from Phase 2's, a bug to fix, not paper over).
- **Reuse_N overlay** (v3 Change 3, `scripts/sweep_reuse.py`): subset sizes are picked
  dynamically from the just-completed reuse=1 CSV (smallest symmetric size, the two
  `is_anchor` symmetric sizes, the size closest to 4 MiB) rather than hardcoded, so this still
  works if the grid changes upstream. Every point on the reuse curve (including `reuse_N=1`
  and the check N=4) is re-measured at the FINAL, stability-verified block counts for full
  self-consistency, rather than reusing the cheaper partial data already on hand.
- **Regime classification** (`scripts/derive_findings.py`): a point's regime
  (L1/scheduling-sensitive vs L2-resident vs L2+SLC-resident vs DRAM-bound) is computed from
  its **size alone** -- per-SM working set `2*S / PARTITION_SM_REF` (fixed reference of 8
  SMs) against the 192 KB/SM L1, then Phase 1's `tier_steps` for the DRAM-bound tail. This is
  deliberately independent of whether green happened to win at that point (deriving regime
  FROM the measured delta would be circular -- it could never show "green helps in the L1
  regime" because the L1 regime was *defined* as "where green won"). `green_helps_size_regime`
  then correlates the two after the fact.
- **`findings.json`'s schema is byte-for-byte unchanged from v2** (v3 prompt: "same schema as
  v2 ... from the reuse=1 sweep only"); the grid-alignment note and reuse-overlay summary are
  FINDINGS.md-only prose, never new JSON keys, so Phase 4's handoff contract doesn't shift
  under it.
- **Timing across two streams / SM split notation / single-split-call requirement /
  green-context-per-cell lifecycle / correctness check / asymmetric-ratio proportional
  sweep:** unchanged since the original Phase 3 implementation; see `prompts/03_green_context.md`
  and the harness for the underlying rationale (still valid in v2/v3).
- `delta_vs_shared_pct` still can't be computed inside a single `phase3_bench` invocation (it
  needs the sibling shared-baseline row for the same test point), so the binary prints `0.0`
  for that column and `scripts/sweep.py` fills in the real value after collecting all cells
  for a test point -- unchanged from v1. The reuse-overlay CSV schema drops this column
  entirely (and `plateau_reached`), since it's a different, simpler row shape.
