#!/bin/bash
# run_failure_experiment.sh
# demonstrates client failover when a server goes down mid-download.
# Runs over both latency and latency-load strategies.
#
# 1. start NUM_SERVERS content servers + selection server
# 2. start NUM_CLIENTS clients all downloading concurrently
# 3. kill server 8001
# 4. restart server 8001
# 5. Save all logs/results to results_failure/<strategy>/

NUM_SERVERS=2
NUM_CLIENTS=10
NUM_TRIALS=10
FAILURE_DELAY=3      # seconds after clients start before killing server
RECOVERY_DELAY=2     # seconds after failure before restarting server
STRATEGIES=("latency" "latency-load")

rm -rf logs_failure/*
rm -rf results_failure/*

mkdir -p logs_failure
mkdir -p results_failure
mkdir -p results

# cleanup any stale processes
pkill -9 -f "python3 server.py" 2>/dev/null
pkill -9 -f "python3 selection_server.py" 2>/dev/null
pkill -9 -f "python3 client.py" 2>/dev/null
sleep 1

for STRATEGY in "${STRATEGIES[@]}"; do
    echo ""
    echo "=============================="
    echo "Strategy: $STRATEGY"
    echo "=============================="

    mkdir -p "logs_failure/$STRATEGY"
    mkdir -p "results_failure/$STRATEGY"

    for TRIAL in $(seq 1 $NUM_TRIALS); do
        echo "" 
        echo "Running trial $TRIAL / $NUM_TRIALS"

        # cleanup stale processes between strategies
        pkill -9 -f "python3 server.py" 2>/dev/null
        pkill -9 -f "python3 selection_server.py" 2>/dev/null
        pkill -9 -f "python3 client.py" 2>/dev/null
        sleep 3

        mkdir -p results
        rm -f results/*

        echo "Starting $NUM_SERVERS servers..."
        for ((i=1; i<=NUM_SERVERS; i++)); do
            PORT=$((8000 + i))
            python3 server.py "$PORT" "content/server$i" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" "$TRIAL" \
            > "logs_failure/server_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_s${i}.txt" 2>&1 &
        done
        sleep 2

        echo "Starting selection server..."
        python3 selection_server.py "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" "$TRIAL" \
            > "logs_failure/selection_server_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}.txt" 2>&1 &
        sleep 1

        echo "Starting $NUM_CLIENTS clients (staggered)..."
        client_pids=()
        for ((i=1; i<=NUM_CLIENTS; i++)); do
            python3 client.py "$NUM_SERVERS" "$NUM_CLIENTS" "$i" "$STRATEGY" "$TRIAL" \
            > "logs_failure/client_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_id${i}.txt" 2>&1 &
            client_pids+=($!)
            sleep 0.1  # stagger starts so we don't overwhelm selection server 
        done

        # ── failure/recovery block (runs concurrently with clients) ────────────────
        (
        echo "[FAILURE] Waiting ${FAILURE_DELAY}s before killing server 8001..."
        sleep "$FAILURE_DELAY"

        echo "[FAILURE] Killing server 8001"
        pkill -TERM -f "server.py 8001"

        # wait until it's actually gone
        while pgrep -f "server.py 8001" > /dev/null; do
            sleep 0.2
        done

        echo "[FAILURE] Server 8001 is fully down"

        echo "[RECOVERY] Waiting ${RECOVERY_DELAY}s before restarting..."
        sleep "$RECOVERY_DELAY"

        # extra buffer for socket release
        sleep 1

        # make restarted to be trial 99 to differentiate for plotting
        echo "[RECOVERY] Restarting server 8001"
        python3 server.py 8001 "content/server1" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" 99 \
            > "logs_failure/server_${STRATEGY}_1_restarted_t${TRIAL}.txt" 2>&1 &

        echo "[RECOVERY] Server 8001 back online"
        ) &

        # wait for all clients to finish
        for pid in "${client_pids[@]}"; do
            wait "$pid"
        done

        # cleanup
        pkill -TERM -f "python3 server.py" 2>/dev/null
        pkill -TERM -f "python3 selection_server.py" 2>/dev/null
        sleep 3

        # move results into strategy output folder
        for f in results/*.csv; do
            base=$(basename "$f")
            mv "$f" "results_failure/${STRATEGY}_c${NUM_CLIENTS}_trial${TRIAL}_$base"
        done
    done
  echo "Strategy $STRATEGY done. Results saved to results_failure/"
done

echo ""
echo "All experiments completed."
echo "Run: python3 plots_failure.py"