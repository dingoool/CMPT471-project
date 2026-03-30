import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

SWEEP_DIR = Path("sweep_results")
STRATEGY_DIR = Path("strategy_results")

# Parse folder names
def parse_run_label(label):
    """
    Example:
    fixed_servers_5__clients_3 -> ("fixed_servers", 5, 3)
    fixed_clients_5__servers_2 -> ("fixed_clients", 5, 2)
    """
    m = re.match(r"fixed_servers_(\d+)__clients_(\d+)", label)
    if m:
        return "fixed_servers", int(m.group(1)), int(m.group(2))

    m = re.match(r"fixed_clients_(\d+)__servers_(\d+)", label)
    if m:
        return "fixed_clients", int(m.group(1)), int(m.group(2))

    return None, None, None

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

# Load all CSVs into DataFrame
def load_data(sweep_dir):
    rows = []

    for run_dir in sorted(sweep_dir.iterdir()):
        if not run_dir.is_dir():
            continue

        sweep_type, fixed_val, varied_val = parse_run_label(run_dir.name)
        if sweep_type != "fixed_servers":
            continue  # only care about number of clients

        for f in run_dir.glob("results/*.csv"):
            try:
                df = pd.read_csv(f)

                df["num_clients"] = varied_val
                df["num_servers"] = fixed_val

                rows.append(df)

            except Exception as e:
                print(f"Skipping {f}: {e}")

    if not rows:
        raise ValueError("No data found.")

    return pd.concat(rows, ignore_index=True)

def load_client_data(results_dir):
    rows = []
    
    for f in sorted(results_dir.glob('*_client*.csv')):
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
        raise ValueError("No client result files found.")

    return pd.concat(rows, ignore_index=True)

# Compute average
def compute_average(df, metric):
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric, "num_clients", "strategy"])

    avg_df = (
        df.groupby(["strategy", "num_clients"])[metric]
        .mean()
        .reset_index()
        .sort_values(["strategy", "num_clients"])
    )

    return avg_df

# Compute improvement
def compute_improvement(avg_df, metric, baseline_strategy="latency", compare_strategy="latency-load"):
    baseline = avg_df[avg_df["strategy"] == baseline_strategy][["num_clients", metric]].copy()
    compare = avg_df[avg_df["strategy"] == compare_strategy][["num_clients", metric]].copy()

    baseline = baseline.rename(columns={metric: "baseline_value"})
    compare = compare.rename(columns={metric: "compare_value"})

    merged = pd.merge(baseline, compare, on="num_clients", how="inner")

    merged["improvement_pct"] = (
        (merged["baseline_value"] - merged["compare_value"]) / merged["baseline_value"]
    ) * 100

    return merged.sort_values("num_clients")

# Plot Average 
def plot_metric(df, metric, ylabel, title, out_file):
    plt.figure(figsize=(10, 6))

    for strategy in sorted(df["strategy"].unique()):
        subset = df[df["strategy"] == strategy]
        plt.plot(
            subset["num_clients"],
            subset[metric],
            marker="o",
            linewidth=2,
            label=strategy
        )

    plt.xlabel("Number of Clients")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.savefig(out_file, dpi=300, bbox_inches="tight")

def plot_improvement(df, out_file, title):
    plt.figure(figsize=(10, 6))

    plt.plot(
        df["num_clients"],
        df["improvement_pct"],
        marker="o",
        linewidth=2
    )

    plt.axhline(0, linestyle="--", linewidth=1, color="red")
    plt.xlabel("Number of Clients")
    plt.ylabel("Download improvement over latency-only (%)")
    plt.title(title)
    plt.grid(True)
    plt.savefig(out_file, dpi=300, bbox_inches="tight")

def main():
    try:
        df = load_client_data(STRATEGY_DIR)

        # plot average time to download
        avg_download_df = compute_average(df, "time_download")
        plot_metric(
            avg_download_df,
            "time_download",
            "Average download time (s)",
            "Average Download Time vs Number of Clients",
            "avg_download_strategy.png"
        )

        # plot average time to get server
        avg_server_df = compute_average(df, "time_server")
        plot_metric(
            avg_server_df,
            "time_server",
            "Average time to get server (s)",
            "Average Time to Get Server vs Number of Clients",
            "avg_server_strategy.png"
        )

        # plot download improvement
        improve_download_df = compute_improvement(
            avg_download_df,
            "time_download",
            baseline_strategy="latency",
            compare_strategy="latency-load"
        )

        plot_improvement(
            improve_download_df,
            "download_improvement.png",
            "Download Time Improvement of Load-Aware Strategy Over Latency-Only"
        )


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()