import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

RESULTS_DIR = Path("results_failure")
OUT_FILE = "server_failure_plots.png"
STRATEGIES = ["latency", "latency-load"]

# Parse folder names
def parse_filename(filename):
    try:
        if "latency-load" in filename:
            strategy = "latency-load"
        elif "latency" in filename:
            strategy = "latency"
        else:
            return None

        trial_m = re.search(r"_t(\d+)_", filename)
        trial = int(trial_m.group(1)) if trial_m else None

        client_m = re.search(r"client(\d+)", filename)
        client_id = int(client_m.group(1)) if client_m else None

        server_m = re.search(r"server(\d+)", filename)
        server_id = int(server_m.group(1)) if server_m else None 
    except Exception as e:
        print("Parse error for:", filename, e)
        return None
    return strategy, trial, client_id, server_id


def load_clients(strategy):
    rows = []
    
    for f in sorted(RESULTS_DIR.glob(f"{strategy}_*.csv")):
        parsed = parse_filename(f.name)
       
        if not parsed:
            print(f"Skipping unrecognized file: {f.name}")
            continue
        
        strat, trial, client_id, _ = parsed
        if client_id is None:
            continue

        try:
            df = pd.read_csv(f)
            df["trial"] = trial
            df["client_id"] = client_id

            rows.append(df)

        except Exception as e:
            print(f"Skipping {f.name}: {e}")

    if not rows:
        return pd.DataFrame()

    df = pd.concat(rows, ignore_index=True)
    df["initial_server"] = df["initial_server"].str.strip()
    df["final_server"] = df["final_server"].str.strip()
    df["switched"] = df["initial_server"] != df["final_server"]
    return df

def load_servers(strategy):
    rows = []
    
    for f in sorted(RESULTS_DIR.glob(f"{strategy}_*.csv")):
        parsed = parse_filename(f.name)
        if not parsed:
            print(f"Skipping {f.name}")
            continue

        strat, trial, _, server_id = parsed
        if server_id is None:
            continue

        df = pd.read_csv(f)
        df["trial"] = trial
        df["port"] = server_id
        rows.append(df)
    
    if not rows:
        return pd.DataFrame()
    
    return pd.concat(rows, ignore_index=True)


def plot_switch_rate(ax, clients, strategy):
    ax.set_title(f"{strategy}\nClient Switching Rate")

    per_trial = clients.groupby("trial")["switched"].mean()

    avg = per_trial.mean()
    std = per_trial.std()

    ax.bar([0], [avg], color="blue")
    ax.errorbar([0], [avg], yerr=[std], fmt='none', capsize=5)

    ax.set_xticks([0])
    ax.set_xticklabels(["Switch rate"])
    ax.set_ylabel("Fraction of clients switching")

    ax.text(0, avg, f"{avg:.2f} ± {std:.2f}", ha="center", va="bottom")

    ax.set_ylim(0, 1)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)


def plot_download_times(ax, clients, strategy):
    ax.set_title(f"{strategy}\nDownload time (avg per trial)")

    grouped = clients.groupby(["trial", "switched"])["time_download"].mean().reset_index()
    stayed_times = grouped[grouped["switched"] == False]["time_download"].dropna()
    switched_times = grouped[grouped["switched"] == True]["time_download"].dropna()

    # value annotations 
    stayed_mean = stayed_times.mean()
    switched_mean = switched_times.mean()
    stayed_std = stayed_times.std()
    switched_std = switched_times.std()
    ax.text(0, stayed_mean + stayed_std, f'{stayed_mean:.2f}', ha='center', va='bottom')
    ax.text(1, switched_mean + switched_std, f'{switched_mean:.2f}', ha='center', va='bottom')

    ax.bar([0, 1], [stayed_mean, switched_mean], yerr=[stayed_std, switched_std], color = ["blue", "orange"])
    
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Stayed on server", "Switched server"])
    ax.set_ylabel("Avg time_download (s)")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

def plot_server_load(ax, servers, strategy):
    ax.set_title(f"{strategy}\nAvg requests per server\n(8001 = failed server)")

    # Filter out restarted server data (trial 99) for port 8001 to show only pre-failure counts
    servers = servers[~((servers["port"] == 8001) & (servers["trial"] == 99))]

    per_trial = (
        servers.groupby(["trial", "port"])["total_req"]
        .max()
        .reset_index()
    )

    summary = (
        per_trial.groupby("port")["total_req"]
        .agg(["mean", "std"])
        .reset_index()
    )

    ports = summary["port"].astype(str)
    means = summary["mean"]
    stds = summary["std"]
    colors = ["red" if p == "8001" else "blue" for p in ports]

    ax.bar(ports, means, yerr=stds, color=colors, alpha=0.85, width=0.5)

    for i, (port, mean, std) in enumerate(zip(ports,means, stds)):
        ax.text(i, mean+std, f"{mean:.0f}", ha="center", va="bottom")
    # print(servers.groupby(["trial", "port"])["total_req"].describe())
    ax.set_xlabel("Server port")
    ax.set_ylabel("Avg requests served")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

def main():
    fig, axes = plt.subplots(len(STRATEGIES), 3, figsize=(16, 5*len(STRATEGIES)))
    fig.patch.set_facecolor("white")
    plt.rcParams.update({"font.size": 10})    
    
    for row_idx, strategy in enumerate(STRATEGIES):
        clients = load_clients(strategy)
        servers = load_servers(strategy)

        if clients.empty:
            for ax in axes[row_idx]:
                ax.text(0.5, 0.4, f"No data for {strategy}", transform=ax.transAxes, ha="center", va="center", color="gray")
            continue
        
        print(f"\n{strategy}:")
        print(f"  Total clients:    {len(clients)}")
        print(f"  Switched server:  {clients['switched'].sum()}")
        print(f"  Stayed on server: {(~clients['switched']).sum()}")
 
        plot_switch_rate(axes[row_idx][0], clients, strategy)
        plot_download_times(axes[row_idx][1], clients, strategy)
        plot_server_load(axes[row_idx][2], servers, strategy)
 
    plt.tight_layout(pad=2.5)
    plt.savefig(OUT_FILE, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {OUT_FILE}")

if __name__ == "__main__":
    main()