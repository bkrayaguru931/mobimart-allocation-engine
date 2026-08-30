# scripts/generate_inventory.py

import os
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data",
    "raw"
)

SALES_FILE = os.path.join(
    DATA_DIR,
    "sales.csv"
)

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "inventory.csv"
)

RANDOM_SEED = 42


# ============================================================
# MAIN
# ============================================================

def main():

    np.random.seed(RANDOM_SEED)

    print("=" * 70)
    print("MOBIMART INVENTORY GENERATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Load sales
    # --------------------------------------------------------

    print("\nLoading sales...")

    sales = pd.read_csv(
        SALES_FILE
    )

    sales["date"] = pd.to_datetime(
        sales["date"]
    )

    print(
        f"Sales rows: {len(sales):,}"
    )

    # --------------------------------------------------------
    # Latest sales date
    # --------------------------------------------------------

    latest_date = sales["date"].max()

    print(
        f"Latest sales date: "
        f"{latest_date.date()}"
    )

    # --------------------------------------------------------
    # Calculate recent daily demand
    #
    # Use the last 28 days because inventory
    # should reflect current demand rather than
    # the entire year's average.
    # --------------------------------------------------------

    history_start = (
        latest_date
        - pd.Timedelta(days=27)
    )

    recent_sales = sales[
        sales["date"] >= history_start
    ].copy()

    # --------------------------------------------------------
    # Aggregate store × model demand
    # --------------------------------------------------------

    demand = (
        recent_sales
        .groupby(
            [
                "store_id",
                "model_id"
            ],
            as_index=False
        )
        .agg(
            recent_units=(
                "units_sold",
                "sum"
            )
        )
    )

    demand["daily_demand"] = (
        demand["recent_units"]
        / 28.0
    )

    # --------------------------------------------------------
    # Generate store inventory
    #
    # Normal stores receive approximately
    # 7–14 days of stock.
    #
    # Some randomness prevents every store
    # from having perfectly identical coverage.
    # --------------------------------------------------------

    coverage_days = np.random.uniform(
        5,
        14,
        size=len(demand)
    )

    demand["coverage_days"] = (
        coverage_days
    )

    demand["current_stock"] = np.ceil(
        demand["daily_demand"]
        * demand["coverage_days"]
    ).astype(int)

    # --------------------------------------------------------
    # Add some stock variability.
    #
    # This creates realistic situations where:
    #
    # - some products are overstocked
    # - some are near stockout
    # - some are adequately stocked
    #
    # That gives the allocation engine
    # something meaningful to optimize.
    # --------------------------------------------------------

    stock_factor = np.random.uniform(
        0.65,
        1.20,
        size=len(demand)
    )

    demand["current_stock"] = np.floor(
        demand["current_stock"]
        * stock_factor
    ).astype(int)

    demand["current_stock"] = (
        demand["current_stock"]
        .clip(lower=0)
    )

    # --------------------------------------------------------
    # Warehouse stock
    #
    # Warehouse stock is intentionally larger
    # than store-level stock.
    #
    # Allocation will decide how much of this
    # should be sent to each store.
    # --------------------------------------------------------

    warehouse = (
        demand
        .groupby(
            "model_id",
            as_index=False
        )
        .agg(
            total_store_stock=(
                "current_stock",
                "sum"
            ),

            total_recent_units=(
                "recent_units",
                "sum"
            )
        )
    )

    warehouse["warehouse_stock"] = np.ceil(
        warehouse["total_recent_units"]
        * np.random.uniform(
            0.35,
            0.60,
            size=len(warehouse)
        )
    ).astype(int)

    # --------------------------------------------------------
    # Merge warehouse stock into every
    # store × model row.
    # --------------------------------------------------------

    inventory = demand[
        [
            "store_id",
            "model_id",
            "current_stock"
        ]
    ].merge(
        warehouse[
            [
                "model_id",
                "warehouse_stock"
            ]
        ],
        on="model_id",
        how="left"
    )

    # --------------------------------------------------------
    # Ensure integer values
    # --------------------------------------------------------

    inventory["current_stock"] = (
        inventory["current_stock"]
        .astype(int)
    )

    inventory["warehouse_stock"] = (
        inventory["warehouse_stock"]
        .astype(int)
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    inventory.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\nInventory generated successfully.")

    print(
        f"Store × product rows: "
        f"{len(inventory):,}"
    )

    print(
        f"Stores: "
        f"{inventory['store_id'].nunique()}"
    )

    print(
        f"Products: "
        f"{inventory['model_id'].nunique()}"
    )

    print(
        f"Total store inventory units: "
        f"{inventory['current_stock'].sum():,}"
    )

    print(
        f"Total warehouse inventory units: "
        f"{warehouse['warehouse_stock'].sum():,}"
    )

    print("\nSample:")

    print(
        inventory.head(10).to_string(
            index=False
        )
    )

    print("\nFile created:")

    print(
        OUTPUT_FILE
    )

    print("=" * 70)


if __name__ == "__main__":
    main()