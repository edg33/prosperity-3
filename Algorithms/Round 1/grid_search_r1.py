import subprocess
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
import itertools
from multiprocessing import Pool, cpu_count
import re

def run_backtest(args: Tuple[str, int, Dict]) -> Tuple[Dict, float]:
    """Run a single backtest with given parameters and return the parameters and profit."""
    script_path, round_num, params = args
    
    # Create a temporary copy of the script with the parameters
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Replace the parameters in the script
    for param, value in params.items():
        script_content = script_content.replace(
            f"{param} = ",  # Original parameter line
            f"{param} = {value}  # Grid search optimized\n"
        )
    
    # Write the modified script to a temporary file
    temp_script = f"temp_grid_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.py"
    with open(temp_script, 'w') as f:
        f.write(script_content)
    
    try:
        # Run the backtest with the correct command format
        cmd = f"python3 -m prosperity3bt {temp_script} {round_num}"
        print(f"\nRunning command: {cmd}")
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        # Debug: Print the full output
        print(f"\nBacktest output for params {json.dumps(params)}:")
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        
        # Try multiple patterns to find the profit
        profit_patterns = [
            r"Total profit:\s*([-+]?\d*\.?\d+)",
            r"Final PnL:\s*([-+]?\d*\.?\d+)",
            r"Profit:\s*([-+]?\d*\.?\d+)"
        ]
        
        profit = float('-inf')
        for pattern in profit_patterns:
            match = re.search(pattern, result.stdout)
            if match:
                profit = float(match.group(1))
                print(f"Extracted profit using pattern '{pattern}': {profit}")
                break
        
        if profit == float('-inf'):
            print("No profit found in output!")
            
    except Exception as e:
        print(f"Error running backtest: {str(e)}")
        profit = float('-inf')
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_script):
            os.remove(temp_script)
    
    return params, profit

def grid_search(script_path: str, round_num: int, param_grid: Dict) -> Tuple[Dict, float, List[Dict]]:
    """Perform grid search over parameter combinations using parallel processing."""
    # Generate all combinations of parameters
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))
    
    # Prepare arguments for parallel processing
    args = [(script_path, round_num, dict(zip(param_names, combo))) for combo in combinations]
    
    # Determine number of processes to use (leave one core free for system)
    num_processes = max(1, cpu_count() - 1)
    print(f"Running grid search with {num_processes} processes...")
    
    # Run backtests in parallel
    with Pool(processes=num_processes) as pool:
        results = pool.map(run_backtest, args)
    
    # Process results
    best_params = None
    best_profit = float('-inf')
    all_results = []
    
    for params, profit in results:
        all_results.append({
            'params': params,
            'profit': profit
        })
        
        if profit > best_profit:
            best_profit = profit
            best_params = params
            print(f"New best parameters found! Profit: {profit:,.2f}")
            print(json.dumps(params, indent=2))
    
    return best_params, best_profit, all_results

def main():
    # Define a smaller parameter grid for testing
    param_grid = {
        # Window sizes (reduced options)
        'window_size': [10],  # Main window size
        'short_window': [3],   # Short window for regime detection
        'resin_window': [5],  # Window size for resin mean reversion
        
        # Trading thresholds (reduced options)
        'buy_threshold': [-1.0],  # Z-score threshold for buying
        'sell_threshold': [1.0],   # Z-score threshold for selling
        'correlation_threshold': [0.2],  # Correlation threshold
        
        # Position scaling (reduced options)
        'position_scale_factor': [0.5]  # How aggressively to scale positions
    }
    
    # Run grid search
    script_path = "Algorithms/Round 1/rishi_r1.py"
    round_num = 1
    
    total_combinations = 1  # Just one combination for testing
    print(f"Starting grid search with {total_combinations} combinations...")
    best_params, best_profit, all_results = grid_search(script_path, round_num, param_grid)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"grid_search_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            'best_params': best_params,
            'best_profit': best_profit,
            'all_results': all_results
        }, f, indent=2)
    
    print(f"\nGrid search completed!")
    print(f"Best parameters: {json.dumps(best_params, indent=2)}")
    print(f"Best profit: {best_profit:,.2f}")
    print(f"Results saved to {results_file}")

if __name__ == "__main__":
    main() 