import csv
import os


SUMMARY_KEYS = (
    "MAX_NUMBER_OF_VEHICLES",
    "NUMBER_OF_VEHICLE_DAYS",
    "TOOL_USE",
    "DISTANCE",
    "COST",
)


def parse_solution_summary(file_path):
    summary = {
        "path": file_path,
        "exists": os.path.exists(file_path),
    }
    if not summary["exists"]:
        return summary

    with open(file_path, "r") as f:
        for line in f:
            if "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            if key not in SUMMARY_KEYS:
                continue
            if key == "TOOL_USE":
                summary[key] = value
            else:
                try:
                    summary[key] = float(value)
                except ValueError:
                    summary[key] = value
    return summary


def compare_summaries(instance_name, algorithm_name, reference, candidate, valid):
    old_cost = reference.get("COST")
    new_cost = candidate.get("COST")
    delta = None
    delta_pct = None

    if isinstance(old_cost, (int, float)) and isinstance(new_cost, (int, float)):
        delta = new_cost - old_cost
        if old_cost:
            delta_pct = (delta / old_cost) * 100

    return {
        "instance": instance_name,
        "algorithm": algorithm_name,
        "valid": valid,
        "old_cost": old_cost,
        "new_cost": new_cost,
        "delta": delta,
        "delta_pct": delta_pct,
        "old_vehicles": reference.get("MAX_NUMBER_OF_VEHICLES"),
        "new_vehicles": candidate.get("MAX_NUMBER_OF_VEHICLES"),
        "old_vehicle_days": reference.get("NUMBER_OF_VEHICLE_DAYS"),
        "new_vehicle_days": candidate.get("NUMBER_OF_VEHICLE_DAYS"),
        "old_distance": reference.get("DISTANCE"),
        "new_distance": candidate.get("DISTANCE"),
        "old_tool_use": reference.get("TOOL_USE"),
        "new_tool_use": candidate.get("TOOL_USE"),
        "reference_path": reference.get("path"),
        "candidate_path": candidate.get("path"),
    }


def format_number(value, decimals=0):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.{decimals}f}"
    return str(value)


def print_comparison(row):
    print("   Benchmark comparison vs current optimal:")
    print(
        "      Cost: "
        f"{format_number(row['old_cost'])} -> {format_number(row['new_cost'])} "
        f"({format_number(row['delta'])}, {format_number(row['delta_pct'], 2)}%)"
    )
    print(
        "      Vehicles: "
        f"{format_number(row['old_vehicles'])} -> {format_number(row['new_vehicles'])} | "
        "Vehicle-days: "
        f"{format_number(row['old_vehicle_days'])} -> {format_number(row['new_vehicle_days'])} | "
        "Distance: "
        f"{format_number(row['old_distance'])} -> {format_number(row['new_distance'])}"
    )
    print(f"      Tool use: {row['old_tool_use']} -> {row['new_tool_use']}")


def write_benchmark_csv(rows, file_path):
    if not rows:
        return

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(file_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
