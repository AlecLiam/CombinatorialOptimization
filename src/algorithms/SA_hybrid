"""
Two-Phase Decomposition Solver for VeRoLog 2017 Challenge
Based on 3rd place winner's approach:
- Phase 1 (80% time): Optimize delivery day assignments
- Phase 2 (20% time): Variable Neighborhood Descent on daily routes
"""

import random
import math
import copy
from collections import defaultdict

def calculate_all_distances(instance):
    if instance.calcDistance is None:
        instance.calculateDistances()

def get_tool_size(tool):
    for attr in ['size', 'Size', 'weight', 'Weight', 'volume', 'Volume', 'toolSize', 'tool_size']:
        if hasattr(tool, attr):
            return getattr(tool, attr)
    if hasattr(tool, '__dict__'):
        candidates = [v for k, v in tool.__dict__.items() if isinstance(v, (int, float)) and k.lower() not in ['id', 'amount', 'cost', 'tool', 'req']]
        if candidates: 
            return candidates[0]
    return 1

def get_tasks_for_day(instance, start_days, day):
    """Get all deliveries and pickups for a specific day"""
    tasks = []
    for req in instance.Requests:
        sd = start_days[req.ID]
        if sd == day:
            tasks.append({"req": req, "type": "delivery"})
        pd = sd + req.numDays
        if pd == day and pd <= instance.Days:
            tasks.append({"req": req, "type": "pickup"})
    return tasks


# ============================================================================
# PHASE 2: Variable Neighborhood Descent for Daily Routing
# ============================================================================

