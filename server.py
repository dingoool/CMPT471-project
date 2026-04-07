# server.py
# Purpose:
# - Receive client request
# - Handle client request

import sys
import os
import csv
import signal
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Lock

lock = Lock()

if len(sys.argv) < 6 or len(sys.argv) > 7:
    print("Usage: python3 server.py <port> <content_dir> <num_servers> <num_clients> <strategy> [trial]")
    sys.exit(1)

PORT = int(sys.argv[1])
CONTENT_DIR = sys.argv[2]
NUM_SERVERS = int(sys.argv[3])
NUM_CLIENTS = int(sys.argv[4])
STRATEGY = sys.argv[5]

if len(sys.argv) == 7:
    TRIAL = int(sys.argv[6])
else:
    TRIAL = 1
    
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
RESULTS_DIR = os.path.abspath(RESULTS_DIR)

stats = {
    "total_req": 0,
    "manifest_req": 0,
    "segment_req": 0,
    "other_req": 0
}

# Change directory to serve files
#os.chdir(CONTENT_DIR) 

current_requests = 0

class MyHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        return os.path.join(CONTENT_DIR, path.lstrip("/"))
    def do_GET(self):
        global current_requests
        # Send server_load to selection server
        if self.path == "/load":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = f'{{"load": {current_requests}}}'
            self.wfile.write(response.encode())
            return
        
        with lock:
            # Request starts
            current_requests += 1 
            
        try:
            return super().do_GET()
        
        finally:
            with lock:
                current_requests -= 1
                # Count requests
                if self.path.endswith("manifest.json"): # change it to .mpd when using FFmpeg
                    stats["manifest_req"] += 1
                elif "segment" in self.path:
                    stats["segment_req"] += 1
                else:
                    stats["other_req"] += 1

                stats["total_req"] += 1
                #write_results()   
        
    
def write_results():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    result_file = os.path.join(RESULTS_DIR, f"s{NUM_SERVERS}_c{NUM_CLIENTS}_{STRATEGY}_t{TRIAL}_server{PORT}.csv")
    #file_exists = os.path.exists(result_file)

    with open(result_file, "w", newline="") as f:
        writer = csv.writer(f)
        # Write col name
        writer.writerow([
            "port",
            "content_dir",
            "strategy",
            "total_req",
            "manifest_req",
            "segment_req",
            "other_req"
        ])

        # Write results
        writer.writerow([
            PORT,
            CONTENT_DIR,
            STRATEGY,
            stats["total_req"],
            stats["manifest_req"],
            stats["segment_req"],
            stats["other_req"]
        ])

ThreadingHTTPServer.allow_reuse_address = True # for reconnecting after failures
server = ThreadingHTTPServer(("localhost", PORT), MyHandler)

def shutdown_handler(signum, frame):
    print(f"[Server {PORT}] Shutdown signal received", flush=True)
    write_results()
    print(f"[SERVER {PORT}] WRITE DONE", flush=True)

    #server.shutdown()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

print(f"Servering {CONTENT_DIR} on port {PORT}", flush=True)
server.serve_forever()