import os
import sys

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORTS
# ============================================================

from allocation.forecast import (
    generate_weekly_forecast,
)

from allocation.allocator import (
    allocate_inventory,
    allocation_summary,
)

from allocation.eol import (
    generate_eol_recommendations,
    eol_summary,
)


# ============================================================
# PATHS
# ============================================================

DATA_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
)

OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "outputs",
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True,
)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("MOBIMART FORECAST + ALLOCATION PIPELINE")
print("=" * 70)

print("\nLoading data...")


sales_df = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "sales.csv",
    )
)

stores_df = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "stores.csv",
    )
)

products_df = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "products.csv",
    )
)

events_df = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "events.csv",
    )
)

inventory_df = pd.read_csv(
    os.path.join(
        DATA_DIR,
        "inventory.csv",
    )
)


# ============================================================
# DATE NORMALIZATION
# ============================================================

sales_df["date"] = pd.to_datetime(
    sales_df["date"]
)

events_df["date"] = pd.to_datetime(
    events_df["date"]
)

products_df["launch_date"] = pd.to_datetime(
    products_df["launch_date"],
    errors="coerce",
)

if "successor_launch_date" in products_df.columns:
    products_df["successor_launch_date"] = pd.to_datetime(
        products_df["successor_launch_date"],
        errors="coerce",
    )


# ============================================================
# DATASET INFORMATION
# ============================================================

print(
    f"Stores:    "
    f"{stores_df['store_id'].nunique():,}"
)

print(
    f"Products:  "
    f"{products_df['model_id'].nunique():,}"
)

print(
    f"Sales rows:"
    f"{len(sales_df):,}"
)

print(
    f"Inventory rows:"
    f"{len(inventory_df):,}"
)


# ============================================================
# 1. GENERATE FORECAST
# ============================================================

print("\n" + "-" * 70)
print("1. GENERATING 7-DAY FORECAST")
print("-" * 70)


forecast_df = generate_weekly_forecast(
    sales_df=sales_df,
    stores_df=stores_df,
    products_df=products_df,
    events_df=events_df,
)


print(
    f"Forecast rows: "
    f"{len(forecast_df):,}"
)

print(
    f"Total forecast units: "
    f"{forecast_df['forecast_units'].sum():,.2f}"
)

print(
    f"Average forecast per store/model: "
    f"{forecast_df['forecast_units'].mean():.2f}"
)


# ============================================================
# SAVE FORECAST
# ============================================================

forecast_path = os.path.join(
    OUTPUT_DIR,
    "weekly_forecast.csv",
)

forecast_df.to_csv(
    forecast_path,
    index=False,
)

print(
    f"\nForecast saved to: "
    f"{forecast_path}"
)


# ============================================================
# 2. RUN INVENTORY ALLOCATOR
# ============================================================

print("\n" + "-" * 70)
print("2. RUNNING INVENTORY ALLOCATOR")
print("-" * 70)


allocation_df = allocate_inventory(
    forecast_df=forecast_df,
    inventory_df=inventory_df,
    products_df=products_df,
    stores_df=stores_df,
)


# ============================================================
# ADD PRODUCT PRICE
# ============================================================
#
# The allocator does not currently expose price in every
# allocation output row, but the EOL engine requires it.
#
# products_df is the authoritative source for model price.
#
# Merge price by model_id before saving the allocation output.
# ============================================================

if "price" not in allocation_df.columns:

    allocation_df = allocation_df.merge(
        products_df[
            [
                "model_id",
                "price",
            ]
        ],
        on="model_id",
        how="left",
        validate="many_to_one",
    )


# ============================================================
# VALIDATE PRICE JOIN
# ============================================================

missing_price = allocation_df["price"].isna()

if missing_price.any():

    missing_models = (
        allocation_df.loc[
            missing_price,
            "model_id",
        ]
        .drop_duplicates()
        .tolist()
    )

    raise ValueError(
        "Price lookup failed for model_id(s): "
        f"{missing_models}"
    )


# ============================================================
# SAVE ALLOCATION
# ============================================================

allocation_path = os.path.join(
    OUTPUT_DIR,
    "monday_allocation.csv",
)

allocation_df.to_csv(
    allocation_path,
    index=False,
)

print(
    f"\nAllocation saved to: "
    f"{allocation_path}"
)


# ============================================================
# 3. EOL RISK ENGINE
# ============================================================

