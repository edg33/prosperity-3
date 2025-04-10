import json
from datamodel import OrderDepth, TradingState, Order
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
                available_sell = max_position + current_position  # units that can be sold (if short)

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
                # Retrieve previous data for KELP (or initialize lists)
                kelp_data = trader_data.get(product, {"short_prices": [], "long_prices": []})
                short_prices = kelp_data.get("short_prices", [])
                long_prices = kelp_data.get("long_prices", [])

                # Append the new mid_price to each list
                short_prices.append(mid_price)
                long_prices.append(mid_price)

                # Keep the short_prices list to a length of 30
                if len(short_prices) > 30:
                    short_prices.pop(0)
                # Keep the long_prices list to a length of 50
                if len(long_prices) > 50:
                    long_prices.pop(0)

                # Compute the short and long MAs
                short_ma = sum(short_prices) / len(short_prices)
                long_ma = sum(long_prices) / len(long_prices)

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; "
                    f"Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; "
                    f"Short MA(30): {short_ma:.2f}; Long MA(50): {long_ma:.2f}; "
                    f"Current Position: {current_position}")

                # Calculate available capacity based on current position
                available_buy = max_position - current_position
                available_sell = max_position + current_position

                # Signal generation using moving average crossovers:
                # Bullish signal if short MA is above long MA; bearish if below.
                if short_ma > long_ma:
                    # Bullish: if best ask is below the short MA, consider buying
                    if best_ask is not None and best_ask < short_ma and available_buy > 0:
                        order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                        if order_size > 0:
                            orders.append(Order(product, best_ask, order_size))
                            print(f"--> KELP: Bullish signal - Placing BUY order for {order_size} units at {best_ask}", end=";")
                elif short_ma < long_ma:
                    # Bearish: if best bid is above the short MA, consider selling
                    if best_bid is not None and best_bid > short_ma and available_sell > 0:
                        order_size = min(available_sell, order_depth.buy_orders[best_bid])
                        if order_size > 0:
                            orders.append(Order(product, best_bid, -order_size))
                            print(f"--> KELP: Bearish signal - Placing SELL order for {order_size} units at {best_bid}", end=";")

                # Update data in trader_data
                kelp_data["short_prices"] = short_prices
                kelp_data["long_prices"] = long_prices
                trader_data[product] = kelp_data

            # If product is neither RAINFOREST_RESIN nor KELP, leave orders empty.
            result[product] = orders

        # Save trader_data as JSON string for the next iteration
        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data