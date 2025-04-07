import sys
import os
from backtester import Round1Backtester
import importlib.util

def load_trader_class(algorithm_path: str):
    """
    Dynamically load the Trader class from a Python file
    """
    # Get the module name from the file path
    module_name = os.path.splitext(os.path.basename(algorithm_path))[0]
    
    # Load the module specification
    spec = importlib.util.spec_from_file_location(module_name, algorithm_path)
    if spec is None:
        raise ImportError(f"Could not load module specification from {algorithm_path}")
    
    # Create the module
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Could not load module from {algorithm_path}")
    
    # Execute the module
    spec.loader.exec_module(module)
    
    # Get the Trader class
    if not hasattr(module, 'Trader'):
        raise AttributeError(f"No Trader class found in {algorithm_path}")
    
    return module.Trader

def main():
    if len(sys.argv) != 3:
        print("Usage: python run_backtest.py <algorithm_path> <data_path>")
        print("Example: python run_backtest.py '../Algorithms/Round 1/rishi_r1.py' '../Test Data/Round 1/r1.csv'")
        sys.exit(1)
        
    algorithm_path = sys.argv[1]
    data_path = sys.argv[2]
    
    # Load the trader class
    try:
        Trader = load_trader_class(algorithm_path)
    except Exception as e:
        print(f"Error loading trader class: {str(e)}")
        sys.exit(1)
        
    # Create and run backtester
    try:
        backtester = Round1Backtester(data_path, Trader)
        backtester.run()
        results = backtester.analyze_performance()
        
        print("\nBacktesting completed successfully!")
        print(f"Results saved to portfolio_value.png")
        print(f"Check the logs directory for detailed trade logs")
        
    except Exception as e:
        print(f"Error during backtesting: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 