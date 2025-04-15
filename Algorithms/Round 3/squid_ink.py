import json
import numpy as np
from datamodel import TradingState, Order
from typing import List, Dict

def erf(x: float) -> float:
    """Numerical approximation to the error function."""
    # Constants
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * np.exp(-x * x))

    return sign * y


def is_in_stable_pocket(prices: List[float], window: int, std_threshold: float) -> bool:
    if len(prices) < window:
        return False
    recent_prices = prices[-window:]
    rolling_std = np.std(recent_prices)
    rolling_mean = np.mean(recent_prices)
    current_price = prices[-1]
    return rolling_std > std_threshold and abs(current_price - rolling_mean) < rolling_std


def normal_cdf(x: float, mean: float, std: float) -> float:
    """Approximate the CDF of a normal distribution using numpy (via erf)."""
    z = (x - mean) / (std * np.sqrt(2))
    return 0.5 * (1 + erf(z))


def pocket_transition_risk(t: int, mean_len: float, std_len: float, horizon: int = 10) -> float:
    """Probability that the pocket ends in the next `horizon` timesteps."""
    p_now = normal_cdf(t, mean_len, std_len)
    p_future = normal_cdf(t + horizon, mean_len, std_len)
    return p_future - p_now


class Trader:
    def run(self, state: TradingState):
        result = {}

        # Load previous state from traderData
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}

        max_position = 50
        window = 30
        std_threshold = 1.0
        mean_len = 100  # avg pocket duration from offline analysis
        std_len = 30

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            current_position = state.position.get(product, 0)

            best_ask = min(order_depth.sell_orders.keys(), default=None)
            best_bid = max(order_depth.buy_orders.keys(), default=None)

            if best_ask is None and best_bid is None:
                continue

            # Mid price calculation
            if best_ask is not None and best_bid is not None:
                mid_price = (best_bid + best_ask) / 2
            elif best_ask is not None:
                mid_price = best_ask * 0.99
            else:
                mid_price = best_bid * 1.01

            # Initialize product history
            product_data = trader_data.get(product, {
                "price_history": [],
                "time_in_pocket": 0,
                "in_pocket": False
            })

            price_history = product_data["price_history"]
            time_in_pocket = product_data["time_in_pocket"]
            in_pocket = product_data["in_pocket"]

            price_history.append(mid_price)
            if len(price_history) > 200:
                price_history.pop(0)

            current_in_pocket = is_in_stable_pocket(price_history, window=window, std_threshold=std_threshold)

            mean_price = np.mean(price_history[-window:]) if len(price_history) >= window else mid_price
            std_price = np.std(price_history[-window:]) if len(price_history) >= window else 1.0

            if current_in_pocket:
                time_in_pocket += 1
                transition_risk = pocket_transition_risk(time_in_pocket, mean_len, std_len)
                scale_factor = max(0, 1 - transition_risk)
                order_size = int(scale_factor * 10)

                if mid_price < mean_price - std_price and current_position < max_position:
                    buy_qty = min(order_size, max_position - current_position)
                    orders.append(Order(product, best_ask, buy_qty))

                elif mid_price > mean_price + std_price and current_position > -max_position:
                    sell_qty = min(order_size, current_position + max_position)
                    orders.append(Order(product, best_bid, -sell_qty))
            else:
                time_in_pocket = 0
                if current_position > 0:
                    orders.append(Order(product, best_bid, -current_position))
                elif current_position < 0:
                    orders.append(Order(product, best_ask, -current_position))

            product_data.update({
                "price_history": price_history,
                "time_in_pocket": time_in_pocket,
                "in_pocket": current_in_pocket
            })

            trader_data[product] = product_data
            result[product] = orders

        updated_trader_data = json.dumps(trader_data)
        conversions = 1
        return result, conversions, updated_trader_data
