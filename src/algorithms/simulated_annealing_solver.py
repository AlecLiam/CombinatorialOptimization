import random
import math
from algorithms.baseline_solver import solve_baseline

ROUTING_METHOD = "greedy"
ROUTE_DAY_CACHE = {}

class SolverContext:
    def __init__(self, instance):
        self.requests = list(instance.Requests)
        self.requests_by_id = {req.ID: req for req in self.requests}
        self.tool_sizes = [get_tool_size(tool) for tool in instance.Tools]
        self.tool_costs = [tool.cost for tool in instance.Tools]
        self.tool_amounts = [tool.amount for tool in instance.Tools]
        self.num_tools = len(instance.Tools)
        self.depot = instance.DepotCoordinate
        self.extended_days = list(range(1, instance.Days + 2))
        self.planning_days = list(range(1, instance.Days + 1))

def get_context(instance):
    context = getattr(instance, "_solver_context", None)
    if context is None:
        context = SolverContext(instance)
        setattr(instance, "_solver_context", context)
    return context

def set_routing_method(method):
    global ROUTING_METHOD, ROUTE_DAY_CACHE
    if method not in ("greedy", "insertion", "regret", "greedy_repair", "insertion_repair", "regret_repair"):
        raise ValueError(f"Unknown routing method: {method}")
    ROUTING_METHOD = method
    ROUTE_DAY_CACHE = {}

def calculate_all_distances(instance):
    if instance.calcDistance is None:
        instance.calculateDistances()

def is_schedule_feasible(instance, start_days):
    num_tools = len(instance.Tools)
    daily_usage = {d: [0] * num_tools for d in range(1, instance.Days + 2)}
    
    for req in instance.Requests:
        sd = start_days[req.ID]
        for d in active_tool_days(instance, req, sd):
            if d <= instance.Days:
                daily_usage[d][req.tool - 1] += req.toolCount
                if daily_usage[d][req.tool - 1] > instance.Tools[req.tool - 1].amount:
                    return False
    return True

def active_tool_days(instance, req, start_day):
    last_active_day = min(start_day + req.numDays, instance.Days)
    return range(start_day, last_active_day + 1)

def get_tool_size(tool):
    for attr in ['size', 'Size', 'weight', 'Weight', 'volume', 'Volume', 'toolSize', 'tool_size']:
        if hasattr(tool, attr):
            return getattr(tool, attr)
    if hasattr(tool, '__dict__'):
        candidates = [v for k, v in tool.__dict__.items() if isinstance(v, (int, float)) and k.lower() not in ['id', 'amount', 'cost', 'tool', 'req']]
        if candidates: return candidates[0]
    return 1

def get_tasks_for_day(instance, start_days, day):
    return build_tasks_by_day(instance, start_days, days=[day]).get(day, [])

def build_tasks_by_day(instance, start_days, days=None):
    ctx = get_context(instance)
    if days is None:
        days = ctx.extended_days
    day_set = set(days)
    tasks_by_day = {day: [] for day in day_set}

    for req in ctx.requests:
        sd = start_days[req.ID]
        if sd in day_set:
            tasks_by_day[sd].append({"req": req, "type": "delivery"})
        pd = sd + req.numDays
        if pd in day_set and pd <= instance.Days:
            tasks_by_day[pd].append({"req": req, "type": "pickup"})

    return tasks_by_day

def evaluate_cost(instance, schedule_by_day):
    return evaluate_cost_components(instance, schedule_by_day)["total"]

def extract_start_days_from_schedule(instance, schedule):
    start_days = {}
    for day, trips in schedule.items():
        for trip in trips:
            route = trip["route"]
            for node_id in route[1:-1]:
                if node_id > 0 and node_id not in start_days:
                    start_days[node_id] = day

    if len(start_days) == len(instance.Requests):
        return start_days
    return None

def calculate_tool_use_from_start_days(instance, start_days):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    daily_usage = {day: [0] * num_tools for day in ctx.planning_days}

    for req in ctx.requests:
        if req.ID not in start_days:
            continue
        start_day = start_days[req.ID]
        for day in active_tool_days(instance, req, start_day):
            daily_usage[day][req.tool - 1] += req.toolCount

    if not daily_usage:
        return [0] * num_tools
    return [
        max(usage[tool_idx] for usage in daily_usage.values())
        for tool_idx in range(num_tools)
    ]

def calculate_validator_tool_use_from_schedule(instance, schedule_by_day):
    # Matches validator/Validate.py: tools used are the maximum shortage in depot inventory
    # implied by route loads and direct customer-to-customer reuse.
    num_tools = get_context(instance).num_tools
    simulated_inventory = [0] * num_tools
    min_inventory = [0] * num_tools

    for day in sorted(schedule_by_day.keys()):
        trips = schedule_by_day[day]
        for trip in trips:
            for i in range(num_tools):
                simulated_inventory[i] += trip["tools_loaded"][i]
        for i in range(num_tools):
            if simulated_inventory[i] < min_inventory[i]:
                min_inventory[i] = simulated_inventory[i]
        for trip in trips:
            for i in range(num_tools):
                simulated_inventory[i] += trip["tools_returned"][i]

    return [abs(x) for x in min_inventory]

def summarize_day_components(instance, trips):
    ctx = get_context(instance)
    loaded = [0] * ctx.num_tools
    returned = [0] * ctx.num_tools
    distance = 0

    for trip in trips:
        distance += trip["distance"]
        for idx in range(ctx.num_tools):
            loaded[idx] += trip["tools_loaded"][idx]
            returned[idx] += trip["tools_returned"][idx]

    return {
        "route_count": len(trips),
        "distance": distance,
        "loaded": loaded,
        "returned": returned,
    }

def calculate_validator_tool_use_from_daily_summaries(instance, daily_loaded, daily_returned):
    ctx = get_context(instance)
    inventory = [0] * ctx.num_tools
    min_inventory = [0] * ctx.num_tools
    inventory_after_day = {}
    min_after_day = {}

    for day in ctx.extended_days:
        loaded = daily_loaded.get(day, [0] * ctx.num_tools)
        returned = daily_returned.get(day, [0] * ctx.num_tools)
        for idx in range(ctx.num_tools):
            inventory[idx] += loaded[idx]
        for idx in range(ctx.num_tools):
            if inventory[idx] < min_inventory[idx]:
                min_inventory[idx] = inventory[idx]
        for idx in range(ctx.num_tools):
            inventory[idx] += returned[idx]

        inventory_after_day[day] = list(inventory)
        min_after_day[day] = list(min_inventory)

    return [abs(value) for value in min_inventory], inventory_after_day, min_after_day

def build_component_result(
    instance,
    tool_use,
    max_vehicles,
    vehicle_days,
    total_distance,
    customer_tool_use=None,
    daily_route_count=None,
    daily_distance=None,
    daily_loaded=None,
    daily_returned=None,
    inventory_after_day=None,
    min_after_day=None,
):
    ctx = get_context(instance)
    tool_cost = sum(tool_use[i] * ctx.tool_costs[i] for i in range(ctx.num_tools))

    veh_cost = getattr(instance, 'VehicleCost', 100000)
    veh_day_cost = getattr(instance, 'VehicleDayCost', 10000)
    dist_cost = getattr(instance, 'DistanceCost', 1)

    fixed_vehicle_cost = max_vehicles * veh_cost
    vehicle_day_cost = vehicle_days * veh_day_cost
    distance_cost = total_distance * dist_cost
    total = fixed_vehicle_cost + vehicle_day_cost + distance_cost + tool_cost

    return {
        "total": total,
        "fixed_vehicle": fixed_vehicle_cost,
        "vehicle_days": vehicle_day_cost,
        "distance": distance_cost,
        "tools": tool_cost,
        "max_vehicles": max_vehicles,
        "vehicle_day_count": vehicle_days,
        "total_distance": total_distance,
        "tool_use": tool_use,
        "customer_tool_use": customer_tool_use,
        "_daily_route_count": daily_route_count,
        "_daily_distance": daily_distance,
        "_daily_loaded": daily_loaded,
        "_daily_returned": daily_returned,
        "_inventory_after_day": inventory_after_day,
        "_min_after_day": min_after_day,
    }

def evaluate_cost_components(instance, schedule_by_day, include_customer_tool_use=False):
    ctx = get_context(instance)
    daily_route_count = {}
    daily_distance = {}
    daily_loaded = {}
    daily_returned = {}

    for day in ctx.extended_days:
        summary = summarize_day_components(instance, schedule_by_day.get(day, []))
        daily_route_count[day] = summary["route_count"]
        daily_distance[day] = summary["distance"]
        daily_loaded[day] = summary["loaded"]
        daily_returned[day] = summary["returned"]

    tool_use, inventory_after_day, min_after_day = calculate_validator_tool_use_from_daily_summaries(
        instance,
        daily_loaded,
        daily_returned,
    )
    customer_tool_use = None
    if include_customer_tool_use:
        start_days = extract_start_days_from_schedule(instance, schedule_by_day)
        customer_tool_use = (
            calculate_tool_use_from_start_days(instance, start_days)
            if start_days is not None
            else None
        )

    return build_component_result(
        instance,
        tool_use,
        max(daily_route_count.values(), default=0),
        sum(daily_route_count.values()),
        sum(daily_distance.values()),
        customer_tool_use=customer_tool_use,
        daily_route_count=daily_route_count,
        daily_distance=daily_distance,
        daily_loaded=daily_loaded,
        daily_returned=daily_returned,
        inventory_after_day=inventory_after_day,
        min_after_day=min_after_day,
    )

