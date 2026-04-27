import random
import math
from algorithms.baseline_solver import solve_baseline

ROUTING_METHOD = "greedy"

def set_routing_method(method):
    global ROUTING_METHOD
    if method not in ("greedy", "insertion"):
        raise ValueError(f"Unknown routing method: {method}")
    ROUTING_METHOD = method

def calculate_all_distances(instance):
    if instance.calcDistance is None:
        instance.calculateDistances()

def is_schedule_feasible(instance, start_days):
    num_tools = len(instance.Tools)
    daily_usage = {d: [0] * num_tools for d in range(1, instance.Days + 2)}
    
    for req in instance.Requests:
        sd = start_days[req.ID]
        for d in range(sd, sd + req.numDays + 1):
            if d <= instance.Days:
                daily_usage[d][req.tool - 1] += req.toolCount
                if daily_usage[d][req.tool - 1] > instance.Tools[req.tool - 1].amount:
                    return False
    return True

def get_tool_size(tool):
    for attr in ['size', 'Size', 'weight', 'Weight', 'volume', 'Volume', 'toolSize', 'tool_size']:
        if hasattr(tool, attr):
            return getattr(tool, attr)
    if hasattr(tool, '__dict__'):
        candidates = [v for k, v in tool.__dict__.items() if isinstance(v, (int, float)) and k.lower() not in ['id', 'amount', 'cost', 'tool', 'req']]
        if candidates: return candidates[0]
    return 1

def get_tasks_for_day(instance, start_days, day):
    tasks = []
    for req in instance.Requests:
        sd = start_days[req.ID]
        if sd == day:
            tasks.append({"req": req, "type": "delivery"})
        pd = sd + req.numDays
        if pd == day and pd <= instance.Days:
            tasks.append({"req": req, "type": "pickup"})
    return tasks

def evaluate_cost(instance, schedule_by_day):
    return evaluate_cost_components(instance, schedule_by_day)["total"]

def evaluate_cost_components(instance, schedule_by_day):
    num_tools = len(instance.Tools)
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
                
    tool_use = [abs(x) for x in min_inventory]
    tool_cost = sum(tool_use[i] * instance.Tools[i].cost for i in range(num_tools))
    
    max_vehicles = max((len(trips) for trips in schedule_by_day.values()), default=0)
    vehicle_days = sum(len(trips) for trips in schedule_by_day.values())
    total_distance = sum(trip["distance"] for trips in schedule_by_day.values() for trip in trips)
    
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
    }

def build_trips_from_state(instance, start_days):
    trips_by_day = {day: [] for day in range(1, instance.Days + 2)}
    for day in range(1, instance.Days + 2):
        tasks = get_tasks_for_day(instance, start_days, day)
        trips_by_day[day] = route_day(instance, tasks)
    return trips_by_day

def changed_request_ids(old_state, new_state):
    return [
        req_id for req_id, old_day in old_state.items()
        if new_state.get(req_id) != old_day
    ]

def affected_days_for_requests(instance, old_state, new_state, req_ids):
    affected_days = set()
    requests_by_id = {req.ID: req for req in instance.Requests}

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
    patched_trips = current_trips.copy()
    for day in affected_days:
        tasks = get_tasks_for_day(instance, new_state, day)
        patched_trips[day] = route_day(instance, tasks)

    return patched_trips, affected_days

def route_day_greedy(instance, tasks):
    if not tasks: return []
    
    depot = instance.DepotCoordinate
    num_tools = len(instance.Tools)
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
                    
                start_cap = sum(-tools_loaded[i] * get_tool_size(instance.Tools[i]) for i in range(num_tools))
                if start_cap > instance.Capacity:
                    continue
                    
                curr_cap = start_cap
                max_cap = start_cap
                for t in temp_route:
                    t_size = t["req"].toolCount * get_tool_size(instance.Tools[t["req"].tool - 1])
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
    requests_by_id = {req.ID: req for req in instance.Requests}
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
    if node == 0:
        return instance.DepotCoordinate
    return instance.Requests[abs(node) - 1].node

def build_trip_from_route(instance, route):
    if len(route) < 3 or route[0] != 0 or route[-1] != 0:
        return None

    num_tools = len(instance.Tools)
    total_dist = 0
    for prev_node, next_node in zip(route, route[1:]):
        if prev_node == 0 and next_node == 0:
            return None
        from_coord = route_node_coordinate(instance, prev_node)
        to_coord = route_node_coordinate(instance, next_node)
        total_dist += instance.calcDistance[from_coord][to_coord]

    if total_dist > instance.MaxDistance:
        return None

    tool_size = [get_tool_size(tool) for tool in instance.Tools]
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
            req = instance.Requests[abs(node) - 1]
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

