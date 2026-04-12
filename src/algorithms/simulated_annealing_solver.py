import random
import math
from utils import calculate_all_distances, is_schedule_feasible, get_tasks_for_day, route_day, build_heuristic_trips, evaluate_cost

def generate_initial_solution(instance):
    from algorithms.baseline_solver import solve_baseline
    baseline_schedule = solve_baseline(instance)
    
    start_days = {}
    for day, trips in baseline_schedule.items():
        for trip in trips:
            route = trip["route"]
            for i in range(1, len(route) - 1):
                req_id = route[i]
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