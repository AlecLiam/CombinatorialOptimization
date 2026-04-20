import random
import math
from algorithms.baseline_solver import solve_baseline

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
    
    return (max_vehicles * veh_cost) + (vehicle_days * veh_day_cost) + (total_distance * dist_cost) + tool_cost

def route_day(instance, tasks):
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

def solve_sa(instance):
    calculate_all_distances(instance)
    
    print("      [SA] Initializing starting solution...")
    current_state = generate_initial_solution(instance)
    
    if current_state is None or not is_schedule_feasible(instance, current_state):
        print("      [SA] Warning: Baseline failed to provide valid state. Fallback to empty.")
        return {day: [] for day in range(1, instance.Days + 2)}

    current_trips = {day: [] for day in range(1, instance.Days + 2)}
    for day in range(1, instance.Days + 2):
        tasks = get_tasks_for_day(instance, current_state, day)
        current_trips[day] = route_day(instance, tasks)
        
    current_cost = evaluate_cost(instance, current_trips)
    
    best_state = current_state.copy()
    best_cost = current_cost
    best_trips = {k: v.copy() for k, v in current_trips.items()}
    
    temperature = 5000.0
    cooling_rate = 0.95
    min_temperature = 1.0
    iterations_per_temp = 10
    
    print(f"      [SA] Starting Annealing. Initial Estimated Cost: {current_cost:,.0f}")
    
    while temperature > min_temperature:
        for _ in range(iterations_per_temp):
            req = random.choice(instance.Requests)
            old_start = current_state[req.ID]
            old_pickup = old_start + req.numDays
            
            possible_days = list(range(req.fromDay, req.toDay + 1))
            if len(possible_days) <= 1: continue
            possible_days.remove(old_start)
            new_start = random.choice(possible_days)
            new_pickup = new_start + req.numDays
            
            current_state[req.ID] = new_start
            
            if not is_schedule_feasible(instance, current_state):
                current_state[req.ID] = old_start 
                continue
                
            affected_days = {d for d in [old_start, old_pickup, new_start, new_pickup] if d <= instance.Days}
            
            new_trips = current_trips.copy()
            for d in affected_days:
                tasks = get_tasks_for_day(instance, current_state, d)
                new_trips[d] = route_day(instance, tasks)
                
            new_cost = evaluate_cost(instance, new_trips)
            
            if new_cost < current_cost:
                current_cost = new_cost
                current_trips = new_trips
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_state = current_state.copy()
                    best_trips = {k: v.copy() for k, v in current_trips.items()}
            else:
                delta = new_cost - current_cost
                probability = math.exp(-delta / temperature)
                if random.random() < probability:
                    current_cost = new_cost 
                    current_trips = new_trips
                else:
                    current_state[req.ID] = old_start 
                    
        temperature *= cooling_rate
        
    print(f"      [SA] Annealing Complete. Best Estimated Cost: {best_cost:,.0f}")
    return best_trips