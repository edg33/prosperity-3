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
        
        # Store mid-prices for later fair value calculations
        mid_prices = {}

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
            
            mid_prices[product] = mid_price

            # Store orders (none yet for components)
            if product in {"DJEMBES", "CROISSANTS", "JAMS"}:
                result[product] = []
            elif product == "PICNIC_BASKET1":
                # Evaluate fair value: 6 CROISSANTS + 3 JAMS + 1 DJEMBES
                if all(p in mid_prices for p in ["CROISSANTS", "JAMS", "DJEMBES"]):
                    fair_value = (
                        6 * mid_prices["CROISSANTS"] +
                        3 * mid_prices["JAMS"] +
                        1 * mid_prices["DJEMBES"]
                    )
                    profit = mid_price - fair_value

                    if profit > 1:  # arbitrage threshold
                        # Sell 1 basket, buy 6/3/1 of components
                        max_trades = min(
                            POSITION_LIMITS["PICNIC_BASKET1"] - state.position.get("PICNIC_BASKET1", 0),
                            (POSITION_LIMITS["CROISSANTS"] - state.position.get("CROISSANTS", 0)) // 6,
                            (POSITION_LIMITS["JAMS"] - state.position.get("JAMS", 0)) // 3,
                            (POSITION_LIMITS["DJEMBES"] - state.position.get("DJEMBES", 0)) // 1,
                        )
                        if best_bid:
                            orders.append(Order(product, best_bid, -max_trades))
                        result["CROISSANTS"] = [Order("CROISSANTS", mid_prices["CROISSANTS"], 6 * max_trades)]
                        result["JAMS"] = [Order("JAMS", mid_prices["JAMS"], 3 * max_trades)]
                        result["DJEMBES"] = [Order("DJEMBES", mid_prices["DJEMBES"], 1 * max_trades)]

            elif product == "PICNIC_BASKET2":
                # Evaluate fair value: 4 CROISSANTS + 2 JAMS
                if all(p in mid_prices for p in ["CROISSANTS", "JAMS"]):
                    fair_value = (
                        4 * mid_prices["CROISSANTS"] +
                        2 * mid_prices["JAMS"]
                    )
                    profit = fair_value - mid_price

                    if profit > 1:  # arbitrage threshold
                        # Buy 1 basket, sell 4/2 of components
                        max_trades = min(
                            POSITION_LIMITS["PICNIC_BASKET2"] - state.position.get("PICNIC_BASKET2", 0),
                            (POSITION_LIMITS["CROISSANTS"] + state.position.get("CROISSANTS", 0)) // 4,
                            (POSITION_LIMITS["JAMS"] + state.position.get("JAMS", 0)) // 2,
                        )
                        if best_ask:
                            orders.append(Order(product, best_ask, max_trades))
                        result["CROISSANTS"] = result.get("CROISSANTS", []) + [Order("CROISSANTS", mid_prices["CROISSANTS"], -4 * max_trades)]
                        result["JAMS"] = result.get("JAMS", []) + [Order("JAMS", mid_prices["JAMS"], -2 * max_trades)]

        
        
        result[product] = orders

        # Save trader_data as JSON string for the next iteration
        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data