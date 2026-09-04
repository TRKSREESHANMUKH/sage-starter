"""
Stage 3 — Baseline validation plots.

Reads the simulated data back out of Postgres and draws charts, so we
can visually confirm the baseline looks like a real, slightly noisy
business — not just check that the numbers reconcile on paper.

This script only reads from the database. It never writes anything.
"""

import pandas as pd
import matplotlib.pyplot as plt
from app.database import engine

# Where the chart images will be saved.
OUTPUT_FOLDER = "simulator/charts"

import os
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================
# LOAD DATA
# ============================================================

items = pd.read_sql(
    "SELECT id, product_id, opening_balance_qty, opening_balance_date "
    "FROM inventory_items",
    engine,
)

products = pd.read_sql("SELECT id, name, category FROM products", engine)

movements = pd.read_sql(
    "SELECT item_id, date, movement_type, quantity FROM stock_movements",
    engine,
)

sales_lines = pd.read_sql(
    "SELECT so.order_date, sol.product_id, sol.quantity_ordered "
    "FROM sales_order_lines sol "
    "JOIN sales_orders so ON so.id = sol.sales_order_id",
    engine,
)

production = pd.read_sql(
    "SELECT planned_start, product_id, actual_qty FROM production_orders",
    engine,
)


# ============================================================
# BUILD A DAILY STOCK LEVEL PER ITEM
#
# For each item: start at its opening balance, then walk forward day
# by day, adding/subtracting whatever moved that day. This is the
# same cumulative-sum idea we designed the Stock Movements table
# around from the very beginning.
# ============================================================

def daily_stock_series(item_id, opening_qty, opening_date, movements_df):
    day_movements = movements_df[movements_df["item_id"] == item_id].copy()
    day_movements["signed_qty"] = day_movements.apply(
        lambda r: r["quantity"] if r["movement_type"] == "IN" else -r["quantity"],
        axis=1,
    )
    daily_net = day_movements.groupby("date")["signed_qty"].sum()

    full_range = pd.date_range(
        start=opening_date, end=daily_net.index.max() if len(daily_net) else opening_date
    )
    daily_net = daily_net.reindex(full_range, fill_value=0)

    running_stock = opening_qty + daily_net.cumsum()
    return running_stock


stock_series = {}
for _, item in items.iterrows():
    product_name = products.loc[products["id"] == item["product_id"], "name"].values[0]
    stock_series[product_name] = daily_stock_series(
        item["id"], item["opening_balance_qty"], item["opening_balance_date"], movements
    )


# ============================================================
# CHART 1 -- RAW MATERIAL INVENTORY OVER TIME
# ============================================================

raw_material_ids = products[products["category"] == "Raw Material"]["id"].tolist()
raw_material_names = products[products["category"] == "Raw Material"]["name"].tolist()

plt.figure(figsize=(12, 5))
for name in raw_material_names:
    if name in stock_series:
        plt.plot(stock_series[name].index, stock_series[name].values, label=name)
plt.title("Raw Material Inventory Over Time")
plt.xlabel("Date")
plt.ylabel("Units in stock")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_FOLDER}/1_raw_material_inventory.png")
plt.close()


# ============================================================
# CHART 2 -- FINISHED GOOD INVENTORY OVER TIME
# ============================================================

finished_good_names = products[products["category"] == "Finished Good"]["name"].tolist()

plt.figure(figsize=(12, 5))
for name in finished_good_names:
    if name in stock_series:
        plt.plot(stock_series[name].index, stock_series[name].values, label=name)
plt.title("Finished Goods Inventory Over Time")
plt.xlabel("Date")
plt.ylabel("Units in stock")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_FOLDER}/2_finished_goods_inventory.png")
plt.close()


# ============================================================
# CHART 3 -- SALES DEMAND OVER TIME (weekly, so it's readable)
# ============================================================

sales_lines["order_date"] = pd.to_datetime(sales_lines["order_date"])
sales_lines = sales_lines.merge(products, left_on="product_id", right_on="id")
weekly_demand = (
    sales_lines.groupby([pd.Grouper(key="order_date", freq="W"), "name"])["quantity_ordered"]
    .sum()
    .unstack(fill_value=0)
)

plt.figure(figsize=(12, 5))
for column in weekly_demand.columns:
    plt.plot(weekly_demand.index, weekly_demand[column], label=column)
plt.title("Weekly Sales Demand Over Time")
plt.xlabel("Week")
plt.ylabel("Units ordered")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_FOLDER}/3_sales_demand.png")
plt.close()


# ============================================================
# CHART 4 -- PRODUCTION OUTPUT OVER TIME
# ============================================================

production["planned_start"] = pd.to_datetime(production["planned_start"])
production = production.merge(products, left_on="product_id", right_on="id")

plt.figure(figsize=(12, 5))
for name, group in production.groupby("name"):
    plt.plot(group["planned_start"], group["actual_qty"], marker="o", linestyle="", label=name, alpha=0.6)
plt.title("Production Output Over Time (each dot = one production run)")
plt.xlabel("Date")
plt.ylabel("Units produced")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_FOLDER}/4_production_output.png")
plt.close()

print(f"Done. 4 charts saved to {OUTPUT_FOLDER}/")