import json
from datamodel import TradingState, Order
from typing import List

class Trader:
    def run(self, state: TradingState):
        result = {}

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

            # Skip if there are no valid bids or asks
            if best_ask is None and best_bid is None:
                continue

            # Calculate mid-price from available orders
            if best_ask is not None and best_bid is not None:
                mid_price = (best_bid + best_ask) / 2
            elif best_ask is not None:
                mid_price = best_ask * 0.99
            else:  # best_bid is not None
                mid_price = best_bid * 1.01
        
        
        # If product is neither RAINFOREST_RESIN nor KELP, leave orders empty.
        result[product] = orders

        # Save trader_data as JSON string for the next iteration
        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data