def evaluate_delta_cost_components(instance, old_components, new_schedule_by_day, affected_days):
    ctx = get_context(instance)
    affected_days = sorted(day for day in affected_days if day in ctx.extended_days)
    required_keys = (
        "_daily_route_count",
        "_daily_distance",
        "_daily_loaded",
        "_daily_returned",
        "_inventory_after_day",
        "_min_after_day",
    )
    if not affected_days or any(old_components.get(key) is None for key in required_keys):
        return evaluate_cost_components(instance, new_schedule_by_day)

    daily_route_count = dict(old_components["_daily_route_count"])
    daily_distance = dict(old_components["_daily_distance"])
    daily_loaded = {
        day: list(values)
        for day, values in old_components["_daily_loaded"].items()
    }
    daily_returned = {
        day: list(values)
        for day, values in old_components["_daily_returned"].items()
    }

    vehicle_days = old_components["vehicle_day_count"]
    total_distance = old_components["total_distance"]

    for day in affected_days:
        old_route_count = daily_route_count.get(day, 0)
        old_distance = daily_distance.get(day, 0)
        summary = summarize_day_components(instance, new_schedule_by_day.get(day, []))
        daily_route_count[day] = summary["route_count"]
        daily_distance[day] = summary["distance"]
        daily_loaded[day] = summary["loaded"]
        daily_returned[day] = summary["returned"]
        vehicle_days += summary["route_count"] - old_route_count
        total_distance += summary["distance"] - old_distance

    inventory_after_day = {
        day: list(values)
        for day, values in old_components["_inventory_after_day"].items()
    }
    min_after_day = {
        day: list(values)
        for day, values in old_components["_min_after_day"].items()
    }

    start_day = affected_days[0]
    previous_day = start_day - 1
    if previous_day in inventory_after_day:
        inventory = list(inventory_after_day[previous_day])
        min_inventory = list(min_after_day[previous_day])
    else:
        inventory = [0] * ctx.num_tools
        min_inventory = [0] * ctx.num_tools

    for day in range(start_day, ctx.extended_days[-1] + 1):
        loaded = daily_loaded.get(day, [0] * ctx.num_tools)
        returned = daily_returned.get(day, [0] * ctx.num_tools)
        for idx in range(ctx.num_tools):
            inventory[idx] += loaded[idx]
        for idx in range(ctx.num_tools):
            if inventory[idx] < min_inventory[idx]:
                min_inventory[idx] = inventory[idx]
        for idx in range(ctx.num_tools):
            inventory[idx] += returned[idx]
        inventory_after_day[day] = list(inventory)
        min_after_day[day] = list(min_inventory)

    tool_use = [abs(value) for value in min_inventory]

    return build_component_result(
        instance,
        tool_use,
        max(daily_route_count.values(), default=0),
        vehicle_days,
        total_distance,
        customer_tool_use=None,
        daily_route_count=daily_route_count,
        daily_distance=daily_distance,
        daily_loaded=daily_loaded,
        daily_returned=daily_returned,
        inventory_after_day=inventory_after_day,
        min_after_day=min_after_day,
    )

def components_within_tool_limits(instance, components):
    tool_amounts = get_context(instance).tool_amounts
    return all(
        used <= tool_amounts[idx]
        for idx, used in enumerate(components["tool_use"])
    )

def schedule_within_tool_limits(instance, schedule_by_day):
    return components_within_tool_limits(
        instance,
        evaluate_cost_components(instance, schedule_by_day),
    )

def build_trips_from_state(instance, start_days):
    ctx = get_context(instance)
    tasks_by_day = build_tasks_by_day(instance, start_days)
    trips_by_day = {day: [] for day in ctx.extended_days}
    for day in ctx.extended_days:
        tasks = tasks_by_day.get(day, [])
        trips_by_day[day] = route_day(instance, tasks)
    affected_days = [
        day for day, trips in trips_by_day.items()
        if trips
    ]
    trips_by_day = improve_affected_days_by_portfolio(
        instance,
        trips_by_day,
        start_days,
        affected_days,
    )
    return trips_by_day

def changed_request_ids(old_state, new_state):
    return [
        req_id for req_id, old_day in old_state.items()
        if new_state.get(req_id) != old_day
    ]

def affected_days_for_requests(instance, old_state, new_state, req_ids):
    affected_days = set()
    requests_by_id = get_context(instance).requests_by_id

    for req_id in req_ids:
        req = requests_by_id[req_id]
        for state in (old_state, new_state):
            if req_id not in state:
                continue
            start_day = state[req_id]
            pickup_day = start_day + req.numDays
            if 1 <= start_day <= instance.Days + 1:
                affected_days.add(start_day)
            if 1 <= pickup_day <= instance.Days + 1:
                affected_days.add(pickup_day)

    return affected_days

def patch_trips_from_state(instance, current_trips, old_state, new_state):
    req_ids = changed_request_ids(old_state, new_state)
    if not req_ids:
        return current_trips, set()

    affected_days = affected_days_for_requests(instance, old_state, new_state, req_ids)
    tasks_by_day = build_tasks_by_day(instance, new_state, days=affected_days)
    patched_trips = current_trips.copy()
    for day in affected_days:
        tasks = tasks_by_day.get(day, [])
        patched_trips[day] = route_day(instance, tasks)

    patched_trips = improve_affected_days_by_portfolio(
        instance,
        patched_trips,
        new_state,
        affected_days,
    )

    return patched_trips, affected_days

def route_day_greedy(instance, tasks):
    if not tasks: return []
    
    ctx = get_context(instance)
    depot = ctx.depot
    num_tools = ctx.num_tools
    tool_sizes = ctx.tool_sizes
    trips = []
    unvisited = tasks.copy()
    
    while unvisited:
        route_tasks = []
        curr_node = depot
        total_dist = 0
        best_tools_loaded = [0] * num_tools
        best_tools_returned = [0] * num_tools
        
        while unvisited:
            best_task = None
            best_dist = float('inf')
            valid_tools_loaded = None
            valid_tools_returned = None
            
            for task in unvisited:
                dist_to = instance.calcDistance[curr_node][task["req"].node]
                dist_return = instance.calcDistance[task["req"].node][depot]
                
                if total_dist + dist_to + dist_return > instance.MaxDistance:
                    continue
                    
                temp_route = route_tasks + [task]
                tools_loaded = [0] * num_tools
                tools_returned = [0] * num_tools
                
                for tool_idx in range(num_tools):
                    current_inv = 0
                    min_inv = 0
                    for t in temp_route:
                        if (t["req"].tool - 1) == tool_idx:
                            if t["type"] == "delivery":
                                current_inv -= t["req"].toolCount
                            else:
                                current_inv += t["req"].toolCount
                        if current_inv < min_inv:
                            min_inv = current_inv
                    tools_loaded[tool_idx] = min_inv
                    tools_returned[tool_idx] = -min_inv + current_inv
                    
                start_cap = sum(-tools_loaded[i] * tool_sizes[i] for i in range(num_tools))
                if start_cap > instance.Capacity:
                    continue
                    
                curr_cap = start_cap
                max_cap = start_cap
                for t in temp_route:
                    t_size = t["req"].toolCount * tool_sizes[t["req"].tool - 1]
                    if t["type"] == "delivery":
                        curr_cap -= t_size
                    else:
                        curr_cap += t_size
                    if curr_cap > max_cap: max_cap = curr_cap
                    
                if max_cap > instance.Capacity:
                    continue
                    
                if dist_to < best_dist:
                    best_dist = dist_to
                    best_task = task
                    valid_tools_loaded = tools_loaded
                    valid_tools_returned = tools_returned
                    
            if best_task is None:
                break 
                
            route_tasks.append(best_task)
            total_dist += best_dist
            curr_node = best_task["req"].node
            best_tools_loaded = valid_tools_loaded
            best_tools_returned = valid_tools_returned
            unvisited.remove(best_task)
            
        if not route_tasks:
            best_task = unvisited.pop(0)
            route_tasks.append(best_task)
            total_dist += instance.calcDistance[depot][best_task["req"].node]
            curr_node = best_task["req"].node
            
            for tool_idx in range(num_tools):
                if (best_task["req"].tool - 1) == tool_idx:
                    if best_task["type"] == "delivery":
                        best_tools_loaded[tool_idx] = -best_task["req"].toolCount
                    else:
                        best_tools_returned[tool_idx] = best_task["req"].toolCount
        
        route_nodes = [depot]
        for t in route_tasks:
            node_id = t["req"].ID if t["type"] == "delivery" else -t["req"].ID
            route_nodes.append(node_id)
        route_nodes.append(depot)
        
        total_dist += instance.calcDistance[curr_node][depot]
        
        trips.append({
            "route": route_nodes,
            "tools_loaded": best_tools_loaded,
            "tools_returned": best_tools_returned,
            "distance": total_dist
        })
        
    return trips

def route_to_tasks(instance, route):
    requests_by_id = get_context(instance).requests_by_id
    tasks = []
    for node_id in route[1:-1]:
        if node_id == 0:
            continue
        req = requests_by_id[abs(node_id)]
        tasks.append({
            "req": req,
            "type": "delivery" if node_id > 0 else "pickup"
        })
    return tasks

def route_node_coordinate(instance, node):
    ctx = get_context(instance)
    if node == 0:
        return ctx.depot
    return ctx.requests_by_id[abs(node)].node

def build_trip_from_route(instance, route):
    if len(route) < 3 or route[0] != 0 or route[-1] != 0:
        return None

    ctx = get_context(instance)
    requests_by_id = ctx.requests_by_id
    num_tools = ctx.num_tools
    depot = ctx.depot

    def node_coordinate(node):
        if node == 0:
            return depot
        return requests_by_id[abs(node)].node

    total_dist = 0
    for prev_node, next_node in zip(route, route[1:]):
        if prev_node == 0 and next_node == 0:
            return None
        from_coord = node_coordinate(prev_node)
        to_coord = node_coordinate(next_node)
        total_dist += instance.calcDistance[from_coord][to_coord]

    if total_dist > instance.MaxDistance:
        return None

    tool_size = ctx.tool_sizes
    current_tools = [0] * num_tools
    segment_states = []
    visit_loads = [[0] * num_tools]

    for node in route[1:]:
        if node == 0:
            if not segment_states:
                return None
            bring_tools = [0] * num_tools
            for state in segment_states:
                bring_tools = [min(a, b) for a, b in zip(bring_tools, state)]
                bring_tools = [min(0, value) for value in bring_tools]

            visit_loads[-1] = [a + b for a, b in zip(visit_loads[-1], bring_tools)]

            loaded = sum(size * -amount for size, amount in zip(tool_size, visit_loads[-1]))
            if loaded > instance.Capacity:
                return None

            for state in segment_states:
                loaded = sum(
                    size * (state_amount - depot_amount)
                    for size, state_amount, depot_amount in zip(tool_size, state, visit_loads[-1])
                )
                if loaded > instance.Capacity:
                    return None

            visit_loads.append([b - a for a, b in zip(bring_tools, segment_states[-1])])
            current_tools = [0] * num_tools
            segment_states = []
        else:
            req = requests_by_id[abs(node)]
            tool_idx = req.tool - 1
            if node > 0:
                current_tools[tool_idx] -= req.toolCount
            else:
                current_tools[tool_idx] += req.toolCount
            segment_states.append(current_tools.copy())

    visit_total = [0] * num_tools
    total_used_at_start = [0] * num_tools
    for visit in visit_loads:
        visit_total = [a + b for a, b in zip(visit_total, visit)]
        total_used_at_start = [
            used - min(0, current)
            for current, used in zip(visit_total, total_used_at_start)
        ]
        visit_total = [max(0, current) for current in visit_total]

    return {
        "route": route,
        "tools_loaded": [-amount for amount in total_used_at_start],
        "tools_returned": visit_total,
        "visit_loads": visit_loads,
        "distance": total_dist
    }

