#!/usr/bin/env python3
"""Parse the raw `ncu --csv --page raw` output written by scripts/profile_l2.sh into
results/l2_profile.csv: one row per (test_point_id, path) with the mean L2 hit-rate
percentage across all captured kernel launches.

Nsight Compute's raw-page CSV column names have varied across versions (quoted metric
name vs "Metric Name"/"Metric Value" long form); this parser tries both shapes and fails
loudly (rather than fabricating a number) if it can't find the metric.
"""
import csv
import glob
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PHASE_DIR, "results", "l2_raw")
OUT_CSV = os.path.join(PHASE_DIR, "results", "l2_profile.csv")

METRIC = "lts__t_sector_hit_rate.pct"


def extract_values_wide(rows, header):
    """Wide form: one column per metric, e.g. header contains 'lts__t_sector_hit_rate.pct'."""
    matches = [i for i, col in enumerate(header) if METRIC in col]
    if not matches:
        return None
    vals = []
    for row in rows:
        for i in matches:
            if i < len(row):
                try:
                    vals.append(float(row[i]))
                except ValueError:
                    pass
    return vals


def extract_values_long(rows, header):
    """Long form: a 'Metric Name' column and a 'Metric Value' column, one metric per row."""
    try:
        name_i = header.index("Metric Name")
        val_i = header.index("Metric Value")
    except ValueError:
        return None
    vals = []
    for row in rows:
        if len(row) > max(name_i, val_i) and METRIC in row[name_i]:
            try:
                vals.append(float(row[val_i].replace(",", "")))
            except ValueError:
                pass
    return vals


def parse_one(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None, "file missing or empty (ncu run likely failed)"
    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return None, "no rows"
    header = rows[0]
    body = rows[1:]
    vals = extract_values_wide(body, header)
    if not vals:
        vals = extract_values_long(body, header)
    if not vals:
        return None, f"metric '{METRIC}' not found in columns: {header}"
    return sum(vals) / len(vals), None


def main():
    if not os.path.isdir(RAW_DIR):
        sys.exit(f"{RAW_DIR} not found — run scripts/profile_l2.sh first")

    results = {}  # test_point_id -> {"cached": val_or_None, "zerocopy": val_or_None}
    for f in sorted(glob.glob(os.path.join(RAW_DIR, "*__cached.csv"))) + \
             sorted(glob.glob(os.path.join(RAW_DIR, "*__zerocopy.csv"))):
        base = os.path.basename(f)
        m = re.match(r"^(.*)__(cached|zerocopy)\.csv$", base)
        if not m:
            continue
        tpid, path = m.group(1), m.group(2)
        val, err = parse_one(f)
        results.setdefault(tpid, {})[path] = val
        if err:
            print(f"WARNING: {base}: {err}", file=sys.stderr)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test_point_id", "l2_hit_rate_cached", "l2_hit_rate_zc"])
        for tpid, paths in sorted(results.items()):
            cached = paths.get("cached")
            zc = paths.get("zerocopy")
            w.writerow([
                tpid,
                f"{cached:.2f}" if cached is not None else "NA",
                f"{zc:.2f}" if zc is not None else "NA",
            ])
    print(f"wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
