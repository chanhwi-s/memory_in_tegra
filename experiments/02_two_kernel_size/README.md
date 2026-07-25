# Phase 2 — Two-Kernel Size Sweep (green context OFF, zero copy OFF)

See `../../OVERVIEW.md` §3, `../../prompts/02_two_kernel_size.md` (main sweep) and
`../../prompts/02_two_kernel_size_v2.md` (reuse-overlay add-on) for the full spec; this README
only covers how to build/run this phase and how it links to Phase 1.

## What this measures

Two `C = A + B` kernels (same kernel as Phase 1), each with its own buffers, launched
concurrently on two CUDA streams, reuse N=1 (the main sweep does not sweep reuse — a separate v2
add-on does, see "v2 add-on: reuse-sweep overlay" below). Green context and zero copy are OFF for
the whole phase.

- **2a symmetric:** K0 and K1 both size S, S swept so combined read footprint (`2*S + 2*S = 4*S`)
  densifies near L2 (4 MB) and L2+SLC (8 MB).
- **2b asymmetric:** K0 fixed at 1 MB, K1 swept up to and past `k`, the cache-overflow /
  bound-crossover point from Phase 1.

Goal: find the **contention onset** — where aggregate throughput falls below the ideal 2x
(perfect scaling) — which Phases 3 and 4 will target.

## Dependency on Phase 1

Per `prompts/02_two_kernel_size.md` ("Dependency") this phase must read its sweep parameters and
single-kernel reference throughput **from Phase 1's measured output at run time**, never
hard-code or re-derive them:

- `scripts/gen_config.py` reads `experiments/01_single_kernel_size/findings.json` for
  `tier_steps.dram_bound_min_read_footprint_bytes` (→ `k = footprint/2`),
  `saturation_blocks_by_size` (block-count hints), and `recommended_threads_per_block`.
- It also reads `experiments/01_single_kernel_size/results/phase1_results.csv` directly for
  per-size `achieved_GBps_median` (the `single_k0_GBps_ref` / `single_k1_GBps_ref` columns) —
  `findings.json` only carries summary tier numbers, not a full per-size curve.