def build_trip_from_tasks(instance, tasks):
    if not tasks:
        return None

    depot = instance.DepotCoordinate
    route_nodes = [depot]
    for task in tasks:
        node_id = task["req"].ID if task["type"] == "delivery" else -task["req"].ID
        route_nodes.append(node_id)
    route_nodes.append(depot)

    return build_trip_from_route(instance, route_nodes)

def insertion_distance_delta(instance, route_tasks, task, pos):
    ctx = get_context(instance)
    prev_coord = ctx.depot if pos == 0 else route_tasks[pos - 1]["req"].node
    next_coord = ctx.depot if pos == len(route_tasks) else route_tasks[pos]["req"].node
    task_coord = task["req"].node
    return (
        instance.calcDistance[prev_coord][task_coord] +
        instance.calcDistance[task_coord][next_coord] -
        instance.calcDistance[prev_coord][next_coord]
    )

def task_cache_key(tasks):
    return tuple(
        (task["req"].ID, task["type"])
        for task in tasks
    )

class DailyRouteEvaluator:
    def __init__(self, instance):
        self.instance = instance
        self.trip_cache = {}
        self.reuse_bonus_cache = {}
        self.route_task_cache = {}
        self.tool_load_cache = {}

    def trip(self, tasks):
        key = task_cache_key(tasks)
        if key not in self.trip_cache:
            self.trip_cache[key] = build_trip_from_tasks(self.instance, tasks)
        return self.trip_cache[key]

    def route_tasks(self, trip):
        key = tuple(trip["route"])
        if key not in self.route_task_cache:
            self.route_task_cache[key] = route_to_tasks(self.instance, trip["route"])
        return self.route_task_cache[key]

    def reuse_bonus(self, route_tasks):
        key = task_cache_key(route_tasks)
        if key in self.reuse_bonus_cache:
            return self.reuse_bonus_cache[key]

        available_by_tool = {}
        bonus = 0
        tools = self.instance.Tools

        for task in route_tasks:
            tool_idx = task["req"].tool - 1
            amount = task["req"].toolCount
            if task["type"] == "pickup":
                available_by_tool[tool_idx] = available_by_tool.get(tool_idx, 0) + amount
            else:
                reused = min(available_by_tool.get(tool_idx, 0), amount)
                if reused > 0:
                    bonus += reused * tools[tool_idx].cost
                    available_by_tool[tool_idx] -= reused

        self.reuse_bonus_cache[key] = bonus
        return bonus

    def tool_load_cost(self, trip):
        if trip is None:
            return 0
        key = tuple(trip["route"])
        if key not in self.tool_load_cache:
            self.tool_load_cache[key] = sum(
                max(0, -amount) * self.instance.Tools[idx].cost
                for idx, amount in enumerate(trip["tools_loaded"])
            )
        return self.tool_load_cache[key]

    def local_score(self, trip):
        route_tasks = self.route_tasks(trip)
        return (
            trip["distance"] * self.instance.DistanceCost
            + 0.35 * self.tool_load_cost(trip)
            - 0.05 * self.reuse_bonus(route_tasks)
        )

    def insertion_option_score(self, old_trip, old_bonus, candidate_trip, candidate_tasks, creates_route):
        old_distance = old_trip["distance"] if old_trip is not None else 0
        distance_delta = candidate_trip["distance"] - old_distance
        reuse_delta = self.reuse_bonus(candidate_tasks) - old_bonus
        tool_load_delta = self.tool_load_cost(candidate_trip) - self.tool_load_cost(old_trip)
        route_penalty = 0
        if creates_route:
            route_penalty = self.instance.VehicleDayCost + 0.05 * self.instance.VehicleCost

        return (
            distance_delta * self.instance.DistanceCost +
            route_penalty -
            0.05 * reuse_delta +
            0.35 * tool_load_delta
        )

def clone_trip(trip):
    cloned = {
        "route": list(trip["route"]),
        "tools_loaded": list(trip["tools_loaded"]),
        "tools_returned": list(trip["tools_returned"]),
        "distance": trip["distance"],
    }
    if "visit_loads" in trip:
        cloned["visit_loads"] = [list(visit) for visit in trip["visit_loads"]]
    return cloned

def clone_trips(trips):
    return [clone_trip(trip) for trip in trips]

def route_day_uncached(instance, tasks, method):
    if method in ("regret", "regret_repair"):
        trips = route_day_regret(instance, tasks)
    elif method in ("insertion", "insertion_repair"):
        trips = route_day_insertion(instance, tasks)
    else:
        trips = route_day_greedy(instance, tasks)

    if method.endswith("_repair"):
        return improve_day_routes(instance, trips)
    return trips

def route_day_with_method(instance, tasks, method):
    cache_key = (method, task_cache_key(tasks))
    if cache_key not in ROUTE_DAY_CACHE:
        ROUTE_DAY_CACHE[cache_key] = route_day_uncached(instance, tasks, method)
    return clone_trips(ROUTE_DAY_CACHE[cache_key])

def route_day_insertion(instance, tasks):
    if not tasks:
        return []

    evaluator = DailyRouteEvaluator(instance)
    unrouted = sorted(
        tasks,
        key=lambda task: instance.calcDistance[instance.DepotCoordinate][task["req"].node],
        reverse=True,
    )
    route_task_lists = []

    while unrouted:
        best_move = None
        best_score = None
        route_stats = [
            evaluator.trip(route_tasks)
            for route_tasks in route_task_lists
        ]

        for task in unrouted:
            single_trip = evaluator.trip([task])
            if single_trip is None:
                continue

            if not route_task_lists:
                best_move = ("new", task, None, None)
                break

            for route_idx, route_tasks in enumerate(route_task_lists):
                old_trip = route_stats[route_idx]
                if old_trip is None:
                    continue
                old_distance = old_trip["distance"] if old_trip else 0
                for pos in range(len(route_tasks) + 1):
                    distance_increase = insertion_distance_delta(instance, route_tasks, task, pos)
                    if old_distance + distance_increase > instance.MaxDistance:
                        continue
                    candidate_tasks = route_tasks[:pos] + [task] + route_tasks[pos:]
                    candidate_trip = evaluator.trip(candidate_tasks)
                    if candidate_trip is None:
                        continue
                    score = distance_increase * instance.DistanceCost
                    if best_score is None or score < best_score:
                        best_score = score
                        best_move = ("insert", task, route_idx, pos)

        if best_move is None:
            task = unrouted.pop(0)
            route_task_lists.append([task])
            continue

        move_type, task, route_idx, pos = best_move
        unrouted.remove(task)
        if move_type == "new":
            route_task_lists.append([task])
        else:
            route_task_lists[route_idx] = (
                route_task_lists[route_idx][:pos] +
                [task] +
                route_task_lists[route_idx][pos:]
            )

    return [
        trip
        for route_tasks in route_task_lists
        for trip in [evaluator.trip(route_tasks)]
        if trip is not None
    ]

def route_reuse_bonus(instance, route_tasks):
    return DailyRouteEvaluator(instance).reuse_bonus(route_tasks)

def trip_tool_load_cost(instance, trip):
    return DailyRouteEvaluator(instance).tool_load_cost(trip)

def insertion_option_score(instance, old_trip, old_bonus, candidate_trip, candidate_tasks, creates_route):
    return DailyRouteEvaluator(instance).insertion_option_score(
        old_trip,
        old_bonus,
        candidate_trip,
        candidate_tasks,
        creates_route,
    )

def best_regret_options_for_task(instance, route_task_lists, route_stats, task, evaluator):
    options = []

    single_trip = evaluator.trip([task])
    if single_trip is not None:
        score = evaluator.insertion_option_score(
            None,
            0,
            single_trip,
            [task],
            creates_route=True,
        )
        options.append((score, "new", None, None, [task], single_trip))

    for route_idx, route_tasks in enumerate(route_task_lists):
        old_trip, old_bonus = route_stats[route_idx]
        if old_trip is None:
            continue
        for pos in range(len(route_tasks) + 1):
            distance_delta = insertion_distance_delta(instance, route_tasks, task, pos)
            if old_trip["distance"] + distance_delta > instance.MaxDistance:
                continue
            candidate_tasks = route_tasks[:pos] + [task] + route_tasks[pos:]
            candidate_trip = evaluator.trip(candidate_tasks)
            if candidate_trip is None:
                continue

            score = evaluator.insertion_option_score(
                old_trip,
                old_bonus,
                candidate_trip,
                candidate_tasks,
                creates_route=False,
            )
            options.append((score, "insert", route_idx, pos, candidate_tasks, candidate_trip))

    options.sort(key=lambda option: option[0])
    return options

def route_day_regret(instance, tasks, regret_k=2):
    if not tasks:
        return []

    unrouted = sorted(
        tasks,
        key=lambda task: (
            -instance.calcDistance[instance.DepotCoordinate][task["req"].node],
            -task["req"].toolCount * instance.Tools[task["req"].tool - 1].cost,
        ),
    )
    route_task_lists = []
    evaluator = DailyRouteEvaluator(instance)

    while unrouted:
        route_stats = [
            (evaluator.trip(route_tasks), evaluator.reuse_bonus(route_tasks))
            for route_tasks in route_task_lists
        ]
        best_choice = None
        best_priority = None

        for task in unrouted:
            options = best_regret_options_for_task(
                instance,
                route_task_lists,
                route_stats,
                task,
                evaluator,
            )
            if not options:
                continue

            best_score = options[0][0]
            comparison_idx = min(regret_k - 1, len(options) - 1)
            regret = options[comparison_idx][0] - best_score
            if len(options) == 1:
                regret += instance.VehicleDayCost

            priority = (
                regret,
                task["req"].toolCount * instance.Tools[task["req"].tool - 1].cost,
                instance.calcDistance[instance.DepotCoordinate][task["req"].node],
                -best_score,
            )
            if best_priority is None or priority > best_priority:
                best_priority = priority
                best_choice = (task, options[0])

        if best_choice is None:
            task = unrouted.pop(0)
            route_task_lists.append([task])
            continue

        task, option = best_choice
        _, move_type, route_idx, pos, candidate_tasks, _ = option
        unrouted.remove(task)
        if move_type == "new":
            route_task_lists.append(candidate_tasks)
        else:
            route_task_lists[route_idx] = candidate_tasks

    return [
        trip
        for route_tasks in route_task_lists
        for trip in [evaluator.trip(route_tasks)]
        if trip is not None
    ]

