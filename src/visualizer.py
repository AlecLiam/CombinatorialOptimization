import os
import matplotlib.pyplot as plt

def plot_network(instance, save_path=None):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "..", "output")
    save_path = os.path.join(output_dir, f"{instance.Name}_network.png")

    depot_index = instance.DepotCoordinate
    depot = instance.Coordinates[depot_index]
    nodes_x = [coord.X for coord in instance.Coordinates if coord.ID != depot_index] 
    nodes_y = [coord.Y for coord in instance.Coordinates if coord.ID != depot_index] 

    plt.figure(figsize=(8, 6))
    plt.scatter(nodes_x, nodes_y, c='lawngreen', label= 'Farms', s=50 , zorder = 3)
    plt.scatter(depot.X, depot.Y, c='magenta', label= 'Depot', s = 60, zorder= 2)
    for coord in instance.Coordinates:
        plt.annotate(str(coord.ID), (coord.X, coord.Y), textcoords="offset points", xytext= (0, 8), ha= 'center', fontsize='14')
    plt.title(f"Node network for {instance.Name}", fontsize= 15)
    plt.xlabel("X coordinate", fontsize= 14)
    plt.ylabel("Y coordinate", fontsize= 14)
    plt.tick_params(axis='both', labelsize=12)
    plt.legend()
    plt.grid(True, linestyle= '--', alpha=0.3)
    
    plt.savefig(save_path, format='png', dpi=300)
    print(f"Graph {save_path} saved.")