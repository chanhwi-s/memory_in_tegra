# Work Prompt — Unified size grid across Phases 1–3, plot cleanup, reuse=32 green/shared, overlap cell re-selection

> Read `../OVERVIEW.md` and `00_conventions.md` first, then the two most recent `../worklog/`
> entries. This prompt is **cross-phase** (it touches `experiments/01_*`, `02_*`, `03_*` and adds
> a new `shared/` module) — that is a deliberate, explicitly-authorized exception to the
> "a phase writes only inside its own directory" isolation rule in `00_conventions.md` §1.
> See Change 0 for exactly what that exception covers and what it does NOT.

---

## Why this exists

Three separate problems, all rooted in the size grids:

1. **The x-axes of Phases 1, 2 and 3 do not line up.** Phase 1 is a single kernel (read footprint
   = `2*S`); Phases 2/3 symmetric are two kernels (combined read footprint = `4*S`). The three
   phases also use three different `S` grids: Phase 1's is hardcoded in
   `experiments/01_single_kernel_size/src/phase1_bench.cu:204-208`, Phase 2's is
   `experiments/02_two_kernel_size/scripts/gen_config.py:symmetric_sizes_bytes()`, and Phase 3
   imports Phase 2's and prepends a small-end extension
   (`experiments/03_green_context/scripts/sweep.py:build_symmetric_sweep_sizes()`). So the
   combined-footprint plots added in the `*_combined_footprint.py` scripts cannot actually be
   overlaid point-for-point.

2. **The dense region of the grid is in the wrong place.** `symmetric_sizes_bytes()`'s docstring
   says it was densified "so 4*S lands near L2=4MB and L2+SLC=8MB" — i.e. around the *nominal*
   cache boundaries from `OVERVIEW.md` §0. But Phase 1 **measured** the effective boundary at a
   **2 MB read footprint** (`experiments/01_single_kernel_size/findings.json`:
   `tier_steps.slc_region_max_read_footprint_bytes = 2097152`), and the interesting structure —
   the symmetric local peak at combined footprint 2 MB (182.0 GB/s), the dip that follows, the
   climb back to the DRAM asymptote — all lives between 1 MB and 4 MB of combined footprint.
   The current grid puts only **5** points in that entire window.

3. **Plot/selection follow-ons** listed as Changes 3–6 below.

**Non-goal / do not touch:** the **asymmetric** size grids
(`gen_config.py:asymmetric_k1_sizes_bytes()` and
`sweep.py:build_asymmetric_k1_sizes()`) stay exactly as they are, in every phase. Only the
**symmetric** grid and Phase 1's single-kernel grid change. Changing the asymmetric grid would
invalidate the `asymmetric_k_used_bytes` handoff from Phase 2 and Phase 4's test points, which
are out of scope here.

---

## Change 0 — New single source of truth: `shared/size_grid.py`

Create `shared/size_grid.py`. It is a **read-only input** to every phase (unlike `shared/env.md`,
which is an append-only output). No phase may edit it as part of a normal run.

It defines the grid in terms of the physically meaningful axis — **combined read footprint `F`** —
and derives each phase's per-buffer size from it, so that a given `F` means the same amount of
cache pressure in every phase:

| phase | kernels | buffers read per kernel | read footprint | per-buffer size to use |
|---|---|---|---|---|
| 1 | 1 | A, B | `2*S` | `S = F/2` |
| 2 / 3 symmetric | 2 | A, B each | `4*S` | `S = F/4` |

Required API:

```python
MiB = 1024 * 1024

def combined_footprint_grid_bytes() -> list[int]:
    """Canonical x-axis: combined READ footprint F, in bytes. Coarse below 1MB
    (latency/L1 regime), 256KB-dense from 1MB to 4MB (brackets the measured 2MB
    effective cache boundary AND the nominal 4MB L2), coarse above."""

def symmetric_per_kernel_sizes_bytes() -> list[int]:   # F/4 -- phases 2 and 3
def phase1_sizes_bytes()             -> list[int]:     # see below -- phase 1
```

**Grid to implement** (24 `F` points; every `F` is a multiple of 128 KB, so `F/4` is always a
multiple of 32 KB and `F/2` a multiple of 64 KB — no rounding, no unaligned float buffers):