def trip_local_score(instance, trip):
    return DailyRouteEvaluator(instance).local_score(trip)

def improve_trip_sequence(instance, trip, max_passes=2, evaluator=None):
    evaluator = evaluator or DailyRouteEvaluator(instance)
    tasks = evaluator.route_tasks(trip)
    if len(tasks) < 2:
        return trip

    best_trip = trip
    best_tasks = tasks
    best_score = evaluator.local_score(trip)

    for _ in range(max_passes):
        improved = False

        for i in range(len(best_tasks)):
            for j in range(i + 1, len(best_tasks)):
                candidate_tasks = best_tasks.copy()
                candidate_tasks[i], candidate_tasks[j] = candidate_tasks[j], candidate_tasks[i]
                candidate_trip = evaluator.trip(candidate_tasks)
                if candidate_trip is None:
                    continue
                candidate_score = evaluator.local_score(candidate_trip)
                if candidate_score < best_score:
                    best_trip = candidate_trip
                    best_tasks = candidate_tasks
                    best_score = candidate_score
                    improved = True

        for i in range(len(best_tasks)):
            task = best_tasks[i]
            remaining = best_tasks[:i] + best_tasks[i + 1:]
            for pos in range(len(remaining) + 1):
                if pos == i:
                    continue
                candidate_tasks = remaining[:pos] + [task] + remaining[pos:]
                candidate_trip = evaluator.trip(candidate_tasks)
                if candidate_trip is None:
                    continue
                candidate_score = evaluator.local_score(candidate_trip)
                if candidate_score < best_score:
                    best_trip = candidate_trip
                    best_tasks = candidate_tasks
                    best_score = candidate_score
                    improved = True

        if not improved:
            break

    return best_trip

def day_route_score(instance, trips, evaluator=None):
    evaluator = evaluator or DailyRouteEvaluator(instance)
    distance_cost = sum(trip["distance"] for trip in trips) * instance.DistanceCost
    route_cost = len(trips) * (instance.VehicleDayCost + 0.05 * instance.VehicleCost)
    tool_load_cost = sum(evaluator.tool_load_cost(trip) for trip in trips)
    reuse_bonus = sum(
        evaluator.reuse_bonus(evaluator.route_tasks(trip))
        for trip in trips
    )
    return route_cost + distance_cost + 0.35 * tool_load_cost - 0.05 * reuse_bonus

def improve_day_routes(instance, trips):
    if not trips:
        return []

    evaluator = DailyRouteEvaluator(instance)
    original_score = day_route_score(instance, trips, evaluator)
    improved_trips = [improve_trip_sequence(instance, trip, evaluator=evaluator) for trip in trips]

    improved = True
    while improved:
        improved = False
        best_move = None
        best_score = day_route_score(instance, improved_trips, evaluator)

        for i in range(len(improved_trips)):
            for j in range(i + 1, len(improved_trips)):
                merged_trip = try_merge_trips(instance, improved_trips[i], improved_trips[j], evaluator=evaluator)
                if merged_trip is None:
                    continue
                candidate_trips = [
                    trip for idx, trip in enumerate(improved_trips)
                    if idx not in (i, j)
                ] + [improve_trip_sequence(instance, merged_trip, evaluator=evaluator)]
                candidate_score = day_route_score(instance, candidate_trips, evaluator)
                if candidate_score < best_score:
                    best_score = candidate_score
                    best_move = candidate_trips

        if best_move is not None:
            improved_trips = best_move
            improved = True

    if day_route_score(instance, improved_trips, evaluator) < original_score:
        return improved_trips
    return trips

def route_day(instance, tasks):
    return route_day_with_method(instance, tasks, ROUTING_METHOD)

def route_signature(trips):
    return tuple(tuple(trip["route"]) for trip in trips)

def route_day_portfolio_candidates(instance, tasks):
    if not tasks:
        return [[]]

    candidates = []
    seen = set()

    methods = ["greedy"]
    if len(tasks) <= 36:
        methods.append("insertion")
    if len(tasks) <= 28:
        methods.append("regret")

    for method in methods:
        trips = route_day_with_method(instance, tasks, method)
        signature = route_signature(trips)
        if signature not in seen:
            candidates.append(trips)
            seen.add(signature)

        if len(tasks) <= 32:
            repaired = route_day_with_method(instance, tasks, f"{method}_repair")
            signature = route_signature(repaired)
            if signature not in seen:
                candidates.append(repaired)
                seen.add(signature)

    return candidates

def improve_affected_days_by_portfolio(instance, schedule_by_day, start_days, affected_days):
    improved_schedule = {
        day: list(trips)
        for day, trips in schedule_by_day.items()
    }
    best_components = evaluate_cost_components(instance, improved_schedule)
    if not components_within_tool_limits(instance, best_components):
        return improved_schedule

    tasks_by_day = build_tasks_by_day(instance, start_days, days=affected_days)
    for day in sorted(affected_days):
        tasks = tasks_by_day.get(day, [])
        best_trips_for_day = improved_schedule.get(day, [])
        best_cost = best_components["total"]

        for candidate_trips in route_day_portfolio_candidates(instance, tasks):
            if route_signature(candidate_trips) == route_signature(best_trips_for_day):
                continue
            candidate_schedule = improved_schedule.copy()
            candidate_schedule[day] = candidate_trips
            candidate_components = evaluate_delta_cost_components(
                instance,
                best_components,
                candidate_schedule,
                {day},
            )
            if not components_within_tool_limits(instance, candidate_components):
                continue
            if candidate_components["total"] < best_cost:
                best_cost = candidate_components["total"]
                best_components = candidate_components
                best_trips_for_day = candidate_trips

        improved_schedule[day] = best_trips_for_day

    return improved_schedule

def route_distance(instance, tasks):
    if not tasks:
        return 0
    depot = instance.DepotCoordinate
    total_dist = 0
    curr_node = depot
    for task in tasks:
        total_dist += instance.calcDistance[curr_node][task["req"].node]
        curr_node = task["req"].node
    total_dist += instance.calcDistance[curr_node][depot]
    return total_dist

def greedy_insert_tasks(instance, base_tasks, inserted_tasks, evaluator=None):
    evaluator = evaluator or DailyRouteEvaluator(instance)
    merged = base_tasks.copy()
    for task in inserted_tasks:
        best_sequence = None
        best_distance = float('inf')
        for pos in range(len(merged) + 1):
            candidate = merged[:pos] + [task] + merged[pos:]
            trip = evaluator.trip(candidate)
            if trip is None:
                continue
            if trip["distance"] < best_distance:
                best_distance = trip["distance"]
                best_sequence = candidate
        if best_sequence is None:
            return None
        merged = best_sequence
    return evaluator.trip(merged)

def try_merge_trips(instance, trip_a, trip_b, evaluator=None):
    evaluator = evaluator or DailyRouteEvaluator(instance)
    tasks_a = evaluator.route_tasks(trip_a)
    tasks_b = evaluator.route_tasks(trip_b)
    candidates = []

    for route in (
        trip_a["route"] + trip_b["route"][1:],
        trip_b["route"] + trip_a["route"][1:],
    ):
        trip = build_trip_from_route(instance, route)
        if trip is not None:
            candidates.append(trip)

    for task_sequence in (tasks_a + tasks_b, tasks_b + tasks_a):
        trip = evaluator.trip(task_sequence)
        if trip is not None:
            candidates.append(trip)

    insertion_candidates = [
        (tasks_a, tasks_b),
        (tasks_b, tasks_a),
        (tasks_a, list(reversed(tasks_b))),
        (tasks_b, list(reversed(tasks_a))),
    ]
    for base_tasks, inserted_tasks in insertion_candidates:
        trip = greedy_insert_tasks(instance, base_tasks, inserted_tasks, evaluator=evaluator)
        if trip is not None:
            candidates.append(trip)

    if not candidates:
        return None
    return min(candidates, key=lambda trip: trip["distance"])

def merge_routes_postprocess(instance, schedule_by_day):
    improved_schedule = {
        day: [trip.copy() for trip in trips]
        for day, trips in schedule_by_day.items()
    }
    current_components = evaluate_cost_components(instance, improved_schedule)
    current_cost = current_components["total"]
    merges_applied = 0

    improved = True
    while improved:
        improved = False
        best_move = None
        best_cost = current_cost

        for day, trips in improved_schedule.items():
            if len(trips) < 2:
                continue
            for i in range(len(trips)):
                for j in range(i + 1, len(trips)):
                    merged_trip = try_merge_trips(instance, trips[i], trips[j])
                    if merged_trip is None:
                        continue

                    candidate_schedule = {
                        d: list(day_trips)
                        for d, day_trips in improved_schedule.items()
                    }
                    candidate_trips = [
                        trip for idx, trip in enumerate(trips)
                        if idx not in (i, j)
                    ]
                    candidate_trips.append(merged_trip)
                    candidate_schedule[day] = candidate_trips
                    candidate_components = evaluate_delta_cost_components(
                        instance,
                        current_components,
                        candidate_schedule,
                        {day},
                    )
                    candidate_cost = candidate_components["total"]

                    if candidate_cost < best_cost:
                        best_cost = candidate_cost
                        best_move = (day, i, j, merged_trip, candidate_components)

        if best_move is not None:
            day, i, j, merged_trip, current_components = best_move
            trips = improved_schedule[day]
            improved_schedule[day] = [
                trip for idx, trip in enumerate(trips)
                if idx not in (i, j)
            ]
            improved_schedule[day].append(merged_trip)
            current_cost = best_cost
            merges_applied += 1
            improved = True

    if merges_applied:
        print(f"      [SA] Route merge post-processing applied {merges_applied} merge(s).")
        print(f"      [SA] Post-processed Estimated Cost: {current_cost:,.0f}")
    else:
        print("      [SA] Route merge post-processing found no improving merges.")

    return improved_schedule

