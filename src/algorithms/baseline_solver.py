import random

def calculate_all_distances(instance):
    if instance.calcDistance is None:
        instance.calculateDistances()

def route_day_naive(instance, tasks):
    if not tasks: return []
    
    depot = instance.DepotCoordinate
    num_tools = len(instance.Tools)
    trips = []
    
    for task in tasks:
        req = task["req"]
        node_id = req.ID if task["type"] == "delivery" else -req.ID
        dist = instance.calcDistance[depot][req.node] + instance.calcDistance[req.node][depot]
        
        tools_loaded = [0] * num_tools
        tools_returned = [0] * num_tools
        
        if task["type"] == "delivery":
            tools_loaded[req.tool - 1] = -req.toolCount
        else:
            tools_returned[req.tool - 1] = req.toolCount
            
        trips.append({
            "route": [depot, node_id, depot],
            "tools_loaded": tools_loaded,
            "tools_returned": tools_returned,
            "distance": dist
        })
        
    return trips

def build_baseline_trips(instance, start_days):
    calculate_all_distances(instance)
    schedule_by_day = {day: [] for day in range(1, instance.Days + 2)}
    for day in range(1, instance.Days + 2):
        tasks = []
        for req in instance.Requests:
            sd = start_days[req.ID]
            if sd == day:
                tasks.append({"req": req, "type": "delivery"})
            pd = sd + req.numDays
            if pd == day and pd <= instance.Days:
                tasks.append({"req": req, "type": "pickup"})
        schedule_by_day[day] = route_day_naive(instance, tasks)
    return schedule_by_day

def solve_baseline(instance):
    calculate_all_distances(instance)
    num_tools = len(instance.Tools)

    def attempt_greedy(sorted_reqs):
        start_days = {}
        daily_tool_usage = {day: [0] * num_tools for day in range(1, instance.Days + 2)}
        
        for req in sorted_reqs:
            tool_idx = req.tool - 1
            max_cap = instance.Tools[tool_idx].amount
            best_start_day = None

            for start_day in range(req.fromDay, req.toDay + 1):
                peak = 0
                for d in range(start_day, start_day + req.numDays + 1):
                    if d <= instance.Days:
                        if daily_tool_usage[d][tool_idx] > peak:
                            peak = daily_tool_usage[d][tool_idx]
                
                if peak + req.toolCount <= max_cap:
                    best_start_day = start_day
                    break 

            if best_start_day is None:
                return None
            
            start_days[req.ID] = best_start_day
            for d in range(best_start_day, best_start_day + req.numDays + 1):
                if d <= instance.Days:
                    daily_tool_usage[d][tool_idx] += req.toolCount
                    
        return start_days

    sort_keys = [
        lambda r: (r.toDay - r.fromDay, -r.toolCount),
        lambda r: (-r.toolCount, r.toDay - r.fromDay),
        lambda r: (r.fromDay, r.toDay - r.fromDay),
        lambda r: (-r.toolCount, r.fromDay),
        lambda r: (r.toDay, -r.toolCount),
        lambda r: (-r.toolCount * r.numDays, r.toDay - r.fromDay)
    ]

    for sort_key in sort_keys:
        sorted_requests = sorted(instance.Requests, key=sort_key)
        result = attempt_greedy(sorted_requests)
        if result is not None:
            return build_baseline_trips(instance, result)

    def attempt_min_conflicts():
        start_days = {req.ID: random.randint(req.fromDay, req.toDay) for req in instance.Requests}
        usage = {d: [0]*num_tools for d in range(1, instance.Days + 2)}
        for req in instance.Requests:
            sd = start_days[req.ID]
            for d in range(sd, sd + req.numDays + 1):
                if d <= instance.Days:
                    usage[d][req.tool - 1] += req.toolCount
                    
        for iteration in range(2000):
            violating_reqs = []
            for req in instance.Requests:
                sd = start_days[req.ID]
                is_violating = False
                for d in range(sd, sd + req.numDays + 1):
                    if d <= instance.Days and usage[d][req.tool - 1] > instance.Tools[req.tool - 1].amount:
                        is_violating = True
                        break
                if is_violating:
                    violating_reqs.append(req)
                    
            if not violating_reqs:
                return start_days
                
            req = random.choice(violating_reqs)
            current_sd = start_days[req.ID]
            tool_idx = req.tool - 1
            max_cap = instance.Tools[tool_idx].amount
            
            for d in range(current_sd, current_sd + req.numDays + 1):
                if d <= instance.Days:
                    usage[d][tool_idx] -= req.toolCount
                    
            best_days = []
            min_v = float('inf')
            
            for potential_sd in range(req.fromDay, req.toDay + 1):
                v = 0
                for d in range(1, instance.Days + 2):
                    daily_amt = usage[d][tool_idx]
                    if potential_sd <= d <= potential_sd + req.numDays:
                        daily_amt += req.toolCount
                    if daily_amt > max_cap:
                        v += daily_amt - max_cap
                
                if v < min_v:
                    min_v = v
                    best_days = [potential_sd]
                elif v == min_v:
                    best_days.append(potential_sd)
                    
            new_sd = random.choice(best_days)
            start_days[req.ID] = new_sd
            
            for d in range(new_sd, new_sd + req.numDays + 1):
                if d <= instance.Days:
                    usage[d][tool_idx] += req.toolCount
                    
        return None

    for restart in range(50):
        res = attempt_min_conflicts()
        if res is not None:
            return build_baseline_trips(instance, res)

    return {day: [] for day in range(1, instance.Days + 2)}