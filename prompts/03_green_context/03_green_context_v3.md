# Work Prompt — Phase 3 (v3 patch): align size grid with Phase 2, power-of-2 axes, + reuse overlay

**Prerequisites:** read `../OVERVIEW.md`, `00_conventions.md`, and the prior
`prompts/03_green_context.md` and `prompts/03_green_context_v2.md` first. Standard phase layout,
worklog, and findings rules apply. **Scope: Phase 3 ONLY** (`experiments/03_green_context/`). Do
**not** touch Phase 4 or any other phase directory. This is a targeted patch on top of the
v2 run — keep everything v2 already does (in-context block saturation, findings schema, %smid
verification, anchors, discrepancy notes) **and keep every existing plot and the reuse=1
`findings.json`/CSV handoff intact**; change/add only the three things below.

> **Why this patch exists.** The v2 size sweep used a pure 1.8× geometric grid
> (`sweep.py`: `SWEEP_SIZE_LO=64KB`, `HI=8MB`, `ratio=1.8`), producing sizes like
> 65536, 117965, 212337, 382206, 687971, 1238347, ... These do **not** line up with
> Phase 2's size grid, so Phase 3's curves cannot be overlaid on Phase 2's on the same
> x positions (only the 3 anchors coincide). We want Phase 3 to reuse Phase 2's exact
> grid so that at every Phase 2 size we can directly compare single-kernel (Phase 1) vs
> concurrent-shared (Phase 2) vs green (Phase 3).

## Change 1 — Reuse Phase 2's size grid (Option A: Phase 2 grid + small-end extension)

Replace Phase 3's geometric size generation in `scripts/sweep.py` with Phase 2's grid, extended
only at the small end so the green-context L1/scheduling regime is still covered.

**Symmetric per-kernel sizes (MiB), where `MiB = 1024*1024`:**
Reuse Phase 2's exact list from `experiments/02_two_kernel_size/scripts/gen_config.py`
(`symmetric_sizes_bytes()`):
```
[0.125, 0.25, 0.5, 0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 3.0, 4.0, 6.0, 12.0, 24.0]
```
and **prepend** a small-end extension for the L1 regime:
```
[0.03125, 0.0625]   # 32 KiB, 64 KiB
```
→ final symmetric list = `[0.03125, 0.0625, 0.125, 0.25, 0.5, 0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 3.0, 4.0, 6.0, 12.0, 24.0]` × MiB.

**Asymmetric K1 sizes:** reuse Phase 2's approach from `asymmetric_k1_sizes_bytes(k)` — fractions of
the Phase-2 crossover `k` (= `asymmetric_k_used_bytes` from Phase 2 findings, 2 MiB), with the same
small-end extension:
```
fracs = [0.03125, 0.0625, 0.125, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
K1_bytes = sorted(set(int(f * k) for f in fracs if int(f*k) > 0))
K0 fixed at 1 MiB (unchanged).
```

**Requirements / guardrails:**
- Prefer literally importing/reusing Phase 2's functions so the two phases can never drift again
  (e.g. `from` the Phase 2 script, or copy the exact MiB lists with a comment pointing at
  `gen_config.py`). Do **not** re-derive with a different ratio.
- Keep the Phase 2 anchor points (786432, 917504 symmetric; 2097152 asymmetric) as labeled anchors.
  With this grid they now fall on exact grid points (0.75/0.875 MiB and k itself), so snapping is
  clean — verify each anchor still appears exactly once and `is_anchor=True`.
- Everything else in the cell plan (shared + SM-split sweep per size, in-context block saturation
  search, per-config plateau detection) stays exactly as v2.
- Regenerate `results/phase3_results.csv`, `findings.json`, `FINDINGS.md` from the new sweep.
- Note in `FINDINGS.md` that the v3 grid now matches Phase 2 (list the shared sizes) so the phases
  are directly overlayable; record that this supersedes the v2 geometric grid.

## Change 2 — Power-of-2 (log base 2) x-axis on size-axis plots

In `scripts/plot.py`, every plot whose x-axis is a byte size must use log base 2 with
power-of-2 tick labels (this is **not** automatic — matplotlib's `set_xscale("log")` defaults to
base 10).

Apply to `green_vs_shared.png` and `delta_vs_size.png` (both have a size x-axis). **Do not** change
`partition_sweep.png`'s main x-axis — that is a categorical SM-split axis (e.g. "8:8"), not a size.