print("\n" + "-" * 70)
print("3. RUNNING EOL RISK ENGINE")
print("-" * 70)


eol_df = generate_eol_recommendations(
    allocation_df
)


# ============================================================
# SAVE EOL RECOMMENDATIONS
# ============================================================

eol_path = os.path.join(
    OUTPUT_DIR,
    "eol_recommendations.csv",
)

eol_df.to_csv(
    eol_path,
    index=False,
)


# ============================================================
# EOL SUMMARY
# ============================================================

eol_stats = eol_summary(
    eol_df
)


print(
    f"EOL risk lines:       "
    f"{eol_stats['at_risk_lines']:,}"
)

print(
    f"EOL excess inventory: "
    f"₹{eol_stats['excess_inventory_value']:,.0f}"
)

print(
    f"Markdown exposure:    "
    f"₹{eol_stats['markdown_loss']:,.0f}"
)

print(
    f"Recommended EOL cost:"
    f" ₹{eol_stats['recommended_cost']:,.0f}"
)

print(
    f"EOL recommendations saved to: "
    f"{eol_path}"
)


# ============================================================
# 4. ALLOCATION SUMMARY
# ============================================================

summary = allocation_summary(
    allocation_df
)


print("\n" + "=" * 70)
print("ALLOCATION SUMMARY")
print("=" * 70)


print(
    f"Allocated units:          "
    f"{summary['allocated_units']:,}"
)

print(
    f"Allocation value:         "
    f"₹{summary['allocation_value']:,.0f}"
)

print(
    f"Protected sales value:    "
    f"₹{summary['protected_sales_value']:,.0f}"
)

print(
    f"Unfilled demand value:    "
    f"₹{summary['unfilled_demand_value']:,.0f}"
)

print(
    f"Budget used:              "
    f"{summary['budget_used_pct']:.2f}%"
)

print(
    f"Priority lines:           "
    f"{summary['high_priority_lines']:,}"
)

print(
    f"Total allocation lines:   "
    f"{summary['total_lines']:,}"
)


# ============================================================
# 5. TOP 20 ALLOCATION RECOMMENDATIONS
# ============================================================

print("\n" + "-" * 70)
print("TOP 20 ALLOCATION RECOMMENDATIONS")
print("-" * 70)


display_columns = [
    "store_id",
    "model_id",
    "forecast_units",
    "current_stock",
    "stock_gap",
    "allocated_units",
    "allocation_value",
    "priority_score",
    "price_band",
    "store_price_band_fit",
    "eol_status",
    "reason",
]


available_display_columns = [
    column
    for column in display_columns
    if column in allocation_df.columns
]


print(
    allocation_df[
        available_display_columns
    ]
    .head(20)
    .to_string(
        index=False
    )
)


# ============================================================
# 6. ALLOCATION BY STORE
# ============================================================

print("\n" + "-" * 70)
print("ALLOCATION BY STORE")
print("-" * 70)


store_summary = (
    allocation_df
    .groupby(
        "store_id",
        as_index=False,
    )
    .agg(
        allocated_units=(
            "allocated_units",
            "sum",
        ),
        allocation_value=(
            "allocation_value",
            "sum",
        ),
        forecast_units=(
            "forecast_units",
            "sum",
        ),
        unfilled_demand_value=(
            "unfilled_demand_value",
            "sum",
        ),
    )
    .sort_values(
        "allocation_value",
        ascending=False,
    )
)


print(
    store_summary.to_string(
        index=False
    )
)


# ============================================================
# 7. EOL SUMMARY
# ============================================================

print("\n" + "-" * 70)
print("EOL RISK SUMMARY")
print("-" * 70)


eol_group_columns = [
    column
    for column in [
        "eol_status",
        "eol_action",
        "risk_level",
    ]
    if column in eol_df.columns
]


if eol_group_columns:

    print(
        eol_df[
            eol_group_columns
        ]
        .value_counts()
        .to_string()
    )

else:

    print(
        "EOL recommendation output generated."
    )


# ============================================================
# PIPELINE COMPLETE
# ============================================================

print("\n" + "=" * 70)
print("PIPELINE COMPLETE")
print("=" * 70)


print("\nFiles created:")

print(
    f"  {forecast_path}"
)

print(
    f"  {allocation_path}"
)

print(
    f"  {eol_path}"
)

print("\n")