```
F below 1MB   (coarse): 0.125, 0.25, 0.5                                    MiB
F 1MB..4MB    (dense) : 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75,
                        3.0, 3.25, 3.5, 3.75, 4.0                           MiB
F above 4MB   (coarse): 5, 6, 8, 12, 16, 24, 48, 96                         MiB
```

This takes the 1–4 MB window from **5 points to 13**, and keeps the total symmetric point count
at 24 (vs 18 today) — a ~33% runtime increase on the symmetric sweeps, not a blow-up.

### `phase1_sizes_bytes()` — measure the union, not just `F/2`

Phase 1 must return **`sorted(set(F/2 for F) | set(F/4 for F))`** — 32 sizes. Reason: the two
halves serve two different consumers and both are needed.

- The `F/2` half is what makes Phase 1's own combined-footprint plot land on exactly the same `F`
  ticks as Phases 2/3 (this is the alignment the whole change is for).
- The `F/4` half makes Phase 1's `saturation_blocks_by_size` contain an **exact** entry for every
  per-kernel size Phases 2/3/4 will ask about. Today those lookups are *nearest-neighbor*
  (`experiments/04_zero_copy/scripts/gen_test_points.py:74`,
  `experiments/03_green_context/src/phase3_bench.cu:35`) — keep the nearest-neighbor code as the
  fallback, but with this union it will hit exact keys and stop silently approximating.

Phase 1 is single-kernel and cheap; 32 sizes is affordable.

Every phase that consumes this module must **echo the grid it used into its own `README.md`**
(provenance rule, `00_conventions.md` §2.2), and record `shared/size_grid.py` in the `consumed`
list of its `findings.json`.

---

## Change 1 — Phase 1 takes its sizes from the shared grid

`experiments/01_single_kernel_size/src/phase1_bench.cu` currently hardcodes `sizesBytes` at lines
204–208. Replace that with a CLI-driven list:

- Add a `--sizes <comma-separated bytes>` argument to `phase1_bench`. When absent, keep the
  current hardcoded list as a fallback so the binary is still runnable standalone (and print a
  warning to stderr that it is not using the shared grid).
- Add `experiments/01_single_kernel_size/scripts/gen_sizes.py` (or extend `run.sh` directly —
  your call, but keep it a one-liner that is obvious in the run log) which imports
  `shared/size_grid.py` and passes `phase1_sizes_bytes()` to the binary via `--sizes`.
- `scripts/run.sh` must use that path by default.

Do not change Phase 1's block-count sweep, its byte accounting, or its tier-step derivation logic.

## Change 2 — Phases 2 and 3 take their symmetric sizes from the shared grid

- `experiments/02_two_kernel_size/scripts/gen_config.py`: `symmetric_sizes_bytes()` becomes a thin
  wrapper that returns `shared/size_grid.py :: symmetric_per_kernel_sizes_bytes()`. Update its
  docstring — the current one describes the old "densified near 4MB and 8MB" rationale, which is
  now wrong and actively misleading. `asymmetric_k1_sizes_bytes()` is **unchanged**.
- `experiments/03_green_context/scripts/sweep.py`: `build_symmetric_sweep_sizes()` keeps importing
  from Phase 2 (that indirection already exists and works — do not duplicate the grid), but the
  hand-maintained `SMALL_END_SYMMETRIC_MIB` extension must be **removed**: the new grid already
  starts at `F = 128 KB` (`S = 32 KB`), which is the small end that extension was adding.
  Removing it is what makes Phase 2 and Phase 3 symmetric grids *identical* rather than
  "Phase 3 ⊃ Phase 2". `build_asymmetric_k1_sizes()` and `SMALL_END_ASYMMETRIC_K1_FRACS` are
  **unchanged**.

After this change, `assert phase2_sym_grid == phase3_sym_grid` must hold — add that as a real
assertion in Phase 3's sweep, not just a comment.

## Change 3 — Reuse-overlay plot label must show combined footprint

`experiments/03_green_context/scripts/plot.py:266` currently labels each panel:

```python
ax.set_xlabel(f"reuse_N (log2) -- {tp} ({_fmt_bytes(int(tp_size[tp]), None)}/kernel)")
```

`tp_size` is `k0_bytes`, i.e. the size of **one buffer of one kernel** — which reads as if it were
the working set and is off by 4× from the actual cache pressure. Change the label so both numbers
are visible, e.g.:

```
reuse_N (log2) -- reuse_sym_917504 (896.0 KB/kernel, combined read 3.50 MB)
```

