# Phase 4 v2 — Zero Copy (Cache Bypass) + Reuse Crossover, In-Context Block Saturation, Widened Size Sweep

See `../../OVERVIEW.md` §3, `../../prompts/04_zero_copy.md` (original spec), and
`../../prompts/04_zero_copy_v2.md` (this re-run's spec) for the full requirements. This
README covers how to build/run this phase and the design decisions made while implementing
the v2 re-sweep. **This run supersedes the first Phase 4 run in place** — see "Discrepancy
vs first Phase 4 run" in `FINDINGS.md` once `scripts/run.sh` has been re-executed.

## Why this v2 re-run exists

The first Phase 4 run had two methodology gaps (mirrors the Phase 3 v2 re-run for the same
reasons):

1. **Block counts were never re-swept in context.** `scripts/gen_test_points.py` pulled a
   block count from Phase 1's *single-kernel* `saturation_blocks_by_size` via
   nearest-neighbor and held it **fixed** for both the cached and zero-copy paths. The
   zero-copy (mapped-pinned, cache-bypassing) path has a different memory-latency profile
   than the cached path and generally saturates at a different block count, so a single
   fixed value can under- or over-subscribe one of the two paths and bias the
   cached-vs-zerocopy delta.
2. **The size sweep was pinned to 3 points**, and two of the three (`sym_0`, `sym_1`) were
   **symmetric** — worse, a naming bug (see "Discrepancy" below) made them resolve to the
   *same* size, so the "large kernel" headline rested on a single symmetric contention
   point, not an actual large/streaming kernel.

## What this measures

On top of Phase 2/3's two-kernel setup, applies **zero copy** (mapped pinned host memory,
`cudaHostAlloc(..., cudaHostAllocMapped)` + `cudaHostGetDevicePointer`) to the large
kernel's A/B input buffers only, and sweeps **reuse N in {1,2,4,8,16,32}** to find where the
sign of `zero-copy vs cached` throughput delta flips. Output buffers (C) always stay in
normal `cudaMalloc` memory for both kernels; only the large kernel's reads are rerouted.

**Convention (unchanged):** the "large kernel" is always **K1** (`large_kernel_id=1`).

### v2 Change 1 — in-context block saturation search
`seed_blocks_k0`/`seed_blocks_k1` in `test_points_config.csv` are only a **search seed**
(Phase 1's single-kernel nearest-neighbor lookup), never the final block count.
`phase4_bench` runs its own local saturation search (`searchBlockSaturation` in
`src/phase4_bench.cu`), mirroring `02_two_kernel_size/src/phase2_bench.cu`'s "1-D pass, K0
then K1" method but widened to multipliers `{1,2,4,8}x seed` (capped at 1024, per the v2
prompt). This search runs **independently for every (test point row's config, cached |
zerocopy) combination** — a shared-config cached search never reuses a green-config or
zerocopy search's result.

Stability check (`searchAndVerifyStable`): the search is run once at `reuse_N=1` and once
at `reuse_N=4`; if the two disagree, the element-wise **max** of the two is used (never
under-provisions) and a note is logged to stderr — this is the ",verify once that the
plateau block count is stable across a couple of N values" requirement. The chosen
`blocks_k0`/`blocks_k1` are then held fixed across the full `reuse_N` sweep and written to
`results/phase4_results.csv`, along with a `plateau_reached` flag (false if the search's
best candidate was the *last* one tried — i.e. still rising at the top of the search range,
meaning the range should be widened).

A side file, `results/chosen_blocks.csv`, records the chosen blocks per (test_point_id,
config, path) so `scripts/profile_l2.sh` can reuse them instead of re-running the search
under Nsight Compute's replay overhead (which would be prohibitively slow).

### v2 Change 2 — widened size sweep
`scripts/gen_test_points.py` builds its own sweep instead of taking 3 fixed points:

- **Asymmetric (primary, the "large kernel" story):** K0 fixed at 1 MB; K1 swept on a
  ~1.75x geometric grid from a small-end anchor (where the per-SM working set
  `2*K1/16 SMs` ≈ 192 KB/SM, i.e. approaching L1 residency) up through the L2/SLC tiers and
  into clearly DRAM-bound territory (K1 > ~8 MB, continuing to ~4x the measured
  `dram_bound_min_read_footprint_bytes`). Capped at 12 points to keep on-device runtime
  reasonable. Phase 2's `asymmetric_k_used_bytes` is snapped onto the nearest grid point (or
  inserted if no grid point is within 10%) and labeled `asym_2`, `is_anchor=1`, for direct
  comparison with the first run.
