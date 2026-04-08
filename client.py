# client.py
# Purpose:
# - Request server
# - Download manifest
# - Download segments

import urllib.request
import urllib.error
import http.client
import json
import time
import sys
import os
import csv

SOURCE_SELECTOR = "http://localhost:8000"
CONTENT_NAME = "sample1"
MAX_RETRIES = 3 # if server goes down mid way (for redirection logic)
MAX_SEG_RETRIES = 7

def get_server():
    # request for best server from source selection server
    with urllib.request.urlopen(SOURCE_SELECTOR) as r:
        data = json.loads(r.read().decode())
    content_server = data['server'] # need to get the "http://localhost:{portnum}" 
    print("Using server:", content_server, flush=True)
    return content_server

def fetch_manifest(content_server, content_name, retries=0):
    # request manifest from recommended content server
    if retries >= MAX_RETRIES:
        print("Could not retrieve manifest from any server")
        return None, None
    try:
        with urllib.request.urlopen(f'{content_server}/{content_name}/manifest.json') as r:
            manifest = json.loads(r.read().decode())
        print("Manifest received:", manifest, flush=True)
        return manifest, manifest['num_segments'] # return the manifest content and the total seg count
    except urllib.error.URLError as e:
        print(f"Server {content_server} failed ({e.reason}), getting new server")
        new_server = get_server()
        return fetch_manifest(new_server, content_name, retries + 1)
    

def fetch_seg(seg, server, content_name, retries=0):
    if retries >= MAX_SEG_RETRIES:
        print(f"Max retries attempted for {seg}, returning None")
        return None
    try:
        url = f'{server}/{content_name}/{seg}'
        with urllib.request.urlopen(url, timeout=5) as r:
            """
            for text, add .decocde()
            """
            content = r.read()
        return content, server # returns the segment, server in case it changed midway 
    except (urllib.error.URLError, http.client.IncompleteRead, ConnectionResetError, TimeoutError, OSError) as e:
        # server down before or during transfer
        msg = getattr(e, "reason", str(e))
        print(f"Content Server {server} failed ({msg}), retry with new server")
        server = get_server()
        return fetch_seg(seg, server, content_name, retries + 1)
    

def write_results(init_server, final_server, time_server, time_download, total_segments):
    results_dir = os.path.join(BASE_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)

    result_file = os.path.join(results_dir, f"s{NUM_SERVERS}_c{NUM_CLIENTS}_{STRATEGY}_t{TRIAL}_client{CLIENT_ID}.csv")
    file_exists = os.path.exists(result_file)

    with open(result_file, "a", newline="") as f:
        writer = csv.writer(f)

        # Write header
        if not file_exists:
            writer.writerow([
                "strategy",
                "client_id",
                "num_servers",
                "num_clients",
                "initial_server",
                "final_server",
                "time_server",
                "time_download",
                "total_segments"
            ])

        # Write data
        writer.writerow([
            STRATEGY,
            CLIENT_ID,
            NUM_SERVERS,
            NUM_CLIENTS,
            init_server,
            final_server,
            time_server,
            time_download,
            total_segments
        ])

def client_runner():

    # Get server from selector
    start = time.perf_counter()
    server = get_server()
    end = time.perf_counter()

    time_server = end - start   # time to get server
    init_server = server        # save initial choice

    # Fetch manifest
    start = time.perf_counter()
    manifest, total = fetch_manifest(server, CONTENT_NAME)

    # currently assuming server won't fail when getting manifest
    if manifest is None:
        print("Could not retrieve manifest, aborting")
        return

    # Download segments
    success = True
    for i, seg in enumerate(manifest['segments'], start=1):
        print(f"[{i}/{total}] Downloading {seg} from {server}...", flush=True)
        result = fetch_seg(seg, server, CONTENT_NAME)
        if result is None:
            print("Invalid content")
            success = False
            continue
        content, server = result
    
    end = time.perf_counter()
    time_download = end - start # total download time (manifest + segments)

    if success:
        write_results(
            init_server=init_server,
            final_server=server,
            time_server=time_server,
            time_download=time_download,
            total_segments=total,
        )

if __name__ == "__main__":
    if len(sys.argv) < 5 or len(sys.argv) > 7:
        print("Usage: python3 client.py <num_servers> <num_clients> <client_id> <strategy> [trial] [base_dir]")
        sys.exit(1)

    NUM_SERVERS = int(sys.argv[1])
    NUM_CLIENTS = int(sys.argv[2])
    CLIENT_ID = int(sys.argv[3])
    STRATEGY = sys.argv[4]

    # Optional trial
    if len(sys.argv) == 6:
        TRIAL = int(sys.argv[5])
    else:
        TRIAL = 1
        BASE_DIR = os.getcwd()
    
    # optional parsing
    if len(sys.argv) >= 6:
        if sys.argv[5].isdigit():
            TRIAL = int(sys.argv[5])
        else:
            BASE_DIR = sys.argv[5]

    if len(sys.argv) == 7:
        BASE_DIR = sys.argv[6]

    client_runner()