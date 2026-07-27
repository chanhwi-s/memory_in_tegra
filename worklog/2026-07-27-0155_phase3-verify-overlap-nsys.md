# Worklog — 2026-07-27 01:55 — phase3-verify-overlap-nsys

**Session/agent:** Claude Code
**Phase / directory worked on:** experiments/03_green_context/ (additive; one pure-extract
edit to scripts/sweep.py)
**State:** completed (implementation + logic validated via mocks; needs a real on-device
run with nsys to produce actual numbers)

## Summary
Implemented `prompts/03_green_context/03_verify_overlap_nsys.md`: a new nsys-based
verification pass that confirms, on the real execution timeline, that Phase 3's two
kernels genuinely run concurrently in both `shared` and `green` configs, for every cell
the throughput sweep measures. This replaces the `wall < serial_sum` heuristic (which
can't distinguish "overlapped" from "bandwidth-shared but serialized") with a real
timeline-derived `overlap_ratio` metric.

## What I did
- **Minimal refactor of `scripts/sweep.py`**: extracted `build_binary_args(cell, trials)`
  out of `run_cell()` (pure extraction, zero behavior change -- verified `sweep.py
  --dry-run` still plans the identical 149 cells afterward). This lets the new nsys
  script import and reuse the EXACT same CLI-argument construction, per the prompt's
  explicit instruction ("reuse exactly the argument construction from sweep.py").
- **`scripts/parse_nsys_sqlite.py`** (the "small parser"): `compute_overlap(sqlite_path)`
  runs a sweep-line over `CUPTI_ACTIVITY_KIND_KERNEL` `start`/`end` intervals to compute
  `union_busy_time` (>=1 kernel running), `concurrent_time` (>=2 kernels running), and
  `overlap_ratio`. Name resolution (filtering to `addKernel` launches, excluding the
  one-time `fillKernel` init) is best-effort against nsys's `StringIds`-joined schema,
  with a documented fallback to all-intervals if that schema variant isn't present.
  **Validated the interval-overlap math against hand-built synthetic sqlite fixtures**
  (no real nsys trace available on this dev machine): a 4-interval case with known
  union=250/concurrent=80/ratio=0.32, run through both the name-resolved-and-filtered
  path (confirmed the decoy `fillKernel` interval gets excluded) and the no-`StringIds`
  fallback path. Both passed exactly.
- **`scripts/run_overlap_nsys.py`**: orchestrator. Imports `sweep.build_plan` +
  `sweep.build_binary_args` (never re-derives the cell list). Per cell: `nsys profile -t
  cuda --force-overwrite=true -o <tmp>/cell <phase3_bench args>`, `nsys export
  --type=sqlite --force-overwrite=true <tmp>/cell.nsys-rep`, `compute_overlap()` on the
  result, then deletes both the `.nsys-rep` and `.sqlite` immediately (disk hygiene, per
  prompt). Recovers env fields (gpu_clock_mhz/power_mode/soc_temp_c/cuda_version/
  driver_version) and k0/k1 bytes by parsing the traced binary's own passthrough stdout
  (it still prints its normal CSV row under nsys) rather than re-querying the
  environment. rc=4 (invalid SM ratio) is skipped with a warning, same convention as
  `sweep.py`; any other nonzero rc is also treated as skip-with-warning rather than
  aborting the whole run (deliberate deviation from `sweep.py`'s fail-fast policy --
  justified because this is a verification-only pass over ~149 x 2 nsys-traced
  invocations, and losing all progress to one bad cell would be expensive to re-run).
  **Validated the full orchestration** (`profile_cell()`) by monkeypatching
  `subprocess.run` to fake `nsys profile`/`nsys export` (writing a real synthetic sqlite
  via Python's stdlib `sqlite3`) -- confirmed correct CLI construction (matches the
  prompt's literal `nsys` invocation), correct combined-footprint math, correct
  overlap_ratio pass-through, correct env-field extraction, and that both temp files are
  actually deleted afterward.
- **`scripts/verify_overlap_nsys.sh`**: entry point -- checks `nsys` is on PATH, rebuilds
  the binary if stale (same guard as `scripts/run.sh`), locks clocks, runs
  `run_overlap_nsys.py`, then `plot_overlap_nsys.py`. Supports `--dry-run` (skips the
  nsys-availability/clock-lock/build steps, just previews the cell list).
- **`scripts/plot_overlap_nsys.py`**: `overlap_ratio` vs combined read footprint (MB,
  log2), shared vs green (green summarized as the mean over that test point's SM-split
  cells -- concurrency isn't expected to vary much by split, unlike throughput), with a
  reference line at `overlap_ratio = 1`. Reuses the log2/MB axis formatter from
  `scripts/plot_combined_footprint.py` via direct import (not duplicated) for visual
  consistency within the phase. Smoke-tested against a synthetic `overlap_nsys.csv`
  (deleted afterward, along with its output PNG, so no fake data was left in the repo).

## Files created / modified
- `experiments/03_green_context/scripts/sweep.py` — extracted `build_binary_args()`
  (behavior-preserving; confirmed via `--dry-run`)
- `experiments/03_green_context/scripts/parse_nsys_sqlite.py` — new
- `experiments/03_green_context/scripts/run_overlap_nsys.py` — new
- `experiments/03_green_context/scripts/verify_overlap_nsys.sh` — new
- `experiments/03_green_context/scripts/plot_overlap_nsys.py` — new

Confirmed via `git status`/`git diff --stat` that `scripts/plot.py`, `findings.json`,
`results/phase3_results.csv`, and `results/phase3_reuse_results.csv` are untouched
(prompt's additive-only constraint).

## Key decisions & rationale
- Refactored `sweep.py` (extract-only) rather than duplicating its ~12-line argument
  list in the new script, because the prompt explicitly warns duplication risks drift
  between the throughput sweep and the verification sweep -- "reuse exactly."
- Treated non-rc-4 nsys/profile failures as skip-with-warning, not fatal, unlike
  `sweep.py`'s stricter policy -- see rationale above (expensive re-run cost for a
  diagnostic-only pass).
- `reuse_N` is hardcoded to `1` in the output CSV (not read from anywhere) because
  `sweep.py`'s cells never pass `--reuse-n`, so `phase3_bench`'s default (reuseN=1)
  is what every profiled cell actually runs -- this is the real parameter, not a guess.
- Assumed `nsys export --type=sqlite <rep>.nsys-rep` (no explicit `-o`) names its output
  `<rep-basename>.sqlite` -- this is nsys's documented default and matches the prompt's
  literal example commands, but is unverified against a real nsys binary (none available
  in this environment). Flagged for on-device confirmation below.

## Results / findings produced
None yet (no `results/overlap_nsys.csv` or plot committed) -- correctly, since nothing
was run against real hardware/nsys. All validation in this session used synthetic
sqlite fixtures and mocked subprocess calls to check the Python logic in isolation.

## Upstream I consumed
- `prompts/03_green_context/03_verify_overlap_nsys.md`, `worklog/2026-07-27-1015_HANDOFF.md`,
  `OVERVIEW.md`, `prompts/00_conventions.md`.
- `experiments/03_green_context/scripts/sweep.py` (read + minimally refactored) and
  `phase3_bench.cu`'s current CLI (`--blocks0-seed`/`--blocks1-seed`/`--reuse-n`/etc.,
  grepped directly) to make sure the reused argument construction matches what the
  binary actually accepts today (post v3).

## Open questions / blockers
- **Not run on real hardware.** This is a Windows dev machine with no CUDA toolchain and
  no `nsys` binary, so nothing here has touched a real trace. Before trusting output:
  1. Confirm `nsys export --type=sqlite --force-overwrite=true <rep>.nsys-rep` really
     produces `<rep-basename>.sqlite` with no `-o` flag (assumed from the prompt's literal
     command; if the installed nsys version differs, adjust `run_overlap_nsys.py`'s
     `sqlite_path` derivation).
  2. Confirm the installed nsys's sqlite schema actually has a `StringIds`-joinable name
     column matching one of `shortName`/`demangledName`/`mangledName` on
     `CUPTI_ACTIVITY_KIND_KERNEL`; if not, `parse_nsys_sqlite.py` will fall back to
     unfiltered intervals and print a NOTE per cell (still correct, per the docstring's
     "negligible fillKernel bias" reasoning, just less precise).
  3. A full run profiles ~149 cells x (1 shared + several green splits each) under nsys --
     expect this to take considerably longer than the untraced sweep; consider a
     `--dry-run` review of cell count first, and maybe a smaller pilot subset if nsys
     overhead per cell turns out to be large.

## Handoff → next session
1. On the Jetson: `experiments/03_green_context/scripts/verify_overlap_nsys.sh
   --dry-run` to confirm the planned cell count, then without `--dry-run` for the real
   run (needs `nsys` on PATH -- part of the JetPack/CUDA install; `which nsys` first).
2. If step 1 above surfaces a schema/export-naming mismatch, fix it in
   `parse_nsys_sqlite.py` / `run_overlap_nsys.py` and re-run; the interval-overlap math
   itself is validated and should not need to change.
3. Per the prompt's Interpretation section: check whether green's `overlap_ratio` stays
   ~1 across all sizes (would pin Phase 3's "green helps only with L1 + reuse" finding,
   §2.4 of the handoff, on shared-bandwidth contention rather than a concurrency/
   scheduling failure) -- write that interpretation into a follow-up worklog entry
   (not into `findings.json`, per the prompt: this is a worklog-only note, not a
   findings.json rewrite).

## Suggested commit message
```
feat(phase3): add nsys-based concurrent-overlap verification (additive)

Adds scripts/verify_overlap_nsys.sh + run_overlap_nsys.py + parse_nsys_sqlite.py
+ plot_overlap_nsys.py, profiling every Phase 3 sweep cell under nsys to compute
a real timeline-derived overlap_ratio (concurrent_time / union_busy_time),
replacing the wall<serial_sum heuristic. Verification-only: writes new
results/overlap_nsys.csv + a new plot, does not touch existing CSVs/findings/plot.py.
Extracts sweep.py's build_binary_args() (behavior-preserving) so both scripts
share one argument-construction path.
```