def route_day_insertion(instance, tasks):
    if not tasks:
        return []

    unrouted = sorted(
        tasks,
        key=lambda task: instance.calcDistance[instance.DepotCoordinate][task["req"].node],
        reverse=True,
    )
    route_task_lists = []

    while unrouted:
        best_move = None
        best_score = None

        for task in unrouted:
            single_trip = build_trip_from_tasks(instance, [task])
            if single_trip is None:
                continue

            if not route_task_lists:
                best_move = ("new", task, None, None)
                break

            for route_idx, route_tasks in enumerate(route_task_lists):
                old_trip = build_trip_from_tasks(instance, route_tasks)
                old_distance = old_trip["distance"] if old_trip else 0
                for pos in range(len(route_tasks) + 1):
                    candidate_tasks = route_tasks[:pos] + [task] + route_tasks[pos:]
                    candidate_trip = build_trip_from_tasks(instance, candidate_tasks)
                    if candidate_trip is None:
                        continue
                    distance_increase = candidate_trip["distance"] - old_distance
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
        build_trip_from_tasks(instance, route_tasks)
        for route_tasks in route_task_lists
    ]

def route_day(instance, tasks):
    if ROUTING_METHOD == "insertion":
        return route_day_insertion(instance, tasks)
    return route_day_greedy(instance, tasks)

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

def greedy_insert_tasks(instance, base_tasks, inserted_tasks):
    merged = base_tasks.copy()
    for task in inserted_tasks:
        best_sequence = None
        best_distance = float('inf')
        for pos in range(len(merged) + 1):
            candidate = merged[:pos] + [task] + merged[pos:]
            trip = build_trip_from_tasks(instance, candidate)
            if trip is None:
                continue
            if trip["distance"] < best_distance:
                best_distance = trip["distance"]
                best_sequence = candidate
        if best_sequence is None:
            return None
        merged = best_sequence
    return build_trip_from_tasks(instance, merged)

def try_merge_trips(instance, trip_a, trip_b):
    tasks_a = route_to_tasks(instance, trip_a["route"])
    tasks_b = route_to_tasks(instance, trip_b["route"])
    candidates = []

    for route in (
        trip_a["route"] + trip_b["route"][1:],
        trip_b["route"] + trip_a["route"][1:],
    ):
        trip = build_trip_from_route(instance, route)
        if trip is not None:
            candidates.append(trip)

    for task_sequence in (tasks_a + tasks_b, tasks_b + tasks_a):
        trip = build_trip_from_tasks(instance, task_sequence)
        if trip is not None:
            candidates.append(trip)

    insertion_candidates = [
        (tasks_a, tasks_b),
        (tasks_b, tasks_a),
        (tasks_a, list(reversed(tasks_b))),
        (tasks_b, list(reversed(tasks_a))),
    ]
    for base_tasks, inserted_tasks in insertion_candidates:
        trip = greedy_insert_tasks(instance, base_tasks, inserted_tasks)
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
    current_cost = evaluate_cost(instance, improved_schedule)
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
                    candidate_cost = evaluate_cost(instance, candidate_schedule)

                    if candidate_cost < best_cost:
                        best_cost = candidate_cost
                        best_move = (day, i, j, merged_trip)

        if best_move is not None:
            day, i, j, merged_trip = best_move
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

def generate_initial_solution(instance):
    baseline_schedule = solve_baseline(instance)
    
    start_days = {}
    for day, trips in baseline_schedule.items():
        for trip in trips:
            route = trip["route"]
            for i in range(1, len(route) - 1):
                req_id = abs(route[i])
                if req_id > 0 and req_id not in start_days: 
                    start_days[req_id] = day
                    
    if len(start_days) == len(instance.Requests):
        return start_days
    
    return {req.ID: req.fromDay for req in instance.Requests}

def calculate_daily_tool_usage(instance, start_days):
    num_tools = len(instance.Tools)
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    for req in instance.Requests:
        start_day = start_days[req.ID]
        for day in range(start_day, start_day + req.numDays + 1):
            if day <= instance.Days:
                daily_usage[day][req.tool - 1] += req.toolCount
    return daily_usage

def calculate_partial_daily_tool_usage(instance, partial_state):
    num_tools = len(instance.Tools)
    daily_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
    for req in instance.Requests:
        if req.ID not in partial_state:
            continue
        start_day = partial_state[req.ID]
        for day in range(start_day, start_day + req.numDays + 1):
            if day <= instance.Days:
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
    for req in instance.Requests:
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

def requests_touching_day(instance, start_days, day):
    candidates = []
    for req in instance.Requests:
        start_day = start_days[req.ID]
        pickup_day = start_day + req.numDays
        if start_day == day or pickup_day == day:
            candidates.append(req)
    return candidates

def choose_peak_tool_request(instance, start_days):
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

