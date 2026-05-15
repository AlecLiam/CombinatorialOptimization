# CombinatorialOptimization

You’re right. My previous answer explained the machinery, but it did not sufficiently tie the machinery to the assignment logic. Let me rebuild it from first principles.

**The Assignment**
The assignment is not a normal “visit customers once” VRP. It has three coupled problems:

1. **Scheduling over days**  
   For every request, choose a delivery day inside its allowed delivery window. If request `r` is delivered on day `d`, then its pickup is forced on day:

   ```text
   pickup_day = d + req.numDays
   ```

   So the solver does not choose pickup days independently.

2. **Routing within each day**  
   Once delivery days are chosen, each day has a set of delivery and pickup tasks. The solver must create vehicle routes for that day. Each route starts and ends at the depot, respects vehicle capacity, and respects max route distance.

3. **Tool inventory / reuse**  
   Tools are scarce and costly. A route may pick up tools and later deliver tools of the same type in the same route. This can reduce how many tools need to be “owned” globally.

The objective combines:

```text
fixed vehicle cost
+ vehicle-day cost
+ distance cost
+ tool-use cost
```

So a good solution must balance fewer vehicles, fewer routes, shorter routes, and fewer tools.

**Chronological Flow**
The program starts in [Solver.py](/Users/ahmedelghani/CO_case/CombinatorialOptimization/src/Solver.py:34).

1. Parse the instance.
2. Run Baseline.
3. Run Simulated Annealing.
4. Write solution.
5. Validate with the official validator.
6. Keep the result if valid and useful.

The real solver is `solve_sa()` in [simulated_annealing_solver.py](/Users/ahmedelghani/CO_case/CombinatorialOptimization/src/algorithms/simulated_annealing_solver.py:2863).

Its chronological order is:

```text
choose routing method default
generate initial delivery schedule
route all days
improve daily routes by portfolio
run simulated annealing over delivery-day choices
run ALNS destroy/repair
merge routes as post-processing
return final schedule
```

**Step 1: Initial Scheduling**
The first important decision is not routing. It is scheduling.

`generate_initial_solution()` creates several complete candidate schedules:

```python
("baseline", generate_baseline_start_days(instance))
("tool-balanced", generate_tool_balanced_start_days(instance))
("vehicle-day-clustered", generate_vehicle_day_clustered_start_days(instance))
("distance-clustered", generate_distance_clustered_start_days(instance))
```

This is in [simulated_annealing_solver.py](/Users/ahmedelghani/CO_case/CombinatorialOptimization/src/algorithms/simulated_annealing_solver.py:1778).

Conceptually:

- **baseline**: find any feasible schedule.
- **tool-balanced**: spread requests so peak tool use is lower.
- **vehicle-day-clustered**: put tasks on already active days to reduce number of used vehicle-days.
- **distance-clustered**: put geographically close requests on the same days so routes can be shorter.

Each candidate schedule is routed and evaluated. The solver picks the cheapest full solution, not just the prettiest schedule.

That is appropriate for the assignment because a schedule is only good if it produces good routes and good inventory use. A schedule that minimizes tools could still create terrible routes. A schedule that clusters distance could exceed tool inventory. So the code evaluates the whole objective.

**Step 2: Convert Schedule To Daily Tasks**
Once a delivery day is chosen, the code builds daily tasks:

```text
if delivery day is d: add delivery task on d
if pickup day is d + numDays: add pickup task there
```

This happens in `build_tasks_by_day()`.

At this moment, the multi-day assignment becomes many smaller daily routing problems.

For example:

```text
Day 4:
  deliver request 12
  deliver request 30
  pick up request 7
```

Now the routing heuristic only sees same-day tasks.

**Step 3: Primary Daily Routing**
The default method is currently `savings`.

That means when the code first routes a day, it starts with `route_day_savings()`.

This is based on the Clarke-Wright savings heuristic from classical VRP theory. The idea is:

Instead of serving two customers separately:

```text
0 -> A -> 0
0 -> B -> 0
```

combine them:

```text
0 -> A -> B -> 0
```

The distance saving is approximately:

```text
distance(0,A) + distance(0,B) - distance(A,B)
```

In the code, this appears in `route_day_savings()`.

Why this makes sense for the assignment:

- The assignment charges per vehicle-day.
- A route per task is valid but expensive.
- Savings directly tries to merge singleton routes.
- Merging routes can reduce vehicle-days and distance.
- The distances are Euclidean-like and symmetric, which is exactly the setting where Clarke-Wright-style savings is reasonable.

But the implementation cannot blindly merge. It must check assignment-specific constraints:

