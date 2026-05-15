# Assignment and Solver Audit

## Assignment Overview

The case is the VeRoLog multi-day tool routing problem. Every customer request asks for a quantity of one tool type at one location. The solver must choose a delivery day inside the request's delivery window. Once a delivery day is chosen, the pickup day is forced:

```text
pickup_day = delivery_day + request_duration
```

The assignment therefore has three coupled subproblems:

- **Scheduling:** choose delivery days for all requests while respecting tool availability over the planning horizon.
- **Daily routing:** for each day, route all deliveries and pickups using vehicles that start/end at the depot, obey vehicle capacity, and obey maximum daily route distance.
- **Inventory accounting:** model tools loaded from the depot, tools picked up, tools reused inside a route, and tools returned to the depot.

The objective minimized by the code and validator is:

```text
VEHICLE_COST * maximum vehicles used on any day
+ VEHICLE_DAY_COST * total number of vehicle routes over all days
+ DISTANCE_COST * total distance
+ sum(tool_use[type] * tool_cost[type])
```

This is not a plain CVRP. It combines multi-day scheduling, capacitated routing, distance-constrained routing, pickup/delivery behavior, and scarce inventory.

## Current Program Flow

The top-level flow starts in `src/Solver.py`.

1. Parse the instance with `InstanceCVRPTWUI`.
2. Run the Baseline solver.
3. Run the main metaheuristic solver.
4. Write the solution file with `output_formatter.write_solution`.
5. Run the official validator.
6. Compare the produced solution to the current reference/optimal file.

The main solver is still named `Simulated Annealing`, but the actual method is:

```text
multi-start constructive scheduling
+ savings-first daily routing
+ bounded daily routing portfolio improvement
+ simulated annealing over delivery days
+ bounded large-neighborhood repair
+ route merge/local-search post-processing
```

This name is shorter than the actual algorithm. In explanations and reports, describe it as a hybrid SA/large-neighborhood heuristic.

## Scheduling Logic

The internal state is:

```python
start_days = {request_id: delivery_day}
```

Pickup days are never optimized independently. They are derived from the assignment rule:

```python
pickup_day = start_day + req.numDays
```

`generate_initial_solution()` evaluates several starting schedules:

- baseline schedule,
- tool-balanced schedule,
- vehicle-day-clustered schedule,
- distance-clustered schedule.

Each candidate schedule is routed and fully costed. The solver keeps the cheapest full solution, not merely the schedule that looks locally good.

## Daily Routing Logic

The default routing mode is `savings`. This keeps runtime predictable. Other modes such as `greedy`, `regret`, and `seeded_regret` remain available for controlled experiments.

For a daily task set, the routing portfolio tries feasible route constructors:

- **greedy:** nearest feasible next task.
- **savings:** Clarke-Wright-style route merging using depot savings.
- **insertion:** insert a task into the route position with lowest marginal cost.
- **regret:** prioritize tasks whose second-best insertion is much worse than the best insertion.
- **seeded regret:** start routes from difficult/far/high-cost tasks, then apply regret insertion.
- **repair variants:** run local route improvement after construction.

The fast path first constructs a daily route plan with the selected method, normally `savings`. Then the schedule-level portfolio may replace an affected day route only if another constructor improves the full objective. This means savings is the baseline route, while the portfolio acts as a bounded improvement layer.

## Thresholds

The portfolio has named runtime guardrails:

```python
INSERTION_TASK_LIMIT = 36
REGRET_TASK_LIMIT = 28
SEEDED_REGRET_TASK_LIMIT = 34
REPAIR_TASK_LIMIT = 32
EXACT_TOOL_REPAIR_LIMIT = 12
```

These are **not theoretical constants** from the assignment or lecture slides. They are empirical runtime limits. Their purpose is to prevent expensive insertion/regret/local-search routines from being called on very large daily task sets during repeated SA/repair evaluations. This is defensible as an engineering guardrail, but the values should be benchmarked if time permits.

## Route Local Search

The daily repair stage includes:

- swaps inside a route,
- single-task relocation inside a route,
- route merges.

Heavier neighborhoods such as full 2-opt and inter-route single-task relocation were considered, but intentionally not enabled because runtime is a priority for this solver.

## Tool-Use Semantics

The assignment narrative describes tools as being in use while located at customers. The provided validator computes tool use from depot inventory shortage after loading and before daily returns. The code follows the validator, because validator consistency is required for accepted solutions.

This creates an apparent off-by-one: pickup-day tools still count until the pickup route has returned them. In the report, explain this as modeling **tool availability to the depot**, not only physical presence at customers.

## ALNS / Large-Neighborhood Repair

The repair phase removes requests and reinserts them. Destroy focus is based on objective pressure:

- tools: target requests around peak tool-use days,
- vehicle-days/fixed vehicles: target busy days,
- distance: target distance-heavy/geographically related requests.

When the strategy is `auto`, the solver chooses one dominant objective pressure from the current solution and keeps that focus during the repair run. This is a lightweight large-neighborhood search, not a full adaptive ALNS with scored operator portfolios.

The exact tool-focused repair path is retained from the historical savings-default solver for reproducibility and runtime. Conceptually it evaluates exact full-cost insertion consequences for small removed sets, but it is intentionally conservative and does not run an expensive full repair refinement loop.

## Current Resolved Issues

- Removed dead helpers from `output_formatter.py`.
- Removed dead wrapper/local scoring helpers from `simulated_annealing_solver.py`.
- Aligned CLI and programmatic routing defaults around `savings`.
- Changed solution output `NAME` back to the actual instance name.
- Added named routing thresholds.
- Added `.gitignore` entries for Python caches, `.DS_Store`, and Codex-generated experiment folders.

## Explicitly Not Changed

`src/InstanceCVRPTWUI.py` is intentionally untouched per user instruction. The XML cost parsing observation remains a known audit note, but the current work does not modify that file.

## Remaining Caveats

- The routing thresholds are still empirical and should be justified through benchmark results if included in a formal report.
- The repair search is lightweight. It uses destroy/repair ideas from ALNS, but it does not adapt operator weights and should be described as ALNS-inspired rather than a full ALNS implementation.
- The algorithm name `Simulated Annealing` is still shorter than the true hybrid method. This is acceptable for file naming, but the report should use the fuller description.
- The default daily route followed by portfolio improvement has some conceptual overlap, but it is retained because the savings-first baseline is faster and more predictable than full portfolio routing as the default.