def propose_best_tool_move(instance, current_state, req):
    old_start = current_state[req.ID]
    best_state = None
    best_tool_cost = None

    for candidate_day in range(req.fromDay, req.toDay + 1):
        if candidate_day == old_start:
            continue
        candidate_state = current_state.copy()
        candidate_state[req.ID] = candidate_day
        if not is_schedule_feasible(instance, candidate_state):
            continue
        daily_usage = calculate_daily_tool_usage(instance, candidate_state)
        tool_use = [
            max(usage[tool_idx] for usage in daily_usage.values())
            for tool_idx in range(len(instance.Tools))
        ]
        tool_cost = sum(tool_use[i] * instance.Tools[i].cost for i in range(len(instance.Tools)))
        if best_tool_cost is None or tool_cost < best_tool_cost:
            best_tool_cost = tool_cost
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
        req = choose_peak_tool_request(instance, current_state)
        return propose_best_tool_move(instance, current_state, req)

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
        anchor = choose_peak_tool_request(instance, current_state)
        candidates = [anchor] + nearby_related_requests(instance, anchor, limit=destroy_size * 2)
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

def score_completed_schedule(instance, schedule, dominant_part, reference_components=None):
    components = evaluate_cost_components(instance, schedule)

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

def partial_repair_score(instance, partial_state, dominant_part):
    daily_usage = calculate_partial_daily_tool_usage(instance, partial_state)
    tool_use = [
        max(usage[tool_idx] for usage in daily_usage.values())
        for tool_idx in range(len(instance.Tools))
    ]
    tool_cost = sum(tool_use[i] * instance.Tools[i].cost for i in range(len(instance.Tools)))

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

    if dominant_part == "tools":
        return (
            tool_cost +
            0.05 * task_day_proxy * instance.VehicleDayCost +
            0.01 * distance_roundtrip_proxy * instance.DistanceCost
        )

    if dominant_part == "vehicle_days":
        return (
            task_day_proxy * instance.VehicleDayCost +
            0.2 * max_task_day_proxy * instance.VehicleCost +
            0.05 * tool_cost
        )

    if dominant_part == "fixed_vehicle":
        return (
            max_task_day_proxy * instance.VehicleCost +
            0.2 * task_day_proxy * instance.VehicleDayCost +
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
        score = partial_repair_score(instance, candidate_state, dominant_part)
        options.append((score, candidate_day))

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

            score = partial_repair_score(instance, candidate_state, dominant_part)
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

def repair_destroyed_requests(instance, current_state, removed_requests, dominant_part, repair_method="greedy"):
    if repair_method == "regret":
        return repair_destroyed_requests_regret(instance, current_state, removed_requests, dominant_part)
    return repair_destroyed_requests_greedy(instance, current_state, removed_requests, dominant_part)

def run_alns(instance, initial_state, iterations=250, destroy_fraction=0.06, strategy="auto", repair_method="auto"):
    current_state = initial_state.copy()
    current_trips = build_trips_from_state(instance, current_state)
    current_components = evaluate_cost_components(instance, current_trips)
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

    destroy_size = max(2, int(len(instance.Requests) * destroy_fraction))
    temperature = max(1000.0, current_cost * 0.001)
    cooling_rate = 0.995

    print(f"      [ALNS] Starting repair search. Initial Estimated Cost: {current_cost:,.0f}")
    print(f"      [ALNS] Strategy: {initial_dominant_part}")
    print(f"      [ALNS] Repair: {selected_repair_method}")
    print(f"      [ALNS] Destroy size: {destroy_size}, iterations: {iterations}")

    for iteration in range(max(0, int(iterations))):
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
        )
        if new_state is None or not is_schedule_feasible(instance, new_state):
            temperature *= cooling_rate
            continue

        new_trips, _ = patch_trips_from_state(instance, current_trips, current_state, new_state)
        new_components = evaluate_cost_components(instance, new_trips)
        new_cost = new_components["total"]
        new_score, new_components = score_completed_schedule(
            instance,
            new_trips,
            initial_dominant_part,
            current_components,
        )

        accept = new_score < current_score
        if not accept:
            delta = new_score - current_score
            accept = random.random() < math.exp(-delta / max(temperature, 1.0))

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
            print(f"      [ALNS] Iteration {iteration + 1}: new best {best_cost:,.0f}")

        temperature *= cooling_rate

    print(f"      [ALNS] Complete. Best Estimated Cost: {best_cost:,.0f}")
    return best_trips, best_state

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
    current_cost = current_components["total"]
    
    best_state = current_state.copy()
    best_cost = current_cost
    best_trips = {k: v.copy() for k, v in current_trips.items()}
    
    temperature = 5000.0
    cooling_rate = 0.95
    min_temperature = 1.0
    iterations_per_temp = 10
    
    print(f"      [SA] Starting Annealing. Initial Estimated Cost: {current_cost:,.0f}")
    print(f"      [SA] Initial dominant cost part: {dominant_cost_part(current_components)}")
    
    while temperature > min_temperature:
        for _ in range(iterations_per_temp):
            new_state = propose_cost_aware_neighbor(instance, current_state, current_trips, current_components)
            if new_state is None:
                continue
            
            if not is_schedule_feasible(instance, new_state):
                continue

            new_trips, _ = patch_trips_from_state(instance, current_trips, current_state, new_state)
            new_components = evaluate_cost_components(instance, new_trips)
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