- **Symmetric (secondary, kept for continuity):** the original two roofline anchors —
  `sym_0` = Phase 2's `ninety_pct` size (786432 B), `sym_1` = `onset` size (917504 B), both
  `is_anchor=1` — plus two optional context points (`sym_ctx_small`/`sym_ctx_large`,
  `is_anchor=0`) reusing the asymmetric grid's small/large ends. **These are explicitly not
  the large-kernel story** (both kernels are the same size); the headline in `FINDINGS.md`
  is drawn from the asymmetric sweep.
- **Regime classification:** every row gets a `size_regime` in `{l1, l2, slc, dram}` —
  `l1` if the large kernel's per-SM footprint (`2*K1/16`) is at or below 192 KB/SM,
  otherwise classified against Phase 1's measured `tier_steps` (falls back to OVERVIEW.md's
  4 MB / 8 MB book values if Phase 1 hasn't run).

### Consuming Phase 3 v2 (regime-aware green-context configs)
Per the v2 prompt's "Ordering" rule, this phase should run *after* Phase 3 v2, whose
`configs_for_phase4` is expected to vary **per size regime** (a single fixed SM split no
longer applies once the sweep spans L1→DRAM). `gen_test_points.py`:

1. Looks for a `regime`/`size_regime` field on `configs_for_phase4` entries. If present,
   builds a regime → `{config, sm_split}` lookup and assigns each generated point's config
   by its own `size_regime` (falling back to the nearest regime in tier order if its exact
   regime is missing from the map).