- Does the merged route exceed max distance?
- Does vehicle load exceed capacity?
- Are tools loaded/picked up in a valid sequence?
- Does a pickup before delivery make sense for route inventory?
- Can picked-up tools be reused later in the same route?

So every candidate route is passed through `build_trip_from_route()`, which validates route feasibility using the same semantics as the validator.

This is why the savings heuristic is conceptually appropriate: it is classical VRP route merging, adapted to the assignment’s tool-capacity constraints.

**Step 4: Automatic Routing Portfolio**
This is the part that matters most for your concern.

Even though the default is `savings`, the solver does not only use savings.

After a day is routed, the code calls:

```python
improve_affected_days_by_portfolio(...)
```

This function tries several routing methods for the same day and keeps the one that improves the full objective.

The portfolio is defined here:

[simulated_annealing_solver.py](/Users/ahmedelghani/CO_case/CombinatorialOptimization/src/algorithms/simulated_annealing_solver.py:1421)

```python
methods = ["greedy", "savings"]
if len(tasks) <= 36:
    methods.append("insertion")
if len(tasks) <= 28:
    methods.append("regret")
if len(tasks) <= 34:
    methods.append("seeded_regret")
```

Then for each method, it also tries a `_repair` version if the day has at most 32 tasks.

So the actual logic is:

```text
try greedy
try savings
if small enough, try insertion
if small enough, try regret
if small enough, try seeded regret
if small enough, try local-search repaired versions
choose the candidate that gives the lowest full objective
```

The solver does not choose by theory alone. It chooses by computed cost.

**What Each Routing Heuristic Means**
`greedy`

This is nearest-neighbor construction.

Conceptually:

```text
start at depot
pick the nearest feasible task
append it to the route
repeat until no more feasible task fits
start a new route
```

It is greedy with respect to immediate travel distance from the current vehicle location. It is not globally optimal.

Why needed:

- Very fast.
- Reliable fallback.
- Useful for large task days where expensive methods may be too slow.
- Gives a basic feasible structure.

`savings`

As explained, this starts from one route per task and merges routes if doing so saves distance and remains feasible.

Why needed:

- Strong classical VRP construction heuristic.
- Particularly appropriate when reducing vehicle-days and distance matters.
- Good default because the assignment heavily penalizes route count and distance.

`insertion`

Insertion builds routes by placing a task at the position where it causes the smallest extra cost.

Instead of saying:

```text
append next customer at the end
```

it asks:

```text
where in an existing route would this task fit best?
```

Example:

```text
current route: 0 -> A -> C -> 0
new task: B
possible insertions:
0 -> B -> A -> C -> 0
0 -> A -> B -> C -> 0
0 -> A -> C -> B -> 0
```

It chooses the feasible insertion with the smallest distance increase.

Why needed:

- Better than nearest-neighbor when task order matters.
- Useful for dense days where many tasks can fit into the same route.
- More expensive than greedy/savings.

`regret`

Regret insertion asks:

```text
If I do not insert this task now, how bad will my future options become?
```

For each unassigned task, it compares the best insertion option to the second-best option. If the gap is large, delaying that task is risky. That task gets priority.

Why needed:

- Some requests are hard to place because of distance, capacity, or tool sequence.
- Greedy insertion may postpone hard tasks until they no longer fit well.
- Regret is a standard VRP construction idea for constrained routing.

`seeded_regret`

Seeded regret first chooses strong route seeds: far, expensive, difficult tasks. Then it uses regret insertion around them.

Why needed:

- If you start routes badly, regret insertion can still be trapped.
- Seeding creates multiple route “centers” early.
- This helps when there are geographically separated clusters.

`*_repair`

The `_repair` methods first construct routes, then run local improvement.

The repair step tries:

- swapping task order inside a route,
- relocating tasks inside a route,
- merging compatible routes.

This corresponds to local search theory from VRP heuristics: construct first, then improve by neighborhood moves.

**How A Routing Strategy Is Chosen**
There are two different levels.

First-level choice:

```text
use default routing method, currently savings
```

This is the initial constructor.

Second-level choice:

```text
portfolio tries multiple routing methods
evaluate each full candidate
keep the one that improves total cost
```

So the real decision is not:

```text
We believe savings is always best.
```

It is:

```text
Start with savings because it is a strong, cheap VRP construction heuristic.
Then test alternatives when the daily task count is small enough.
Keep whatever improves the actual assignment objective.
```

That is important: the code does not choose based only on distance. It evaluates total cost, including vehicles, vehicle-days, distance, and tool-use.

**Step 5: Simulated Annealing**
Simulated annealing does not primarily change route order. It changes delivery days.

