import sys
import os
import pandas as pd

# Add the Algorithms directory to sys.path
sys.path.append(os.path.abspath('/Users/evangray/Desktop/Projects/prosperity/prosperity-3/Algorithms'))

# Now you can import normally
from Tutorial.kelp_ma_resin_mr import Trader
from mock_datamodel import Order, OrderDepth, TradingState

# Load your data (assumes 'activities' DataFrame is already defined)
activities = pd.read_csv("/Users/evangray/Desktop/Projects/prosperity/prosperity-3/Data Logs/Tutorial/de9d8071-3ac8-42ae-8de2-038a9acde3b3.csv")  # if loading from file

def create_order_depth(row, price_keys, volume_keys):
    """Helper to extract buy/sell orders from a row."""
    orders = {}
    for price_key, volume_key in zip(price_keys, volume_keys):
        price = row.get(price_key)
        volume = row.get(volume_key)
        if pd.notna(price) and pd.notna(volume):
            orders[float(price)] = int(volume)
    return orders

def backtest(df):
    trader = Trader()
    trader_data = ""
    position = {"RAINFOREST_RESIN": 0, "KELP": 0}
    cash = 0.0
    trade_log = []

    for i, row in df.iterrows():
        timestamp = int(row["timestamp"])
        order_depths = {}

        for product in ["RAINFOREST_RESIN", "KELP"]:
            product_rows = df[(df["timestamp"] == timestamp) & (df["product"] == product)]
            if product_rows.empty:
                continue
            r = product_rows.iloc[0]

            buy_orders = create_order_depth(r, 
                                            ["bid_price_1", "bid_price_2", "bid_price_3"], 
                                            ["bid_volume_1", "bid_volume_2", "bid_volume_3"])
            sell_orders = create_order_depth(r, 
                                             ["ask_price_1", "ask_price_2", "ask_price_3"], 
                                             ["ask_volume_1", "ask_volume_2", "ask_volume_3"])

            order_depths[product] = OrderDepth(buy_orders, sell_orders)

        state = TradingState(timestamp=timestamp,
                             order_depths=order_depths,
                             position=position.copy(),
                             traderData=trader_data)

        result, conversions, trader_data = trader.run(state)

        for product, orders in result.items():
            mid_price = row['mid_price']
            for order in orders:
                fill_price = order.price
                quantity = order.quantity
                cash -= fill_price * quantity  # buy = negative cash, sell = positive
                position[product] += quantity
                trade_log.append((timestamp, product, "BUY" if quantity > 0 else "SELL", abs(quantity), fill_price))

    # Liquidate all positions at final mid_price
    for product in ["RAINFOREST_RESIN", "KELP"]:
        final_mid = df[df["product"] == product]["mid_price"].iloc[-1]
        final_qty = position[product]
        cash += final_qty * final_mid
        trade_log.append(("FINAL", product, "LIQUIDATE", final_qty, final_mid))

    return cash, trade_log

# Example usage (assuming you already have activities DataFrame)
final_cash, trades = backtest(activities)
print("Final Cash:", final_cash)
# for trade in trades:
#     print(trade)
