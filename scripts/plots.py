import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR/"results/normal"
PLOTS_DIR = BASE_DIR/ "plots"
PLOTS_DIR.mkdir(exist_ok=True)

# Parse Strategy results
def parse_result_filename(filename):
    """
    Example:
    s2_c10_latency-load_t1_client1.csv
    """
    match = re.match(r"s(\d+)_c(\d+)_.+?_t(\d+)_client(\d+)\.csv$", filename)
    if not match:
        return None, None, None, None
    
    num_servers = int(match.group(1))
    num_clients = int(match.group(2))
    trial = int(match.group(3))
    client_id = int(match.group(4))
    return num_servers, num_clients, trial, client_id

def load_client_data(results_dir):
    rows = []
    
    for file_path in sorted(results_dir.glob('*_client*.csv')):
        num_servers, num_clients, trial, client_id = parse_result_filename(file_path.name)

        if num_servers is None:
            print(f"Skipping unrecognized file: {file_path.name}")
            continue

        try:
            df = pd.read_csv(file_path)
            
            df["num_servers"] = num_servers
            df["num_clients"] = num_clients
            df["trial"] = trial
            df["client_id"] = client_id

            rows.append(df)

        except Exception as e:
            print(f"Skipping {file_path.name}: {e}")

    if not rows:
        raise ValueError("No client result files found.")

    df = pd.concat(rows, ignore_index=True)
    df['num_clients'] = pd.to_numeric(df['num_clients'], errors='coerce')
    df['time_download'] = pd.to_numeric(df['time_download'], errors='coerce')
    
    return df.dropna(subset=['strategy', 'num_clients'])

def remove_outliers_group(df, metric):
    df = df.copy()
    df[metric] = pd.to_numeric(df[metric], errors="coerce")

    filtered_groups = []

    for (strategy, num_clients), group in df.groupby(["strategy", "num_clients"]):
        q1 = group[metric].quantile(0.25)
        q3 = group[metric].quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        filtered = group[(group[metric] >= lower) & (group[metric] <= upper)]
        filtered_groups.append(filtered)

    if not filtered_groups:
        raise ValueError("No data left after outlier removal.")

    return pd.concat(filtered_groups, ignore_index=True)

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

def compute_trial_avg(df, metric):
    df[metric] = pd.to_numeric(df[metric], errors='coerce')
    trial_avg = (
        df.groupby(['strategy', 'num_clients', 'trial'])[metric]
        .mean()
        .reset_index()
    )
    return trial_avg

def compute_improvement_per_trial(df, metric):
    baseline = df[df["strategy"] == "latency"]
    compare = df[df["strategy"] == "latency-load"]

    merged = pd.merge(
        baseline,
        compare,
        on=["num_clients", "trial"],
        suffixes=("_base", "_comp")
    )

    merged["improvement_pct"] = (
        (merged[f"{metric}_base"] - merged[f"{metric}_comp"])
        / merged[f"{metric}_base"]
    ) * 100

    return merged

def compute_stats(df, metric):
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric, "num_clients", "strategy"])

    stats_df = (
        df.groupby(["strategy", "num_clients"])[metric]
        .agg(['mean', 'std'])
        .reset_index()
        .sort_values(["strategy", "num_clients"])
    )

    return stats_df

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

def compute_improvement_stats(df):
    stats = (
        df.groupby("num_clients")["improvement_pct"]
        .agg(["mean", "std"])
        .reset_index()
        .sort_values("num_clients")
    )
    return stats

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

# Plot metric with error
def plot_with_error(df, metric_mean, metric_std, ylabel, title, out_file):
    plt.figure(figsize=(10,6))

    for strategy in sorted(df['strategy'].unique()):
        subset = df[df['strategy'] == strategy]

        plt.errorbar(
            subset['num_clients'],
            subset[metric_mean],
            yerr=subset[metric_std],
            marker='o',
            linewidth=2,
            capsize=5,
            label=strategy
        )
    
    plt.xlabel("Number of Clients")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.savefig(out_file, dpi=300, bbox_inches='tight')

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

def plot_improvement_with_error(df, out_file, title):
    plt.figure(figsize=(10, 6))

    plt.errorbar(
        df["num_clients"],
        df["mean"],
        yerr=df["std"],
        marker="o",
        linewidth=2,
        capsize=5,
        ecolor='black'
    )

    plt.axhline(0, linestyle="--", linewidth=1, color="red")

    plt.xlabel("Number of Clients")
    plt.ylabel("Download improvement over latency-only (%)")
    plt.title(title)
    plt.grid(True)

    plt.savefig(out_file, dpi=300, bbox_inches="tight")

def main():
    try:
        df = load_client_data(RESULTS_DIR)
        
        # remove ouliers
        df = remove_outliers_group(df, 'time_download')

        # compute stats
        stats = compute_stats(df, 'time_download')
        print(stats)
        # plot
        plot_with_error(
            stats,
            'mean',
            'std',
            'Average download time (s)',
            'Average Download Time vs Number of Clients (with error)',
            PLOTS_DIR/'avg_download_error.png'
        )
        
        # plot average time to download
        avg_download_df = compute_average(df, "time_download")

        plot_metric(
            avg_download_df,
            "time_download",
            "Average download time (s)",
            "Average Download Time vs Number of Clients",
            PLOTS_DIR/"avg_download_strategy.png"
        )

        # plot average time to get server
        avg_server_df = compute_average(df, "time_server")
        plot_metric(
            avg_server_df,
            "time_server",
            "Average time to get server (s)",
            "Average Time to Get Server vs Number of Clients",
            PLOTS_DIR/"avg_server_strategy.png"
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
            PLOTS_DIR/"download_improvement.png",
            "Download Time Improvement of Load-Aware Strategy Over Latency-Only"
        )

        # improvement with error bars
        trial_avg_df = compute_trial_avg(df, "time_download")

        improve_df = compute_improvement_per_trial(trial_avg_df, "time_download")
        improve_stats = compute_improvement_stats(improve_df)
        plot_improvement_with_error(
            improve_stats,
            PLOTS_DIR/"download_improvement_error.png",
            "Download Improvement with Variability"
        )


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()