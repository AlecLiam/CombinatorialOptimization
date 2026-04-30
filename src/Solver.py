import argparse
import os
import glob
import shutil
from datetime import datetime
from InstanceCVRPTWUI import InstanceCVRPTWUI
from algorithms.baseline_solver import solve_baseline
from algorithms.simulated_annealing_solver import solve_sa
from output_formatter import write_solution
from validator_runner import run_validator
from benchmark import (
    compare_summaries,
    parse_solution_summary,
    print_comparison,
    write_benchmark_csv,
)

ALGORITHMS = {
    "Baseline": solve_baseline,
    "Simulated Annealing": solve_sa
}

def get_existing_cost(file_path):
    if not os.path.exists(file_path): 
        return float('inf')
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith("COST ="):
                    return float(line.split("=")[1].strip())
    except: pass
    return float('inf')

def process_instance(file_path, results_root, reference_results_root, update_best=True, make_visuals=True, sa_runs=1, sa_seed=None, route_merge=True, routing_method="greedy", alns_iterations=0, alns_destroy_fraction=0.06, alns_strategy="auto", alns_repair="auto"):
    instance = InstanceCVRPTWUI(file_path)
    
    instance.Name = os.path.splitext(os.path.basename(file_path))[0]
    print(f"\n{'='*60}\nProcessing Instance: {instance.Name}\n{'='*60}")
    
    instance_results_dir = os.path.abspath(os.path.join(results_root, instance.Name))
    optimal_dir = os.path.join(instance_results_dir, "optimal_solution")
    reference_opt_path = os.path.join(
        reference_results_root,
        instance.Name,
        "optimal_solution",
        f"{instance.Name}_optimal.txt",
    )
    
    os.makedirs(instance_results_dir, exist_ok=True)
    if update_best:
        os.makedirs(optimal_dir, exist_ok=True)

    if not instance.isValid():
        print("Parser found errors. Skipping...")
        return []

    if make_visuals:
        from visualizer import plot_network

        network_path = os.path.join(instance_results_dir, f"{instance.Name}_network.png")
        plot_network(instance, network_path)

    benchmark_rows = []
    for algo_name, solver_func in ALGORITHMS.items():
        print(f"\n-> Running Algorithm: [{algo_name}]")
        
        algo_dir = os.path.join(instance_results_dir, algo_name)
        os.makedirs(algo_dir, exist_ok=True)
        
        final_sol_path = os.path.join(algo_dir, f"{instance.Name}_{algo_name}.txt")
        temp_sol_path = os.path.join(algo_dir, f"temp_{instance.Name}.txt")
        gif_path = os.path.join(algo_dir, f"{instance.Name}_{algo_name}_active_routes.gif")
        
        best_algo_cost = get_existing_cost(final_sol_path)
        
        if algo_name == "Simulated Annealing":
            schedule = solver_func(
                instance,
                runs=sa_runs,
                seed=sa_seed,
                route_merge=route_merge,
                routing_method=routing_method,
                alns_iterations=alns_iterations,
                alns_destroy_fraction=alns_destroy_fraction,
                alns_strategy=alns_strategy,
                alns_repair=alns_repair,
            )
        else:
            schedule = solver_func(instance)
        new_cost = write_solution(instance, schedule, file_path=temp_sol_path, solution_name=f"{instance.Name}_{algo_name}")
        is_valid = run_validator(instance.Name, temp_sol_path)
        
        if is_valid:
            if new_cost < best_algo_cost:
                if update_best:
                    print(f"   [SUCCESS] Found new best for {algo_name}! Cost: {new_cost:,.0f}")
                else:
                    print(f"   [RECORDED] Experiment solution cost: {new_cost:,.0f}")
                os.replace(temp_sol_path, final_sol_path)
                if make_visuals:
                    from visualizer import animate_routes_to_gif

                    animate_routes_to_gif(instance, schedule, gif_path)
            else:
                if update_best:
                    os.remove(temp_sol_path)
                    print(f"   [SKIPPED] Cost {new_cost:,.0f} did not beat {algo_name} best of {best_algo_cost:,.0f}.")
                else:
                    os.replace(temp_sol_path, final_sol_path)
                    print(f"   [RECORDED] Experiment solution cost: {new_cost:,.0f}")

            candidate_path = final_sol_path if os.path.exists(final_sol_path) else temp_sol_path
            reference_summary = parse_solution_summary(reference_opt_path)
            candidate_summary = parse_solution_summary(candidate_path)
            row = compare_summaries(instance.Name, algo_name, reference_summary, candidate_summary, True)
            benchmark_rows.append(row)
            print_comparison(row)
            
            if update_best:
                global_opt_path = os.path.join(optimal_dir, f"{instance.Name}_optimal.txt")
                best_global_cost = get_existing_cost(global_opt_path)
                
                if new_cost < best_global_cost or not os.path.exists(global_opt_path):
                    print(f"   NEW GLOBAL OPTIMAL FOUND! Cost: {new_cost:,.0f}")
                    if os.path.exists(final_sol_path): shutil.copy(final_sol_path, global_opt_path)
                    if os.path.exists(gif_path): shutil.copy(gif_path, os.path.join(optimal_dir, f"{instance.Name}_optimal_active_routes.gif"))
        else:
            os.remove(temp_sol_path)
            print(f"   [FAILED] The {algo_name} generated an invalid solution.")
            reference_summary = parse_solution_summary(reference_opt_path)
            candidate_summary = {"path": temp_sol_path, "exists": False}
            benchmark_rows.append(compare_summaries(instance.Name, algo_name, reference_summary, candidate_summary, False))

    return benchmark_rows

