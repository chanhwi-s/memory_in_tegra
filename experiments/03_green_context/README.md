# Phase 3 — Green Context (SM Partitioning) on the Two-Kernel Roofline

See `../../OVERVIEW.md` §3 and `../../prompts/03_green_context.md` for the full spec;
this README only covers how to build/run this phase.

## What this measures

Two concurrent `C = A + B` kernels (K0, K1) at Phase 2's roofline test points, comparing
**shared SMs** (Phase 2 baseline, both kernels on all 16 SMs) vs **green-context partitioned
SMs** (each kernel gets a disjoint SM set). Zero copy stays OFF this phase. Swept: test point
(from Phase 2) x SM partition ratio (symmetric: 4:12..12:4 around 8:8; asymmetric: ratios near
the kernels' size ratio).

## Layout

```
src/phase3_bench.cu     CUDA/driver-API benchmark: measures ONE cell per invocation
                        (shared|green config), plus a --verify mode (%smid probe) and
                        a --check-api mode (green context availability check)
scripts/build.sh        nvcc build -> build/phase3_bench (gitignored), links -lcuda
scripts/sweep.py        outer driver: reads Phase 1/2 findings.json at run time, builds
                        the test-point x partition-ratio cell list, invokes the binary
                        per cell, joins delta_vs_shared_pct, writes results/phase3_results.csv
scripts/run.sh          locks clocks, runs sweep.py, runs partition verification, appends
                        shared/env.md
scripts/plot.py         results/phase3_results.csv -> results/plots/*.png
scripts/derive_findings.py  results/phase3_results.csv -> findings.json + FINDINGS.md
results/                CSV + plots + partition_verification.txt (committed)
```

## Dependency on upstream findings (00_conventions.md #2)

This phase **reads, at run time**, `experiments/01_single_kernel_size/findings.json`
(saturation blocks, recommended threads/block) and `experiments/02_two_kernel_size/findings.json`
(`recommended_phase3_test_points`). **As of writing, neither file exists yet** (Phase 1 has not
been run on real hardware; Phase 2 has not been implemented). Per the Phase 3 prompt's explicit
instruction, the harness is implemented now anyway: `scripts/sweep.py` falls back to placeholder
test points / tpb / block counts (`DEFAULT_TEST_POINTS`, `DEFAULT_TPB`, `DEFAULT_BLOCKS`) with a
loud `TODO(read from phase{1,2} findings)` warning on stderr — it never fabricates the missing
upstream numbers, only supplies its own clearly-labeled placeholders so the sweep is runnable
standalone. Re-run `scripts/sweep.py` once those `findings.json` files exist; do not trust a run
that printed those warnings as final.

Sanity-check the plan without a CUDA device:
```bash
python3 scripts/sweep.py --dry-run
```

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh
```

Single entry point: build (if needed) -> lock clocks -> `--check-api` -> sweep
(`results/phase3_results.csv`) -> `--verify` (`results/partition_verification.txt`) -> plots
(`results/plots/green_vs_shared.png`, `partition_sweep.png`) -> findings
(`findings.json`, `FINDINGS.md`) -> append `shared/env.md`. No separate `plot.py` /
`derive_findings.py` invocation needed.

`run.sh`, `build.sh`, and `sweep.py` all resolve their own paths, so they can be invoked from
any working directory. The plot/findings steps need `pandas` + `matplotlib`; run
`scripts/plot.py` / `scripts/derive_findings.py` directly only if you want to regenerate just
those from an existing `results/phase3_results.csv` without re-running the sweep.

`scripts/run.sh` first runs `phase3_bench --check-api`, which reports whether the CUDA driver
green-context API (CUDA >= 12.4) is actually available on this device — per the prompt: **"First
verify the API and required CUDA version are available on this device; if not, stop and report
in the worklog rather than faking partitioning."** If the check fails, `shared`-config cells still
run (they need no green context), but every `green`-config cell in the sweep will error out
(`phase3_bench` returns exit code 3 and refuses to proceed rather than silently falling back to
an unpartitioned run).

## Status

**Not yet compiled or run.** This environment (Windows dev machine) has no CUDA toolkit or
Jetson device, so `src/phase3_bench.cu` could not be built or executed here — only written
against the documented CUDA 12.4 Green Context driver API from memory and reviewed against the
prompt spec (same situation as Phase 1 — see `../01_single_kernel_size/README.md`). Before
trusting this on real hardware:
- **Verify the green-context driver API call signatures** (`cuDeviceGetDevResource`,
  `cuDevSmResourceSplitByCount`, `cuDevResourceGenerateDesc`, `cuGreenCtxCreate`,
  `cuCtxFromGreenCtx`, `cuGreenCtxStreamCreate`) against the installed `<cuda.h>` — struct/enum
  names may differ slightly by CUDA minor version; this file has never been compiled.
- Run `scripts/build.sh` and fix any compile errors against the real `cuda.h` first.
- Run `phase3_bench --check-api` and confirm it reports the API as available before trusting
  any `green`-config row.
- Run `phase3_bench --verify` (or `scripts/run.sh`, which does this automatically) and confirm
  `results/partition_verification.txt` reports disjoint smid sets between the two partitions —
  if it reports overlap, partitioning did not actually take effect and every green-config number
  upstream of that is suspect.
- `results/`, `findings.json`, `FINDINGS.md`, and `../../shared/env.md` are intentionally **not**
  pre-populated with placeholder numbers — only `scripts/sweep.py`'s *cell plan* (which sizes/
  ratios to test) uses placeholders when upstream `findings.json` is missing, never the
  *measured results themselves*.

## Design notes

- **Timing across two streams:** both kernels are launched after a shared "start" barrier
  (`cudaEventRecord` on K0's stream, `cudaStreamWaitEvent` on K1's stream against it), each with
  its own stop event; wall time = `max(elapsed_to_stop0, elapsed_to_stop1)`. Same discipline as
  Phase 1/2 otherwise: 3 untimed warm-up launches, >=10 timed trials, median reported.
  `delta_vs_shared_pct` cannot be computed inside a single `phase3_bench` invocation (it needs
  the sibling shared-baseline row for the same test point), so `phase3_bench` prints `0.0` for
  that column and `scripts/sweep.py` fills in the real value after collecting all cells for a
  test point.
- **SM split notation:** `sm_split_k0:sm_split_k1` always sums to 16 (the device's total SM
  count) for `green` rows; `shared` rows record `16:16` (both kernels see all SMs) as a
  self-describing sentinel, not a real disjoint split.
- **Green context creation is per-cell**, not cached across trials within a cell — partitions are
  created once before the warm-up loop and destroyed after the timed trials for that cell, so
  context-creation overhead is excluded from the measured window.
- **Correctness check** happens after the timed run (not before, since `dC0`/`dC1` are only
  written by `addKernel`, not by the buffer-fill step) on both kernels' outputs, same tolerance
  as Phase 1.
- **Asymmetric partition ratios** in `sweep.py` are chosen proportional to the two kernels' byte
  sizes (`round(16 * k0_bytes / (k0_bytes + k1_bytes))`, clamped to `[2, 14]`, plus +/-2 SM
  neighbors) rather than the fixed symmetric sweep, per the prompt's "sweep ratios around the
  size ratio of the two kernels" instruction.
