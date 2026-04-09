# CMPT471-project

## Video File Requirement

This project requires a video file to generate DASH content.
The video is **not included in the repository** due to its large size.

### Setup
1. Download any `.mp4` video file of your choice
2. Rename it to `mv.mp4`
3. Place it in the project root: `CMPT471-project/mv.mp4`

## Setting up Testing Environment:

From root directory:
1. Generate content:
```bash
./scripts/create_content.sh <num_servers>
```

2. Run predefined test procedures:
```bash
 run ./scripts/run_tests.sh <mode> [num_servers] [num_trials]
```
**Modes:**
   - **normal** 
      - Varies number of clients (2, 5, 10, 20, 30) 
      - No failures 
      - Compares both strategies
   - **failure** 
      - Fixed 10 clients 
      - Simulates server failure (1 server fails)

## Generating Plots

After running the experiments, you can generate plots from the collected results.

From the project root directory:

```bash
python3 scripts/plots.py
python3 scripts/plots_failure.py
```

This will read the result files from `results/normal/` and `results/failure/` and generates plots in `plots/`.

*Note: all plots and logs are removed/overwritten each run. Please save any of these to your own system if needed.*

