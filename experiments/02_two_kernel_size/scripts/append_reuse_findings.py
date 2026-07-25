#!/usr/bin/env python3
"""v2 add-on (prompts/02_two_kernel_size_v2.md): append a "Reuse overlay" prose section to
FINDINGS.md, computed from results/phase2_reuse_results.csv. Never touches findings.json --
the reuse=1 machine handoff to Phases 3/4 stays frozen.

Idempotent: re-running replaces a previously appended section (identified by the
`## Reuse overlay` heading) rather than duplicating it.

Ordering note: scripts/derive_findings.py (the main, reuse=1 pipeline) rewrites FINDINGS.md
from scratch every time it runs, which would silently drop this section. Always run this
script *after* derive_findings.py in any given session -- scripts/run_reuse_overlay.sh already
does this in the right order; only a concern if you invoke the two pipelines manually out of
order.
"""
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PHASE_DIR, "results", "phase2_reuse_results.csv")
FINDINGS_MD_PATH = os.path.join(PHASE_DIR, "FINDINGS.md")

SECTION_HEADING = "## Reuse overlay"
COLLAPSE_THRESHOLD = 0.05  # relative spread between lowest/highest reuse_N agg_GBps


def find_collapse_point(df, x_col):
    """Smallest x (in x_col) beyond which the aggregate-GB/s spread between the lowest and
    highest measured reuse_N stays within COLLAPSE_THRESHOLD for every larger x -- i.e. where
    the reuse lines have visibly merged onto one curve (DRAM-bound, no more cache benefit).
    Returns (collapse_x, spread_series) ; collapse_x is None if never observed in range."""
    reuse_ns = sorted(df.reuse_N.unique())
    lo, hi = reuse_ns[0], reuse_ns[-1]
    pivot = df.pivot_table(index=x_col, values="agg_GBps_median", columns="reuse_N")
    pivot = pivot.sort_index()
    if lo not in pivot.columns or hi not in pivot.columns:
        return None, None
    spread = (pivot[hi] - pivot[lo]) / pivot[lo]
    xs = spread.index.tolist()
    for i, x in enumerate(xs):
        if (spread.iloc[i:] <= COLLAPSE_THRESHOLD).all():
            return x, spread
    return None, spread


def fmt_bytes(n):
    n = float(n)
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n:.0f} B"


def describe(df, x_col, label):
    if df.empty:
        return f"No {label} rows in `phase2_reuse_results.csv`."
    collapse_x, spread = find_collapse_point(df, x_col)
    reuse_ns = sorted(int(n) for n in df.reuse_N.unique())
    hi = reuse_ns[-1]
    lo = reuse_ns[0]
    lines = [
        f"- **{label} reuse_N values swept:** {reuse_ns}",
    ]
    if collapse_x is not None:
        lines.append(
            f"- **Collapse point:** at/above {fmt_bytes(collapse_x)}, reuse N={lo} and N={hi} "
            f"aggregate GB/s agree within {COLLAPSE_THRESHOLD * 100:.0f}% (no further reuse "
            f"benefit -- DRAM-bound)."
        )
    else:
        lines.append(
            f"- **Collapse point:** not reached within the measured range -- reuse N={lo} and "
            f"N={hi} still differ by more than {COLLAPSE_THRESHOLD * 100:.0f}% at the largest "
            f"tested size. Consider extending the sweep."
        )
    max_x = df[x_col].max()
    at_max = df[df[x_col] == max_x]
    if not at_max.empty and collapse_x is not None:
        row_hi = at_max[at_max.reuse_N == hi]
        if not row_hi.empty:
            lines.append(
                f"- At the largest tested size ({fmt_bytes(max_x)}): reuse N={hi} aggregate = "
                f"{row_hi.iloc[0].agg_GBps_median:.1f} GB/s."
            )
    min_x = df[x_col].min()
    at_min = df[df[x_col] == min_x]
    row_hi_min = at_min[at_min.reuse_N == hi]
    row_lo_min = at_min[at_min.reuse_N == lo]
    if not row_hi_min.empty and not row_lo_min.empty:
        lift_pct = (row_hi_min.iloc[0].agg_GBps_median / row_lo_min.iloc[0].agg_GBps_median - 1) * 100
        lines.append(
            f"- At the smallest tested size ({fmt_bytes(min_x)}): reuse N={hi} aggregate = "
            f"{row_hi_min.iloc[0].agg_GBps_median:.1f} GB/s vs N={lo} = "
            f"{row_lo_min.iloc[0].agg_GBps_median:.1f} GB/s ({lift_pct:+.0f}% from reuse)."
        )
    return "\n".join(lines)


def build_section(df):
    sym = df[df["mode"] == "symmetric"].copy()
    asym = df[df["mode"] == "asymmetric"].copy()

    return f"""{SECTION_HEADING}

Two-kernel analog of Phase 1's `bw_vs_footprint.png` (see `results/plots/
reuse_bw_vs_footprint.png`), computed from `results/phase2_reuse_results.csv`
(`scripts/append_reuse_findings.py`; not part of the frozen `findings.json` handoff --
diagnostic only).

### Symmetric

{describe(sym, "combined_read_footprint_bytes", "Symmetric")}

### Asymmetric

{describe(asym, "k1_bytes", "Asymmetric")}

### Reading the plot

In the cache-resident region (small combined footprint), higher `reuse_N` lifts the aggregate
above the measured DRAM peak (cache hits on the re-read buffers). Once the combined footprint
overflows the effective cache, all `reuse_N` lines collapse onto the DRAM peak line -- reuse
stops helping because every kernel launch has to re-fetch from DRAM regardless of how many times
the same buffer is reused. Compare the collapse point above against Phase 1's single-kernel
collapse (~4 MB read footprint, per Phase 1's `findings.json` /
`reuse_crossover_note`) -- with two kernels sharing the cache concurrently, the collapse is
expected at a smaller *per-kernel* footprint than Phase 1's single-kernel number, since the
effective cache available to each kernel is reduced by the other kernel's concurrent footprint.
"""


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV not found: {CSV_PATH} (run scripts/run_reuse_overlay.sh first)")
    df = pd.read_csv(CSV_PATH)

    section = build_section(df)

    if os.path.exists(FINDINGS_MD_PATH):
        with open(FINDINGS_MD_PATH, encoding="utf-8") as f:
            existing = f.read()
    else:
        existing = ""

    if SECTION_HEADING in existing:
        head, _, rest = existing.partition(SECTION_HEADING)
        # Drop the stale section (from the heading up to the next top-level heading, if any).
        remainder = rest.split("\n## ", 1)
        tail = ("\n## " + remainder[1]) if len(remainder) > 1 else ""
        new_content = head.rstrip() + "\n\n" + section.strip() + "\n" + tail
    elif existing:
        new_content = existing.rstrip("\n") + "\n\n" + section.strip() + "\n"
    else:
        new_content = section

    with open(FINDINGS_MD_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"updated {FINDINGS_MD_PATH} with '{SECTION_HEADING}' section")


if __name__ == "__main__":
    main()