Why?

Because in this assignment, the biggest decision is often:

```text
When should each request be delivered?
```

Moving one delivery changes:

- its delivery day,
- its pickup day,
- tool overlap,
- daily routing tasks,
- possible route combinations,
- vehicle-days,
- distance,
- tool-use cost.

SA proposes neighboring schedules:

- move one request,
- swap two delivery days,
- shift related requests,
- target requests based on dominant cost component.

Then it reroutes only affected days.

Acceptance rule:

- If new cost is better: accept.
- If worse: maybe accept with probability:

```text
exp(-cost_increase / temperature)
```

At high temperature, worse moves can be accepted. This helps escape local optima. At low temperature, the search becomes more conservative.

This is appropriate theory-wise because the assignment search space is huge and non-convex. Exact methods would be too slow. SA is a metaheuristic for escaping local minima.

**Step 6: ALNS**
After SA, the code optionally runs ALNS.

ALNS means Adaptive Large Neighborhood Search. This code is not fully adaptive in the classic operator-weight sense, but it does use large destroy/repair neighborhoods.

Conceptually:

```text
remove several requests from the schedule
reinsert them better
reroute affected days
accept or reject the new full solution
```

Destroy strategy depends on the dominant cost component:

- If tools dominate: remove requests around the peak tool-use day.
- If vehicle-days or fixed vehicles dominate: remove requests around busy days.
- If distance dominates: remove geographically related requests.

Repair strategy:

- If distance dominates: use greedy repair.
- Otherwise: use regret repair.

Why?

If distance dominates, quick geographical repair is reasonable.  
If tools/vehicles dominate, regret repair is better because placement flexibility matters more.

**Your Concrete Question: Why 34, 28, 36?**
These values are here:

```python
if len(tasks) <= 36:
    methods.append("insertion")
if len(tasks) <= 28:
    methods.append("regret")
if len(tasks) <= 34:
    methods.append("seeded_regret")
```

They are not from the assignment.

They are not from Clarke-Wright theory.

They are not mathematically justified.

They are implementation thresholds, almost certainly empirical runtime guards.

Why are thresholds needed at all?

Because these methods have different computational cost.

- `greedy` is cheap.
- `savings` is relatively cheap.
- `insertion` checks many insertion positions.
- `regret` checks insertion options for many tasks repeatedly.
- `seeded_regret` also evaluates many combinations.

As the number of tasks on a day grows, insertion/regret methods become expensive. So the code limits them to days with “not too many” tasks.

But are `36`, `28`, and `34` correct?

Strictly speaking: **we cannot say they are correct from theory.**

They are plausible, but arbitrary. A better implementation would base this on:

- actual runtime budget,
- instance size,
- number of days,
- number of requests,
- average tasks per day,
- observed time per routing method,
- whether previous uses of a method improved the solution.

For example, a more principled version would say:

```text
Try all routing methods until a per-day time budget is exhausted.
Track which methods actually improve cost.
Use heavier methods only when they historically help.
```

That would be closer to true adaptive heuristic design.

So your instinct is right: those numbers are not theoretically grounded. They are engineering cutoffs.

**Is The Current Logic Bad?**
Not completely.

The idea is good:

```text
cheap methods always
expensive methods only for smaller days
choose by actual objective
```

That is a sensible heuristic design.

But the exact numbers are weakly justified. They should be described in the report as empirical thresholds, not theory.

If you want the code to be cleaner and more defensible, I would replace those constants with named parameters:

```python
INSERTION_TASK_LIMIT = 36
REGRET_TASK_LIMIT = 28
SEEDED_REGRET_TASK_LIMIT = 34
REPAIR_TASK_LIMIT = 32
```

And document:

```text
These are runtime guardrails chosen empirically; they are not theoretical constants.
```

Even better, benchmark them.

**The Most Important Conceptual Summary**
The assignment requires solving a coupled scheduling-routing-inventory problem.

The code handles this by:

1. Choosing delivery days.
2. Deriving pickup days.
3. Creating daily task sets.
4. Routing each day using VRP construction heuristics.
5. Automatically comparing multiple route constructors when affordable.
6. Evaluating the full assignment objective.
7. Using SA to explore different schedules.
8. Using ALNS to make larger schedule changes.
9. Using route merge/local repair to reduce vehicle-days and distance.
10. Validating final feasibility with the official checker.

So the routing methods are not independent “manual modes” in the conceptual solver. They are candidate route constructors inside a larger search system. The default only chooses the first constructor; the portfolio and cost evaluation decide whether another routing strategy is better for a particular day.