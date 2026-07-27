#!/usr/bin/env python3
"""Parse an nsys sqlite export (`nsys export --type=sqlite ...nsys-rep`) and
compute the label-free concurrent-overlap metric for Phase 3's nsys
verification (prompts/03_green_context/03_verify_overlap_nsys.md):

    union_busy_time  = total time during which >= 1 kernel is executing
    concurrent_time  = total time during which >= 2 kernels execute simultaneously
    overlap_ratio    = concurrent_time / union_busy_time

overlap_ratio == 1 means the GPU was never busy with only one kernel running --
i.e. whenever anything executed, both kernels were running together. This is a
time-weighted average over the WHOLE traced run (every launch pair across
warm-up + in-context block search + timed trials), so no per-launch K0-vs-K1
labeling is needed -- exactly the "average aggregation" the prompt asks for.

Standalone use (debug a single trace):
    python3 parse_nsys_sqlite.py <path-to-export>.sqlite
prints the computed metrics as JSON to stdout.

Schema note: nsys's sqlite export schema has shifted across versions. The
`start`/`end` INTEGER-nanosecond columns on CUPTI_ACTIVITY_KIND_KERNEL have
been stable across the CUDA 12/13 toolkits this project targets, so those are
used unconditionally. The kernel-NAME column is not: some nsys versions store
it as a `shortName`/`demangledName` id into a `StringIds` table, others don't
export a resolvable name at all. Name resolution is therefore best-effort: if
it works, intervals are filtered to `addKernel` launches (excluding the
one-time fillKernel init and, in --verify runs, smidProbeKernel); if it
doesn't, every kernel interval in the trace is used and a warning is printed
by the caller (the one-time fillKernel call is a negligible fraction of
union_busy_time for any cell with >= 10 timed trials, so this fallback does
not meaningfully bias overlap_ratio).
"""
import json
import sqlite3
import sys


def _resolve_kernel_name_expr(cur):
    """Return (select_expr, join_clause) to resolve each kernel row's name as
    text via a StringIds-style lookup table, or (None, None) if no known
    schema matches (caller falls back to using all intervals)."""
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "StringIds" not in tables:
        return None, None
    cols = {r[1] for r in cur.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")}
    for name_col in ("shortName", "demangledName", "mangledName"):
        if name_col in cols:
            return f"k.{name_col}", f"JOIN StringIds s ON s.id = k.{name_col}"
    return None, None


def _load_intervals(sqlite_path, name_filter):
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()

    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "CUPTI_ACTIVITY_KIND_KERNEL" not in tables:
        con.close()
        raise RuntimeError(f"{sqlite_path}: no CUPTI_ACTIVITY_KIND_KERNEL table -- is this an "
                            f"`nsys export --type=sqlite` export of a `-t cuda` trace?")

    intervals = []
    name_filtered = False
    name_expr, join_clause = _resolve_kernel_name_expr(cur)
    if name_expr and join_clause:
        try:
            rows = cur.execute(
                f"SELECT k.start, k.end, s.value FROM CUPTI_ACTIVITY_KIND_KERNEL k {join_clause}"
            ).fetchall()
            named = [(s, e) for s, e, nm in rows if nm and name_filter in nm]
            if named:
                intervals = named
                name_filtered = True
        except sqlite3.OperationalError:
            pass  # unresolvable schema variant -- fall through to the unfiltered query below

    if not intervals:
        rows = cur.execute("SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL").fetchall()
        intervals = [(s, e) for s, e in rows]

    con.close()
    return intervals, name_filtered


def compute_overlap(sqlite_path, name_filter="addKernel"):
    """Returns a dict: kernel_instances, union_busy_ms, concurrent_ms,
    overlap_ratio, name_filtered (whether addKernel-name filtering succeeded,
    for transparency)."""
    intervals, name_filtered = _load_intervals(sqlite_path, name_filter)

    if not intervals:
        return {
            "kernel_instances": 0, "union_busy_ms": 0.0, "concurrent_ms": 0.0,
            "overlap_ratio": 0.0, "name_filtered": name_filtered,
        }

    # Sweep-line over start(+1)/end(-1) events: at every point in time, `depth`
    # is the number of kernels currently executing. Accumulate the time spent
    # at depth >= 1 (union_busy) and depth >= 2 (concurrent) between events.
    events = []
    for s, e in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort()  # ties: -1 sorts before +1, so back-to-back touches don't over-count

    union_ns = 0
    concurrent_ns = 0
    depth = 0
    prev_t = events[0][0]
    for t, delta in events:
        dt = t - prev_t
        if dt > 0:
            if depth >= 1:
                union_ns += dt
            if depth >= 2:
                concurrent_ns += dt
        depth += delta
        prev_t = t

    union_ms = union_ns / 1e6
    concurrent_ms = concurrent_ns / 1e6
    overlap_ratio = (concurrent_ms / union_ms) if union_ms > 0 else 0.0

    return {
        "kernel_instances": len(intervals),
        "union_busy_ms": union_ms,
        "concurrent_ms": concurrent_ms,
        "overlap_ratio": overlap_ratio,
        "name_filtered": name_filtered,
    }


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <nsys-export>.sqlite")
    print(json.dumps(compute_overlap(sys.argv[1]), indent=2))


if __name__ == "__main__":
    main()
