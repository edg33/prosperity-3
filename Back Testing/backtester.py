import pandas as pd
from typing import Dict, List, Type, Any
import sys
import os

# Add the root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datamodel import TradingState, Listing, Observation, OrderDepth
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import logging
import json
import datetime

class BaseBacktester(ABC):
    def __init__(self, csv_path: str, trader_class: Type, logger_level: int = logging.INFO):
        """
        Initialize the backtester with data path and trader class
        
        Args:
            csv_path: Path to the CSV file containing market data
            trader_class: The trader class to backtest
            logger_level: Logging level (default: INFO)
        """
        self.csv_path = csv_path
        self.trader_class = trader_class
        self.trader_instance = None
        self.data = None
        self.current_position: Dict[str, int] = {}
        self.cash = 0
        self.trades_history: List[Dict] = []
        self.pnl_history: List[float] = []
        
        # Setup logging
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Create a unique log filename based on timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        algo_name = os.path.basename(str(trader_class.__module__))
        log_filename = f"{log_dir}/backtest_{algo_name}_{timestamp}.log"
        
        # Configure file handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logger_level)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)
        
        # Remove existing handlers if any
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        # Add the file handler
        self.logger.addHandler(file_handler)
        
        # Disable propagation to avoid duplicate logs
        self.logger.propagate = False
        
        self.logger.info(f"Logging to {log_filename}")
        
    @abstractmethod
    def preprocess_data(self) -> pd.DataFrame:
        """
        Preprocess the CSV data into a format suitable for backtesting.
        Must be implemented by each round's specific backtester.
        """
        pass
    
    def load_data(self):
        """Load and preprocess the market data"""
        self.logger.info(f"Loading data from {self.csv_path}")
        self.data = self.preprocess_data()
        self.logger.info(f"Loaded {len(self.data)} market data points")
        
    def create_order_depth(self, row: pd.Series) -> OrderDepth:
        """Create order depth dictionary from a data row"""
        order_depth = OrderDepth()
        
        # Add non-NaN bid prices and volumes
        for i in range(1, 4):
            bid_price = row.get(f'bid_price_{i}')
            bid_volume = row.get(f'bid_volume_{i}')
            if pd.notna(bid_price) and pd.notna(bid_volume):
                order_depth.buy_orders[float(bid_price)] = int(bid_volume)
                
        # Add non-NaN ask prices and volumes
        for i in range(1, 4):
            ask_price = row.get(f'ask_price_{i}')
            ask_volume = row.get(f'ask_volume_{i}')
            if pd.notna(ask_price) and pd.notna(ask_volume):
                order_depth.sell_orders[float(ask_price)] = int(ask_volume)
                
        return order_depth
    
    def create_trading_state(self, timestamp: int, 
                           order_depths: Dict[str, Dict], 
                           own_trades: Dict[str, List], 
                           market_trades: Dict[str, List],
                           position: Dict[str, int],
                           observations: Dict[str, Any]) -> TradingState:
        """Create a TradingState object from current market state"""
        # Create empty listings dictionary for each product
        listings = {}
        
        # Initialize empty trade lists for each product
        empty_own_trades = {product: [] for product in order_depths.keys()}
        empty_market_trades = {product: [] for product in order_depths.keys()}
        
        # Create listings for each product
        for product in order_depths.keys():
            listings[product] = Listing(symbol=product, product=product, denomination="USDT")
            
        # Create empty Observation object
        empty_observation = Observation(plainValueObservations={}, conversionObservations={})
        
        # Convert trader data to JSON string if it exists
        if isinstance(self.trader_data, str):
            trader_data = self.trader_data
        else:
            trader_data = json.dumps(self.trader_data)
        
        return TradingState(
            traderData=trader_data,
            timestamp=timestamp,
            listings=listings,
            order_depths=order_depths,
            own_trades=empty_own_trades,
            market_trades=empty_market_trades,
            position=position,
            observations=empty_observation
        )
    
    def execute_trades(self, orders: Any, 
                      current_prices: Dict[str, float],
                      timestamp: int) -> float:
        """
        Execute trades and calculate PnL
        Returns the PnL for this round of trades
        """
        round_pnl = 0
        
        # Convert tuple return (orders, conversions, trader_data) to just orders
        if isinstance(orders, tuple):
            orders, _, trader_data = orders
            if isinstance(trader_data, str):
                try:
                    self.trader_data = json.loads(trader_data)
                except json.JSONDecodeError:
                    self.trader_data = {}
            else:
                self.trader_data = trader_data
            
        # Handle empty orders
        if not orders:
            return 0.0
            
        # Handle dictionary of orders
        if isinstance(orders, dict):
            for product, product_orders in orders.items():
                if not product_orders:  # Skip empty order lists
                    continue
                for order in product_orders:
                    # Update position and cash
                    old_position = self.current_position.get(product, 0)
                    self.current_position[product] = old_position + order.quantity
                    
                    # Calculate trade cash flow (negative for buys, positive for sells)
                    cash_flow = -order.quantity * order.price
                    self.cash += cash_flow
                    
                    # Log trade details similar to what's in the trader logs
                    trade_type = "BUY" if order.quantity > 0 else "SELL"
                    self.logger.info(f"--> {product}: Placing {trade_type} order for {abs(order.quantity)} units at {order.price}")
                    
                    # Calculate trade PnL based on market price
                    if order.quantity > 0:  # Buy order
                        position_value_change = (current_prices[product] - order.price) * order.quantity
                    else:  # Sell order
                        # For short selling, we make money when price goes down after we sell
                        # If current price is higher than sell price, that's a loss
                        position_value_change = -(current_prices[product] - order.price) * abs(order.quantity)
                    trade_pnl = position_value_change
                    round_pnl += trade_pnl
                    
                    # Log PnL information
                    pnl_status = "PROFIT" if position_value_change > 0 else "LOSS" if position_value_change < 0 else "BREAK EVEN"
                    self.logger.info(f"    Trade PnL: {position_value_change:.2f} ({pnl_status}) | Market price: {current_prices[product]} | New position: {self.current_position[product]}")
                    
                    # Record trade
                    self.trades_history.append({
                        'timestamp': str(timestamp),
                        'product': product,
                        'quantity': order.quantity,
                        'price': order.price,
                        'cash_flow': cash_flow,
                        'position_value_change': position_value_change,
                        'pnl': trade_pnl,
                        'position': self.current_position[product],
                        'market_price': current_prices[product]
                    })
                    
        return round_pnl
    
    def run(self):
        """Run the backtesting simulation"""
        if self.data is None:
            self.load_data()
            
        self.trader_instance = self.trader_class()
        self.logger.info("Starting backtest simulation")
        
        # Initialize trader data as a dictionary
        self.trader_data = {}
        
        # Group data by timestamp
        grouped_data = self.data.groupby(['day', 'timestamp'])
        
        for (day, timestamp), group in grouped_data:
            # Prepare order depths for all products
            order_depths = {}
            current_prices = {}
            
            for _, row in group.iterrows():
                product = row['product']
                order_depths[product] = self.create_order_depth(row)
                current_prices[product] = row['mid_price']
            
            # Create trading state
            state = self.create_trading_state(
                timestamp=timestamp,
                order_depths=order_depths,
                own_trades={},  # Empty for now, could be enhanced
                market_trades={},  # Empty for now, could be enhanced
                position=self.current_position.copy(),
                observations={}  # Could be enhanced with additional market data
            )
            
            # Get trading decisions
            try:
                result = self.trader_instance.run(state)
                round_pnl = self.execute_trades(result, current_prices, timestamp)
                self.pnl_history.append(round_pnl)
            except Exception as e:
                self.logger.error(f"Error during trading at day {day}, timestamp {timestamp}: {str(e)}")
                continue
                
        self.logger.info("Backtest simulation completed")
        
    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value including cash and positions"""
        total_value = self.cash  # Start with cash
        
        # Add value of all positions (both long and short)
        for product, position in self.current_position.items():
            if position != 0 and product in current_prices:
                position_value = position * current_prices[product]  # This will be negative for shorts
                total_value += position_value
                
        return total_value
        
    def analyze_performance(self):
        """Analyze trading performance and generate insights"""
        if not self.trades_history:
            self.logger.warning("No trades to analyze")
            return
        
        # Convert trades history to DataFrame
        trades_df = pd.DataFrame(self.trades_history)
        
        # Create a DataFrame with all timestamps from the original data
        all_timestamps = self.data[['timestamp']].drop_duplicates().sort_values('timestamp')
        portfolio_df = pd.DataFrame(index=all_timestamps['timestamp'])
        
        # Initialize tracking variables
        current_cash = 0
        current_positions = {}
        
        # Track portfolio value at each timestamp
        portfolio_values = []
        timestamps = []
        
        for timestamp in all_timestamps['timestamp']:
            # Update cash and positions with any trades at this timestamp
            trades_at_ts = trades_df[trades_df['timestamp'] == str(timestamp)]
            if not trades_at_ts.empty:
                current_cash += trades_at_ts['cash_flow'].sum()
                for _, trade in trades_at_ts.iterrows():
                    current_positions[trade['product']] = trade['position']
            
            # Get current market prices
            current_prices = {}
            for product in self.data[self.data['timestamp'] == timestamp]['product'].unique():
                price = self.data[(self.data['timestamp'] == timestamp) & 
                                (self.data['product'] == product)]['mid_price'].iloc[0]
                current_prices[product] = price
            
            # Calculate total portfolio value (cash + position values)
            position_value = sum(pos * current_prices.get(prod, 0) 
                               for prod, pos in current_positions.items())
            portfolio_value = current_cash + position_value
            
            portfolio_values.append(portfolio_value)
            timestamps.append(timestamp)
        
        # Plot portfolio value over time
        plt.figure(figsize=(15, 8))
        plt.plot(range(len(timestamps)), portfolio_values, label='Portfolio Value', linewidth=2)
        
        # Add markers for trades
        trade_indices = []
        trade_values = []
        for ts in trades_df['timestamp'].unique():
            try:
                idx = timestamps.index(int(ts))
                trade_indices.append(idx)
                trade_values.append(portfolio_values[idx])
            except (ValueError, IndexError):
                continue
        
        plt.scatter(trade_indices, trade_values, color='red', label='Trades', zorder=5)
        
        plt.title('Portfolio Value Over Time')
        plt.xlabel('Iteration')
        plt.ylabel('Value')
        plt.legend()
        plt.grid(True)
        plt.margins(y=0.1)
        plt.tight_layout()
        plt.savefig('portfolio_value.png')
        plt.close()
        
        # Print analysis
        self.logger.info("\n=== Performance Analysis ===")
        self.logger.info(f"Total Trades: {len(trades_df)}")
        self.logger.info(trades_df)
        self.logger.info(f"Profitable Trades: {len(trades_df[trades_df['position_value_change'] > 0])} ({len(trades_df[trades_df['position_value_change'] > 0])/len(trades_df)*100:.2f}%)")
        self.logger.info(f"Loss Making Trades: {len(trades_df[trades_df['position_value_change'] < 0])} ({len(trades_df[trades_df['position_value_change'] < 0])/len(trades_df)*100:.2f}%)")
        self.logger.info(f"Break Even Trades: {len(trades_df[trades_df['position_value_change'] == 0])} ({len(trades_df[trades_df['position_value_change'] == 0])/len(trades_df)*100:.2f}%)")
        
        self.logger.info("\n=== Portfolio Summary ===")
        final_portfolio_value = portfolio_values[-1]
        self.logger.info(f"Final Portfolio Value: {final_portfolio_value:,.2f}")
        self.logger.info(f"Total Cash: {current_cash:,.2f}")
        
        self.logger.info("\n=== Final Positions ===")
        for product, position in current_positions.items():
            last_price = current_prices.get(product, 0)
            position_value = position * last_price
            self.logger.info(f"{product}: {position:,} units @ {last_price:,.2f} = {position_value:,.2f}")
        
        self.logger.info("\n=== Product Analysis ===")
        product_analysis = trades_df.groupby('product').agg({
            'cash_flow': ['sum', 'count'],
            'position_value_change': ['sum', 'mean', 'std'],
            'pnl': ['sum', 'mean', 'std'],
            'quantity': 'sum'
        }).to_dict()
        self.logger.info(product_analysis)
        
        return {
            'total_trades': len(trades_df),
            'profitable_trades': len(trades_df[trades_df['position_value_change'] > 0]),
            'loss_making_trades': len(trades_df[trades_df['position_value_change'] < 0]),
            'break_even_trades': len(trades_df[trades_df['position_value_change'] == 0]),
            'final_portfolio_value': final_portfolio_value,
            'total_cash': current_cash,
            'total_realized_pnl': trades_df['position_value_change'].sum(),
            'unrealized_pnl': final_portfolio_value - current_cash - trades_df['position_value_change'].sum(),
            'product_analysis': product_analysis
        }

class Round1Backtester(BaseBacktester):
    def preprocess_data(self) -> pd.DataFrame:
        """
        Preprocess Round 1 specific CSV data
        """
        df = pd.read_csv(self.csv_path, sep=';')
        
        # Ensure required columns exist
        required_columns = [
            'day', 'timestamp', 'product',
            'bid_price_1', 'bid_volume_1',
            'ask_price_1', 'ask_volume_1',
            'mid_price'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
            
        # Convert price and volume columns to numeric
        price_columns = [col for col in df.columns if 'price' in col]
        volume_columns = [col for col in df.columns if 'volume' in col]
        
        for col in price_columns + volume_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Validate price data
        df = df.dropna(subset=['mid_price'])  # Remove rows with invalid mid prices
        
        # Sort by timestamp to ensure chronological order
        df = df.sort_values(['day', 'timestamp'])
        
        # Initialize positions to 0 for each product
        products = df['product'].unique()
        for product in products:
            self.current_position[product] = 0
            
        return df 