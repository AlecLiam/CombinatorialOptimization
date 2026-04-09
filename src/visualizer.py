import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation

def plot_network(instance, save_path):
    if os.path.exists(save_path): 
        return

    depot_index = instance.DepotCoordinate
    depot = instance.Coordinates[depot_index]
    nodes_x = [coord.X for coord in instance.Coordinates if coord.ID != depot_index] 
    nodes_y = [coord.Y for coord in instance.Coordinates if coord.ID != depot_index] 

    plt.figure(figsize=(8, 6))
    plt.scatter(nodes_x, nodes_y, c='lawngreen', label='Farms', s=50, zorder=2)
    plt.scatter(depot.X, depot.Y, c='magenta', label='Depot', s=100, zorder=3)
    for coord in instance.Coordinates:
        plt.annotate(str(coord.ID), (coord.X, coord.Y), textcoords="offset points", xytext=(0, 8), ha='center', fontsize='14')
    plt.title(f"Node network for {instance.Name}", fontsize=15)
    plt.xlabel("X coordinate", fontsize=14)
    plt.ylabel("Y coordinate", fontsize=14)
    plt.tick_params(axis='both', labelsize=12)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    
    plt.savefig(save_path, format='png', dpi=300)
    plt.close()

def animate_routes_to_gif(instance, schedule_by_day, save_path):    
    """Generates the day-by-day active route radar GIF."""
    print(f"   Generating route animation: {os.path.basename(save_path)} ...")
    depot_idx = instance.DepotCoordinate
    depot = instance.Coordinates[depot_idx]
    nodes_x = [coord.X for coord in instance.Coordinates if coord.ID != depot_idx] 
    nodes_y = [coord.Y for coord in instance.Coordinates if coord.ID != depot_idx] 

    fig, ax = plt.subplots(figsize=(8, 6))
    all_x = [c.X for c in instance.Coordinates]
    all_y = [c.Y for c in instance.Coordinates]
    x_min, x_max = min(all_x) - 10, max(all_x) + 10
    y_min, y_max = min(all_y) - 10, max(all_y) + 10

    def update(day):
        ax.clear()
        ax.scatter(nodes_x, nodes_y, c='lawngreen', label='Farms', s=50, zorder=3)
        ax.scatter(depot.X, depot.Y, c='magenta', label='Depot', s=60, zorder=3)
        
        for coord in instance.Coordinates:
            ax.annotate(str(coord.ID), (coord.X, coord.Y), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=12)
            
        if day in schedule_by_day and len(schedule_by_day[day]) > 0:
            for trip in schedule_by_day[day]:
                route = trip["route"]
                for i in range(len(route) - 1):
                    start_req_id = abs(route[i])
                    end_req_id = abs(route[i+1])
                    
                    start_node_id = depot_idx if start_req_id == 0 else instance.Requests[start_req_id - 1].node
                    end_node_id = depot_idx if end_req_id == 0 else instance.Requests[end_req_id - 1].node
                    
                    start_coord = instance.Coordinates[start_node_id]
                    end_coord = instance.Coordinates[end_node_id]
                    ax.plot([start_coord.X, end_coord.X], [start_coord.Y, end_coord.Y], 
                            c='blue', alpha=0.8, linewidth=2.5, zorder=1)

        ax.set_title(f"Active Routes - Day {day} / {instance.Days}", fontsize=15)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

    ani = animation.FuncAnimation(fig, update, frames=range(1, instance.Days + 1), interval=500, repeat=False)
    ani.save(save_path, writer='pillow', fps=1)
    plt.close()