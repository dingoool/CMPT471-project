# CMPT471-project

**Setting up Testing Environment:**

1. In the root directory, run `./create_content.sh [num_servers]`
2. To run predefined test procedures, run `./run_tests.sh <mode> [num_servers] [num_trials]`
   - MODE = "normal" (varies clients 1–10, no failure over the 2 strategies)
   - MODE = "failure" (fixed 10 clients, with failure simulation). Only 1 server fails.