# Worklog — 2026-07-25 12:00 — phase2-reuse-overlay

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/02_two_kernel_size/
**State:** in-progress (implementation complete, not yet run — no CUDA/Jetson in this environment)

## Summary
Implemented the Phase 2 v2 add-on (`prompts/02_two_kernel_size/02_two_kernel_size_v2.md`): a
reuse_N in {1,2,4,8,16,32} sweep overlay for the two-concurrent-kernel harness, purely additive
on top of the existing (already hardware-verified) reuse=1 sweep. Not run on real hardware — this
is a macOS dev machine with no CUDA toolchain (`nvcc` not found).

## What I did
- `src/phase2_bench.cu`:
  - Added a `reuseN` parameter to `measureConcurrent()` (loops each stream's kernel launch
    `reuseN` times per timed trial, multiplies moved bytes by `reuseN`), mirroring Phase 4's
    reuse loop. All existing call sites pass `reuseN=1`, reproducing the exact prior
    behavior/values for the main sweep.
  - Factored the inline block-count search out of `main()` into a reusable `searchBlocks()`
    helper (now parameterized by `reuseN` too), so the reuse-overlay code can search at an
    arbitrary N without duplicating the two-1D-pass logic.
  - Added `runReuseSweep()` + an optional `--reuse-out <path>` CLI flag: when set, `main()`
    switches entirely to this mode (does **not** also write `--out`), searches block counts once
    at reuse_N=1, verifies stability at a second N (checkN=4, taking the element-wise max with a
    stderr `NOTE` if unstable), holds those blocks fixed across all six reuse_N values per cell,
    and writes `results/phase2_reuse_results.csv` (same columns as `phase2_results.csv` plus
    `reuse_N`). Correctness is sample-checked at the smallest/largest reuse_N per cell.
- `scripts/run_reuse_overlay.sh` (new): build if needed, lock clocks, run
  `phase2_bench --reuse-out ...`, then `plot_reuse.py` + `append_reuse_findings.py`, append
  `shared/env.md`. Reuses the existing `phase2_config.csv` (same size grid); does not re-run the
  main sweep or touch `run.sh`.
- `scripts/plot_reuse.py` (new): reads `phase2_reuse_results.csv` ->
  `results/plots/reuse_bw_vs_footprint.png`, two panels (symmetric vs combined footprint,
  asymmetric vs K1 size), one line per reuse_N, log2 x-axis with a `FuncFormatter` for
  human-readable K/M tick labels (not automatic under `set_xscale("log", base=2)`), DRAM-peak
  dotted reference line from Phase 1's `findings.json`.
- `scripts/append_reuse_findings.py` (new): computes a "collapse point" (smallest x beyond which
  the lowest/highest reuse_N aggregate GB/s agree within 5%) for both symmetric and asymmetric,
  and appends a "Reuse overlay" prose section to `FINDINGS.md`. Idempotent (replaces a
  previously-appended section by heading match rather than duplicating). Never touches
  `findings.json`.
- `README.md`: added a "v2 add-on: reuse-sweep overlay" section (new files, `--reuse-out` flag,
  ordering dependency between `derive_findings.py` and `append_reuse_findings.py`); corrected the
  stale "Not yet run on real hardware" Status section (the main sweep *has* been run — real
  numbers are in `findings.json`/`FINDINGS.md` per git history) and added an honest v2-specific
  status; updated the "Reuse: fixed at N=1" design note to point at the new add-on.
- Verified `scripts/plot_reuse.py` and `scripts/append_reuse_findings.py` end-to-end against
  synthetic CSV data (two scenarios: no-collapse and a clean collapse at a marked footprint), then
  **deleted the synthetic `phase2_reuse_results.csv` / plot and `git checkout`'d `FINDINGS.md`**
  before finishing — no fabricated numbers were left in the repo.

## Files created / modified
- `experiments/02_two_kernel_size/src/phase2_bench.cu` — modified (see above)
- `experiments/02_two_kernel_size/scripts/run_reuse_overlay.sh` — new
- `experiments/02_two_kernel_size/scripts/plot_reuse.py` — new
- `experiments/02_two_kernel_size/scripts/append_reuse_findings.py` — new
- `experiments/02_two_kernel_size/README.md` — modified (v2 add-on section, Status correction)

## Key decisions & rationale
- **`--reuse-out` is a fully separate code path in `main()`, not merged into the existing loop** —
  when set, it skips writing `--out` entirely rather than writing both files in one invocation.
  This makes it structurally impossible for the reuse-overlay run to ever clobber the frozen
  `phase2_results.csv` handoff, even if someone points `--out` at the real path by mistake.
