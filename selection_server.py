# selection_server.py
# Purpose:
# - Receive client request
# - Choose best content server
# - Return selected server address

import sys
import os
import csv
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.request
import json
import time
from enum import Enum

class Strategy(Enum):
    LATENCY = "latency"
    LATENCY_LOAD = "latency-load"

OUTPUT_LOCK = threading.Lock()

def parse_args():
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        print("Usage: python3 selection_server.py <num_servers> <num_clients> <strategy> [trial] [base_dir]")
        print("Strategies: latency | latency-load")
        sys.exit(1)
    
    try:
        num_servers = int(sys.argv[1])
        num_clients = int(sys.argv[2])
        if len(sys.argv) == 5:
            trial = int(sys.argv[4])
        else:
            trial = 1
            base_dir = os.getcwd()
        
        if len(sys.argv) >= 5:
            if sys.argv[4].isdigit(): # trial
                trial = int(sys.argv[4])
            else:
                base_dir = sys.argv[4] 
        
        if len(sys.argv) == 6:
            base_dir = sys.argv[5]
    
            
    except ValueError:
        print("num_servers and num_clients and trial must be integers")
        sys.exit(1)
    
    try:
        strategy = Strategy(sys.argv[3])
    except ValueError:
        print("Invalid strategy. Usage: latency or latency-load")
        sys.exit(1)
    
    return num_servers, num_clients, strategy, trial, base_dir

def get_latency(server):
    # Measure latency
    url = f"{server}/{CONTENT_NAME}/manifest.json"
    try:
        start = time.perf_counter()
        with urllib.request.urlopen(url, timeout=2) as r:
            r.read(1) # read only first byte
        end = time.perf_counter()
        return end - start
    except: # for failed server
        return float('inf')

def get_load(server):
    try:
        with urllib.request.urlopen(f"{server}/load") as r:
            data = json.loads(r.read().decode())
            return data["load"]
    except: # for failed server
        return float('inf')

def compute_cost(latency, load):
    if STRATEGY == Strategy.LATENCY:
        return latency
    elif STRATEGY == Strategy.LATENCY_LOAD:
        return latency + 0.005 * load
    
def select_best_server():
    best_cost = float('inf')
    best_server = None
    
    latencies = {}
    loads = {}

    for server in SERVERS:
        lat = get_latency(server)
        load = get_load(server)
        cost = compute_cost(lat, load)
        
        latencies[server] = lat
        loads[server] = load
        
        if cost < best_cost:
            best_cost = cost
            best_server = server
    
    return best_server, latencies, loads

def write_result(best_server, latencies, loads):
    row = { 
        "strategy": STRATEGY.value,
        "chosen_server": best_server 
    }

    for server, lat in latencies.items():
        port = server.split(":")[-1]
        row[f"lat_{port}"] = lat
    
    for server, load in loads.items():
        port = server.split(":")[-1]
        row[f"load_{port}"] = load

    with OUTPUT_LOCK:
        file_exists = os.path.exists(RESULT_FILE)
        with open(RESULT_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())

            if not file_exists:
                writer.writeheader()
            
            writer.writerow(row)

class SelectionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Handle client request

        # Choose best server
        best_server, latencies, loads = select_best_server()

        if best_server is not None:
            write_result(best_server, latencies, loads)

        response = {
            "server": best_server
        }

        # Send response back to client
        self.send_response(200) # 200 = success
        self.send_header("Content-type", "application/json") # JSON response type
        self.end_headers() # Done sending header
        self.wfile.write(json.dumps(response).encode()) # python dict -> JSON string -> bytes

def run():
    server = ThreadingHTTPServer(("localhost", 8000), SelectionHandler)
    print("Threaded Selection server running...")
    server.serve_forever()


if __name__ == "__main__":
    NUM_SERVERS, NUM_CLIENTS, STRATEGY, TRIAL, BASE_DIR = parse_args()

    # List of available content servers
    SERVERS = []
    for i in range(1, NUM_SERVERS + 1):
        PORT = 8000 + i
        SERVERS.append(f"http://localhost:{PORT}")

    CONTENT_NAME = "sample1"
    RESULTS_DIR = os.path.join(BASE_DIR, "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    RESULT_FILE = os.path.join(RESULTS_DIR, f"s{NUM_SERVERS}_c{NUM_CLIENTS}_{STRATEGY.value}_t{TRIAL}_selection.csv")
    
    run()
