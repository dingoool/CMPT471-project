#!/bin/bash
# Combined script for running normal strategy tests and server failure tests.
# Usage: ./run_combined.sh <mode> [num_servers] [num_trials]
# Modes: normal (varies clients 1-10, no failure), failure (fixed 10 clients, with failure simulation)
# Defaults: num_servers=2, num_trials=10

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

MODE=${1:-normal} #default to normal if mode not given
NUM_SERVERS=${2:-2}
NUM_TRIALS=${3:-10}
STRATEGIES=("latency" "latency-load")

LOG_BASE="$ROOT_DIR/logs"
RESULT_BASE="$ROOT_DIR/results"
LOG_DIR="$LOG_BASE/$MODE"
RESULT_DIR="$RESULT_BASE/$MODE"

# mode settings
if [ "$MODE" = "failure" ]; then
    NUM_CLIENTS=10
    FAILURE_DELAY=3      # seconds after clients start before killing server
    RECOVERY_DELAY=2     # seconds after failure before restarting server
fi

# sub dirs created and cleared depending on mode
mkdir -p "$LOG_BASE" "$RESULT_BASE" "$LOG_DIR" "$RESULT_DIR"
rm -rf "$LOG_DIR"/* "$RESULT_DIR"/*

# initial cleanup of any stale processes
pkill -9 -f "python3 $ROOT_DIR/server.py" 2>/dev/null
pkill -9 -f "python3 $ROOT_DIR/selection_server.py" 2>/dev/null
pkill -9 -f "python3 $ROOT_DIR/client.py" 2>/dev/null
sleep 1

for STRATEGY in "${STRATEGIES[@]}"; do
    echo ""
    echo "=============================="
    echo "Mode: $MODE, Strategy: $STRATEGY"
    echo "=============================="

    # determine how many clients
    if [ "$MODE" = "normal" ]; then
        CLIENT_RANGE="1 2 3 4 5 6 7 8 9 10"
        CLIENT_RANGE="1 2 3"

    else
        CLIENT_RANGE="10" #fixed 10 clients at a time for server fail mode
    fi

    for NUM_CLIENTS in $CLIENT_RANGE; do
        for TRIAL in $(seq 1 $NUM_TRIALS); do
            echo "" 
            echo "Running: mode=$MODE servers=$NUM_SERVERS clients=$NUM_CLIENTS strategy=$STRATEGY trial= $TRIAL / $NUM_TRIALS"

            # cleanup stale processes between runs
            pkill -9 -f "python3 $ROOT_DIR/server.py" 2>/dev/null
            pkill -9 -f "python3 $ROOT_DIR/selection_server.py" 2>/dev/null
            sleep 3

            mkdir -p "$ROOT_DIR/results"
            rm -f "$ROOT_DIR/results"/*.csv

            echo "Starting $NUM_SERVERS servers..."
            for ((i=1; i<=NUM_SERVERS; i++)); do
                PORT=$((8000 + i))
                LOG_FILE="$LOG_DIR/server_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_s${i}.txt"
                python3 "$ROOT_DIR/server.py" "$PORT" "$ROOT_DIR/content/server$i" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" "$TRIAL" \
                > "$LOG_FILE" 2>&1 &
            done
            sleep 2

            echo "Starting selection server..."
            LOG_FILE="$LOG_DIR/selection_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}.txt"
            python3 "$ROOT_DIR/selection_server.py" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" "$TRIAL" "$ROOT_DIR" \
                > "$LOG_FILE" 2>&1 &
            sleep 1

            echo "Starting $NUM_CLIENTS clients..."
            client_pids=()
            for ((i=1; i<=NUM_CLIENTS; i++)); do
                LOG_FILE="$LOG_DIR/client_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_id${i}.txt"
                python3 "$ROOT_DIR/client.py" "$NUM_SERVERS" "$NUM_CLIENTS" "$i" "$STRATEGY" "$TRIAL" "$ROOT_DIR" \
                    > "$LOG_FILE" 2>&1 &
                client_pids+=($!)
                if [ "$MODE" = "failure" ]; then
                    #echo "Staggered"
                    sleep 0.1  # stagger for failure mode
                fi
            done

            # failure/recovery block (runs concurrently with clients) 
            if [ "$MODE" = "failure" ]; then
                (
                    echo "[FAILURE] Waiting ${FAILURE_DELAY}s before killing server 8001..."
                    sleep "$FAILURE_DELAY"

                    echo "[FAILURE] Killing server 8001"
                    pkill -TERM -f "python3 $ROOT_DIR/server.py 8001"

                    # wait until it's actually gone
                    while pgrep -f "$ROOT_DIR/server.py 8001" > /dev/null; do
                        sleep 0.2
                    done

                    echo "[FAILURE] Server 8001 is fully down"

                    echo "[RECOVERY] Waiting ${RECOVERY_DELAY}s before restarting..."
                    sleep "$RECOVERY_DELAY"

                    # extra buffer for socket release
                    sleep 1

                    # make restarted to be trial 99 to differentiate for plotting
                    echo "[RECOVERY] Restarting server 8001"
                    python3 "$ROOT_DIR/server.py" 8001 "$ROOT_DIR/content/server1" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" 99 \
                        > "$LOG_DIR/server_${STRATEGY}_1_restarted_t${TRIAL}.txt" 2>&1 &

                    echo "[RECOVERY] Server 8001 back online"
                ) &
                failure_pid=$!
            fi

            # wait for all clients to finish
            for pid in "${client_pids[@]}"; do
                wait "$pid"
            done
            
            # clean up failed server for next run
            if [ "$MODE" = "failure" ]; then
                wait "$failure_pid"
            fi

            # cleanup
            pkill -TERM -f "python3 $ROOT_DIR/server.py" 2>/dev/null
            pkill -TERM -f "python3 $ROOT_DIR/selection_server.py" 2>/dev/null
            sleep 3

            # move results into the mode subdirectory
            shopt -s nullglob
            for f in "$ROOT_DIR/results"/*.csv; do
                if [ -f "$f" ]; then
                    if [ "$MODE" = "failure" ]; then
                        base=$(basename "$f")
                        mv "$f" "$RESULT_DIR/${STRATEGY}_c${NUM_CLIENTS}_trial${TRIAL}_$base"
                    else
                        mv "$f" "$RESULT_DIR/$(basename "$f")"
                    fi
                fi
            done
        done
    done
done

echo ""
echo "All $MODE experiments completed."
if [ "$MODE" = "failure" ]; then
    echo "Run: python3 plots_failure.py"
else
    echo "Run: python3 plots.py"
fi