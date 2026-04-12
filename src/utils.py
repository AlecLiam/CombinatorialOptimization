import math

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
                
                # Accurately calculate the true net depot interactions
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
                    # tools_loaded must be negative (taken from depot)
                    tools_loaded[tool_idx] = min_inv
                    tools_returned[tool_idx] = -min_inv + current_inv
                    
                # Evaluate Capacity exactly based on depot loaded tools
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
            
        # Fallback if a single giant task somehow fails normal checks
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
        
        total_dist += instance.calcDistance[curr_node][depot]
        
        route_nodes = [depot]
        for t in route_tasks:
            node_id = t["req"].ID if t["type"] == "delivery" else -t["req"].ID
            route_nodes.append(node_id)
        route_nodes.append(depot)
        
        trips.append({
            "route": route_nodes,
            "tools_loaded": best_tools_loaded,
            "tools_returned": best_tools_returned,
            "distance": total_dist
        })
        
    return trips

def build_heuristic_trips(instance, start_days):
    calculate_all_distances(instance)
    schedule_by_day = {day: [] for day in range(1, instance.Days + 2)}
    for day in range(1, instance.Days + 2):
        tasks = get_tasks_for_day(instance, start_days, day)
        schedule_by_day[day] = route_day(instance, tasks)
    return schedule_by_day

def evaluate_cost(instance, trips_dict):
    dist_cost = 0
    veh_cost = 100000 
    for attr in ['VehicleCost', 'vehicleCost', 'vehicle_cost', 'VehicleDayCost']:
        if hasattr(instance, attr):
            veh_cost = getattr(instance, attr)
            break
            
    num_vehicles = sum(len(trips) for trips in trips_dict.values())
    for trips in trips_dict.values():
        for trip in trips:
            dist_cost += trip["distance"]
            
    return dist_cost + (num_vehicles * veh_cost)