- Both reads are read-only (isolation rule in `00_conventions.md` #1: never write into another
  phase's directory).

**Status: Phase 1 has not been run on real hardware yet** (see
`../01_single_kernel_size/README.md`), so neither file exists. `gen_config.py` falls back to
placeholder defaults (marked `TODO(read from phase1 findings)` in the source) and writes
`single_k0_GBps_ref` / `single_k1_GBps_ref` as `-1` (sentinel "unknown"). `phase2_bench` then
writes `scaling_efficiency = -1` for those cells rather than inventing a number.
**Re-run `gen_config.py` (and then the binary + `derive_findings.py`) once Phase 1 has real
results** — the fallback config is only there so this phase's harness could be built and
reviewed independently, per the prompt's "may implement... independently of Phase 1" note.

## Layout

```
src/phase2_bench.cu       CUDA benchmark: concurrent K0/K1 measurement, correctness, CSV writer
scripts/gen_config.py     reads Phase 1 findings/CSV -> results/phase2_config.csv (sweep plan)
scripts/build.sh          nvcc build -> build/phase2_bench (gitignored)
scripts/run.sh            single entry point: build + gen_config + lock clocks + sweep + plot + derive findings + appends shared/env.md
scripts/plot.py           results/phase2_results.csv -> results/plots/*.png (called by run.sh; standalone re-run also works)
scripts/derive_findings.py  results/phase2_results.csv -> findings.json + FINDINGS.md (called by run.sh; standalone re-run also works)
results/                  config CSV, results CSV, plots (committed)
```

### v2 add-on: reuse-sweep overlay

```
scripts/run_reuse_overlay.sh    build + lock clocks + reuse sweep + plot + append findings
scripts/plot_reuse.py           results/phase2_reuse_results.csv -> results/plots/reuse_bw_vs_footprint.png
scripts/append_reuse_findings.py  appends a "Reuse overlay" section to FINDINGS.md (never touches findings.json)
results/phase2_reuse_results.csv  reuse_N in {1,2,4,8,16,32}, same size grid as the main sweep
```

Per `prompts/02_two_kernel_size_v2.md`: `phase2_bench` gained an optional `--reuse-out <path>`
flag (mirroring Phase 4's reuse loop) that switches entirely to this overlay mode -- when set, it
does **not** also write `--out`, so `results/phase2_results.csv` and `findings.json` (the frozen
reuse=1 handoff to Phases 3/4) can never be touched by this add-on. Config/sizes are unchanged
(`scripts/gen_config.py` was not modified); block counts are searched once at reuse_N=1, verified
stable at a second N (checkN=4, holding the element-wise max if unstable, with a `NOTE` to
stderr), then held fixed across all six reuse_N values per cell -- so the added cost is ~6x a
single reuse=1 run, not 6x a fresh search per N.

**`scripts/run.sh` now runs this add-on automatically** as the last step of the main pipeline
(after `derive_findings.py`, since that script rewrites `FINDINGS.md` from scratch and would
otherwise drop the appended "Reuse overlay" section). Use `scripts/run_reuse_overlay.sh`
standalone only if you want to re-run *just* the reuse overlay (e.g. after editing
`plot_reuse.py`) without re-running the full main sweep.

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh   # build + gen_config + lock clocks + sweep + plot + derive findings + reuse overlay, all in one step
```

`run.sh` runs the full pipeline end to end: `results/phase2_results.csv` +
`results/phase2_reuse_results.csv`, `results/plots/sym_agg_vs_footprint.png` +
`asym_vs_k1.png` + `reuse_bw_vs_footprint.png`, and `findings.json` + `FINDINGS.md` (including
its "Reuse overlay" section) are all produced by this single command — no separate manual
`plot.py` / `derive_findings.py` / `plot_reuse.py` / `append_reuse_findings.py` step needed.
Re-run any of those scripts standalone only if you want to regenerate a subset of
plots/findings from already-existing CSVs without re-running the sweep(s).

All scripts resolve their own paths, so they can be invoked from any working directory.
`gen_config.py` / `plot.py` / `derive_findings.py` need `pandas` + `matplotlib`.

`scripts/run.sh` attempts `sudo nvpmodel -m 0` and `sudo jetson_clocks` itself
(`00_conventions.md` §4); if sudo/those tools aren't available it warns and continues rather than
failing, so re-run it with proper privileges on the real device before trusting the numbers.

## Status

**Main sweep (2a/2b, reuse=1): run on real hardware.** `results/phase2_results.csv`,
`findings.json`, and `FINDINGS.md` contain real measured numbers (see git history) — this is no
longer the "not yet run" placeholder state described in earlier revisions of this file.

**v2 reuse-overlay add-on: implemented, not yet run on hardware.** This development environment
has no CUDA toolchain / Jetson device (checked: no `nvcc` on PATH here), so the `--reuse-out`
code path in `src/phase2_bench.cu` and the new `scripts/run_reuse_overlay.sh` /
`scripts/plot_reuse.py` / `scripts/append_reuse_findings.py` could not be compiled or executed in
this environment — only reviewed against `prompts/02_two_kernel_size_v2.md` and exercised with
synthetic CSV data (deleted before commit) to verify the plotting/findings scripts run
end-to-end and are idempotent. Run `scripts/run_reuse_overlay.sh` on the Jetson (after the main
sweep above) to produce `results/phase2_reuse_results.csv`,
`results/plots/reuse_bw_vs_footprint.png`, and the "Reuse overlay" section of `FINDINGS.md`.

## Design notes

- **Concurrency timing:** a "join" `cudaEvent` is recorded on stream0 and waited on by stream1
  (`cudaStreamWaitEvent`) immediately before each trial's launches, so both kernels' timed
  regions start from the same reference point; `wall_ms = max(elapsed(join, stop0), elapsed(join,
  stop1))`. This is what `wall_ms_median` / `agg_GBps_median` are computed from.
- **Overlap sanity check** (prompt Verification: "wall < serial sum"): each cell also measures K0
  and K1 *alone* (5 trials each, not concurrent) purely as an internal check; if
  `wall_ms_median >= serial_sum_ms` the binary prints a `WARNING` to stderr. These isolated
  timings are **not** written to the CSV and are **not** the source of `single_k*_GBps_ref` — that
  column comes from Phase 1's established baseline (see "Dependency on Phase 1"), per
  `00_conventions.md` #2 ("never... re-derive them").
- **Block-count search:** rather than a full 2D grid search over (blocks_k0, blocks_k1), each
  cell does two 1D passes — sweep K0's blocks (multipliers `{1,2,4}` of Phase 1's hint, capped at
  1024) with K1 fixed at its hint, keep the best; then sweep K1's blocks the same way with K0
  fixed at the value just found. This is a documented simplification to keep the aggregate-plateau
  confirmation cheap; it can miss a joint optimum in principle but should be close given each
  kernel's per-SM saturation behavior is largely independent of the other kernel's block count.
  Block count is still a knob, not a reported swept axis — `blocks_k0`/`blocks_k1` in the CSV
  record whatever the search landed on for that cell.
- **Reuse:** the main sweep (`phase2_results.csv`) is fixed at N=1 throughout — the original
  prompt does not list reuse as a swept axis (unlike Phase 1), and its CSV schema has no
  `reuse_N` column. The v2 add-on (`prompts/02_two_kernel_size_v2.md`) adds a *separate*
  reuse_N in {1,2,4,8,16,32} sweep via `--reuse-out` -> `phase2_reuse_results.csv`, diagnostic
  only, never merged into the main CSV/findings — see "v2 add-on: reuse-sweep overlay" above.
- **Env fields, correctness check, stats (median/min/max/stddev):** identical approach to Phase 1
  (`../01_single_kernel_size/src/phase1_bench.cu`), duplicated rather than shared per the
  phase-isolation rule in `00_conventions.md` #1.
