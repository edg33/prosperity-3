import sys
import os
import pandas as pd

# Add the Algorithms directory to sys.path
sys.path.append(os.path.abspath('/Users/evangray/Desktop/Projects/prosperity/prosperity-3/Research'))

import json
from mock_datamodel import OrderDepth, TradingState, Order
from typing import List 

class Trader:
    def run(self, state: TradingState):
        result = {}
        max_position = 50  # Position limit per product

        # Load previous state from traderData (if available)
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}

        # Process each product separately
        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            current_position = state.position.get(product, 0)

            # Determine best ask (lowest sell) and best bid (highest buy)
            best_ask = min(order_depth.sell_orders.keys(), default=None)
            best_bid = max(order_depth.buy_orders.keys(), default=None)

            if best_ask is None and best_bid is None:
                continue

            # Calculate mid-price from available orders
            if best_ask is not None and best_bid is not None:
                mid_price = (best_bid + best_ask) / 2
            elif best_ask is not None:
                mid_price = best_ask * 0.99
            else:  # best_bid is not None
                mid_price = best_bid * 1.01

            # ================================
            # RAINFOREST_RESIN Trading Logic
            # ================================
            if product == "RAINFOREST_RESIN":
                # Retrieve previous historical mean for RAINFOREST_RESIN (default to mid_price)
                historical_mean = trader_data.get(product, mid_price)
                # Update historical mean using exponential smoothing (alpha = 0.1)
                alpha = 0.1
                updated_mean = alpha * mid_price + (1 - alpha) * historical_mean

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; "
                      f"Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; Historical Mean: {historical_mean:.2f}; "
                      f"Updated Mean: {updated_mean:.2f}; Current Position: {current_position}")

                # Calculate available capacity based on current position
                available_buy = max_position - current_position   # units that can be bought
                available_sell = max_position + current_position   # units that can be sold (if short)

                # BUY: If best ask is below historical mean and we have capacity to buy
                if best_ask is not None and best_ask < historical_mean and available_buy > 0:
                    order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                    if order_size > 0:
                        orders.append(Order(product, best_ask, order_size))
                        print(f"--> RAINFOREST_RESIN: Placing BUY order for {order_size} units at {best_ask}", end=";")
                
                # SELL: If best bid is above historical mean and we have capacity to sell
                if best_bid is not None and best_bid > historical_mean and available_sell > 0:
                    order_size = min(available_sell, order_depth.buy_orders[best_bid])
                    if order_size > 0:
                        orders.append(Order(product, best_bid, -order_size))
                        print(f"--> RAINFOREST_RESIN: Placing SELL order for {order_size} units at {best_bid}", end=";")
                
                # Update the historical mean in trader_data
                trader_data[product] = updated_mean

            # ================================
            # KELP Trading Logic (Multiple MAs)
            # ================================
            elif product == "KELP":
                # For KELP we use two moving averages: short-term and long-term
                # Retrieve previous MAs from trader_data for KELP; if not present, initialize both to mid_price
                kelp_data = trader_data.get(product, {"short_ma": mid_price, "long_ma": mid_price})
                short_ma = kelp_data.get("short_ma", mid_price)
                long_ma = kelp_data.get("long_ma", mid_price)
                
                # Update moving averages using exponential smoothing:
                # Short-term with alpha_short and long-term with alpha_long
                alpha_short = 0.3
                alpha_long = 0.1
                updated_short_ma = alpha_short * mid_price + (1 - alpha_short) * short_ma
                updated_long_ma = alpha_long * mid_price + (1 - alpha_long) * long_ma

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; "
                      f"Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; Short MA: {updated_short_ma:.2f}; "
                      f"Long MA: {updated_long_ma:.2f}; Current Position: {current_position}")

                # Calculate available capacity based on current position
                available_buy = max_position - current_position   # units available to buy
                available_sell = max_position + current_position   # units available to sell

                # Signal generation using moving average crossovers:
                # Bullish signal if short MA is above long MA, bearish if below.
                if updated_short_ma > updated_long_ma:
                    # Bullish: if best ask is below the short MA, consider buying.
                    if best_ask is not None and best_ask < updated_short_ma and available_buy > 0:
                        order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                        if order_size > 0:
                            orders.append(Order(product, best_ask, order_size))
                            print(f"--> KELP: Bullish signal - Placing BUY order for {order_size} units at {best_ask}", end=";")
                elif updated_short_ma < updated_long_ma:
                    # Bearish: if best bid is above the short MA, consider selling.
                    if best_bid is not None and best_bid > updated_short_ma and available_sell > 0:
                        order_size = min(available_sell, order_depth.buy_orders[best_bid])
                        if order_size > 0:
                            orders.append(Order(product, best_bid, -order_size))
                            print(f"--> KELP: Bearish signal - Placing SELL order for {order_size} units at {best_bid}", end=";")
                
                # Update KELP data in trader_data
                trader_data[product] = {"short_ma": updated_short_ma, "long_ma": updated_long_ma}

            # If product is neither RAINFOREST_RESIN nor KELP, leave orders empty.
            result[product] = orders

        # Save trader_data as JSON string for the next iteration
        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data