- **Block search done twice (N=1, checkN=4), not once per reuse_N** — per the prompt's explicit
  cost concern ("verify stable at one extra N... so cost stays ~6x the reuse=1 run rather than 6x
  a fresh search per N"). Held blocks are the element-wise max on disagreement, never the min
  (avoids under-saturation), same pattern as Phase 4's `searchAndVerifyStable`.
- **`gen_config.py` untouched** — the v2 prompt says "config stays shared", and the existing size
  grid functions already produce exactly the sizes needed; no new script needed to generate the
  reuse sweep's cell list, it reads the same `phase2_config.csv`.
- **`append_reuse_findings.py` is a separate script from `derive_findings.py`, not a merge into
  it** — keeps `derive_findings.py` (part of the frozen reuse=1 pipeline) completely untouched, at
  the cost of an ordering dependency (documented in both the script's docstring and README) since
  `derive_findings.py` rewrites `FINDINGS.md` from scratch and would silently drop an
  already-appended section.
- **Collapse-point metric: smallest x where the lowest/highest reuse_N spread stays ≤5% for every
  larger x** — chosen over a single-point threshold check because (like Phase 2's
  `contention_onset`) real data need not cross the threshold monotonically; requiring it to *stay*
  below threshold for all larger sizes avoids picking a size that dips below 5% once and then
  diverges again.

## Results / findings produced
- None from real hardware — this environment cannot build/run CUDA. The synthetic-data trial runs
  used only to verify the two new Python scripts were deleted before finishing (see above).

## Upstream I consumed
- Read `prompts/02_two_kernel_size/02_two_kernel_size_v2.md`, the original
  `prompts/02_two_kernel_size/02_two_kernel_size.md`, `prompts/00_conventions.md`.
- Read the existing `experiments/02_two_kernel_size/src/phase2_bench.cu`,
  `scripts/gen_config.py`, `scripts/plot.py`, `scripts/derive_findings.py`, `scripts/run.sh`,
  `scripts/build.sh`, `README.md`, `FINDINGS.md`, `findings.json` (all already
  hardware-verified — the main sweep predates this session).
- Read Phase 4's reuse-loop implementation (`experiments/04_zero_copy/src/phase4_bench.cu`,
  `measureConcurrentCell` / `searchBlockSaturation` / `searchAndVerifyStable`) as the pattern to
  mirror, per the v2 prompt's explicit instruction.
- Read Phase 1's `scripts/plot.py` (`plot_bw_vs_footprint`) as the style reference for the new
  `reuse_bw_vs_footprint.png`.
- Read `experiments/01_single_kernel_size/findings.json` for `measured_dram_peak_GBps` (consumed
  read-only by `plot_reuse.py`, same as the existing `plot.py`/`gen_config.py` already do).

## Open questions / blockers
- **Blocked on Jetson hardware access.** `src/phase2_bench.cu`'s new `--reuse-out` path,
  `scripts/run_reuse_overlay.sh`, `scripts/plot_reuse.py`, and
  `scripts/append_reuse_findings.py` have not been compiled or run against real CUDA — only
  reviewed and (for the two Python scripts) exercised against synthetic CSV data.
- The C++ changes were checked for balanced braces/parens and careful manual review, but
  `nvcc` was not available anywhere in this environment to actually compile
  `src/phase2_bench.cu`.

## Handoff → next session
1. On the Jetson AGX Orin (with `results/phase2_config.csv` already present from the main sweep):
   `experiments/02_two_kernel_size/scripts/run_reuse_overlay.sh`.
2. Watch stderr for `NOTE: block saturation NOT stable across reuse_N` (search wasn't stable at
   checkN=4 — held blocks were the conservative max, but worth noting which cells triggered it)
   and `CORRECTNESS FAILURE (reuse overlay)`.
3. Sanity-check `results/plots/reuse_bw_vs_footprint.png` per the prompt's Verification section:
   at the largest combined/K1 footprint all reuse_N lines should coincide near DRAM peak; at a
   small cache-resident footprint the high-N lines should rise above DRAM peak. If a high-reuse
   line does **not** rise in the cache region, the reuse loop isn't actually re-reading the
   buffers — fix before trusting the plot.
4. Re-run `scripts/append_reuse_findings.py` any time `FINDINGS.md` gets regenerated by
   `derive_findings.py` afterward (see README's ordering note) — otherwise the "Reuse overlay"
   section silently disappears.
5. Confirm the two-kernel collapse point (in the appended `FINDINGS.md` section) sits at a
   smaller *per-kernel* footprint than Phase 1's single-kernel ~4 MB collapse, as expected from
   cache sharing between the two concurrent kernels — flag in `FINDINGS.md` if it doesn't.

Suggested commit message:
`Add Phase 2 v2 reuse-sweep overlay (--reuse-out, plot, findings appender)`
