import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import colorsys

def plot_network(instance, save_path):
    if os.path.exists(save_path): 
        return

    depot_index = instance.DepotCoordinate
    depot = instance.Coordinates[depot_index]
    nodes_x = [coord.X for coord in instance.Coordinates if coord.ID != depot_index] 
    nodes_y = [coord.Y for coord in instance.Coordinates if coord.ID != depot_index] 

    plt.figure(figsize=(12, 9))
    plt.scatter(nodes_x, nodes_y, c='black', label='Farms', s=20, zorder=2)
    plt.scatter(depot.X, depot.Y, c='red', label='Depot', s=120, zorder=3)
    plt.title(f"Node network for {instance.Name}", fontsize=15)
    plt.xlabel("X coordinate", fontsize=14)
    plt.ylabel("Y coordinate", fontsize=14)
    plt.tick_params(axis='both', labelsize=12)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    
    if instance.Name == "testInstance":
        all_x = [c.X for c in instance.Coordinates]
        all_y = [c.Y for c in instance.Coordinates]
        plt.xlim(min(all_x) - 10, max(all_x) + 10)
        plt.ylim(min(all_y) - 10, max(all_y) + 10)
    else:
        plt.xlim(0, 10000)
        plt.ylim(0, 10000)
    
    plt.savefig(save_path, format='png', dpi=300)
    plt.close()

def animate_routes_to_gif(instance, schedule_by_day, save_path):    
    print(f"   Generating route animation: {os.path.basename(save_path)} ...")
    depot_idx = instance.DepotCoordinate
    depot = instance.Coordinates[depot_idx]
    nodes_x = [coord.X for coord in instance.Coordinates if coord.ID != depot_idx] 
    nodes_y = [coord.Y for coord in instance.Coordinates if coord.ID != depot_idx] 

    fig, ax = plt.subplots(figsize=(12, 9))
    
    if instance.Name == "testInstance":
        all_x = [c.X for c in instance.Coordinates]
        all_y = [c.Y for c in instance.Coordinates]
        x_min, x_max = min(all_x) - 10, max(all_x) + 10
        y_min, y_max = min(all_y) - 10, max(all_y) + 10
    else:
        x_min, x_max = 0, 10000
        y_min, y_max = 0, 10000

    max_vehicles = max([len(trips) for trips in schedule_by_day.values()] + [1])
    colors = [colorsys.hsv_to_rgb((i * 0.618033988749895) % 1.0, 0.9, 0.9) for i in range(max_vehicles)]

    def update(day):
        ax.clear()
        ax.scatter(nodes_x, nodes_y, c='black', label='Farms', s=20, zorder=3)
        ax.scatter(depot.X, depot.Y, c='red', label='Depot', s=120, zorder=3)
        
        if day in schedule_by_day and len(schedule_by_day[day]) > 0:
            active_nodes = set()
            for trip_idx, trip in enumerate(schedule_by_day[day]):
                route = trip["route"]
                route_color = colors[trip_idx]
                
                for i in range(len(route) - 1):
                    start_req_id = abs(route[i])
                    end_req_id = abs(route[i+1])
                    
                    start_node_id = depot_idx if start_req_id == 0 else instance.Requests[start_req_id - 1].node
                    end_node_id = depot_idx if end_req_id == 0 else instance.Requests[end_req_id - 1].node
                    
                    start_coord = instance.Coordinates[start_node_id]
                    end_coord = instance.Coordinates[end_node_id]
                    if start_node_id != depot_idx: active_nodes.add(start_node_id)
                    if end_node_id != depot_idx: active_nodes.add(end_node_id)
                    ax.plot([start_coord.X, end_coord.X], [start_coord.Y, end_coord.Y], 
                            c=route_color, alpha=0.8, linewidth=1.0, zorder=1)

            if active_nodes:
                ring_x = [instance.Coordinates[nid].X for nid in active_nodes]
                ring_y = [instance.Coordinates[nid].Y for nid in active_nodes]
                ax.scatter(ring_x, ring_y, facecolors='none', edgecolors='lime', s=150, linewidths=1.5, zorder=4)

        ax.set_title(f"Active Routes - Day {day} / {instance.Days}", fontsize=15)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

    ani = animation.FuncAnimation(fig, update, frames=range(1, instance.Days + 1), interval=500, repeat=False)
    ani.save(save_path, writer='pillow', fps=1)
    plt.close()