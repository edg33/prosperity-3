import json
from datamodel import OrderDepth, TradingState, Order
from typing import List 

class Trader:
    def run(self, state: TradingState):
        result = {}
        max_position = 50  # Position limit per product

        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}

        prices = {}  # Track mid-prices for cointegration logic

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            current_position = state.position.get(product, 0)

            best_ask = min(order_depth.sell_orders.keys(), default=None)
            best_bid = max(order_depth.buy_orders.keys(), default=None)

            if best_ask is None and best_bid is None:
                continue

            if best_ask is not None and best_bid is not None:
                mid_price = (best_bid + best_ask) / 2
            elif best_ask is not None:
                mid_price = best_ask * 0.99
            else:
                mid_price = best_bid * 1.01

            prices[product] = mid_price  # Save for cointegration logic later

            if product == "RAINFOREST_RESIN":
                historical_mean = trader_data.get(product, mid_price)
                alpha = 0.1
                updated_mean = alpha * mid_price + (1 - alpha) * historical_mean

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; "
                      f"Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; Historical Mean: {historical_mean:.2f}; "
                      f"Updated Mean: {updated_mean:.2f}; Current Position: {current_position}")

                available_buy = max_position - current_position
                available_sell = max_position + current_position

                if best_ask is not None and best_ask < historical_mean and available_buy > 0:
                    order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                    if order_size > 0:
                        orders.append(Order(product, best_ask, order_size))
                        print(f"--> RAINFOREST_RESIN: Placing BUY order for {order_size} units at {best_ask}", end=";")

                if best_bid is not None and best_bid > historical_mean and available_sell > 0:
                    order_size = min(available_sell, order_depth.buy_orders[best_bid])
                    if order_size > 0:
                        orders.append(Order(product, best_bid, -order_size))
                        print(f"--> RAINFOREST_RESIN: Placing SELL order for {order_size} units at {best_bid}", end=";")

                trader_data[product] = updated_mean

            elif product == "KELP":
                kelp_data = trader_data.get(product, {"short_ma": mid_price, "long_ma": mid_price})
                short_ma = kelp_data.get("short_ma", mid_price)
                long_ma = kelp_data.get("long_ma", mid_price)

                alpha_short = 0.3
                alpha_long = 0.1
                updated_short_ma = alpha_short * mid_price + (1 - alpha_short) * short_ma
                updated_long_ma = alpha_long * mid_price + (1 - alpha_long) * long_ma

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; "
                      f"Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; Short MA: {updated_short_ma:.2f}; "
                      f"Long MA: {updated_long_ma:.2f}; Current Position: {current_position}")

                available_buy = max_position - current_position
                available_sell = max_position + current_position

                if updated_short_ma > updated_long_ma:
                    if best_ask is not None and best_ask < updated_short_ma and available_buy > 0:
                        order_size = min(available_buy, -order_depth.sell_orders[best_ask])
                        if order_size > 0:
                            orders.append(Order(product, best_ask, order_size))
                            print(f"--> KELP: Bullish signal - Placing BUY order for {order_size} units at {best_ask}", end=";")
                elif updated_short_ma < updated_long_ma:
                    if best_bid is not None and best_bid > updated_short_ma and available_sell > 0:
                        order_size = min(available_sell, order_depth.buy_orders[best_bid])
                        if order_size > 0:
                            orders.append(Order(product, best_bid, -order_size))
                            print(f"--> KELP: Bearish signal - Placing SELL order for {order_size} units at {best_bid}", end=";")

                trader_data[product] = {"short_ma": updated_short_ma, "long_ma": updated_long_ma}

            elif product == "SQUID_INK":
                kelp_price = prices.get("KELP")
                if kelp_price is None:
                    result[product] = []
                    continue  # Need KELP to calculate spread

                spread = mid_price - kelp_price
                spread_data = trader_data.get(product, {"mean": spread, "std": 1})
                mean_spread = spread_data.get("mean", spread)
                std_spread = spread_data.get("std", 1)
                alpha_spread = 0.05

                # Update mean and std using exponential moving average (Welford could be better)
                updated_mean = alpha_spread * spread + (1 - alpha_spread) * mean_spread
                updated_std = alpha_spread * abs(spread - mean_spread) + (1 - alpha_spread) * std_spread

                z_score = (spread - updated_mean) / (updated_std + 1e-5)

                print(f"[Time {state.timestamp}] Product: {product}; Spread: {spread:.2f}; Z-score: {z_score:.2f}; "
                      f"Mean Spread: {updated_mean:.2f}; Std Dev: {updated_std:.2f}; Current Position: {current_position}")

                available_buy = max_position - current_position
                available_sell = max_position + current_position

                if z_score > 1 and available_sell > 0:
                    order_size = min(available_sell, order_depth.buy_orders.get(best_bid, 0))
                    if order_size > 0:
                        orders.append(Order(product, best_bid, -order_size))
                        print(f"--> SQUID_INK: Spread high - Placing SELL order for {order_size} units at {best_bid}", end=";")
                elif z_score < -1 and available_buy > 0:
                    order_size = min(available_buy, -order_depth.sell_orders.get(best_ask, 0))
                    if order_size > 0:
                        orders.append(Order(product, best_ask, order_size))
                        print(f"--> SQUID_INK: Spread low - Placing BUY order for {order_size} units at {best_ask}", end=";")

                trader_data[product] = {"mean": updated_mean, "std": updated_std}

            result[product] = orders

        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data
