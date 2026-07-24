# Phase 2 — Two-Kernel Size Sweep (green context OFF, zero copy OFF)

See `../../OVERVIEW.md` §3 and `../../prompts/02_two_kernel_size.md` for the full spec; this
README only covers how to build/run this phase and how it links to Phase 1.

## What this measures

Two `C = A + B` kernels (same kernel as Phase 1), each with its own buffers, launched
concurrently on two CUDA streams, reuse N=1 (Phase 2 does not sweep reuse). Green context and
zero copy are OFF for the whole phase.

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
scripts/run.sh            build + gen_config + locks clocks + runs the sweep + appends shared/env.md
scripts/plot.py           results/phase2_results.csv -> results/plots/*.png
scripts/derive_findings.py  results/phase2_results.csv -> findings.json + FINDINGS.md
results/                  config CSV, results CSV, plots (committed)
```

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh                       # build + gen_config + lock clocks + sweep -> results/phase2_results.csv
python3 scripts/plot.py              # -> results/plots/sym_agg_vs_footprint.png, asym_vs_k1.png
python3 scripts/derive_findings.py   # -> findings.json, FINDINGS.md
```

All scripts resolve their own paths, so they can be invoked from any working directory.
`gen_config.py` / `plot.py` / `derive_findings.py` need `pandas` + `matplotlib`.

`scripts/run.sh` attempts `sudo nvpmodel -m 0` and `sudo jetson_clocks` itself
(`00_conventions.md` §4); if sudo/those tools aren't available it warns and continues rather than
failing, so re-run it with proper privileges on the real device before trusting the numbers.

## Status

**Not yet run on real hardware.** This environment (Windows dev machine) has no CUDA toolkit /
Jetson device, so `src/phase2_bench.cu` could not be compiled or executed here — only reviewed
for correctness against the prompt spec. `results/`, `findings.json`, `FINDINGS.md`, and
`../../shared/env.md` are intentionally **not** pre-populated with placeholder numbers beyond
`gen_config.py`'s documented fallback sweep plan (see "Dependency on Phase 1" above). Run the
three commands above on the Jetson (ideally after Phase 1 has real results) to produce them.

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
- **Reuse:** fixed at N=1 throughout — Phase 2's prompt does not list reuse as a swept axis (unlike
  Phase 1), and the CSV schema has no `reuse_N` column.
- **Env fields, correctness check, stats (median/min/max/stddev):** identical approach to Phase 1
  (`../01_single_kernel_size/src/phase1_bench.cu`), duplicated rather than shared per the
  phase-isolation rule in `00_conventions.md` #1.
