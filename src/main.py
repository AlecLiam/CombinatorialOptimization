import os
from InstanceCVRPTWUI import InstanceCVRPTWUI
from visualizer import plot_network

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

if __name__ == "__main__":
    main()