2. If Phase 3's `findings.json` is missing, or its `configs_for_phase4` has **no** regime
   field (i.e. it's still the stale, flat v1 shape), this is treated as "Phase 3 v2 hasn't
   run yet": every generated point gets `config="shared"` with a loud warning recorded in
   both stderr and `results/test_points_provenance.json`. **As of this writing, Phase 3 v2
   has not run** (a different session owns `03_green_context/`), so the checked-in
   `test_points_config.csv` is entirely `config=shared` — re-run `scripts/gen_test_points.py`
   once `experiments/03_green_context/findings.json` is the v2 (regime-aware) version.

## Layout

```
src/phase4_bench.cu            CUDA benchmark: two-kernel concurrent sweep, zero-copy alloc,
                                green-context launch, in-context block saturation search,
                                correctness check, CSV writer
scripts/build.sh                nvcc build -> build/phase4_bench (gitignored), links -lcuda
scripts/gen_test_points.py       reads Phase 1/2/3 findings.json -> results/test_points_config.csv
                                 (widened sweep, seed blocks only, regime-aware config)
scripts/run.sh                   locks clocks, archives the v1 baseline CSV (once), gen_test_points,
                                  runs the sweep, appends shared/env.md
scripts/profile_l2.sh            Nsight Compute L2 hit-rate verification (cached vs zerocopy),
                                  reuses results/chosen_blocks.csv instead of re-searching
scripts/parse_l2_profile.py      raw ncu csv -> results/l2_profile.csv
scripts/plot.py                  results/phase4_results.csv -> results/plots/*.png
scripts/derive_findings.py       merges l2_profile.csv, runs the Change-1 sanity gate against
                                  results/phase4_results_v1_baseline.csv, -> findings.json + FINDINGS.md
results/                         CSV + plots (committed)
```

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh   # the only command you need — does everything below in order:
                 #   archive v1 baseline (once) -> gen_test_points -> build (if needed)
                 #   -> lock clocks -> sweep (with in-context block saturation search)
                 #   -> results/phase4_results.csv -> profile_l2 (if `ncu` on PATH)
                 #   -> plot.py -> derive_findings.py (incl. the Change-1 sanity gate)
                 # -> results/phase4_results.csv, results/plots/*.png, findings.json, FINDINGS.md
```

If `ncu` isn't on PATH when `run.sh` runs, it skips L2 profiling with a warning
(`l2_hit_rate_*` columns and `l2_bypass_verified` stay `NA`/`false`) rather than failing —
install Nsight Compute and re-run `scripts/profile_l2.sh` followed by
`scripts/derive_findings.py` to fill those in afterward.

Each step is also a standalone script if you need to re-run just one piece after editing
something — `scripts/gen_test_points.py`, `scripts/profile_l2.sh`,
`python3 scripts/plot.py`, `python3 scripts/derive_findings.py`.

All scripts resolve their own paths, so they can be invoked from any working directory.
`plot.py` / `derive_findings.py` / `gen_test_points.py` / `parse_l2_profile.py` need
`pandas` (+ `matplotlib`, `numpy` for plotting) — `pip install pandas matplotlib numpy`.

`scripts/run.sh` attempts `sudo nvpmodel -m 0` and `sudo jetson_clocks` itself
(00_conventions.md §4); if sudo/those tools aren't available it warns and continues rather
than failing, so re-run it with proper privileges on the real device before trusting the
numbers.

## Status

**v2 harness implemented; not yet re-run on hardware.** This development environment has no
CUDA toolchain / Jetson device, so `src/phase4_bench.cu` could not be compiled here — it was
reviewed carefully against `prompts/04_zero_copy_v2.md` and its structure closely mirrors
the (already hardware-verified) `phase2_bench.cu` search pattern. `scripts/gen_test_points.py`,
`scripts/plot.py`, and `scripts/derive_findings.py` (pure Python) **were** executed here
against real/synthetic inputs and produce correct output:

- `gen_test_points.py` was run against this repo's actual upstream `findings.json` files;
  `results/test_points_config.csv` and `results/test_points_provenance.json` in this repo
  reflect a real v2 run of that script (11 test points, all `config=shared` since Phase 3 v2
  hasn't landed yet — see warnings in `test_points_provenance.json`).
- `plot.py` and `derive_findings.py` were smoke-tested against a synthetic
  v2-shaped CSV (not committed) to confirm the new columns/grouping/plots work end-to-end.

**`results/phase4_results.csv`, `results/plots/*.png`, `findings.json`, and `FINDINGS.md`
in this repo still reflect the first Phase 4 run** (real hardware numbers) — they are
intentionally left untouched rather than overwritten with fabricated v2 numbers.
`scripts/run.sh` will archive that file to `results/phase4_results_v1_baseline.csv` (used by
the Change-1 sanity gate) the first time it's re-run, then overwrite
`phase4_results.csv`/plots/`findings.json`/`FINDINGS.md` with real v2 measurements. **Do not
treat the current `findings.json`/`FINDINGS.md` as v2 results until `scripts/run.sh` has
actually been re-executed on the Jetson device.**

Also unverified until run on-device (unchanged from the first run):
1. **Green-context driver-API calls** — written to match the public CUDA 12.4+ API; if the
   on-device CUDA/driver is older, this compiles out to a stub that skips `config=green`
   rows. Since Phase 3 v2 hasn't run yet, no `config=green` rows exist in the checked-in
   config CSV anyway — this only matters once Phase 3 v2 lands and green rows appear.
2. **`scripts/parse_l2_profile.py`**'s Nsight Compute CSV column detection (unchanged from
   the first run — see its own comments).

## Design notes

- **Correctness:** unchanged — `A[i]=1, B[i]=2` => `C[i]==3`, sampled up to 4096 elements
  per kernel, checked once per (test point, path).
- **Per-kernel vs aggregate timing:** unchanged from the first run — see
  `measureConcurrentCell` in `src/phase4_bench.cu`.
- **`delta_vs_cached_pct`**: unchanged computation (cached path always measured first per
  test point, keyed by `reuse_N`).
- **Block saturation search (v2):** see "v2 Change 1" above. The search's per-candidate
  measurement uses only 3 trials (matching `phase2_bench`'s search-pass trial count) since
  it only needs to find the argmax, not a publication-quality number; the final
  measured-and-reported cell at the chosen block count still uses the full `trials=10`.
- **Regime classification order matters:** the L1 per-SM check (`2*K1/16 <= 192KB`) is
  checked *before* the aggregate L2/SLC/DRAM footprint tiers, so a small K1 that would
  otherwise classify as "L2-resident" by aggregate footprint gets tagged `l1` instead —
  intentional, since green context's predicted benefit tracks the per-SM/L1 view, not the
  global cache-footprint view that zero copy targets. Documented here since it's a modeling
  choice, not a measured fact.
- **`l2_hit_rate_*` columns are broadcast, not per-row:** unchanged rationale from the first
  run (see git history for the original explanation) — profiled once per (test point, path)
  at `reuse_N=1`, broadcast across the full `reuse_N` sweep for that row.
- **`gen_test_points.py` no longer matches Phase 3 ids by substring.** The first run's
  `"90" in tpid` heuristic caused the sym_0/sym_1 bug (see `FINDINGS.md`
  "Discrepancy vs first Phase 4 run"). v2 reads Phase 2's
  `symmetric_roofline_points.{ninety_pct,onset}` directly for symmetric anchor sizes, and
  only consults Phase 3 v2 for the **config/sm_split** (via the size-regime map), never for
  sizes.
