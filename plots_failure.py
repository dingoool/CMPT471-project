import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

RESULTS_DIR = Path("results_failure")
OUT_FILE = "server_failure_plots.png"
STRATEGIES = ["latency", "latency-load"]

# Parse folder names
def parse_port_label(url):
    """
    Ex. http://localhost:8001 --> 8001
    """
    m = re.search(r":(\d+)", str(url))
    if m:
        return m.group(1)
    else:
        return str(url)

def parse_client_files(filename):
    m = re.match(r"s(\d+)_c(\d+)_(.+)_t(\d+)_client(\d+)\.csv$", filename)
    if m:
        return int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    return None, None, None, None, None


def load_clients(strategy):
    rows = []
    
    for f in sorted(RESULTS_DIR.glob(f"*_{strategy}_*_client*.csv")):
        num_servers, num_clients, trial, client_id = parse_strategy_result(f.name)

        if num_servers is None:
            print(f"Skipping unrecognized file: {f.name}")
            continue

        try:
            df = pd.read_csv(f)

            df["num_servers"] = num_servers
            df["num_clients"] = num_clients
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
    
    for f in sorted(RESULTS_DIR.glob(f"*_{strategy}_t*_server*.csv")):
        df = pd.read_csv(f)
        rows.append(df)
    
    combined = pd.concat(rows, ignore_index=True)
    result = (
        combined.groupby("port")[["total_req", "manifest_req", "segment_req", "other_req"]]
        .sum()
        .reset_index()
        .sort_values("port")
    )
    return result

# Parse Strategy results
def parse_strategy_result(filename):
    m = re.match(r"s(\d+)_c(\d+)_.+?_t(\d+)_client(\d+).csv$", filename)
    if m:
        num_servers = int(m.group(1))
        num_clients = int(m.group(2))
        trial = int(m.group(4))
        client_id = int(m.group(4))
        return num_servers, num_clients, trial, client_id

    return None, None, None, None

def plot_switches(ax, clients, strategy):
    ax.set_title(f"{strategy}\nClient server assignment (initial -> final)")

    # y-pos for each unique server
    unique_servers = sorted(set(clients["initial_server"]) | set(clients["final_server"]))
    server_pos = {s: i for i, s in enumerate(unique_servers)}

    for _, row in clients.sort_values("client_id").iterrows():
        clientId = int(row["client_id"])
        y_start = server_pos[row["initial_server"]]
        y_end = server_pos[row["final_server"]]

        if row["switched"]:
            # arrow from init to final
            ax.annotate("", xy=(clientId, y_end), xytext=(clientId, y_start), arrowprops=dict(arrowstyle="->", color="red"))
            ax.scatter(clientId, y_start, color="red")
            ax.scatter(clientId, y_end, color="red", marker="*")
        else:
            ax.scatter(clientId, y_start, color="blue")
    
    ax.set_yticks(range(len(unique_servers)))
    ax.set_yticklabels([parse_port_label(s) for s in unique_servers])
    ax.set_xlabel("Client ID")
    ax.set_ylabel("Server")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(handles=[
        mpatches.Patch(color="blue", label="stayed"),
        mpatches.Patch(color="red", label="switched"),
    ], fontsize=8, framealpha=0.5)

def plot_download_times(ax, clients, strategy):
    ax.set_title(f"{strategy}\nDownload time (Switched vs Stayed)")

    stayed_times = clients[~clients["switched"]]["time_download"].dropna()
    switched_times = clients[clients["switched"]]["time_download"].dropna()

    def draw_group(times, x_pos, color, text_color):
        if times.empty:
            return
        ax.scatter([x_pos] * len(times), times, color=color, alpha=0.7, s=50, zorder=3)
        ax.plot([x_pos], [times.mean()], marker="_", color=color, markersize=20)
        ax.text(x_pos, times.mean(), f" avg={times.mean():.3f}s", va="bottom", color=text_color)
    
    draw_group(stayed_times, x_pos=0, color="red", text_color="red")
    draw_group(switched_times, x_pos=1, color="blue", text_color="blue")

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Stayed on server", "Switched server"])
    ax.set_ylabel("time_download (s)")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

def plot_server_load(ax, servers, strategy):
    ax.set_title(f"{strategy}\nTotal requests per server\n(8001 = failed server)")

    if servers.empty:
        ax.text(0.5, 0.5, "No server stats found", transform=ax.transAxes,
                ha="center", va="center", color="gray")
        return

    ports = servers["port"].astype(str).tolist()
    req_count = servers["total_req"].tolist()
    colors = ["red" if p == "8001" else "blue" for p in ports]

    bars = ax.bar(ports, req_count, color=colors, alpha=0.85, width=0.5)
    ax.bar_label(bars, padding=3, fontsize=9)
    ax.legend(handles=[
        mpatches.Patch(color="red", label="failed server (8001)"),
        mpatches.Patch(color="blue", label="normal server"),
    ], fontsize=8, framealpha=0.5)

    ax.set_xlabel("Server port")
    ax.set_ylabel("Total requests served")
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
 
        plot_switches(axes[row_idx][0], clients, strategy)
        plot_download_times(axes[row_idx][1], clients, strategy)
        plot_server_load(axes[row_idx][2], servers, strategy)
 
    plt.tight_layout(pad=2.5)
    plt.savefig(OUT_FILE, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {OUT_FILE}")

if __name__ == "__main__":
    main()