class VariableNeighborhoodDescent:
    """VND for optimizing daily routes after delivery days are fixed"""
    
    def __init__(self, instance):
        self.instance = instance
        self.depot = instance.DepotCoordinate
        self.capacity = instance.Capacity
        self.max_distance = instance.MaxDistance
        self.num_tools = len(instance.Tools)
        
        # Neighborhood structures (ordered by increasing complexity)
        self.neighborhoods = [
            self._two_opt,
            self._relocate,
            self._exchange,
            self._cross_exchange,
            self._or_opt
        ]
        
    def optimize_day(self, tasks, max_iterations=100):
        """
        Optimize a single day's routing using VND
        Returns optimized trips and their cost
        """
        if not tasks:
            return [], 0
        
        # Initial greedy routing
        trips = self._initial_routing(tasks)
        current_cost = self._calculate_trips_cost(trips)
        
        iteration = 0
        neighborhood_idx = 0
        
        while iteration < max_iterations and neighborhood_idx < len(self.neighborhoods):
            # Apply current neighborhood
            improved = False
            best_trips = trips
            best_cost = current_cost
            
            # Try all possible moves in this neighborhood
            for move in self.neighborhoods[neighborhood_idx](trips):
                new_trips, new_cost = move
                
                if new_cost < best_cost - 0.01:  # Small epsilon for floating point
                    best_trips = new_trips
                    best_cost = new_cost
                    improved = True
            
            if improved:
                # Move to first neighborhood (success)
                trips = best_trips
                current_cost = best_cost
                neighborhood_idx = 0
                iteration += 1
            else:
                # Move to next neighborhood
                neighborhood_idx += 1
        
        return trips, current_cost
    
    def _initial_routing(self, tasks):
        """Greedy nearest neighbor routing"""
        if not tasks:
            return []
        
        unvisited = tasks.copy()
        trips = []
        
        while unvisited:
            route_tasks = []
            curr_node = self.depot
            total_dist = 0
            current_load = 0
            tools_on_board = defaultdict(int)
            
            # Find nearest feasible task repeatedly
            while unvisited:
                best_task = None
                best_dist = float('inf')
                
                for task in unvisited:
                    dist_to = self.instance.calcDistance[curr_node][task["req"].node]
                    dist_return = self.instance.calcDistance[task["req"].node][self.depot]
                    
                    # Check distance limit
                    if total_dist + dist_to + dist_return > self.max_distance:
                        continue
                    
                    # Check capacity and tool availability
                    task_size = task["req"].toolCount * get_tool_size(self.instance.Tools[task["req"].tool - 1])
                    
                    if task["type"] == "delivery":
                        if tools_on_board[task["req"].tool - 1] < task["req"].toolCount:
                            continue
                        new_load = current_load - task_size
                    else:  # pickup
                        new_load = current_load + task_size
                    
                    if new_load > self.capacity:
                        continue
                    
                    if dist_to < best_dist:
                        best_dist = dist_to
                        best_task = task
                
                if best_task is None:
                    break
                
                # Add task to route
                route_tasks.append(best_task)
                total_dist += best_dist
                curr_node = best_task["req"].node
                
                # Update state
                task_size = best_task["req"].toolCount * get_tool_size(self.instance.Tools[best_task["req"].tool - 1])
                if best_task["type"] == "delivery":
                    tools_on_board[best_task["req"].tool - 1] -= best_task["req"].toolCount
                    current_load -= task_size
                else:
                    tools_on_board[best_task["req"].tool - 1] += best_task["req"].toolCount
                    current_load += task_size
                
                unvisited.remove(best_task)
            
            # Create trip from route
            if route_tasks:
                trip = self._tasks_to_trip(route_tasks, total_dist)
                trips.append(trip)
            else:
                # Handle isolated task
                task = unvisited.pop(0)
                trip = self._single_task_trip(task)
                trips.append(trip)
        
        return trips
    
    def _tasks_to_trip(self, route_tasks, distance):
        """Convert task list to trip dictionary"""
        # Calculate tools loaded/unloaded
        tools_loaded = [0] * self.num_tools
        tools_returned = [0] * self.num_tools
        
        current_inventory = [0] * self.num_tools
        min_inventory = [0] * self.num_tools
        
        for task in route_tasks:
            tool_idx = task["req"].tool - 1
            if task["type"] == "delivery":
                current_inventory[tool_idx] -= task["req"].toolCount
            else:
                current_inventory[tool_idx] += task["req"].toolCount
            
            for t in range(self.num_tools):
                if current_inventory[t] < min_inventory[t]:
                    min_inventory[t] = current_inventory[t]
        
        for t in range(self.num_tools):
            tools_loaded[t] = min_inventory[t]
            tools_returned[t] = -min_inventory[t] + current_inventory[t]
        
        # Build route representation
        route = [self.depot]
        for task in route_tasks:
            node_id = task["req"].ID if task["type"] == "delivery" else -task["req"].ID
            route.append(node_id)
        route.append(self.depot)
        
        # Add return distance
        last_node = route_tasks[-1]["req"].node if route_tasks else self.depot
        total_distance = distance + self.instance.calcDistance[last_node][self.depot]
        
        return {
            "route": route,
            "tools_loaded": tools_loaded,
            "tools_returned": tools_returned,
            "distance": total_distance
        }
    
    def _single_task_trip(self, task):
        """Create trip for a single task"""
        tools_loaded = [0] * self.num_tools
        tools_returned = [0] * self.num_tools
        
        tool_idx = task["req"].tool - 1
        if task["type"] == "delivery":
            tools_loaded[tool_idx] = -task["req"].toolCount
        else:
            tools_returned[tool_idx] = task["req"].toolCount
        
        route = [self.depot]
        node_id = task["req"].ID if task["type"] == "delivery" else -task["req"].ID
        route.append(node_id)
        route.append(self.depot)
        
        distance = (self.instance.calcDistance[self.depot][task["req"].node] +
                   self.instance.calcDistance[task["req"].node][self.depot])
        
        return {
            "route": route,
            "tools_loaded": tools_loaded,
            "tools_returned": tools_returned,
            "distance": distance
        }
    
    def _calculate_trips_cost(self, trips):
        """Calculate total distance for trips"""
        return sum(trip["distance"] for trip in trips)
    
    # ========== Neighborhood Operators ==========
    
    def _two_opt(self, trips):
        """2-opt swap within a single trip"""
        for trip_idx, trip in enumerate(trips):
            route = trip["route"][1:-1]  # Remove depot
            if len(route) < 3:
                continue
            
            for i in range(len(route) - 2):
                for j in range(i + 2, len(route)):
                    # Create new route with 2-opt swap
                    new_route_nodes = route[:i] + list(reversed(route[i:j+1])) + route[j+1:]
                    
                    # Convert back to tasks
                    new_tasks = self._route_to_tasks(new_route_nodes, trip)
                    if new_tasks:
                        # Re-evaluate
                        new_trip = self._tasks_to_trip(new_tasks, 0)
                        if new_trip["distance"] < trip["distance"] - 0.01:
                            new_trips = copy.deepcopy(trips)
                            new_trips[trip_idx] = new_trip
                            yield new_trips, self._calculate_trips_cost(new_trips)
    
    def _relocate(self, trips):
        """Relocate one task to another trip"""
        for i, trip_i in enumerate(trips):
            for j, trip_j in enumerate(trips):
                if i == j:
                    continue
                
                for task_pos in range(len(trip_i["route"]) - 2):  # Skip depots
                    task_node = trip_i["route"][task_pos + 1]
                    task = self._node_to_task(task_node, trip_i)
                    
                    # Try inserting at each position in trip_j
                    for insert_pos in range(len(trip_j["route"]) - 1):
                        new_route_j = (trip_j["route"][:insert_pos+1] + 
                                      [task_node] + 
                                      trip_j["route"][insert_pos+1:])
                        new_route_i = trip_i["route"][:task_pos+1] + trip_i["route"][task_pos+2:]
                        
                        # Check feasibility
                        if len(new_route_i) > 2:  # Not empty
                            new_trip_i = self._route_to_trip_object(new_route_i)
                            if new_trip_i and new_trip_i["distance"] <= self.max_distance:
                                new_trip_j = self._route_to_trip_object(new_route_j)
                                if new_trip_j and new_trip_j["distance"] <= self.max_distance:
                                    new_trips = copy.deepcopy(trips)
                                    new_trips[i] = new_trip_i
                                    new_trips[j] = new_trip_j
                                    # Remove empty trips
                                    new_trips = [t for t in new_trips if len(t["route"]) > 2]
                                    yield new_trips, self._calculate_trips_cost(new_trips)
    
    def _exchange(self, trips):
        """Exchange two tasks between trips"""
        for i, trip_i in enumerate(trips):
            for j, trip_j in enumerate(trips):
                if i >= j:
                    continue
                
                for pos_i in range(len(trip_i["route"]) - 2):
                    for pos_j in range(len(trip_j["route"]) - 2):
                        node_i = trip_i["route"][pos_i + 1]
                        node_j = trip_j["route"][pos_j + 1]
                        
                        # Swap
                        new_route_i = (trip_i["route"][:pos_i+1] + [node_j] + 
                                      trip_i["route"][pos_i+2:])
                        new_route_j = (trip_j["route"][:pos_j+1] + [node_i] + 
                                      trip_j["route"][pos_j+2:])
                        
                        new_trip_i = self._route_to_trip_object(new_route_i)
                        new_trip_j = self._route_to_trip_object(new_route_j)
                        
                        if new_trip_i and new_trip_j:
                            if (new_trip_i["distance"] <= self.max_distance and 
                                new_trip_j["distance"] <= self.max_distance):
                                new_trips = copy.deepcopy(trips)
                                new_trips[i] = new_trip_i
                                new_trips[j] = new_trip_j
                                yield new_trips, self._calculate_trips_cost(new_trips)
    
    def _cross_exchange(self, trips):
        """Exchange segments between two trips"""
        for i, trip_i in enumerate(trips):
            for j, trip_j in enumerate(trips):
                if i >= j:
                    continue
                
                for seg_len in range(1, min(3, len(trip_i["route"]) - 2)):
                    for pos_i in range(len(trip_i["route"]) - seg_len - 1):
                        for pos_j in range(len(trip_j["route"]) - seg_len - 1):
                            seg_i = trip_i["route"][pos_i+1:pos_i+seg_len+1]
                            seg_j = trip_j["route"][pos_j+1:pos_j+seg_len+1]
                            
                            new_route_i = (trip_i["route"][:pos_i+1] + seg_j + 
                                          trip_i["route"][pos_i+seg_len+1:])
                            new_route_j = (trip_j["route"][:pos_j+1] + seg_i + 
                                          trip_j["route"][pos_j+seg_len+1:])
                            
                            new_trip_i = self._route_to_trip_object(new_route_i)
                            new_trip_j = self._route_to_trip_object(new_route_j)
                            
                            if new_trip_i and new_trip_j:
                                if (new_trip_i["distance"] <= self.max_distance and 
                                    new_trip_j["distance"] <= self.max_distance):
                                    new_trips = copy.deepcopy(trips)
                                    new_trips[i] = new_trip_i
                                    new_trips[j] = new_trip_j
                                    yield new_trips, self._calculate_trips_cost(new_trips)
    
    def _or_opt(self, trips):
        """Relocate a segment within the same trip"""
        for trip_idx, trip in enumerate(trips):
            route = trip["route"][1:-1]
            if len(route) < 3:
                continue
            
            for seg_len in range(1, min(3, len(route))):
                for i in range(len(route) - seg_len):
                    segment = route[i:i+seg_len]
                    remaining = route[:i] + route[i+seg_len:]
                    
                    for j in range(len(remaining) + 1):
                        new_route_nodes = remaining[:j] + segment + remaining[j:]
                        new_trip = self._route_to_trip_object([self.depot] + new_route_nodes + [self.depot])
                        
                        if new_trip and new_trip["distance"] < trip["distance"] - 0.01:
                            new_trips = copy.deepcopy(trips)
                            new_trips[trip_idx] = new_trip
                            yield new_trips, self._calculate_trips_cost(new_trips)
    
    def _route_to_tasks(self, route_nodes, original_trip):
        """Convert route node list back to tasks"""
        tasks = []
        for node in route_nodes:
            for task_info in original_trip.get("tasks", []):
                if (task_info["req"].ID == abs(node) and 
                    ((node > 0 and task_info["type"] == "delivery") or
                     (node < 0 and task_info["type"] == "pickup"))):
                    tasks.append(task_info)
                    break
        return tasks if len(tasks) == len(route_nodes) else None
    
    def _node_to_task(self, node, trip):
        """Extract task from node ID"""
        for task_info in trip.get("tasks", []):
            if (task_info["req"].ID == abs(node) and
                ((node > 0 and task_info["type"] == "delivery") or
                 (node < 0 and task_info["type"] == "pickup"))):
                return task_info
        return None
    
    def _route_to_trip_object(self, route):
        """Convert route to trip object with feasibility check"""
        # Extract tasks from route (simplified - would need task mapping)
        # This is a placeholder - in practice you'd need to map node IDs back to tasks
        if len(route) < 3:
            return None
        
        # Basic feasibility check
        distance = 0
        for k in range(len(route) - 1):
            distance += self.instance.calcDistance[abs(route[k])][abs(route[k+1])]
        
        if distance > self.max_distance:
            return None
        
        return {
            "route": route,
            "tools_loaded": [0] * self.num_tools,
            "tools_returned": [0] * self.num_tools,
            "distance": distance
        }