def generate_baseline_start_days(instance):
    baseline_schedule = solve_baseline(instance)
    start_days = extract_start_days_from_schedule(instance, baseline_schedule)
    if start_days is not None:
        return start_days
    return {req.ID: req.fromDay for req in instance.Requests}

def tool_peak_cost_from_usage(instance, daily_usage):
    total = 0
    for tool_idx, tool in enumerate(instance.Tools):
        peak = max(usage[tool_idx] for usage in daily_usage.values())
        total += peak * tool.cost
    return total

def generate_tool_balanced_start_days(instance):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    start_days = {}
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    ordered_requests = sorted(
        ctx.requests,
        key=lambda req: (
            -req.toolCount * instance.Tools[req.tool - 1].cost * req.numDays,
            req.toDay - req.fromDay,
        ),
    )

    for req in ordered_requests:
        best_day = None
        best_score = None
        for candidate_day in range(req.fromDay, req.toDay + 1):
            candidate_usage = {day: usage[:] for day, usage in daily_usage.items()}
            feasible = True
            for day in active_tool_days(instance, req, candidate_day):
                candidate_usage[day][req.tool - 1] += req.toolCount
                if candidate_usage[day][req.tool - 1] > instance.Tools[req.tool - 1].amount:
                    feasible = False
                    break
            if not feasible:
                continue

            weighted_peak = tool_peak_cost_from_usage(instance, candidate_usage)
            active_days = sum(1 for usage in candidate_usage.values() if any(usage))
            score = (
                weighted_peak,
                active_days,
                abs(candidate_day - ((req.fromDay + req.toDay) / 2)),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_day = candidate_day

        if best_day is None:
            return None

        start_days[req.ID] = best_day
        for day in active_tool_days(instance, req, best_day):
            daily_usage[day][req.tool - 1] += req.toolCount

    return start_days

def generate_vehicle_day_clustered_start_days(instance):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    start_days = {}
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    task_counts = {day: 0 for day in range(1, instance.Days + 2)}
    ordered_requests = sorted(
        ctx.requests,
        key=lambda req: (req.toDay - req.fromDay, -req.toolCount),
    )

    for req in ordered_requests:
        best_day = None
        best_score = None
        for candidate_day in range(req.fromDay, req.toDay + 1):
            pickup_day = candidate_day + req.numDays
            feasible = True
            for day in active_tool_days(instance, req, candidate_day):
                if daily_usage[day][req.tool - 1] + req.toolCount > instance.Tools[req.tool - 1].amount:
                    feasible = False
                    break
            if not feasible:
                continue

            creates_delivery_day = 1 if task_counts[candidate_day] == 0 else 0
            creates_pickup_day = 1 if pickup_day <= instance.Days and task_counts[pickup_day] == 0 else 0
            delivery_pressure = task_counts[candidate_day]
            pickup_pressure = task_counts[pickup_day] if pickup_day <= instance.Days else 0
            score = (
                creates_delivery_day + creates_pickup_day,
                delivery_pressure + pickup_pressure,
                tool_peak_cost_from_usage(instance, daily_usage),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_day = candidate_day

        if best_day is None:
            return None

        start_days[req.ID] = best_day
        pickup_day = best_day + req.numDays
        task_counts[best_day] += 1
        if pickup_day <= instance.Days:
            task_counts[pickup_day] += 1
        for day in active_tool_days(instance, req, best_day):
            daily_usage[day][req.tool - 1] += req.toolCount

    return start_days

def generate_distance_clustered_start_days(instance):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    start_days = {}
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    task_node_by_day = {day: [] for day in range(1, instance.Days + 2)}
    ordered_requests = sorted(
        ctx.requests,
        key=lambda req: instance.calcDistance[instance.DepotCoordinate][req.node],
        reverse=True,
    )

    for req in ordered_requests:
        best_day = None
        best_score = None
        for candidate_day in range(req.fromDay, req.toDay + 1):
            pickup_day = candidate_day + req.numDays
            feasible = True
            for day in active_tool_days(instance, req, candidate_day):
                if daily_usage[day][req.tool - 1] + req.toolCount > instance.Tools[req.tool - 1].amount:
                    feasible = False
                    break
            if not feasible:
                continue

            day_nodes = task_node_by_day[candidate_day]
            pickup_nodes = task_node_by_day[pickup_day] if pickup_day <= instance.Days else []
            if day_nodes:
                delivery_cluster_dist = min(instance.calcDistance[req.node][node] for node in day_nodes)
            else:
                delivery_cluster_dist = instance.calcDistance[instance.DepotCoordinate][req.node]
            if pickup_nodes:
                pickup_cluster_dist = min(instance.calcDistance[req.node][node] for node in pickup_nodes)
            else:
                pickup_cluster_dist = instance.calcDistance[instance.DepotCoordinate][req.node]
            score = (
                delivery_cluster_dist + pickup_cluster_dist,
                len(day_nodes) + len(pickup_nodes),
                tool_peak_cost_from_usage(instance, daily_usage),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_day = candidate_day

        if best_day is None:
            return None

        start_days[req.ID] = best_day
        pickup_day = best_day + req.numDays
        task_node_by_day[best_day].append(req.node)
        if pickup_day <= instance.Days:
            task_node_by_day[pickup_day].append(req.node)
        for day in active_tool_days(instance, req, best_day):
            daily_usage[day][req.tool - 1] += req.toolCount

    return start_days

def generate_initial_solution(instance):
    candidates = [
        ("baseline", generate_baseline_start_days(instance)),
        ("tool-balanced", generate_tool_balanced_start_days(instance)),
        ("vehicle-day-clustered", generate_vehicle_day_clustered_start_days(instance)),
        ("distance-clustered", generate_distance_clustered_start_days(instance)),
    ]

    best_name = None
    best_state = None
    best_cost = None

    for name, start_days in candidates:
        if start_days is None or len(start_days) != len(instance.Requests):
            continue
        if not is_schedule_feasible(instance, start_days):
            continue
        schedule = build_trips_from_state(instance, start_days)
        components = evaluate_cost_components(instance, schedule)
        if not components_within_tool_limits(instance, components):
            continue
        cost = components["total"]
        if best_cost is None or cost < best_cost:
            best_name = name
            best_state = start_days
            best_cost = cost

    if best_state is not None:
        print(f"      [SA] Selected initial strategy: {best_name} ({best_cost:,.0f})")
        return best_state

    print("      [SA] Warning: all strategy starts failed; falling back to earliest days.")
    return {req.ID: req.fromDay for req in instance.Requests}

def calculate_daily_tool_usage(instance, start_days):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    for req in ctx.requests:
        start_day = start_days[req.ID]
        for day in active_tool_days(instance, req, start_day):
            daily_usage[day][req.tool - 1] += req.toolCount
    return daily_usage

def calculate_partial_daily_tool_usage(instance, partial_state):
    ctx = get_context(instance)
    num_tools = ctx.num_tools
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    for req in ctx.requests:
        if req.ID not in partial_state:
            continue
        start_day = partial_state[req.ID]
        for day in active_tool_days(instance, req, start_day):
            daily_usage[day][req.tool - 1] += req.toolCount
    return daily_usage

def is_partial_schedule_feasible(instance, partial_state):
    daily_usage = calculate_partial_daily_tool_usage(instance, partial_state)
    for usage in daily_usage.values():
        for tool_idx, amount in enumerate(usage):
            if amount > instance.Tools[tool_idx].amount:
                return False
    return True

def get_partial_tasks_for_day(instance, partial_state, day):
    tasks = []
    for req in get_context(instance).requests:
        if req.ID not in partial_state:
            continue
        start_day = partial_state[req.ID]
        if start_day == day:
            tasks.append({"req": req, "type": "delivery"})
        pickup_day = start_day + req.numDays
        if pickup_day == day and pickup_day <= instance.Days:
            tasks.append({"req": req, "type": "pickup"})
    return tasks

def dominant_cost_part(components):
    parts = {
        "tools": components["tools"],
        "vehicle_days": components["vehicle_days"],
        "fixed_vehicle": components["fixed_vehicle"],
        "distance": components["distance"],
    }
    return max(parts, key=parts.get)

def component_pressure(instance, components):
    total = max(1, components["total"])
    return {
        "tools": components["tools"] / total,
        "vehicle_days": components["vehicle_days"] / total,
        "fixed_vehicle": components["fixed_vehicle"] / total,
        "distance": components["distance"] / total,
    }

def weighted_tool_use_cost(instance, tool_use):
    return sum(
        amount * instance.Tools[idx].cost
        for idx, amount in enumerate(tool_use)
    )

def weighted_tool_regression(instance, old_components, new_components):
    return sum(
        max(0, new - old) * instance.Tools[idx].cost
        for idx, (new, old) in enumerate(zip(new_components["tool_use"], old_components["tool_use"]))
    )

def is_clearly_dominant(pressure, dominant_part):
    dominant_pressure = pressure.get(dominant_part, 0)
    other_pressures = [
        value for part, value in pressure.items()
        if part != dominant_part
    ]
    second_pressure = max(other_pressures, default=0)
    return dominant_pressure >= 0.30 and dominant_pressure >= second_pressure + 0.05

def component_regression_cost(instance, dominant_part, old_components, new_components):
    if dominant_part == "tools":
        return weighted_tool_regression(instance, old_components, new_components)

    if dominant_part == "vehicle_days":
        extra_days = new_components["vehicle_day_count"] - old_components["vehicle_day_count"]
        return max(0, extra_days) * instance.VehicleDayCost

    if dominant_part == "fixed_vehicle":
        extra_vehicles = new_components["max_vehicles"] - old_components["max_vehicles"]
        return max(0, extra_vehicles) * instance.VehicleCost

    if dominant_part == "distance":
        extra_distance = new_components["total_distance"] - old_components["total_distance"]
        return max(0, extra_distance) * instance.DistanceCost

    return 0

def component_guard_budget(old_components, dominant_part, pressure, temperature):
    total = max(1, old_components["total"])
    hotness = min(1.0, max(0.0, temperature / max(1.0, total * 0.002)))
    dominance = pressure.get(dominant_part, 0)
    strictness = max(0.35, 1.10 - dominance)

    base_ratios = {
        "tools": 0.00035,
        "vehicle_days": 0.00020,
        "fixed_vehicle": 0.00020,
        "distance": 0.00050,
    }
    hot_ratios = {
        "tools": 0.00150,
        "vehicle_days": 0.00100,
        "fixed_vehicle": 0.00100,
        "distance": 0.00200,
    }

    ratio = base_ratios.get(dominant_part, 0.00025) + hotness * hot_ratios.get(dominant_part, 0.001)
    budget_from_total = total * ratio * strictness
    budget_from_temperature = temperature * (0.20 + 0.40 * hotness)
    return max(1.0, budget_from_total, budget_from_temperature)

def component_guard_allows(instance, dominant_part, old_components, new_components, temperature):
    if new_components["total"] <= old_components["total"]:
        return True

    pressure = component_pressure(instance, old_components)
    if dominant_part == "distance":
        return True

    if not is_clearly_dominant(pressure, dominant_part):
        return True

    regression = component_regression_cost(instance, dominant_part, old_components, new_components)
    if regression <= 0:
        return True

    return regression <= component_guard_budget(
        old_components,
        dominant_part,
        pressure,
        temperature,
    )

def requests_touching_day(instance, start_days, day):
    candidates = []
    for req in instance.Requests:
        start_day = start_days[req.ID]
        pickup_day = start_day + req.numDays
        if start_day == day or pickup_day == day:
            candidates.append(req)
    return candidates

def validator_tool_peak_day(instance, schedule_by_day):
    tool_status = [0] * len(instance.Tools)
    tool_use = [0] * len(instance.Tools)
    peak_day_by_tool = [None] * len(instance.Tools)

    for day in sorted(schedule_by_day.keys()):
        for trip in schedule_by_day[day]:
            tool_status = [
                current + loaded
                for current, loaded in zip(tool_status, trip["tools_loaded"])
            ]
        for tool_idx, current in enumerate(tool_status):
            shortage = max(0, -current)
            if shortage > tool_use[tool_idx]:
                tool_use[tool_idx] = shortage
                peak_day_by_tool[tool_idx] = day
        for trip in schedule_by_day[day]:
            tool_status = [
                current + returned
                for current, returned in zip(tool_status, trip["tools_returned"])
            ]

    if not tool_use:
        return None, None

    peak_tool_idx = max(
        range(len(instance.Tools)),
        key=lambda idx: tool_use[idx] * instance.Tools[idx].cost,
    )
    return peak_tool_idx, peak_day_by_tool[peak_tool_idx]

def active_tool_requests_on_day(instance, start_days, day, tool_idx):
    if day is None:
        return []

    candidates = []
    for req in instance.Requests:
        if req.tool - 1 != tool_idx:
            continue
        start_day = start_days[req.ID]
        if start_day <= day <= start_day + req.numDays:
            candidates.append(req)
    return candidates

def choose_peak_tool_request(instance, start_days, current_trips=None):
    if current_trips is not None:
        peak_tool_idx, peak_day = validator_tool_peak_day(instance, current_trips)
        candidates = active_tool_requests_on_day(instance, start_days, peak_day, peak_tool_idx)
        if candidates:
            return max(
                candidates,
                key=lambda req: (
                    req.toolCount * instance.Tools[req.tool - 1].cost,
                    req.toDay - req.fromDay,
                ),
            )

    daily_usage = calculate_daily_tool_usage(instance, start_days)
    best_score = None
    peak_day = None
    peak_tool_idx = None

    for day, usage in daily_usage.items():
        for tool_idx, amount in enumerate(usage):
            score = amount * instance.Tools[tool_idx].cost
            if best_score is None or score > best_score:
                best_score = score
                peak_day = day
                peak_tool_idx = tool_idx

    if peak_day is None:
        return random.choice(instance.Requests)

    candidates = []
    for req in instance.Requests:
        start_day = start_days[req.ID]
        if req.tool - 1 != peak_tool_idx:
            continue
        if start_day <= peak_day <= start_day + req.numDays:
            candidates.append(req)

    if not candidates:
        return random.choice(instance.Requests)

    return max(candidates, key=lambda req: req.toolCount * instance.Tools[req.tool - 1].cost)

def choose_busy_day_request(instance, start_days, current_trips):
    day_scores = {}
    for day, trips in current_trips.items():
        day_scores[day] = (len(trips), sum(trip["distance"] for trip in trips))

    worst_day = max(day_scores, key=day_scores.get)
    candidates = requests_touching_day(instance, start_days, worst_day)
    if candidates:
        return random.choice(candidates)
    return random.choice(instance.Requests)

def choose_distance_day_request(instance, start_days, current_trips):
    worst_day = max(
        current_trips,
        key=lambda day: sum(trip["distance"] for trip in current_trips[day])
    )
    candidates = requests_touching_day(instance, start_days, worst_day)
    if candidates:
        return random.choice(candidates)
    return random.choice(instance.Requests)

def nearby_related_requests(instance, req, limit=3):
    same_tool = [
        other for other in instance.Requests
        if other.ID != req.ID and other.tool == req.tool
    ]
    same_tool.sort(key=lambda other: instance.calcDistance[req.node][other.node])
    return same_tool[:limit]

def propose_single_move(instance, current_state, req=None):
    if req is None:
        req = random.choice(instance.Requests)

    old_start = current_state[req.ID]
    possible_days = list(range(req.fromDay, req.toDay + 1))
    if len(possible_days) <= 1:
        return None
    possible_days.remove(old_start)

    new_state = current_state.copy()
    new_state[req.ID] = random.choice(possible_days)
    return new_state

def propose_best_tool_move(instance, current_state, req, current_trips=None, current_components=None):
    old_start = current_state[req.ID]
    best_state = None
    best_score = current_components["total"] if current_components is not None else None

    for candidate_day in range(req.fromDay, req.toDay + 1):
        if candidate_day == old_start:
            continue
        candidate_state = current_state.copy()
        candidate_state[req.ID] = candidate_day
        if not is_schedule_feasible(instance, candidate_state):
            continue

        if current_trips is not None and current_components is not None:
            candidate_trips, affected_days = patch_trips_from_state(
                instance,
                current_trips,
                current_state,
                candidate_state,
            )
            candidate_components = evaluate_delta_cost_components(
                instance,
                current_components,
                candidate_trips,
                affected_days,
            )
            if not components_within_tool_limits(instance, candidate_components):
                continue
            score, _ = score_components(
                instance,
                candidate_components,
                "tools",
                current_components,
            )
        else:
            daily_usage = calculate_daily_tool_usage(instance, candidate_state)
            tool_use = [
                max(usage[tool_idx] for usage in daily_usage.values())
                for tool_idx in range(len(instance.Tools))
            ]
            score = weighted_tool_use_cost(instance, tool_use)

        if best_score is None or score < best_score:
            best_score = score
            best_state = candidate_state

    return best_state

def propose_swap_move(instance, current_state):
    req_a, req_b = random.sample(instance.Requests, 2)
    start_a = current_state[req_a.ID]
    start_b = current_state[req_b.ID]

    if not (req_a.fromDay <= start_b <= req_a.toDay and req_b.fromDay <= start_a <= req_b.toDay):
        return None

    new_state = current_state.copy()
    new_state[req_a.ID] = start_b
    new_state[req_b.ID] = start_a
    return new_state

def propose_group_shift(instance, current_state):
    anchor = random.choice(instance.Requests)
    group = [anchor] + nearby_related_requests(instance, anchor, limit=2)
    possible_deltas = [-3, -2, -1, 1, 2, 3]
    random.shuffle(possible_deltas)

    for delta in possible_deltas:
        new_state = current_state.copy()
        moved = False
        for req in group:
            old_start = current_state[req.ID]
            new_start = old_start + delta
            if req.fromDay <= new_start <= req.toDay:
                new_state[req.ID] = new_start
                moved = True
        if moved:
            return new_state
    return None

def propose_cost_aware_neighbor(instance, current_state, current_trips, components):
    dominant_part = dominant_cost_part(components)
    roll = random.random()

    if roll < 0.4:
        return propose_single_move(instance, current_state)

    if roll < 0.55:
        return propose_swap_move(instance, current_state)

    if roll < 0.68:
        return propose_group_shift(instance, current_state)

    if dominant_part == "tools":
        req = choose_peak_tool_request(instance, current_state, current_trips)
        return propose_best_tool_move(
            instance,
            current_state,
            req,
            current_trips=current_trips,
            current_components=components,
        )

    if dominant_part in ("vehicle_days", "fixed_vehicle"):
        req = choose_busy_day_request(instance, current_state, current_trips)
        return propose_single_move(instance, current_state, req)

    if dominant_part == "distance":
        req = choose_distance_day_request(instance, current_state, current_trips)
        return propose_single_move(instance, current_state, req)

    return propose_single_move(instance, current_state)

def choose_destroy_requests(instance, current_state, current_trips, components, destroy_size):
    dominant_part = dominant_cost_part(components)
    destroy_size = max(1, min(destroy_size, len(instance.Requests)))

    if dominant_part == "tools":
        peak_tool_idx, peak_day = validator_tool_peak_day(instance, current_trips)
        peak_candidates = active_tool_requests_on_day(instance, current_state, peak_day, peak_tool_idx)
        peak_candidates.sort(
            key=lambda req: (
                -req.toolCount * instance.Tools[req.tool - 1].cost,
                req.toDay - req.fromDay,
            )
        )
        anchor = peak_candidates[0] if peak_candidates else choose_peak_tool_request(instance, current_state, current_trips)
        candidates = peak_candidates + nearby_related_requests(instance, anchor, limit=destroy_size * 2)
    elif dominant_part in ("vehicle_days", "fixed_vehicle"):
        anchor = choose_busy_day_request(instance, current_state, current_trips)
        day = current_state[anchor.ID]
        candidates = requests_touching_day(instance, current_state, day)
    elif dominant_part == "distance":
        anchor = choose_distance_day_request(instance, current_state, current_trips)
        candidates = [anchor] + nearby_related_requests(instance, anchor, limit=destroy_size * 2)
    else:
        anchor = random.choice(instance.Requests)
        candidates = [anchor] + nearby_related_requests(instance, anchor, limit=destroy_size * 2)

    unique = []
    seen = set()
    for req in candidates:
        if req.ID not in seen:
            unique.append(req)
            seen.add(req.ID)

    if len(unique) < destroy_size:
        remaining = [req for req in instance.Requests if req.ID not in seen]
        random.shuffle(remaining)
        unique.extend(remaining[:destroy_size - len(unique)])

    return unique[:destroy_size]

def score_components(instance, components, dominant_part, reference_components=None):
    if reference_components is None:
        return components["total"], components

    if dominant_part == "tools":
        tool_regression = sum(
            max(0, new - old) * instance.Tools[idx].cost * 5
            for idx, (new, old) in enumerate(zip(components["tool_use"], reference_components["tool_use"]))
        )
        return components["total"] + tool_regression, components

    if dominant_part == "vehicle_days":
        vehicle_day_regression = max(
            0,
            components["vehicle_day_count"] - reference_components["vehicle_day_count"],
        ) * instance.VehicleDayCost * 10
        return components["total"] + vehicle_day_regression, components

    if dominant_part == "fixed_vehicle":
        fixed_vehicle_regression = max(
            0,
            components["max_vehicles"] - reference_components["max_vehicles"],
        ) * instance.VehicleCost * 10
        return components["total"] + fixed_vehicle_regression, components

    return components["total"], components

def score_completed_schedule(instance, schedule, dominant_part, reference_components=None):
    components = evaluate_cost_components(instance, schedule)
    return score_components(instance, components, dominant_part, reference_components)

def partial_repair_score(instance, partial_state, dominant_part, exact_days=None):
    daily_usage = calculate_partial_daily_tool_usage(instance, partial_state)
    tool_use = [
        max(usage[tool_idx] for usage in daily_usage.values())
        for tool_idx in range(len(instance.Tools))
    ]
    tool_cost = weighted_tool_use_cost(instance, tool_use)

    task_counts_by_day = {day: 0 for day in range(1, instance.Days + 2)}
    distance_roundtrip_proxy = 0
    for req in instance.Requests:
        if req.ID not in partial_state:
            continue
        start_day = partial_state[req.ID]
        pickup_day = start_day + req.numDays
        if start_day <= instance.Days:
            task_counts_by_day[start_day] += 1
        if pickup_day <= instance.Days:
            task_counts_by_day[pickup_day] += 1
        distance_roundtrip_proxy += 2 * instance.calcDistance[instance.DepotCoordinate][req.node]

    task_day_proxy = sum(task_counts_by_day.values())
    max_task_day_proxy = max(task_counts_by_day.values(), default=0)
    exact_days = set(exact_days or [])

    exact_vehicle_days = 0
    exact_max_vehicles = 0
    exact_distance = 0
    exact_task_day_proxy = 0
    if exact_days:
        for day in exact_days:
            if day < 1 or day > instance.Days + 1:
                continue
            tasks = get_partial_tasks_for_day(instance, partial_state, day)
            exact_task_day_proxy += len(tasks)
            trips = route_day(instance, tasks)
            exact_vehicle_days += len(trips)
            exact_max_vehicles = max(exact_max_vehicles, len(trips))
            exact_distance += sum(trip["distance"] for trip in trips)

    mixed_task_day_proxy = max(0, task_day_proxy - exact_task_day_proxy) + exact_vehicle_days
    mixed_max_vehicle_proxy = max(
        exact_max_vehicles,
        max(
            (
                count for day, count in task_counts_by_day.items()
                if day not in exact_days
            ),
            default=0,
        ),
    )

    if dominant_part == "tools":
        return (
            tool_cost +
            0.05 * mixed_task_day_proxy * instance.VehicleDayCost +
            0.01 * distance_roundtrip_proxy * instance.DistanceCost
        )

    if dominant_part == "vehicle_days":
        return (
            mixed_task_day_proxy * instance.VehicleDayCost +
            0.2 * mixed_max_vehicle_proxy * instance.VehicleCost +
            0.05 * tool_cost
        )

    if dominant_part == "fixed_vehicle":
        return (
            mixed_max_vehicle_proxy * instance.VehicleCost +
            0.2 * mixed_task_day_proxy * instance.VehicleDayCost +
            0.05 * tool_cost
        )

    max_vehicles = 0
    vehicle_days = 0
    total_distance = 0
    for day in range(1, instance.Days + 2):
        tasks = get_partial_tasks_for_day(instance, partial_state, day)
        trips = route_day(tasks=tasks, instance=instance)
        max_vehicles = max(max_vehicles, len(trips))
        vehicle_days += len(trips)
        total_distance += sum(trip["distance"] for trip in trips)

    distance_proxy = total_distance * instance.DistanceCost
    vehicle_day_proxy = vehicle_days * instance.VehicleDayCost
    fixed_vehicle_proxy = max_vehicles * instance.VehicleCost

    if dominant_part == "distance":
        return distance_proxy + 0.1 * vehicle_day_proxy + 0.05 * tool_cost
    return vehicle_day_proxy + 0.2 * fixed_vehicle_proxy + 0.05 * tool_cost

def best_request_insertions(instance, repaired_state, req, dominant_part):
    options = []
    days = list(range(req.fromDay, req.toDay + 1))
    random.shuffle(days)

    for candidate_day in days:
        candidate_state = repaired_state.copy()
        candidate_state[req.ID] = candidate_day
        if not is_partial_schedule_feasible(instance, candidate_state):
            continue
        exact_days = {candidate_day, candidate_day + req.numDays}
        score = partial_repair_score(instance, candidate_state, dominant_part, exact_days=exact_days)
        options.append((score, candidate_day))

    options.sort(key=lambda item: item[0])
    return options

def exact_request_insertions(
    instance,
    current_state,
    current_trips,
    repaired_state,
    req,
    dominant_part,
    reference_components,
):
    options = []
    days = list(range(req.fromDay, req.toDay + 1))
    random.shuffle(days)

    for candidate_day in days:
        candidate_state = repaired_state.copy()
        candidate_state[req.ID] = candidate_day
        if not is_schedule_feasible(instance, candidate_state):
            continue

        candidate_trips, affected_days = patch_trips_from_state(
            instance,
            current_trips,
            current_state,
            candidate_state,
        )
        candidate_components = evaluate_delta_cost_components(
            instance,
            reference_components,
            candidate_trips,
            affected_days,
        )
        if not components_within_tool_limits(instance, candidate_components):
            continue

        score, candidate_components = score_components(
            instance,
            candidate_components,
            dominant_part,
            reference_components,
        )
        options.append((score, candidate_day, candidate_components))

    options.sort(key=lambda item: item[0])
    return options

def repair_destroyed_requests_greedy(instance, current_state, removed_requests, dominant_part):
    partial_state = current_state.copy()
    for req in removed_requests:
        partial_state.pop(req.ID, None)

    repaired_state = partial_state.copy()
    ordered_requests = sorted(
        removed_requests,
        key=lambda req: (req.toDay - req.fromDay, -req.toolCount * instance.Tools[req.tool - 1].cost),
    )

    for req in ordered_requests:
        best_day = None
        best_score = None
        days = list(range(req.fromDay, req.toDay + 1))
        random.shuffle(days)

        for candidate_day in days:
            candidate_state = repaired_state.copy()
            candidate_state[req.ID] = candidate_day
            if not is_partial_schedule_feasible(instance, candidate_state):
                continue

            exact_days = {candidate_day, candidate_day + req.numDays}
            score = partial_repair_score(instance, candidate_state, dominant_part, exact_days=exact_days)
            if best_score is None or score < best_score:
                best_score = score
                best_day = candidate_day

        if best_day is None:
            return None
        repaired_state[req.ID] = best_day

    return repaired_state

def repair_destroyed_requests_regret(instance, current_state, removed_requests, dominant_part, regret_k=2):
    repaired_state = current_state.copy()
    uninserted = list(removed_requests)
    for req in uninserted:
        repaired_state.pop(req.ID, None)

    while uninserted:
        best_choice = None
        best_regret = None

        for req in uninserted:
            options = best_request_insertions(instance, repaired_state, req, dominant_part)
            if not options:
                return None

            best_score = options[0][0]
            comparison_idx = min(regret_k - 1, len(options) - 1)
            regret = options[comparison_idx][0] - best_score
            if len(options) == 1:
                regret += abs(best_score) + 1

            priority = (
                regret,
                req.toolCount * instance.Tools[req.tool - 1].cost,
                -(req.toDay - req.fromDay),
            )

            if best_regret is None or priority > best_regret:
                best_regret = priority
                best_choice = (req, options[0][1])

        req, best_day = best_choice
        repaired_state[req.ID] = best_day
        uninserted.remove(req)

    return repaired_state

def repair_destroyed_requests_exact_regret(
    instance,
    current_state,
    current_trips,
    current_components,
    removed_requests,
    dominant_part,
    regret_k=2,
):
    repaired_state = current_state.copy()
    uninserted = list(removed_requests)

    while uninserted:
        best_choice = None
        best_priority = None

        for req in uninserted:
            options = exact_request_insertions(
                instance,
                current_state,
                current_trips,
                repaired_state,
                req,
                dominant_part,
                current_components,
            )
            if not options:
                return None

            best_score = options[0][0]
            comparison_idx = min(regret_k - 1, len(options) - 1)
            regret = options[comparison_idx][0] - best_score
            if len(options) == 1:
                regret += abs(best_score) + 1

            best_components = options[0][2]
            tool_improvement = current_components["tools"] - best_components["tools"]
            total_improvement = current_components["total"] - best_components["total"]
            priority = (
                regret,
                tool_improvement,
                total_improvement,
                req.toolCount * instance.Tools[req.tool - 1].cost,
                -(req.toDay - req.fromDay),
            )

            if best_priority is None or priority > best_priority:
                best_priority = priority
                best_choice = (req, options[0][1])

        req, best_day = best_choice
        repaired_state[req.ID] = best_day
        uninserted.remove(req)

    return repaired_state

def repair_destroyed_requests(
    instance,
    current_state,
    removed_requests,
    dominant_part,
    repair_method="greedy",
    current_trips=None,
    current_components=None,
):
    if (
        dominant_part == "tools"
        and current_trips is not None
        and current_components is not None
        and len(removed_requests) <= 12
    ):
        exact_state = repair_destroyed_requests_exact_regret(
            instance,
            current_state,
            current_trips,
            current_components,
            removed_requests,
            dominant_part,
        )
        if exact_state is not None:
            return exact_state

    if repair_method == "regret":
        return repair_destroyed_requests_regret(instance, current_state, removed_requests, dominant_part)
    return repair_destroyed_requests_greedy(instance, current_state, removed_requests, dominant_part)

def adaptive_destroy_size(base_size, request_count, iterations_without_improvement):
    if iterations_without_improvement >= 50:
        multiplier = 3
    elif iterations_without_improvement >= 20:
        multiplier = 2
    else:
        multiplier = 1

    cap = max(base_size, int(request_count * 0.20))
    return max(1, min(base_size * multiplier, cap, request_count))

def run_alns(instance, initial_state, initial_trips=None, iterations=250, destroy_fraction=0.06, strategy="auto", repair_method="auto"):
    current_state = initial_state.copy()
    current_trips = (
        {day: clone_trips(trips) for day, trips in initial_trips.items()}
        if initial_trips is not None
        else build_trips_from_state(instance, current_state)
    )
    current_components = evaluate_cost_components(instance, current_trips)
    if not components_within_tool_limits(instance, current_components):
        print("      [ALNS] Initial route plan exceeds validator tool limits; skipping repair search.")
        return current_trips, current_state
    current_cost = current_components["total"]
    initial_dominant_part = dominant_cost_part(current_components) if strategy == "auto" else strategy

    if repair_method == "auto":
        selected_repair_method = "greedy" if initial_dominant_part == "distance" else "regret"
    else:
        selected_repair_method = repair_method

    current_score, current_components = score_completed_schedule(
        instance,
        current_trips,
        initial_dominant_part,
        current_components,
    )

    best_state = current_state.copy()
    best_trips = current_trips
    best_cost = current_cost
    best_score = current_score

    base_destroy_size = max(2, int(len(instance.Requests) * destroy_fraction))
    temperature = max(1000.0, current_cost * 0.001)
    cooling_rate = 0.995
    iterations_without_improvement = 0

    print(f"      [ALNS] Starting repair search. Initial Estimated Cost: {current_cost:,.0f}")
    print(f"      [ALNS] Strategy: {initial_dominant_part}")
    print(f"      [ALNS] Repair: {selected_repair_method}")
    print(f"      [ALNS] Base destroy size: {base_destroy_size}, iterations: {iterations}")

    for iteration in range(max(0, int(iterations))):
        destroy_size = adaptive_destroy_size(
            base_destroy_size,
            len(instance.Requests),
            iterations_without_improvement,
        )
        removed = choose_destroy_requests(
            instance,
            current_state,
            current_trips,
            current_components,
            destroy_size,
        )
        new_state = repair_destroyed_requests(
            instance,
            current_state,
            removed,
            initial_dominant_part,
            repair_method=selected_repair_method,
            current_trips=current_trips,
            current_components=current_components,
        )
        if new_state is None or not is_schedule_feasible(instance, new_state):
            temperature *= cooling_rate
            continue

        new_trips, affected_days = patch_trips_from_state(instance, current_trips, current_state, new_state)
        new_components = evaluate_delta_cost_components(
            instance,
            current_components,
            new_trips,
            affected_days,
        )
        if not components_within_tool_limits(instance, new_components):
            temperature *= cooling_rate
            continue
        new_cost = new_components["total"]
        new_score, new_components = score_components(
            instance,
            new_components,
            initial_dominant_part,
            current_components,
        )

        guard_allows = component_guard_allows(
            instance,
            initial_dominant_part,
            current_components,
            new_components,
            temperature,
        )
        accept = guard_allows and new_score < current_score
        if not accept:
            delta = new_score - current_score
            accept = guard_allows and random.random() < math.exp(-delta / max(temperature, 1.0))

        if accept:
            current_state = new_state
            current_trips = new_trips
            current_components = new_components
            current_cost = new_cost
            current_score = new_score

        if new_score < best_score and new_cost <= best_cost:
            best_state = new_state.copy()
            best_trips = new_trips
            best_cost = new_cost
            best_score = new_score
            iterations_without_improvement = 0
            print(f"      [ALNS] Iteration {iteration + 1}: new best {best_cost:,.0f}")
        else:
            iterations_without_improvement += 1

        temperature *= cooling_rate

    print(f"      [ALNS] Complete. Best Estimated Cost: {best_cost:,.0f}")
    return best_trips, best_state

def estimate_initial_temperature(instance, current_state, current_trips, current_components, samples=35, target_acceptance=0.65):
    uphill_deltas = []
    current_cost = current_components["total"]
    floor_temperature = max(1000.0, current_cost * 0.01)
    cap_temperature = max(floor_temperature, current_cost * 0.05)

    for _ in range(samples):
        new_state = propose_cost_aware_neighbor(
            instance,
            current_state,
            current_trips,
            current_components,
        )
        if new_state is None or not is_schedule_feasible(instance, new_state):
            continue

        new_trips, affected_days = patch_trips_from_state(instance, current_trips, current_state, new_state)
        new_components = evaluate_delta_cost_components(
            instance,
            current_components,
            new_trips,
            affected_days,
        )
        if not components_within_tool_limits(instance, new_components):
            continue

        delta = new_components["total"] - current_cost
        if delta > 0:
            uphill_deltas.append(delta)

    if not uphill_deltas:
        return floor_temperature

    uphill_deltas.sort()
    median_delta = uphill_deltas[len(uphill_deltas) // 2]
    temperature = -median_delta / math.log(target_acceptance)
    return min(
        max(floor_temperature, temperature),
        cap_temperature,
    )

def solve_sa_single(instance, return_state=False, initial_state=None):
    calculate_all_distances(instance)
    
    print("      [SA] Initializing starting solution...")
    current_state = initial_state.copy() if initial_state is not None else generate_initial_solution(instance)
    
    if current_state is None or not is_schedule_feasible(instance, current_state):
        print("      [SA] Warning: Baseline failed to provide valid state. Fallback to empty.")
        empty_schedule = {day: [] for day in range(1, instance.Days + 2)}
        return (empty_schedule, {}) if return_state else empty_schedule

    current_trips = build_trips_from_state(instance, current_state)
    current_components = evaluate_cost_components(instance, current_trips)
    if not components_within_tool_limits(instance, current_components):
        print("      [SA] Warning: Initial route plan exceeds validator tool limits.")
    current_cost = current_components["total"]
    
    best_state = current_state.copy()
    best_cost = current_cost
    best_trips = {k: v.copy() for k, v in current_trips.items()}
    
    temperature = estimate_initial_temperature(
        instance,
        current_state,
        current_trips,
        current_components,
    )
    cooling_rate = 0.92
    min_temperature = max(1.0, temperature * 0.002)
    iterations_per_temp = 8
    
    print(f"      [SA] Starting Annealing. Initial Estimated Cost: {current_cost:,.0f}")
    print(f"      [SA] Initial dominant cost part: {dominant_cost_part(current_components)}")
    print(f"      [SA] Initial temperature: {temperature:,.0f}")
    
    while temperature > min_temperature:
        for _ in range(iterations_per_temp):
            new_state = propose_cost_aware_neighbor(instance, current_state, current_trips, current_components)
            if new_state is None:
                continue
            
            if not is_schedule_feasible(instance, new_state):
                continue

            new_trips, affected_days = patch_trips_from_state(instance, current_trips, current_state, new_state)
            new_components = evaluate_delta_cost_components(
                instance,
                current_components,
                new_trips,
                affected_days,
            )
            if not components_within_tool_limits(instance, new_components):
                continue
            new_cost = new_components["total"]
            
            if new_cost < current_cost:
                current_cost = new_cost
                current_state = new_state
                current_trips = new_trips
                current_components = new_components
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_state = current_state.copy()
                    best_trips = {k: v.copy() for k, v in current_trips.items()}
            else:
                if not component_guard_allows(
                    instance,
                    dominant_cost_part(current_components),
                    current_components,
                    new_components,
                    temperature,
                ):
                    continue
                delta = new_cost - current_cost
                probability = math.exp(-delta / temperature)
                if random.random() < probability:
                    current_cost = new_cost 
                    current_state = new_state
                    current_trips = new_trips
                    current_components = new_components
                    
        temperature *= cooling_rate
        
    print(f"      [SA] Annealing Complete. Best Estimated Cost: {best_cost:,.0f}")
    if return_state:
        return best_trips, best_state
    return best_trips

def solve_sa(instance, runs=1, seed=None, route_merge=True, routing_method="greedy", alns_iterations=0, alns_destroy_fraction=0.06, alns_strategy="auto", alns_repair="auto"):
    set_routing_method(routing_method)
    runs = max(1, int(runs))
    initial_state = generate_initial_solution(instance)

    if runs == 1:
        if seed is not None:
            random.seed(seed)
        schedule, state = solve_sa_single(instance, return_state=True, initial_state=initial_state)
        if alns_iterations:
            schedule, state = run_alns(
                instance,
                state,
                initial_trips=schedule,
                iterations=alns_iterations,
                destroy_fraction=alns_destroy_fraction,
                strategy=alns_strategy,
                repair_method=alns_repair,
            )
        if route_merge:
            schedule = merge_routes_postprocess(instance, schedule)
        return schedule

    best_schedule = None
    best_state = None
    best_cost = float('inf')

    print(f"      [SA] Multi-start enabled: {runs} runs")
    for run_idx in range(runs):
        if seed is not None:
            random.seed(seed + run_idx)

        print(f"      [SA] Run {run_idx + 1}/{runs}")
        schedule, state = solve_sa_single(instance, return_state=True, initial_state=initial_state)
        if alns_iterations:
            schedule, state = run_alns(
                instance,
                state,
                initial_trips=schedule,
                iterations=alns_iterations,
                destroy_fraction=alns_destroy_fraction,
                strategy=alns_strategy,
                repair_method=alns_repair,
            )
        if route_merge:
            schedule = merge_routes_postprocess(instance, schedule)
        cost = evaluate_cost(instance, schedule)

        if cost < best_cost:
            best_cost = cost
            best_schedule = schedule
            best_state = state
            print(f"      [SA] New multi-start best: {best_cost:,.0f}")

    print(f"      [SA] Multi-start complete. Best Estimated Cost: {best_cost:,.0f}")
    return best_schedule
