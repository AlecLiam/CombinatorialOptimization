# CombinatorialOptimization


Phase 1: SA for Delivery Days (80% of time)

What it does: Finds which day each request should be delivered

How it works:
1. Start with initial delivery days (from baseline solver)
2. Randomly pick a request, shift its delivery day
3. Re-route affected days using VND (not greedy anymore!)
4. Accept/reject based on SA rules
5. Track the best found


Phase 2: VND Fine-Tuning (20% of time)

What it does: Takes the best solution from Phase 1 and improves each day's routes

How it works:
For each day (busiest days first):
    Try 5 different route improvements in order:
    
    1. 2-opt        - Reverse a segment within a route
    2. Relocate     - Move one task to another vehicle
    3. Exchange     - Swap tasks between two vehicles  
    4. Cross-exchange - Swap segments between vehicles
    5. Or-opt       - Move a segment within same route
    
    If any move improves cost → keep it, restart from #1
    If no improvement → try next neighborhood
