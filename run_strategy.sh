#!/bin/bash

NUM_SERVERS=2
NUM_TRIALS=5
STRATEGIES=("latency" "latency-load")

mkdir -p logs results

# clear old files once at start
rm -f logs/*
rm -f results/*

for STRATEGY in "${STRATEGIES[@]}"; do
  echo "=============================="
  echo "Strategy: $STRATEGY"
  echo "=============================="

  for NUM_CLIENTS in {1..10}; do
    for TRIAL in $(seq 1 $NUM_TRIALS); do
      echo ""
      echo "Running: servers=$NUM_SERVERS clients=$NUM_CLIENTS strategy=$STRATEGY trial=$TRIAL"

      # cleanup before each run
      pkill -9 -f "python3 server.py" 2>/dev/null
      pkill -9 -f "python3 selection_server.py" 2>/dev/null
      sleep 1

      # start servers
      for ((i=1;i<=NUM_SERVERS;i++)); do
        PORT=$((8000 + i))
        python3 server.py "$PORT" "content/server$i" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" \
          > "logs/server_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_s${i}.txt" 2>&1 &
      done

      sleep 2

      # start selection server
      python3 selection_server.py "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" "$TRIAL" \
        > "logs/selection_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}.txt" 2>&1 &

      sleep 1

      # start clients
      client_pids=()

      for ((i=1;i<=NUM_CLIENTS;i++)); do
        python3 client.py "$NUM_SERVERS" "$NUM_CLIENTS" "$i" "$STRATEGY" "$TRIAL" \
          > "logs/client_${STRATEGY}_c${NUM_CLIENTS}_t${TRIAL}_id${i}.txt" 2>&1 &
        client_pids+=($!)
      done

      # wait for all clients
      for pid in "${client_pids[@]}"; do
        wait "$pid"
      done

      # cleanup after run
      pkill -f "python3 server.py" 2>/dev/null
      pkill -f "python3 selection_server.py" 2>/dev/null

      echo "Finished: clients=$NUM_CLIENTS strategy=$STRATEGY trial=$TRIAL"
      sleep 1
    done
  done
done

echo ""
echo "All experiments completed."