def main():
    parser = argparse.ArgumentParser(description="Run CO case solvers and optionally benchmark experiments.")
    parser.add_argument(
        "instances",
        nargs="*",
        help="Instance file names or paths. Defaults to all data/*.txt files.",
    )
    parser.add_argument(
        "--experiment",
        metavar="NAME",
        help="Write outputs under experiments/NAME and compare against current results without updating them.",
    )
    parser.add_argument(
        "--no-visuals",
        action="store_true",
        help="Skip network plots and GIFs for faster benchmark runs.",
    )
    parser.add_argument(
        "--sa-runs",
        type=int,
        default=1,
        help="Number of simulated annealing starts to run before keeping the best schedule.",
    )
    parser.add_argument(
        "--sa-seed",
        type=int,
        default=None,
        help="Optional base random seed for reproducible simulated annealing multi-start runs.",
    )
    parser.add_argument(
        "--no-route-merge",
        action="store_true",
        help="Disable simulated annealing route merge post-processing.",
    )
    parser.add_argument(
        "--routing-method",
        choices=("greedy", "insertion", "regret", "greedy_repair", "insertion_repair", "regret_repair"),
        default="greedy",
        help="Daily route construction method for simulated annealing.",
    )
    parser.add_argument(
        "--alns-iterations",
        type=int,
        default=0,
        help="Run this many ALNS destroy/repair iterations after each simulated annealing run.",
    )
    parser.add_argument(
        "--alns-destroy-fraction",
        type=float,
        default=0.06,
        help="Fraction of requests removed and repaired in each ALNS iteration.",
    )
    parser.add_argument(
        "--alns-strategy",
        choices=("auto", "distance", "tools", "vehicle_days", "fixed_vehicle"),
        default="auto",
        help="ALNS strategy. Auto chooses the current dominant objective part.",
    )
    parser.add_argument(
        "--alns-repair",
        choices=("auto", "greedy", "regret"),
        default="auto",
        help="ALNS repair method. Auto uses greedy for distance and regret otherwise.",
    )
    args = parser.parse_args()

    print("Starting Combinatorial Optimization Pipeline")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    data_dir = os.path.join(project_root, "data")
    reference_results_root = os.path.join(project_root, "results")

    if args.instances:
        all_instances = []
        for path in args.instances:
            if os.path.isabs(path) or os.path.exists(path):
                all_instances.append(os.path.abspath(path))
            else:
                all_instances.append(os.path.join(data_dir, path))
    else:
        all_instances = glob.glob(os.path.join(data_dir, "*.txt"))

    if args.experiment:
        results_root = os.path.join(project_root, "experiments", args.experiment, "results")
        update_best = False
        benchmark_csv = os.path.join(project_root, "experiments", args.experiment, "benchmark_summary.csv")
        print(f"Experiment mode: writing isolated outputs to {results_root}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_root = reference_results_root
        update_best = True
        benchmark_csv = os.path.join(project_root, "experiments", f"run_{timestamp}_benchmark_summary.csv")

    print(f"Found {len(all_instances)} datasets to process.")

    all_rows = []
    for file_path in all_instances:
        rows = process_instance(
            file_path,
            results_root=results_root,
            reference_results_root=reference_results_root,
            update_best=update_best,
            make_visuals=not args.no_visuals,
            sa_runs=args.sa_runs,
            sa_seed=args.sa_seed,
            route_merge=not args.no_route_merge,
            routing_method=args.routing_method,
            alns_iterations=args.alns_iterations,
            alns_destroy_fraction=args.alns_destroy_fraction,
            alns_strategy=args.alns_strategy,
            alns_repair=args.alns_repair,
        )
        all_rows.extend(rows)

    write_benchmark_csv(all_rows, benchmark_csv)
    if all_rows:
        print(f"\nBenchmark summary written to: {benchmark_csv}")
            
if __name__ == "__main__":
    main()
