#!/usr/bin/env python3
"""
plot_clients.py — plots time_server and time_download per client across both sweeps (fixed server, fixed client).

plots two metrics:
  - time_server:   how long it took the client to get a server assigned
                   (client-side measurement, includes network round trip
                   to selection server)
  - time_download: how long it took to fetch the manifest + all segments
                   from the content server

Each client is shown as its own colored line so you can compare individual
client experiences across different server/client counts.
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

SWEEP_DIR = Path("sweep_results")
OUT_FILE  = "client_getServer_download_analysis.png"

# helpers 

def parse_run_label(label):
    """
    Extract sweep type and varied value from a run folder name.
    e.g. "fixed_servers_5__clients_3" -> ("fixed_servers", 5, 3)
         "fixed_clients_5__servers_2" -> ("fixed_clients", 5, 2)
    Returns (None, None, None) if the folder name doesn't match either pattern.
    """
    m = re.match(r"fixed_servers_(\d+)__clients_(\d+)", label)
    if m:
        return "fixed_servers", int(m.group(1)), int(m.group(2))
    m = re.match(r"fixed_clients_(\d+)__servers_(\d+)", label)
    if m:
        return "fixed_clients", int(m.group(1)), int(m.group(2))
    return None, None, None

def read_clients(run_dir):
    """
    Read all client result CSVs from a single run's results/ subfolder.
    Each file is one client's row: client_id, time_server, time_download, etc.
    Returns a flat list of dicts (one per client).
    """
    results = []
    for f in sorted(run_dir.glob("results/s*_c*_client*_results.csv")):
        with open(f) as fh:
            results.extend(list(csv.DictReader(fh)))
    return results

# data collection 

# data[sweep_type][varied_val] = list of client result dicts for that run
# e.g. data["fixed_servers"][3] = [{client_id: 1, time_server: 0.02, ...}, ...]
data = defaultdict(lambda: defaultdict(list))

for run_dir in sorted(SWEEP_DIR.iterdir()):
    if not run_dir.is_dir():
        continue
    sweep_type, _, varied_val = parse_run_label(run_dir.name)
    if sweep_type is None:
        continue
    data[sweep_type][varied_val] = read_clients(run_dir)

if not data:
    print("No client data found in sweep_results/")
    exit(1)

# plotting 

# Two sweeps: one row each
# Two metrics: one column each
SWEEP_CONFIGS = [
    ("fixed_servers", "Number of clients", "Fixed servers (5)"),
    ("fixed_clients", "Number of servers", "Fixed clients (5)"),
]

METRICS = [
    ("time_server",   "Time to get server (s)"),
    ("time_download", "Download time (s)"),
]

# only first elem is grabbed
num_sweeps = sum(1 for st, _, _ in SWEEP_CONFIGS if st in data)
fig, axes = plt.subplots(num_sweeps, 2,
                         figsize=(12, 4.5 * num_sweeps),
                         squeeze=False)
fig.patch.set_facecolor("#ffffff")
plt.rcParams.update({"font.size": 10})

row_idx = 0
for sweep_type, x_label, sweep_title in SWEEP_CONFIGS:
    if sweep_type not in data:
        continue

    sweep  = data[sweep_type]
    x_vals = sorted(sweep.keys()) 

    # collect all unique client IDs across the entire sweep so colors stay consistent 
    all_cids = sorted({int(c["client_id"])
                       for xv in x_vals
                       for c in sweep[xv]
                       if c.get("client_id", "").isdigit()})

    cmap   = matplotlib.colormaps["tab10"].resampled(max(len(all_cids), 1))
    ccolor = {cid: cmap(i) for i, cid in enumerate(all_cids)}

    for col_idx, (metric, metric_label) in enumerate(METRICS):
        ax = axes[row_idx][col_idx]
        ax.set_facecolor("#fafafa")
        ax.set_title(f"{sweep_title}\n{metric_label}", fontsize=10, pad=8)
        ax.set_xlabel(x_label)
        ax.set_ylabel(metric_label)

        any_plotted = False
        for cid in all_cids:
            # collect this client's metric value at each x value (server or client count)
            xs, ys = [], []
            for xv in x_vals:
                for c in sweep[xv]:
                    try:
                        if int(c.get("client_id", -1)) == cid:
                            ys.append(float(c[metric]))
                            xs.append(xv)
                    except (KeyError, ValueError):
                        pass  # skip rows with missing or non-numeric data

            if xs:
                ax.plot(xs, ys, marker="o", markersize=4,
                        color=ccolor[cid], label=f"client {cid}", linewidth=1.5)
                any_plotted = True

        if any_plotted:
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles, labels, fontsize=7, ncol=2, framealpha=0.5)
        else:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                    ha="center", va="center", color="gray")

        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_xticks(x_vals)

    row_idx += 1

plt.tight_layout(pad=2.5)
plt.savefig(OUT_FILE, dpi=150, bbox_inches="tight")
print(f"Saved: {OUT_FILE}")