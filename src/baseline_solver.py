def solve_baseline(instance):
    schedule_by_day = {}
    for day in range(1, instance.Days + 1):
        schedule_by_day[day] = []

    depot = instance.DepotCoordinate
    num_tools = len(instance.Tools)

    if instance.calcDistance is None:
        instance.calculateDistances()

    for req in instance.Requests:
        dist = instance.calcDistance[depot][req.node] + instance.calcDistance[req.node][depot]
        
        delivery_day = req.fromDay
        tools_loaded = [0] * num_tools
        tools_loaded[req.tool - 1] = -req.toolCount
        tools_returned = [0] * num_tools
        
        schedule_by_day[delivery_day].append({
            "route": [depot, req.node, depot],
            "tools_loaded": tools_loaded,
            "tools_returned": tools_returned,
            "distance": dist
        })

        pickup_day = req.fromDay + req.numDays
        if pickup_day <= instance.Days:
            tools_loaded = [0] * num_tools
            tools_returned = [0] * num_tools
            tools_returned[req.tool - 1] = req.toolCount
            
            schedule_by_day[pickup_day].append({
                "route": [depot, -req.node, depot],
                "tools_loaded": tools_loaded,
                "tools_returned": tools_returned,
                "distance": dist
            })

    return schedule_by_day