# Phase 4 — Zero Copy (Cache Bypass) + Reuse Crossover

See `../../OVERVIEW.md` §3 and `../../prompts/04_zero_copy.md` for the full spec; this
README covers how to build/run this phase and the design decisions made while implementing
it ahead of Phase 2/3 actually running (allowed per the prompt's "Dependency" section).

## What this measures

On top of the Phase 2/3 two-kernel test points (symmetric and asymmetric, shared or green
SM config), applies **zero copy** (mapped pinned host memory, `cudaHostAlloc(...,
cudaHostAllocMapped)` + `cudaHostGetDevicePointer`) to the large/streaming kernel's A/B
input buffers only, and sweeps **reuse N in {1,2,4,8,16,32}** to find where the sign of
`zero-copy vs cached` throughput delta flips. Output buffers (C) always stay in normal
`cudaMalloc` memory for both kernels; only the large kernel's reads are rerouted.

**Convention adopted:** the "large kernel" is always **K1** (`large_kernel_id=1`). This
matches Phase 2's asymmetric definition (K0 fixed 1 MB, K1 grown to `k`) directly; for
symmetric test points, where both kernels are the same size, K1 is picked by an arbitrary
but fixed convention so the harness has one code path for both modes.

## Layout

```
src/phase4_bench.cu           CUDA benchmark: two-kernel concurrent sweep, zero-copy alloc,
                               green-context launch, correctness check, CSV writer
scripts/build.sh               nvcc build -> build/phase4_bench (gitignored), links -lcuda
scripts/gen_test_points.py      reads Phase 1/2/3 findings.json -> results/test_points_config.csv
scripts/run.sh                  locks clocks, gen_test_points, runs the sweep, appends shared/env.md
scripts/profile_l2.sh           Nsight Compute L2 hit-rate verification (cached vs zerocopy)
scripts/parse_l2_profile.py     raw ncu csv -> results/l2_profile.csv
scripts/plot.py                 results/phase4_results.csv -> results/plots/*.png
scripts/derive_findings.py      merges l2_profile.csv, -> findings.json + FINDINGS.md
results/                        CSV + plots (committed)
```

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh                    # gen_test_points + build + lock clocks + sweep -> results/phase4_results.csv
scripts/profile_l2.sh             # requires `ncu` on PATH -> results/l2_profile.csv (L2 bypass evidence)
python3 scripts/plot.py           # -> results/plots/zc_vs_cached_reuse.png, zc_benefit_map.png
python3 scripts/derive_findings.py  # merges l2_profile.csv into the CSV, -> findings.json, FINDINGS.md
```

All scripts resolve their own paths, so they can be invoked from any working directory.
`plot.py` / `derive_findings.py` / `gen_test_points.py` / `parse_l2_profile.py` need
`pandas` (+ `matplotlib`, `numpy` for plotting) — `pip install pandas matplotlib numpy`.

`scripts/run.sh` attempts `sudo nvpmodel -m 0` and `sudo jetson_clocks` itself
(00_conventions.md §4); if sudo/those tools aren't available it warns and continues rather
than failing, so re-run it with proper privileges on the real device before trusting the
numbers.

## Status

**Not yet run on real hardware.** Like Phase 1, this environment (Windows dev machine) has
no CUDA toolkit / Jetson device, so `src/phase4_bench.cu` could not be compiled or executed
here — only reviewed for correctness against the prompt spec. Two additional pieces are
therefore **unverified until run on-device**:

1. **Green-context driver-API calls** (`cuDeviceGetDevResource`, `cuDevSmResourceSplitByCount`,
   `cuDevResourceGenerateDesc`, `cuGreenCtxCreate`, `cuGreenCtxStreamCreate` — CUDA 12.4+) —
   written to match the public API as documented, but not compile-tested. If the on-device
   CUDA/driver is older than 12.4, this code path compiles out to a stub that logs a warning
   and skips `config=green` rows (never fakes partitioning, per `prompts/03_green_context.md`
   / `04_zero_copy.md`). If it's 12.4+, **verify on first run** that green rows actually
   execute (check stderr for `green-context driver call failed` messages) before trusting
   any `config=green` numbers.
2. **`scripts/parse_l2_profile.py`**'s Nsight Compute CSV column detection — `ncu`'s raw-page
   CSV shape has varied across versions; the parser tries both a wide form (one column named
   containing `lts__t_sector_hit_rate.pct`) and a long form (`Metric Name`/`Metric Value`
   columns) and reports which one it found. If neither matches on your `ncu` version, it
   warns and leaves that cell `NA` rather than guessing.

**Upstream findings.json also don't exist yet:** `experiments/02_two_kernel_size/` and
`experiments/03_green_context/` haven't been implemented (only `01_single_kernel_size/` has,
and it too hasn't been run). Per the prompt's "Dependency" section this phase implements the
full harness anyway; `scripts/gen_test_points.py` falls back to clearly-marked
`*_PLACEHOLDER*` test points (2 MB symmetric, 1 MB vs 8 MB asymmetric — bracketing the 4 MB
L2 / 8 MB L2+SLC tiers from `OVERVIEW.md`) when it can't find real upstream numbers, and
records exactly what it consumed/fell back to in `results/test_points_provenance.json`.
**Do not treat a `phase4_results.csv` produced from placeholder test points as a real
finding** — re-run `gen_test_points.py` once Phase 2 and 3 have actually run, before trusting
`findings.json`.

## Design notes

- **Correctness:** same as Phase 1 (`A[i]=1, B[i]=2` => `C[i]==3`), sampled up to 4096
  elements per kernel, checked once per (test point, path).
- **Per-kernel vs aggregate timing:** per-kernel time uses one CUDA event pair per stream
  (`k0_ms`/`k1_ms`); aggregate wall time uses a CPU-side `std::chrono` bracket around
  submission + both streams' `cudaStreamSynchronize`, since the two kernels run
  concurrently on separate streams and a single global CUDA-event pair on one stream
  wouldn't capture the other stream's tail.
- **`delta_vs_cached_pct`** is computed at write time by keying the just-measured
  `cached`-path aggregate GB/s (per `reuse_N`) in a map, then diffing against it when the
  `zerocopy`-path row for the same `reuse_N` is written (the harness always runs `cached`
  before `zerocopy` for a given test point). It is `NA` if a `zerocopy` row is written
  without a corresponding `cached` baseline (only possible when using `--profile-one` with
  `--profile-path zerocopy` in isolation, e.g. `profile_l2.sh`'s per-launch runs).
- **L2 hit-rate columns are broadcast, not per-row:** `l2_hit_rate_cached`/`l2_hit_rate_zc`
  in `phase4_results.csv` hold the *same* profiled pair of values on every row (every
  `reuse_N`, every `large_kernel_path`) for a given `test_point_id`. Rationale: zero-copy
  bypasses L2 on every launch regardless of how many times a buffer is reused within one
  measured cell (it's not a residency effect, it's a routing decision), and the cached
  path's steady-state per-launch hit rate for a fixed buffer size doesn't change with
  `reuse_N` either — only the *aggregate* benefit of that hit rate does (captured already
  by `agg_GBps_median`). Profiling once per (test point, path) at `reuse_N=1` is therefore
  treated as representative; `scripts/profile_l2.sh` documents this in its header comment.
  If on-device measurement shows this assumption doesn't hold, flag it in a future
  worklog entry per `00_conventions.md` §2 rule 4 (don't silently overwrite).
- **`gen_test_points.py` ID matching:** Phase 3's `configs_for_phase4` findings key gives
  `(test_point_id, config, sm_split)`; sizes are re-derived from Phase 2's
  `symmetric_roofline_points`/`asymmetric_k_used_bytes` by matching on the `sym`/`asym`
  prefix of `test_point_id` and, for symmetric, whether `"90"` appears in the id (onset vs
  90%-below point). This is a naming-convention assumption, not a schema guarantee — if
  Phase 3 ships with different id strings, `gen_test_points.py` will warn
  (`could not resolve sizes for test_point_id=...`) and skip that entry rather than
  guessing a size.
