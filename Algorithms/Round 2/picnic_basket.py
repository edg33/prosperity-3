import json
from datamodel import TradingState, Order
from typing import List

class Trader:
    def run(self, state: TradingState):
        result = {}
        # POSITION LIMITS:
        POSITION_LIMITS = {
            "CROISSANTS": 250,
            "JAMS": 350,
            "DJEMBES": 60,
            "PICNIC_BASKET1": 60,
            "PICNIC_BASKET2": 100,
        }
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
            if product == "DJEMBES":
                ...
            elif product == "CROISSANTS":
                ...
            elif product == "JAMS":
                ...
            elif product == "PICNIC_BASKET1":
                ...
            elif product == "PICNIC_BASKET2":
                ...
            # SAMPLE:
                # order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                # if order_size > 0:
                #     orders.append(Order(product, best_ask, order_size))
        
        
        result[product] = orders

        # Save trader_data as JSON string for the next iteration
        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data