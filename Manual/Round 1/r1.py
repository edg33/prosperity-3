# key is from, values are to
from collections import deque


conversion_rates = {
    "Snowballs": {"Snowballs": 1, "Pizzas": 1.45, "Silicon Nuggets": 0.52, "Seashells": 0.72},
    "Pizzas": {"Snowballs": 0.7, "Pizzas": 1, "Silicon Nuggets": 0.31, "Seashells": 0.48},
    "Silicon Nuggets": {"Snowballs": 1.95, "Pizzas": 3.1, "Silicon Nuggets": 1, "Seashells": 1.49},
    "Seashells": {"Snowballs": 1.34, "Pizzas": 1.98, "Silicon Nuggets": 0.64, "Seashells": 1}
}

available_capital = 2000000
max_trades = 5

# make trades starting at seashells and ending at seashells... maximuze the amount of seashells at end

def calculate_path_multiplier(path):
    """Calculate the total multiplier for a given path of trades."""
    if len(path) <= 1:
        return 1.0
    
    total_multiplier = 1.0
    for i in range(len(path) - 1):
        from_currency = path[i]
        to_currency = path[i + 1]
        multiplier = conversion_rates[from_currency][to_currency]
        total_multiplier *= multiplier
    return total_multiplier

def find_best_path(max_trades):
    """Find the path with the highest return multiplier."""
    def generate_paths(current_path, trades_left):
        if trades_left == 0:
            if current_path[-1] == "Seashells":  # Only consider paths that end in Seashells
                return [current_path]
            return []
        
        paths = []
        for next_currency in conversion_rates[current_path[-1]]:
            new_path = current_path + [next_currency]
            paths.extend(generate_paths(new_path, trades_left - 1))
        return paths
    
    # Generate all possible paths starting and ending with Seashells
    all_paths = generate_paths(["Seashells"], max_trades)
    
    # Calculate multiplier for each path
    best_path = None
    best_multiplier = 0
    
    for path in all_paths:
        multiplier = calculate_path_multiplier(path)
        if multiplier > best_multiplier:
            best_multiplier = multiplier
            best_path = path
    
    return best_path, best_multiplier

def bfs(available_capital, max_trades):
    # Initialize the amount of seashells at the start
    current_capital = available_capital
    
    # Initialize a queue for BFS with (item, capital, trades_count, path)
    queue = deque([("Seashells", current_capital, 0, [("Seashells", current_capital)])])
    
    # Keep track of the best result
    best_result = (current_capital, [("Seashells", current_capital)])
    
    # Process each state in the queue
    while queue:
        current_item, current_capital, current_trades, current_path = queue.popleft()
        
        # If we've reached max trades and current item is Seashells, check if it's the best result
        if current_trades == max_trades and current_item == "Seashells":
            if current_capital > best_result[0]:
                best_result = (current_capital, current_path)
            continue
        elif current_trades == max_trades:
            continue
            
        # Calculate the amount of each item we can buy
        for item, conversion_rate in conversion_rates[current_item].items():
            new_capital = current_capital * conversion_rate
            new_path = current_path + [(item, new_capital)]
            queue.append((item, new_capital, current_trades + 1, new_path))
    
    return best_result[1]  # Return the path that gives maximum profit

# Run both methods and compare results
print("BFS Method Result:")
bfs_path = bfs(available_capital, max_trades)
print(f"Final amount: {bfs_path[-1][1]}")
print("Path taken:")
for item, amount in bfs_path:
    print(f"{item}: {amount:,.2f}")

print("\nBest Multiplier Path:")
best_path, best_multiplier = find_best_path(max_trades)
print(f"Best path: {' -> '.join(best_path)}")
print(f"Multiplier: {best_multiplier:.4f}")
print(f"Starting with {available_capital:,.2f} would yield: {available_capital * best_multiplier:,.2f}")
    