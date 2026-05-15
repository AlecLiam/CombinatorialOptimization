# Combinatorial Optimization Case Solver

This repository contains a solver for the CVRPTWUI case instances. The solver chooses delivery days for requests, builds daily vehicle routes for deliveries and pickups, validates the resulting solution, and writes the current run outputs to the `results/` directory.

## Running

Run all instances with the default production settings:

```bash
python3 src/Solver.py
```

Run selected instances:

```bash
python3 src/Solver.py B1.txt B2.txt B3.txt
```

The production run writes:

- per-algorithm solutions under `results/<instance>/<algorithm>/`
- the best valid solution from the current run under `results/<instance>/optimal_solution/`
- a summary table at `results/benchmark_summary.csv`

Use `--no-visuals` for faster test runs without route plots and GIFs.

## Main Settings

The default production settings are:

```text
sa-runs = 3
sa-seed = 42
sa-seed-count = 3
routing-method = savings
alns-iterations = 30
```

These defaults are deterministic for a fixed code version and input set.

## Experiment Mode

Experiment mode writes isolated outputs under `experiments/<name>/` and compares them against the current `results/` folder:

```bash
python3 src/Solver.py B3.txt --experiment b3_test --no-visuals
```

Experiment mode is intended for local testing only.
