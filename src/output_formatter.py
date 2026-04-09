import os

def write_solution(instance, schedule_by_day, solution_name = "solution"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "..", "results", instance.Name)   
    file_path = os.path.join(output_dir, f"{solution_name}.txt")

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
    
    max_vehicles = max((len(trips) for trips in schedule_by_day.values()), default=0)
    vehicle_days = sum(len(trips) for trips in schedule_by_day.values())
    total_distance = sum(trip["distance"] for trips in schedule_by_day.values() for trip in trips)
    
    tool_cost = sum(tool_use[i] * instance.Tools[i].cost for i in range(num_tools))
        
    total_cost = (max_vehicles * instance.VehicleCost) + \
                 (vehicle_days * instance.VehicleDayCost) + \
                 (total_distance * instance.DistanceCost) + \
                 tool_cost
                 
    current_inventory = list(tool_use)
        
    with open(file_path, 'w') as f:
        f.write(f"DATASET = {instance.Dataset}\n")
        f.write(f"NAME = {solution_name}\n\n")
        
        f.write(f"MAX_NUMBER_OF_VEHICLES = {max_vehicles}\n")
        f.write(f"NUMBER_OF_VEHICLE_DAYS = {vehicle_days}\n")
        f.write(f"TOOL_USE = {' '.join(str(x) for x in tool_use)}\n")
        f.write(f"DISTANCE = {total_distance}\n")
        f.write(f"COST = {total_cost}\n\n")
        
        for day in sorted(schedule_by_day.keys()):
            trips = schedule_by_day[day]
            if not trips:
                continue
                
            f.write(f"DAY = {day}\n")
            f.write(f"NUMBER_OF_VEHICLES = {len(trips)}\n")
            
            start_depot = list(current_inventory)
            for trip in trips:
                for i in range(num_tools):
                    start_depot[i] += trip["tools_loaded"][i] 
            f.write(f"START_DEPOT = {' '.join(str(x) for x in start_depot)}\n")
            
            finish_depot = list(start_depot)
            for trip in trips:
                for i in range(num_tools):
                    finish_depot[i] += trip["tools_returned"][i] 
            f.write(f"FINISH_DEPOT = {' '.join(str(x) for x in finish_depot)}\n")
            
            for vehicle_idx, trip in enumerate(trips, start=1):
                route_str = "\t".join(str(node) for node in trip["route"])
                f.write(f"{vehicle_idx}\tR\t{route_str}\n")
                
                loaded_str = "\t".join(str(x) for x in trip["tools_loaded"])
                f.write(f"{vehicle_idx}\tV\t1\t{loaded_str}\n")
                
                returned_str = "\t".join(str(x) for x in trip["tools_returned"])
                f.write(f"{vehicle_idx}\tV\t2\t{returned_str}\n")
                
                f.write(f"{vehicle_idx}\tD\t{trip['distance']}\n")
                
            f.write("\n")
            current_inventory = finish_depot

    print(f"Final solution saved to: {file_path}")
    return file_path