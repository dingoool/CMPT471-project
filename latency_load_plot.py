#!/usr/bin/env python3
import csv
from pathlib import Path
from collections import Counter
import matplotlib
import matplotlib.pyplot as plt
import re

matplotlib.use("Agg")

SWEEP_DIR = Path("sweep_results")
OUT_FILE  = "selection_analysis.png"

# sorting helper func
def natural_key(path):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', str(path))]

# load logs 
runs = []
for run_dir in sorted(SWEEP_DIR.iterdir()):
    results_dir = run_dir / "results"
    if not results_dir.is_dir():
        continue
    for f in results_dir.glob("s*_c*_selection.csv"):
        with open(f) as fh:
            rows = list(csv.DictReader(fh))
        if rows:
            runs.append((run_dir.name, rows))

runs.sort(key = natural_key)

if not runs:
    print("No selection logs found in sweep_results/results")
    exit(1)


"""
for each run, produces:
1. latency correctness plot (best vs chosen + bad picks shown by vertical red line)
2. server selection distribution (bar graph)
"""
# plotting
fig, axes = plt.subplots(len(runs), 2, figsize=(15, 4 * len(runs)), squeeze=False)

for row_idx, (label, rows) in enumerate(runs):
    # lat --> latency
    lat_keys = [k for k in rows[0].keys() if k.startswith("lat_")]

    chosen_lats = []
    best_lats   = []
    bad_picks   = []
    chosen_servers = []

    # extract data (the selection's chosen latency, the actual best latency)
    for i, row in enumerate(rows):
        chosen = row.get("chosen_server", "").strip()
        if not chosen:
            continue

        port = chosen.split(":")[-1]
        chosen_key = f"lat_{port}"

        try:
            chosen_lat = float(row[chosen_key])
            best_lat = min(float(row[k]) for k in lat_keys if row[k] not in ("", "inf"))
        except (KeyError, ValueError):
            continue

        chosen_lats.append(chosen_lat)
        best_lats.append(best_lat)
        chosen_servers.append(chosen)

        # tolerance of ~1 ms for of best chosen (server) latency
        if chosen_lat - best_lat > 0.001:
            bad_picks.append(len(chosen_lats) - 1)

    x = range(len(chosen_lats))

    # 1. latency correctness plot
    ax1 = axes[row_idx, 0]
    ax1.plot(x, best_lats, label="best", linewidth=1.5)
    ax1.plot(x, chosen_lats, linestyle="--", label="chosen", linewidth=1.5)

    for idx in bad_picks:
        ax1.axvline(idx, alpha=0.3, color='red')

    correct = len(chosen_lats) - len(bad_picks)
    pct = 100 * correct / len(chosen_lats) if chosen_lats else 0

    ax1.set_title(f"{label}\nCorrectness ({pct:.0f}%)")
    ax1.set_xlabel("Selection event")
    ax1.set_ylabel("Latency")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.4)

    # 2. load balancing (bar graph)
    ax2 = axes[row_idx, 1]
    counts = Counter(chosen_servers)

    # only existing servers that were in csv
    servers = list(counts.keys())
    values = list(counts.values())

    ax2.bar(servers, values)
    ax2.set_title("Server Selection Distribution")
    ax2.set_xlabel("Server")
    ax2.set_ylabel("# selections")
    ax2.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=150)
print(f"Saved: {OUT_FILE}")

