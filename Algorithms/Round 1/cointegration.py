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

        pair_trading_executed = False

        # ================================
        # Pair Trading Logic for KELP and SQUID_INK
        # ================================
        if "KELP" in state.order_depths and "SQUID_INK" in state.order_depths:
            kelp_depth = state.order_depths["KELP"]
            squid_depth = state.order_depths["SQUID_INK"]

            # Compute mid-price for KELP
            best_ask_kelp = min(kelp_depth.sell_orders.keys(), default=None)
            best_bid_kelp = max(kelp_depth.buy_orders.keys(), default=None)
            if best_ask_kelp is not None and best_bid_kelp is not None:
                mid_price_kelp = (best_bid_kelp + best_ask_kelp) / 2
            elif best_ask_kelp is not None:
                mid_price_kelp = best_ask_kelp * 0.99
            elif best_bid_kelp is not None:
                mid_price_kelp = best_bid_kelp * 1.01
            else:
                mid_price_kelp = None

            # Compute mid-price for SQUID_INK
            best_ask_squid = min(squid_depth.sell_orders.keys(), default=None)
            best_bid_squid = max(squid_depth.buy_orders.keys(), default=None)
            if best_ask_squid is not None and best_bid_squid is not None:
                mid_price_squid = (best_bid_squid + best_ask_squid) / 2
            elif best_ask_squid is not None:
                mid_price_squid = best_ask_squid * 0.99
            elif best_bid_squid is not None:
                mid_price_squid = best_bid_squid * 1.01
            else:
                mid_price_squid = None

            if mid_price_kelp is not None and mid_price_squid is not None:
                spread = mid_price_kelp - mid_price_squid

                # Retrieve historical pair data; if not present, initialize with current spread
                pair_key = "KELP_SQUID_PAIR"
                pair_data = trader_data.get(pair_key, {"spread_mean": spread, "spread_var": 0.0})
                alpha_spread = 0.1
                new_spread_mean = alpha_spread * spread + (1 - alpha_spread) * pair_data["spread_mean"]
                new_spread_var = alpha_spread * ((spread - new_spread_mean) ** 2) + (1 - alpha_spread) * pair_data["spread_var"]
                spread_std = new_spread_var ** 0.5 if new_spread_var > 0 else 1.0  # avoid division by zero
                z_score = (spread - new_spread_mean) / spread_std

                print(f"[Time {state.timestamp}] Pair Trading: KELP-SQUID_INK Spread: {spread:.2f}, Mean: {new_spread_mean:.2f}, Std: {spread_std:.2f}, Z-Score: {z_score:.2f}")

                # Save updated pair data
                trader_data[pair_key] = {"spread_mean": new_spread_mean, "spread_var": new_spread_var}

                threshold = 1.0
                # Ensure result has keys for both products
                result.setdefault("KELP", [])
                result.setdefault("SQUID_INK", [])

                # If the Z-score is high: short KELP and go long on SQUID_INK
                if z_score > threshold:
                    # For KELP: Short
                    current_position_kelp = state.position.get("KELP", 0)
                    available_sell_kelp = max_position + current_position_kelp
                    if best_bid_kelp is not None and available_sell_kelp > 0:
                        order_size = min(available_sell_kelp, kelp_depth.buy_orders[best_bid_kelp])
                        if order_size > 0:
                            result["KELP"].append(Order("KELP", best_bid_kelp, -order_size))
                            print(f"--> Pair Trading: Shorting KELP: SELL order for {order_size} units at {best_bid_kelp}", end=";")
                    # For SQUID_INK: Long
                    current_position_squid = state.position.get("SQUID_INK", 0)
                    available_buy_squid = max_position - current_position_squid
                    if best_ask_squid is not None and available_buy_squid > 0:
                        order_size = min(available_buy_squid, -squid_depth.sell_orders[best_ask_squid])
                        if order_size > 0:
                            result["SQUID_INK"].append(Order("SQUID_INK", best_ask_squid, order_size))
                            print(f"--> Pair Trading: Going Long SQUID_INK: BUY order for {order_size} units at {best_ask_squid}", end=";")
                # If the Z-score is low: long KELP and short SQUID_INK
                elif z_score < -threshold:
                    # For KELP: Long
                    current_position_kelp = state.position.get("KELP", 0)
                    available_buy_kelp = max_position - current_position_kelp
                    if best_ask_kelp is not None and available_buy_kelp > 0:
                        order_size = min(available_buy_kelp, -kelp_depth.sell_orders[best_ask_kelp])
                        if order_size > 0:
                            result["KELP"].append(Order("KELP", best_ask_kelp, order_size))
                            print(f"--> Pair Trading: Going Long KELP: BUY order for {order_size} units at {best_ask_kelp}", end=";")
                    # For SQUID_INK: Short
                    current_position_squid = state.position.get("SQUID_INK", 0)
                    available_sell_squid = max_position + current_position_squid
                    if best_bid_squid is not None and available_sell_squid > 0:
                        order_size = min(available_sell_squid, squid_depth.buy_orders[best_bid_squid])
                        if order_size > 0:
                            result["SQUID_INK"].append(Order("SQUID_INK", best_bid_squid, -order_size))
                            print(f"--> Pair Trading: Shorting SQUID_INK: SELL order for {order_size} units at {best_bid_squid}", end=";")
                pair_trading_executed = True

        # ================================
        # Process Each Product Separately
        # (Skip KELP and SQUID_INK if pair trading was executed.)
        # ================================
        for product, order_depth in state.order_depths.items():
            if product in ["KELP", "SQUID_INK"] and pair_trading_executed:
                continue

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

            # RAINFOREST_RESIN Trading Logic (using a historical mean)
            if product == "RAINFOREST_RESIN":
                historical_mean = trader_data.get(product, mid_price)
                alpha = 0.1
                updated_mean = alpha * mid_price + (1 - alpha) * historical_mean

                print(f"[Time {state.timestamp}] Product: {product}; Best Bid: {best_bid}; Best Ask: {best_ask}; Mid Price: {mid_price:.2f}; Historical Mean: {historical_mean:.2f}; Updated Mean: {updated_mean:.2f}; Current Position: {current_position}")

                available_buy = max_position - current_position   # units that can be bought
                available_sell = max_position + current_position   # units that can be sold

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

            # For products not explicitly handled above, no orders are placed.
            result[product] = orders

        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data
