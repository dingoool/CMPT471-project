#!/bin/bash

if [ "$#" -ne 3 ]; then
  echo "Usage: ./run_experiment.sh <num_servers> <num_clients> <strategy>"
  echo "Strategy: latency or latency-load"
  exit 1
fi 

NUM_SERVERS=$1
NUM_CLIENTS=$2
STRATEGY=$3

echo "NUM_SERVERS=$NUM_SERVERS"
echo "NUM_CLIENTS=$NUM_CLIENTS"
echo "STRATEGY=$STRATEGY"

# create logs, results folder
mkdir -p logs results

# clear old files
rm -f logs/*
rm -f results/*

# start cleanup
pkill -9 -f "python3 server.py" 2>/dev/null
pkill -9 -f "python3 selection_server.py" 2>/dev/null
sleep 1

# run experiment
echo "Starting $NUM_SERVERS servers..."

for ((i=1;i<=NUM_SERVERS;i++)); do
  PORT=$((8000 + i))
  python3 server.py "$PORT" "content/server$i" "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY"> "logs/server_$i.txt" 2>&1 &
done

sleep 2

echo "Starting selection server..."
python3 selection_server.py "$NUM_SERVERS" "$NUM_CLIENTS" "$STRATEGY" > logs/selection_server.txt 2>&1 &

sleep 1

echo "Starting $NUM_CLIENTS clients..."

client_pids=()

for ((i=1;i<=NUM_CLIENTS;i++)); do
  python3 client.py "$NUM_SERVERS" "$NUM_CLIENTS" "$i" "$STRATEGY" > "logs/client_$i.txt" 2>&1 &
  client_pids+=($!)
done

for pid in "${client_pids[@]}"; do
  wait "$pid"
done

# end cleanup
pkill -f "python3 server.py" 2>/dev/null
pkill -f "python3 selection_server.py" 2>/dev/null

echo "Done"