For each size x-axis:
```python
import matplotlib.ticker as mticker

ax.set_xscale("log", base=2)
# tick at each swept size (or at power-of-2 backbone); label human-readable:
def _fmt_bytes(x, _pos):
    for unit, div in (("M", 1024*1024), ("K", 1024)):
        if x >= div:
            v = x / div
            return f"{v:.0f}{unit}" if v == int(v) else f"{v:.2f}{unit}"
    return f"{int(x)}"
ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_bytes))
ax.xaxis.set_minor_formatter(mticker.NullFormatter())
```
- Update axis labels from "(bytes, log)" to "(bytes, log2)".
- Keep the anchor star markers and everything else in those plots.

## Change 3 — Add a reuse-sweep overlay plot (new; existing reuse=1 sweep stays)

Currently Phase 3 runs at reuse N=1 only, so it can only see green context's scheduling/occupancy
isolation — **not** its predicted main benefit, stabilizing L1 **inter-launch** reuse (which only
exists at reuse N>1, per OVERVIEW §1). Add a reuse axis as a **separate, additive** experiment that
does not disturb the reuse=1 sweep, CSV, or `findings.json` handoff to Phase 4.

**What to add:**
- A reuse axis `reuse_N ∈ {1, 2, 4, 8, 16, 32}` — both kernels launched N times over the identical
  buffers (inter-launch, full-buffer reuse; same definition as Phase 1 and Phase 4). This requires
  adding a `--reuse-n` flag + an N-iteration launch loop to `phase3_bench` (mirror Phase 4's
  `phase4_bench` reuse loop) and multiplying moved-bytes by N in the throughput calc.
- **Bound the cost.** Do NOT run reuse over the full 18+11 size grid × 6 splits. Restrict the reuse
  overlay to a **small representative subset of sizes** (≈4–5): at minimum one L1/small point, both
  Phase 2 anchors (786432, 917504 symmetric), and one clearly DRAM-bound point (e.g. 4 MiB). For
  each subset size run **shared** and the **best-green split** that the reuse=1 v3 sweep already
  found for that size (read it back from this run's `findings.json`/CSV — do not re-sweep all
  splits). **Reuse the reuse=1 saturated block counts** (hold them fixed across reuse_N; verify
  stable at one extra N, like Phase 4) rather than re-searching per N.
- Write results to a **separate** CSV `results/phase3_reuse_results.csv` (with a `reuse_N` column).
  Leave `phase3_results.csv` and `findings.json` (the Phase 4 handoff) untouched — this overlay is
  diagnostic only.

**New plot — `results/plots/reuse_green_vs_shared.png`:**
- One panel per subset size. x-axis = `reuse_N` on **log base 2** (power-of-2 ticks: 1, 2, 4, …, 32);
  y-axis = aggregate GB/s. Two lines per panel: **shared** and **best-green**. Draw the measured
  DRAM-peak reference line (from Phase 1 findings) as a horizontal marker.
- Purpose: reveal whether green context's delta vs shared **improves with reuse** — i.e. whether at
  N>1 (where L1 inter-launch reuse exists) green starts to win at the small/L1 sizes, even though it
  lost at N=1. State the finding in `FINDINGS.md` as a new "Reuse overlay" section (prose only; do
  not alter the reuse=1 numbers or the Phase 4 configs).

## Verification
- `sweep.py --dry-run` should now print symmetric sizes matching the list above (18 sizes) and
  asymmetric K1 matching the Phase 2 fracs × k (plus the 2 small ones); confirm the 3 anchors are
  present and flagged.
- Open `green_vs_shared.png` and confirm x ticks read as powers of two (…, 256K, 512K, 1M, 2M, …)
  and that Phase 3's shared curve now sits at the **same x positions** as Phase 2's symmetric sizes.
- Re-confirm the Change-1 (v2) block-saturation sanity gate still passes (re-swept shared @ 917504
  ≥ Phase 2's 143.6 GB/s).
- `reuse_green_vs_shared.png`: at a large DRAM-bound size, both shared and green lines should be
  ~flat across reuse_N (nothing to reuse); at a small/L1 size, at least the shared line should rise
  with reuse_N (cache hits). If neither line moves anywhere, the reuse launch loop isn't re-reading
  the buffers — fix before trusting the overlay.

## Findings handoff
Regenerate `findings.json` (same schema as v2 — the widened `per_point`, `best_partition_ratios`
per mode×regime, `configs_for_phase4`, sanity gate) from the **reuse=1** sweep only; the reuse
overlay (Change 3) must **not** change `findings.json` or the Phase 4 handoff. Do **not** overwrite
Phase 1/2 findings. Add a "Reuse overlay" prose section to `FINDINGS.md` summarizing whether green's
delta improves with reuse. Write a new `worklog/YYYY-MM-DD-HHMM_phase3-v3-grid-align-reuse.md`, and
print a suggested one-line git commit message. Do not commit automatically.