Compute combined read footprint as `2*k0_bytes + 2*k1_bytes` — **reuse the existing column**
`combined_read_footprint_bytes` where the CSV has it (that is how
`experiments/02_two_kernel_size/scripts/plot_combined_footprint.py` does it) and only fall back to
recomputing it if the column is absent. Apply the same treatment to the panel `title`.

## Change 4 — Drop the per-kernel-size green-vs-shared plot

Delete `experiments/03_green_context/results/plots/green_vs_shared.png` and the code path in
`scripts/plot.py` that generates it. `green_vs_shared_combined_footprint.png` (from
`scripts/plot_combined_footprint.py`) is the only green-vs-shared figure that should remain, so
there is exactly one x-axis convention in the phase's output.

Keep `delta_vs_size.png` and `partition_sweep.png` as they are.

> **Explicitly lifting a prior restriction:** several files in this phase (e.g. the docstring of
> `scripts/run_overlap_nsys.py`, and `prompts/03_green_context/03_combined_footprint_plot.md`)
> state that `scripts/plot.py` is off-limits / additive-only. **That restriction is lifted for
> Changes 3 and 4 of this prompt.** Update those stale comments where you touch them so the next
> session is not misled.

## Change 5 — `green_vs_shared_combined_footprint.png` must be measured at reuse_N = 32

Today that figure is drawn from the `reuse_N = 1` main sweep (`results/phase3_results.csv`).
Redraw it from a **full-grid sweep at `reuse_N = 32`** instead.

This is a **measurement change, not just a plot change** — `results/phase3_reuse_results.csv`
currently holds only 4 test points (32768 / 917504 / 1048576 / 4194304) × 6 values of N. You need
green-vs-shared at N=32 across the whole symmetric grid.

Implementation notes:

- Extend `experiments/03_green_context/scripts/sweep_reuse.py` (or add a sibling script) so it can
  sweep the **full symmetric grid at a single fixed N**, and run it with `N = 32`.
- **Cost control — do not sweep every SM split at N=32.** Each cell does 32× the work of the
  N=1 sweep. Run only `shared` plus the single best-performing green split. Take that split from
  the existing N=1 result for the same test point (`results/phase3_results.csv`, the
  `max agg_GBps_median` green row — the same selection `plot.py` already uses), rather than
  re-searching it. Record in the phase README that the N=32 figure uses the N=1-optimal split, so
  it is a *conditional* comparison and is labelled as such on the figure.
- Hold block counts fixed across N, exactly as the existing reuse overlay does (`--fixed-blocks0/1`).
- Write to a clearly separate CSV (e.g. `results/phase3_reuse32_results.csv`); do **not**
  overwrite `phase3_results.csv` or `phase3_reuse_results.csv`.
- Keep the N=1 data — the phase should be able to show both. If you keep a reuse=1 version of the
  figure, name it unambiguously (`..._combined_footprint_n1.png` vs `..._combined_footprint_n32.png`).

Rationale to record in `FINDINGS.md`: at N=1 the aggregate curve is dominated by cold-miss DRAM
traffic and green loses at every point; the mechanism green is supposed to exploit (stabilized
inter-launch L1 residency) only exists when there *is* inter-launch reuse. N=32 is where the
existing 4-point overlay shows green's only win (+33.5% at `sym_32768`) and its worst loss
(−26.0% at `sym_917504`), so the full-grid N=32 curve is the figure that actually maps green's
useful range.

## Change 6 — nsys overlap: select the cache-bound local peak and its two neighbours

`experiments/03_green_context/scripts/run_overlap_nsys.py:96`
(`select_peak_bandwidth_test_points`) currently picks, per mode, the test point with the global
max `agg_GBps_median`. For the **symmetric** sweep that is broken: after the dip, aggregate
bandwidth rises monotonically toward the DRAM asymptote, so the global max is always simply the
**largest size in the grid** (today `sym_25165824`, 24 MB/kernel) — a point whose green delta is
−1.0%, the least informative cell in the entire phase. It is also fragile: the cache-region local
peak (182.0 GB/s) and the DRAM asymptote (189.3 GB/s) are only 4% apart, so re-measurement noise
can flip which one wins.

Replace it with:

1. Take the `shared` rows only (the current code takes the max over *all* configs including
   `green`, which lets a green row decide the selection — remove that).
