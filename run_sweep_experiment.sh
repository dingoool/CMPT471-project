#!/bin/bash

# for batch test running, based off run_experiment.sh

FIXED=5
SWEEP_MIN=1
SWEEP_MAX=10
SWEEP_DIR="sweep_results"

# segments per sample (SAMPLE_SEGMENTS[1]=3, SAMPLE_SEGMENTS[2]=5)
declare -A SAMPLE_SEGMENTS=([1]=3 [2]=5)

mkdir -p "$SWEEP_DIR"

# generate server content for each sweep as needed
generate_content() {
  local num_servers=$1
  rm -rf content/ 

  # create the server# sample dir, manifests, and segment files
  for ((i=1; i<=num_servers; i++)); do
    local server_dir="content/server$i"
    mkdir -p "$server_dir"
    for samp in "${!SAMPLE_SEGMENTS[@]}"; do
      local num_segs=${SAMPLE_SEGMENTS[$samp]}
      local sample_dir="$server_dir/sample$samp"
      mkdir -p "$sample_dir"

      for ((seg=1; seg<=num_segs; seg++)); do
        echo "sample $samp segment $seg" > "$sample_dir/segment${seg}.txt"
      done

      seg_entries=""
      for ((seg=1; seg<=num_segs; seg++)); do
        if [ $seg -lt $num_segs ]; then
          seg_entries+="    \"segment${seg}.txt\","$'\n'
        else
          seg_entries+="    \"segment${seg}.txt\""$'\n'
        fi
      done

      cat > "$sample_dir/manifest.json" << MANIFEST
{
  "content": "sample${samp}",
  "num_segments": ${num_segs},
  "segments": [
${seg_entries}  ]
}
MANIFEST
    done
  done
  echo "   Content for each $num_servers server(s) ready"
}

run_experiment() {
  local num_servers=$1
  local num_clients=$2
  local label=$3
  local out_dir="$SWEEP_DIR/$label"

  # create this run's output and results folder
  mkdir -p "$out_dir"
  mkdir -p "$out_dir/results"

  generate_content "$num_servers"

  # isolate results per run
  rm -rf results
  ln -sfn "$out_dir/results" results

  # cleanup stale processes
  pkill -9 -f "python3 server.py" 2>/dev/null
  pkill -9 -f "python3 selection_server.py" 2>/dev/null
  sleep 1

  # start servers, logs directly into out_dir
  for ((i=1;i<=num_servers;i++)); do
    PORT=$((8000 + i))
    python3 server.py "$PORT" "content/server$i" "$num_servers" "$num_clients" > "${out_dir}/server_${i}.txt" 2>&1 &
  done
  sleep 2

  # start selection server
  python3 selection_server.py "$num_servers" "$num_clients" > "${out_dir}/selection_server.txt" 2>&1 &
  sleep 1

  # start clients
  client_pids=()
  for ((i=1;i<=num_clients;i++)); do
    python3 client.py "$num_servers" "$num_clients" "$i" > "${out_dir}/client_${i}.txt" 2>&1 &
    client_pids+=($!)
  done

  for pid in "${client_pids[@]}"; do
    wait "$pid"
  done

  # cleanup
  pkill -f "python3 server.py" 2>/dev/null
  pkill -f "python3 selection_server.py" 2>/dev/null

  echo "   Saved to $out_dir"
}

# sweep 1: fixed servers, vary clients 
echo "----------------------------------------"
echo "Sweep 1: Fixed servers=$FIXED, clients $SWEEP_MIN..$SWEEP_MAX"
echo "----------------------------------------"
for ((c=SWEEP_MIN; c<=SWEEP_MAX; c++)); do
  run_experiment "$FIXED" "$c" "fixed_servers_${FIXED}__clients_${c}"
done

# sweep 2: fixed clients, vary servers 
echo ""
echo "----------------------------------------"
echo "Sweep 2: Fixed clients=$FIXED, servers $SWEEP_MIN..$SWEEP_MAX"
echo "----------------------------------------"
for ((s=SWEEP_MIN; s<=SWEEP_MAX; s++)); do
  run_experiment "$s" "$FIXED" "fixed_clients_${FIXED}__servers_${s}"
done

echo ""
echo "All sweeps done. Run: python3 latency_load_plot.py for analysis"