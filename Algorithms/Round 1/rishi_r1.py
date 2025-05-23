import json
from datamodel import TradingState, Order
from typing import List, Dict, Tuple
import numpy as np

class Trader:
    def calculate_vwap(self, trades: List[Dict]) -> Tuple[float, float]:
        if not trades:
            return 0, 0
        total_volume = sum(abs(trade.quantity) for trade in trades)
        if total_volume == 0:
            return 0, 0
        vwap = sum(trade.price * abs(trade.quantity) for trade in trades) / total_volume
        return vwap, total_volume

    def update_price_history(self, 
                           product: str, 
                           market_trades: Dict[str, List], 
                           order_depth,
                           trader_data: Dict,
                           window_size: int) -> Tuple[float, List[float]]:
        # Initialize price history from trader_data
        price_history = trader_data.get(f'{product}_prices', [])
        
        # Get current market price from trades or order book
        current_price = None
        current_volume = 0
        
        # First try to get VWAP from recent market trades
        if product in market_trades and isinstance(market_trades[product], list) and market_trades[product]:
            vwap, volume = self.calculate_vwap(market_trades[product])
            if volume > 0:
                current_price = vwap
                current_volume = volume
        
        # If no trades, fall back to mid price from order book
        if current_price is None:
            best_ask = min(order_depth.sell_orders.keys(), default=None)
            best_bid = max(order_depth.buy_orders.keys(), default=None)
            
            if best_ask is not None and best_bid is not None:
                current_price = (best_bid + best_ask) / 2
                # Use the minimum volume available at best bid/ask as the volume
                current_volume = min(abs(order_depth.sell_orders[best_ask]), 
                                  abs(order_depth.buy_orders[best_bid]))
            elif best_ask is not None:
                current_price = best_ask
                current_volume = abs(order_depth.sell_orders[best_ask])
            elif best_bid is not None:
                current_price = best_bid
                current_volume = abs(order_depth.buy_orders[best_bid])
            else:
                # If no price information available, use last known price
                current_price = price_history[-1] if price_history else None
                current_volume = 0
        
        # Only update history if we have a valid price
        if current_price is not None:
            price_history.append(current_price)
            # Also store volume information
            volume_history = trader_data.get(f'{product}_volumes', [])
            volume_history.append(current_volume)
            trader_data[f'{product}_volumes'] = volume_history[-window_size:]
            
            # Maintain window size
            if len(price_history) > window_size:
                price_history = price_history[-window_size:]
            
            # Update the price history in trader_data
            trader_data[f'{product}_prices'] = price_history
                
        return current_price, price_history

    def run(self, state: TradingState):
        result = {}
        # Grid search parameters
        max_position = 50  # Position limit per product
        window_size = 20  # Rolling window size for correlation calculation
        short_window = 5  # Shorter window for regime detection
        resin_window = 10  # Window size for resin mean reversion
        buy_threshold = -1.0  # Z-score threshold for buying
        sell_threshold = 1.0  # Z-score threshold for selling
        correlation_threshold = 0.3  # Correlation threshold
        position_scale_factor = 0.75  # How aggressively to scale positions
        
        # Load previous state from traderData (if available)
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}

        # Initialize correlation history
        correlation_history = trader_data.get('correlation_history', [])

        # Track own trades and market trades
        own_trades = state.own_trades
        market_trades = state.market_trades
        positions = state.position

        # Update price histories for all products
        current_kelp_price, kelp_prices = self.update_price_history(
            "KELP", market_trades, state.order_depths["KELP"], trader_data, window_size)
        current_squid_price, squid_ink_prices = self.update_price_history(
            "SQUID_INK", market_trades, state.order_depths["SQUID_INK"], trader_data, window_size)
        current_resin_price, resin_prices = self.update_price_history(
            "RAINFOREST_RESIN", market_trades, state.order_depths["RAINFOREST_RESIN"], trader_data, resin_window)

        # Debug: Print initial state
        print(f"\n[Time {state.timestamp}] Initial State:")
        print(f"KELP prices collected: {len(kelp_prices)}/{window_size}")
        print(f"SQUID_INK prices collected: {len(squid_ink_prices)}/{window_size}")
        print(f"RAINFOREST_RESIN prices collected: {len(resin_prices)}/{resin_window}")

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            current_position = positions.get(product, 0)

            best_ask = min(order_depth.sell_orders.keys(), default=None)
            best_bid = max(order_depth.buy_orders.keys(), default=None)

            if best_ask is None and best_bid is None:
                continue

            if product == "RAINFOREST_RESIN":
                if len(resin_prices) < 5:  # Minimum required data points
                    print(f"RAINFOREST_RESIN: Waiting for more data ({len(resin_prices)}/5)")
                    continue
                    
                # Mean reversion strategy for RAINFOREST_RESIN
                mean_price = np.mean(resin_prices)
                std_price = np.std(resin_prices)
                
                if std_price > 0:  # Only trade if there's some price variation
                    z_score = (current_resin_price - mean_price) / std_price
                    
                    # Calculate position size based on deviation from mean
                    position_scale = min(1.0, abs(z_score) / 2) * position_scale_factor
                    max_trade_size = int(max_position * position_scale)
                    
                    # Debug: Print trading conditions
                    print(f"\nRAINFOREST_RESIN Trading Conditions:")
                    print(f"Current Price: {current_resin_price:.2f}, Mean: {mean_price:.2f}, Std: {std_price:.2f}")
                    print(f"Z-Score: {z_score:.2f}, Position Scale: {position_scale:.2f}")
                    
                    # Sell when price is high
                    if z_score > sell_threshold and best_bid is not None:
                        available_sell = max_trade_size + current_position
                        order_size = min(available_sell, order_depth.buy_orders[best_bid])
                        if order_size > 0:
                            orders.append(Order(product, best_bid, -order_size))
                            print(f"SELL Signal: Z-Score {z_score:.2f} > {sell_threshold}, Order Size: {order_size}")
                    
                    # Buy when price is low
                    elif z_score < buy_threshold and best_ask is not None:
                        available_buy = max_trade_size - current_position
                        order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                        if order_size > 0:
                            orders.append(Order(product, best_ask, order_size))
                            print(f"BUY Signal: Z-Score {z_score:.2f} < {buy_threshold}, Order Size: {order_size}")

            # Correlation trading for KELP and SQUID_INK
            elif product in ["KELP", "SQUID_INK"]:
                if len(kelp_prices) < 5 or len(squid_ink_prices) < 5:  # Minimum required data points
                    print(f"{product}: Waiting for more data (KELP: {len(kelp_prices)}/5, SQUID_INK: {len(squid_ink_prices)}/5)")
                    continue
                    
                # Calculate current correlation
                correlation = np.corrcoef(kelp_prices, squid_ink_prices)[0, 1]
                correlation_history.append(correlation)
                if len(correlation_history) > short_window:
                    correlation_history.pop(0)

                # Detect correlation regime
                recent_correlation = np.mean(correlation_history[-short_window:])
                correlation_trend = np.mean(np.diff(correlation_history[-short_window:]))

                # Debug: Print correlation state
                print(f"\n{product} Correlation State:")
                print(f"Current Correlation: {correlation:.2f}, Recent Mean: {recent_correlation:.2f}")
                print(f"Correlation Trend: {correlation_trend:.2f}")

                # Trading logic based on correlation regime
                if abs(correlation) > correlation_threshold:
                    position_scale = min(1.0, abs(correlation)) * position_scale_factor
                    max_trade_size = int(max_position * position_scale)

                    if correlation > correlation_threshold:
                        if product == "KELP" and len(squid_ink_prices) >= 2:
                            squid_trend = squid_ink_prices[-1] - squid_ink_prices[-2]
                            if squid_trend > 0 and best_ask is not None:
                                available_buy = max_trade_size - current_position
                                order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                                if order_size > 0:
                                    orders.append(Order(product, best_ask, order_size))
                                    print(f"BUY Signal: Strong positive correlation ({correlation:.2f}), Squid trend up ({squid_trend:.2f})")
                            elif squid_trend < 0 and best_bid is not None:
                                available_sell = max_trade_size + current_position
                                order_size = min(available_sell, order_depth.buy_orders[best_bid])
                                if order_size > 0:
                                    orders.append(Order(product, best_bid, -order_size))
                                    print(f"SELL Signal: Strong positive correlation ({correlation:.2f}), Squid trend down ({squid_trend:.2f})")

                    elif correlation < -correlation_threshold:
                        if product == "KELP" and len(squid_ink_prices) >= 2:
                            squid_trend = squid_ink_prices[-1] - squid_ink_prices[-2]
                            if squid_trend > 0 and best_bid is not None:
                                available_sell = max_trade_size + current_position
                                order_size = min(available_sell, order_depth.buy_orders[best_bid])
                                if order_size > 0:
                                    orders.append(Order(product, best_bid, -order_size))
                                    print(f"SELL Signal: Strong negative correlation ({correlation:.2f}), Squid trend up ({squid_trend:.2f})")
                            elif squid_trend < 0 and best_ask is not None:
                                available_buy = max_trade_size - current_position
                                order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                                if order_size > 0:
                                    orders.append(Order(product, best_ask, order_size))
                                    print(f"BUY Signal: Strong negative correlation ({correlation:.2f}), Squid trend down ({squid_trend:.2f})")

            # Save orders if any were generated
            if orders:
                result[product] = orders
                print(f"Generated {len(orders)} orders for {product}")
            else:
                print(f"No orders generated for {product}")

        # Save trader_data as JSON string for the next iteration
        trader_data['correlation_history'] = correlation_history
        updated_trader_data = json.dumps(trader_data)
        
        return result, 1, updated_trader_data
