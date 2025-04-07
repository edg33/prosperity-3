# mock_datamodel.py

from typing import Dict, List

class Order:
    def __init__(self, product: str, price: float, quantity: int):
        self.product = product
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        action = "BUY" if self.quantity > 0 else "SELL"
        return f"{action} {abs(self.quantity)} {self.product} @ {self.price}"

class OrderDepth:
    def __init__(self, buy_orders: Dict[float, int], sell_orders: Dict[float, int]):
        self.buy_orders = buy_orders
        self.sell_orders = sell_orders

class TradingState:
    def __init__(self, timestamp: int, order_depths: Dict[str, OrderDepth],
                 position: Dict[str, int], traderData: str = ""):
        self.timestamp = timestamp
        self.order_depths = order_depths
        self.position = position
        self.traderData = traderData
