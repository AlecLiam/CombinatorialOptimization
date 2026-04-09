import os
import glob
from InstanceCVRPTWUI import InstanceCVRPTWUI
from baseline_solver import solve_baseline
from output_formatter import write_solution
from visualizer import plot_network, animate_routes_to_gif
from validator_runner import run_validator

def process_instance(file_path):
    """Runs the entire pipeline for a single instance file."""
    instance = InstanceCVRPTWUI(file_path)
    short_name = os.path.splitext(os.path.basename(file_path))[0]
    instance.Name = short_name 
    print(f"\nProcessing: {instance.Name}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__)) 
    results_dir = os.path.abspath(os.path.join(current_dir, "..", "results", instance.Name))
    expected_solution = os.path.join(current_dir, "..", "results", instance.Name, f"{instance.Name}.txt")
    if os.path.exists(expected_solution):
        print(f"Solution already exists for {instance.Name}.")
        return

    os.makedirs(results_dir, exist_ok=True)
    is_distance_valid, distance_message = instance.areDistancesValid()
    if not instance.isValid():
        print("Parser found errors:")
        for err in instance.errorReport: 
            print(err)
        return

    plot_network(instance)    
    schedule = solve_baseline(instance)
    animate_routes_to_gif(instance, schedule) 
    write_solution(instance, schedule, solution_name=f"{instance.Name}")
    run_validator(instance.Name)


def main():
    print("Starting Combinatorial Optimization algorithm")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "..", "data")
    all_instances = glob.glob(os.path.join(data_dir, "*.txt"))
        
    print(f"Found {len(all_instances)} datasets to process.")

    for file_path in all_instances:
        process_instance(file_path)
            
if __name__ == "__main__":
    main()
