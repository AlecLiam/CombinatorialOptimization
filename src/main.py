import os
import glob
import shutil
from InstanceCVRPTWUI import InstanceCVRPTWUI
from baseline_solver import solve_baseline
from output_formatter import write_solution
from visualizer import plot_network, animate_routes_to_gif
from validator_runner import run_validator

ALGORITHMS = {
    "Baseline": solve_baseline
}

def get_existing_cost(file_path):
    """Helper function to read the cost of an existing solution file."""
    if not os.path.exists(file_path): 
        return float('inf')
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith("COST ="):
                    return float(line.split("=")[1].strip())
    except: pass
    return float('inf')

def process_instance(file_path):
    instance = InstanceCVRPTWUI(file_path)
    instance.Name = os.path.splitext(os.path.basename(file_path))[0]
    print(f"\n{'='*60}\nProcessing Instance: {instance.Name}\n{'='*60}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__)) 
    instance_results_dir = os.path.abspath(os.path.join(current_dir, "..", "results", instance.Name))
    optimal_dir = os.path.join(instance_results_dir, "optimal_solution")
    os.makedirs(instance_results_dir, exist_ok=True)
    os.makedirs(optimal_dir, exist_ok=True)

    if not instance.isValid():
        print("Parser found errors. Skipping...")
        return

    plot_network(instance, instance_results_dir)    
    for algo_name, solver_func in ALGORITHMS.items():
        print(f"\n-> Running Algorithm: [{algo_name}]") 
        algo_dir = os.path.join(instance_results_dir, algo_name)
        os.makedirs(algo_dir, exist_ok=True)
        final_sol_path = os.path.join(algo_dir, f"{instance.Name}_{algo_name}.txt")
        temp_sol_path = os.path.join(algo_dir, f"temp_{instance.Name}.txt")

        best_algo_cost = get_existing_cost(final_sol_path)
        schedule = solver_func(instance)
        new_cost = write_solution(instance, schedule, file_path=temp_sol_path, solution_name=f"{instance.Name}_{algo_name}")
        is_valid = run_validator(instance.Name, temp_sol_path)
        
        if is_valid and new_cost < best_algo_cost:
            print(f"   [SUCCESS] Found new best for {algo_name}! Cost: {new_cost:,.0f}")
            os.replace(temp_sol_path, final_sol_path)
            gif_path = os.path.join(algo_dir, f"{instance.Name}_{algo_name}_routes.gif")
            animate_routes_to_gif(instance, schedule, gif_path)
            global_opt_path = os.path.join(optimal_dir, f"{instance.Name}_optimal.txt")
            best_global_cost = get_existing_cost(global_opt_path)
            
            if new_cost < best_global_cost:
                print(f"New global optimal solution found! Cost: {new_cost:,.0f}")
                shutil.copy(final_sol_path, global_opt_path)
                shutil.copy(gif_path, os.path.join(optimal_dir, f"{instance.Name}_optimal_routes.gif"))
                
        else:
            os.remove(temp_sol_path)
            if not is_valid:
                print(f"[FAILED] The {algo_name} generated an invalid solution.")
            else:
                print(f"[SKIPPED] Cost {new_cost:,.0f} did not beat the existing {algo_name} cost of {best_algo_cost:,.0f}.")

def main():
    print("Starting Combinatorial Optimization Pipeline")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "..", "data")
    all_instances = glob.glob(os.path.join(data_dir, "*.txt"))
    print(f"Found {len(all_instances)} datasets to process.")

    for file_path in all_instances:
        process_instance(file_path)
            
if __name__ == "__main__":
    main()