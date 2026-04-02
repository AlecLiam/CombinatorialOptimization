import os
from InstanceCVRPTWUI import InstanceCVRPTWUI
from baseline_solver import solve_baseline
from output_formatter import write_solution
from visualizer import plot_network, animate_routes_to_gif
from validator_runner import run_validator
def main():
    print("Starting Combinatorial Optimization algorithm")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "..", "data", "testInstance.txt")
    instance = InstanceCVRPTWUI(file_path)
    is_distance_valid, distance_message = instance.areDistancesValid()

    print(f"Reading instance: {file_path}")

    if not os.path.exists(file_path):
        print(f"Error: Could not find the data file at {file_path}")
        return

    if not instance.isValid():
        print("Parser found the following errors in the instance file:")
        for err in instance.errorReport:
            print(f"{err}")
        return

    if not is_distance_valid:
        print(f"Distance warning:{distance_message}")

    print("Parsing succesful\n")

    print(f"Dataset name: {instance.Name}")
    print(f"Total days: {instance.Days}")
    print(f"Vehicle Capacity: {instance.Capacity}")
    print(f"Number of Tools: {len(instance.Tools)}")
    print(f"Number of Coordinates: {len(instance.Coordinates)}")
    print(f"Number of Requests: {len(instance.Requests)}")

    plot_network(instance)
    schedule = solve_baseline(instance)
    animate_routes_to_gif(instance, schedule)
    write_solution(instance, schedule, solution_name = f"{instance.Name}")
    run_validator(instance.Name)
    
if __name__ == "__main__":
    main()