2. Sort by swept size ascending.
3. Find the **first local maximum**: the smallest index `i` with `agg[i] > agg[i-1]` and
   `agg[i] > agg[i+1]`. That is the cache-bound peak. (Sanity check on today's data: symmetric →
   `S = 0.5 MB`, 182.0 GB/s, combined footprint 2 MB, exactly the measured cache boundary;
   asymmetric → `asym_131072`, 212.9 GB/s. Both correct.)
4. Select test points `{i-1, i, i+1}` — the peak plus one neighbour on each side. Clamp at the
   grid ends and warn if clamping occurred.
5. If no local maximum exists, fall back to the current global-argmax behaviour and print a loud
   `WARNING` saying the fallback was used.

Within each selected test point keep the existing per-cell selection (the `shared` row + the
`green` row with max `agg_GBps_median`). Result: 3 test points × 2 configs × 2 modes = **12 cells**
instead of 4.

This also finally makes `results/plots/overlap_ratio_vs_footprint_combined_footprint.png` a real
curve — with 2 points it could never be one.

Also, while in this file: `profile_cell()` records an empty-metrics row for **two different**
failures (nsys timeout, and `parse_nsys_csv` raising) but the CSV cannot distinguish them, which
is why `overlap_nsys_table.md` says `N/A (timeout/parse failure)`. Add a `failure_reason` column
(empty on success, else `timeout` / `parse_error: <message>`), and surface it in the table.

---

## Verification (do all of these before writing the worklog)

1. `python3 -c "import sys; sys.path.insert(0,'shared'); import size_grid; print(len(size_grid.combined_footprint_grid_bytes()))"` → 24; `phase1_sizes_bytes()` → 32.
2. Assert every `F` is divisible by 4 and by 131072, and that no derived per-buffer size is 0 or
   unaligned to 4 bytes.
3. Assert Phase 2's and Phase 3's symmetric grids are element-wise identical.
4. `python3 experiments/03_green_context/scripts/sweep.py --dry-run` and the Phase 1/2 equivalents:
   confirm the planned cell counts and that the **asymmetric** rows are byte-for-byte what they
   were before this change (diff them against the current `results/*.csv` size columns).
5. `python3 experiments/03_green_context/scripts/run_overlap_nsys.py --dry-run` → 12 cells,
   3 test points per mode, peak in the middle of each triple.
6. Regenerate all plots from the **existing** CSVs first (before any re-measurement) to confirm
   the plot code changes (3, 4) don't crash on current data; `green_vs_shared.png` must be gone.
7. Re-run the sweeps on the Jetson (clocks locked — `sudo nvpmodel -m 0 && sudo jetson_clocks`),
   in order: `01 → 02 → 03`. Phase 4 is **out of scope** for this prompt and is separately known
   broken (see `worklog/2026-07-27-1015_HANDOFF.md` §4 and the newer timing-harness finding); do
   not attempt to fix it here, but do note in the worklog that Phase 4's test points derive from
   Phase 2's asymmetric grid, which this change deliberately leaves untouched, so Phase 4 is not
   invalidated by it.

## Findings handoff

- Phase 1's `findings.json` will now carry ~32 `saturation_blocks_by_size` entries and a
  re-derived `tier_steps`. **The measured tier boundaries may move** now that the 1–4 MB region is
  densely sampled — that is a legitimate result, not an error. If they do move, say so explicitly
  in `experiments/01_single_kernel_size/FINDINGS.md` and flag it for `OVERVIEW.md` §0, which still
  documents the *nominal* 4 MB / 8 MB tiers. Do not edit `OVERVIEW.md` yourself.
- Each phase adds `shared/size_grid.py` to the `consumed` list in its `findings.json` and echoes
  the grid into its `README.md`.
- Record in each phase's `FINDINGS.md` that the symmetric x-axis is now the shared combined-read-
  footprint grid, and that the asymmetric grid is unchanged and therefore still not comparable
  point-for-point across phases.

## Session close (`00_conventions.md` §5)

Write a new `worklog/YYYY-MM-DD-HHMM_unified-size-grid.md` from `worklog/_TEMPLATE.md` covering:
what ran on hardware vs. what is code-only, whether the tier steps moved, the new overlap cell
list, and the reuse=32 figure's "N=1-optimal split" caveat. Print a suggested one-line commit
message; do not commit automatically.
