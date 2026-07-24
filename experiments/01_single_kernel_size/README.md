# Phase 1 — Single-Kernel Memory-Hierarchy Characterization

See `../../OVERVIEW.md` §3 and `../../prompts/01_single_kernel_size.md` for the full spec;
this README only covers how to build/run this phase.

## What this measures

`C = A + B` (float, grid-stride, uniform/coalesced), zero copy OFF, green context OFF.
Sweeps working-set size (16 values, 32 KB - 96 MB per buffer) x reuse N (1..32 launches
over the same buffers) x block count (16..1024, saturation knob) at threads/block=256,
plus a one-off threads/block check (128/256/512) at one mid size. Goal: locate the
L1/L2/SLC/DRAM bandwidth steps and the measured DRAM peak for later phases to build on.

## Layout

```
src/phase1_bench.cu       CUDA benchmark: kernel, sweep, correctness check, CSV writer
scripts/build.sh          nvcc build -> build/phase1_bench (gitignored)
scripts/run.sh            locks clocks, runs the sweep, appends shared/env.md
scripts/plot.py           results/phase1_results.csv -> results/plots/*.png
scripts/derive_findings.py  results/phase1_results.csv -> findings.json + FINDINGS.md
results/                  CSV + plots (committed)
```

## Running (on the Jetson AGX Orin device)

```bash
scripts/run.sh                 # build + lock clocks + sweep -> results/phase1_results.csv
python3 scripts/plot.py        # -> results/plots/bw_vs_footprint.png, saturation.png
python3 scripts/derive_findings.py   # -> findings.json, FINDINGS.md
```

`run.sh` and `build.sh` resolve their own paths, so they can be invoked from any
working directory. `plot.py` / `derive_findings.py` need `pandas` + `matplotlib`
(`pip install pandas matplotlib` if not already present on-device).

`scripts/run.sh` attempts `sudo nvpmodel -m 0` and `sudo jetson_clocks` itself
(00_conventions.md §4); if sudo/those tools aren't available it warns and continues
rather than failing, so re-run it with proper privileges on the real device before
trusting the numbers.

## Status

**Not yet run on real hardware.** This environment (Windows dev machine) has no CUDA
toolkit / Jetson device, so `src/phase1_bench.cu` could not be compiled or executed
here — only reviewed for correctness against the prompt spec. `results/`,
`findings.json`, `FINDINGS.md`, and `../../shared/env.md` are intentionally **not**
pre-populated with placeholder numbers: `derive_findings.py` computes every value
directly from the measured CSV so nothing here is guessed. Run the three commands
above on the Jetson to produce them, then check the Verification section of
`../../prompts/01_single_kernel_size.md` (tier sanity a/b, saturation validity,
correctness sample-check — the latter two are also asserted by the program itself
and it will print `CORRECTNESS FAILURE` / high-variance warnings to stderr if
something looks wrong).

## Design notes

- **Correctness:** `A[i]=1, B[i]=2` so `C[i]==3` is checked after the first measured
  cell (sample of up to 4096 elements copied back).
- **Saturation:** for each (size, reuse) group, a row is marked `saturated=1` if its
  achieved GB/s is within 2% of that group's max; `derive_findings.py` reports the
  minimum such block count per size.
- **Env fields self-reported by the binary:** `gpu_clock_mhz` via
  `cudaDeviceGetAttribute(cudaDevAttrClockRate)` (reflects the actual locked clock,
  not just the requested one), `cuda_version`/`driver_version` via the CUDA runtime
  API, `power_mode`/`soc_temp_c` via best-effort `nvpmodel -q` / thermal-zone sysfs
  reads (fall back to `unknown`/`-1` off-Jetson).
- **Tier-boundary detection** in `derive_findings.py` is heuristic: it uses the
  highest-reuse plateau curve as a residency proxy, finds where BW converges to
  within 10% of the measured DRAM peak (DRAM-bound boundary), and the largest single
  BW drop below that (L2 -> L2+SLC step). Sanity-check its output against
  `results/plots/bw_vs_footprint.png` before Phase 2 consumes `findings.json`.