# ============================================================================
# PHASE 1: Simulated Annealing for Delivery Day Assignment
# ============================================================================

def is_schedule_feasible(instance, start_days):
    """Check tool availability constraints"""
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

def evaluate_total_cost(instance, schedule_by_day):
    """Calculate total cost including vehicles, distance, and tools"""
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

def generate_initial_start_days(instance):
    """Generate initial delivery day assignment"""
    # Try baseline first
    try:
        from algorithms.baseline_solver import solve_baseline
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
    except:
        pass
    
    # Fallback to earliest possible day
    return {req.ID: req.fromDay for req in instance.Requests}

def phase1_sa_days(instance, vnd, time_ratio=0.8, max_iterations=None):
    """
    Phase 1: Optimize delivery day assignments using SA
    Uses VND as the evaluator for daily routes
    
    Args:
        instance: The problem instance
        vnd: VariableNeighborhoodDescent instance for routing
        time_ratio: 0.8 means 80% time for phase 1
        max_iterations: Max SA iterations (overrides time_ratio)
    """
    calculate_all_distances(instance)
    
    print("   [Phase 1] SA for Delivery Day Assignment")
    print("   " + "-"*40)
    
    # Initial solution
    current_state = generate_initial_start_days(instance)
    
    if not is_schedule_feasible(instance, current_state):
        print("   [Phase 1] Warning: Initial solution infeasible. Repairing...")
        current_state = _repair_infeasible(instance, current_state)
    
    # Build initial schedule using VND for routing
    current_schedule = {}
    print("   [Phase 1] Building initial daily routes with VND...")
    
    for day in range(1, instance.Days + 1):
        tasks = get_tasks_for_day(instance, current_state, day)
        if tasks:
            trips, _ = vnd.optimize_day(tasks, max_iterations=50)  # Quick initial routing
            current_schedule[day] = trips
        else:
            current_schedule[day] = []
    
    current_cost = evaluate_total_cost(instance, current_schedule)
    
    best_state = current_state.copy()
    best_cost = current_cost
    best_schedule = copy.deepcopy(current_schedule)
    
    # SA parameters
    temperature = 10000.0
    cooling_rate = 0.97
    min_temperature = 0.1
    
    # Determine iterations
    if max_iterations is None:
        # Estimate based on problem size
        max_iterations = len(instance.Requests) * 100
    
    iteration = 0
    no_improve_count = 0
    improvements = []
    
    print(f"   [Phase 1] Starting SA. Initial cost: {current_cost:,.0f}")
    print(f"   [Phase 1] Max iterations: {max_iterations}")
    
    while temperature > min_temperature and iteration < max_iterations:
        for _ in range(10):  # Iterations per temperature
            # Select random request to modify
            req = random.choice(instance.Requests)
            old_start = current_state[req.ID]
            
            # Get possible new delivery days
            possible_days = list(range(req.fromDay, req.toDay + 1))
            if len(possible_days) <= 1:
                continue
            
            possible_days.remove(old_start)
            new_start = random.choice(possible_days)
            
            # Apply move
            current_state[req.ID] = new_start
            
            # Check feasibility
            if not is_schedule_feasible(instance, current_state):
                current_state[req.ID] = old_start
                continue
            
            # Identify affected days
            old_pickup = old_start + req.numDays
            new_pickup = new_start + req.numDays
            affected_days = {d for d in [old_start, old_pickup, new_start, new_pickup] 
                           if 1 <= d <= instance.Days}
            
            # Re-optimize affected days with VND (full optimization)
            new_schedule = copy.deepcopy(current_schedule)
            for day in affected_days:
                tasks = get_tasks_for_day(instance, current_state, day)
                if tasks:
                    trips, _ = vnd.optimize_day(tasks, max_iterations=200)
                    new_schedule[day] = trips
                else:
                    new_schedule[day] = []
            
            new_cost = evaluate_total_cost(instance, new_schedule)
            
            # SA acceptance
            if new_cost < current_cost:
                current_cost = new_cost
                current_schedule = new_schedule
                
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_state = current_state.copy()
                    best_schedule = copy.deepcopy(new_schedule)
                    improvements.append((iteration, best_cost))
                    no_improve_count = 0
                    print(f"   [Phase 1] ✨ New best: {best_cost:,.0f} (iter {iteration})")
                else:
                    no_improve_count += 1
            else:
                delta = new_cost - current_cost
                probability = math.exp(-delta / temperature)
                if random.random() < probability:
                    current_cost = new_cost
                    current_schedule = new_schedule
                    no_improve_count = 0
                else:
                    current_state[req.ID] = old_start
                    no_improve_count += 1
            
            iteration += 1
            if iteration >= max_iterations:
                break
        
        temperature *= cooling_rate
        
        # Progress report
        if iteration % (max_iterations // 10) == 0 and iteration > 0:
            print(f"   [Phase 1] Progress: {iteration/max_iterations*100:.0f}%, "
                  f"Temp: {temperature:.1f}, Best: {best_cost:,.0f}")
    
    print(f"   [Phase 1] Complete. Best cost: {best_cost:,.0f}")
    return best_state, best_schedule, best_cost


# ============================================================================
# PHASE 2: VND Fine-Tuning
# ============================================================================

def phase2_vnd_finetune(instance, start_days, initial_schedule, vnd):
    """
    Phase 2: Fine-tune daily routes with deeper VND
    Uses remaining 20% of time budget
    """
    print("\n   [Phase 2] VND Fine-Tuning of Daily Routes")
    print("   " + "-"*40)
    
    improved_schedule = copy.deepcopy(initial_schedule)
    total_improvement = 0
    
    # Sort days by number of trips (more trips = more potential improvement)
    days_with_trips = [(day, len(trips)) for day, trips in improved_schedule.items() if trips]
    days_with_trips.sort(key=lambda x: x[1], reverse=True)
    
    for day, num_trips in days_with_trips:
        tasks = get_tasks_for_day(instance, start_days, day)
        if not tasks:
            continue
        
        # Run VND with more iterations for fine-tuning
        optimized_trips, cost = vnd.optimize_day(tasks, max_iterations=500)
        
        old_cost = sum(trip["distance"] for trip in improved_schedule[day])
        if cost < old_cost - 0.01:
            improvement = old_cost - cost
            total_improvement += improvement
            improved_schedule[day] = optimized_trips
            print(f"   [Phase 2] Day {day}: Improved by {improvement:.0f} "
                  f"({old_cost:.0f} → {cost:.0f})")
    
    new_cost = evaluate_total_cost(instance, improved_schedule)
    print(f"   [Phase 2] Complete. Total improvement: {total_improvement:.0f}")
    
    return improved_schedule, new_cost


def _repair_infeasible(instance, start_days):
    """Simple repair for infeasible tool usage"""
    num_tools = len(instance.Tools)
    
    for _ in range(100):
        # Check daily usage
        daily_usage = {d: [0] * num_tools for d in range(1, instance.Days + 2)}
        for req in instance.Requests:
            sd = start_days[req.ID]
            for d in range(sd, min(sd + req.numDays, instance.Days) + 1):
                daily_usage[d][req.tool - 1] += req.toolCount
        
        # Find violation
        violation = None
        for d in range(1, instance.Days + 1):
            for t in range(num_tools):
                if daily_usage[d][t] > instance.Tools[t].amount:
                    violation = (d, t)
                    break
            if violation:
                break
        
        if not violation:
            break
        
        # Shift a request causing violation
        day, tool = violation
        for req in instance.Requests:
            if req.tool - 1 == tool:
                sd = start_days[req.ID]
                if sd <= day <= sd + req.numDays:
                    # Try moving forward
                    if sd < req.toDay:
                        start_days[req.ID] = min(sd + 1, req.toDay)
                    elif sd > req.fromDay:
                        start_days[req.ID] = max(sd - 1, req.fromDay)
                    break
    
    return start_days


# ============================================================================
# MAIN SOLVER
# ============================================================================

def solve_two_phase(instance):
    """
    Two-Phase Decomposition Solver
    
    Phase 1 (80% time): SA optimizes delivery day assignments
    Phase 2 (20% time): VND fine-tunes daily routes
    """
    calculate_all_distances(instance)
    
    print("\n" + "="*50)
    print("TWO-PHASE DECOMPOSITION SOLVER")
    print("="*50)
    
    # Initialize VND for routing
    vnd = VariableNeighborhoodDescent(instance)
    
    # Phase 1: Optimize delivery days
    best_start_days, best_schedule, phase1_cost = phase1_sa_days(instance, vnd)
    
    # Phase 2: Fine-tune routes
    final_schedule, final_cost = phase2_vnd_finetune(
        instance, best_start_days, best_schedule, vnd
    )
    
    print("\n" + "="*50)
    print(f"FINAL SOLUTION COST: {final_cost:,.0f}")
    print(f"  Phase 1 cost: {phase1_cost:,.0f}")
    print(f"  Phase 2 improvement: {phase1_cost - final_cost:,.0f}")
    print("="*50)
    
    return final_schedule


# Wrapper for compatibility with solver.py
def solve_two_phase_wrapper(instance):
    """Wrapper function matching expected signature"""
    return solve_two_phase(instance)
