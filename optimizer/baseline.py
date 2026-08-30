"""
Naive MobiMart allocation baseline.

Baseline rule:

    Allocate inventory in proportion to last month's sales.

No lifecycle intelligence.
No store-price affinity.
No stockout penalty.
No EOL intelligence.

This is deliberately simple so the MobiMart allocator
has a meaningful benchmark.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


INVENTORY_BUDGET = 40_000_000
LOOKBACK_DAYS = 30


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        if not np.isfinite(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def _validate_inputs(
    sales_df,
    inventory_df,
    products_df,
):
    required_sales = {
        "date",
        "store_id",
        "model_id",
        "units_sold",
    }

    required_inventory = {
        "store_id",
        "model_id",
        "current_stock",
    }

    required_products = {
        "model_id",
        "price",
    }

    for name, df, required in [
        ("sales_df", sales_df, required_sales),
        ("inventory_df", inventory_df, required_inventory),
        ("products_df", products_df, required_products),
    ]:

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"{name} missing columns: {missing}"
            )


def generate_naive_allocation(
    sales_df,
    inventory_df,
    products_df,
    allocation_date=None,
    inventory_budget=INVENTORY_BUDGET,
):
    """
    Generate naive allocation using the previous 30 days
    of store × model sales.

    The baseline uses the same warehouse availability and
    chain budget as the optimized allocator.
    """

    _validate_inputs(
        sales_df,
        inventory_df,
        products_df,
    )

    sales = sales_df.copy()
    inventory = inventory_df.copy()
    products = products_df.copy()

    sales["date"] = pd.to_datetime(
        sales["date"]
    )

    if allocation_date is None:
        allocation_date = (
            sales["date"].max()
            + pd.Timedelta(days=1)
        )

    allocation_date = pd.Timestamp(
        allocation_date
    )

    history_start = (
        allocation_date
        - pd.Timedelta(days=LOOKBACK_DAYS)
    )

    history = sales[
        (sales["date"] >= history_start)
        & (sales["date"] < allocation_date)
    ].copy()

    history["units_sold"] = pd.to_numeric(
        history["units_sold"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    last_month = (
        history
        .groupby(
            ["store_id", "model_id"],
            as_index=False,
        )
        .agg(
            last_month_units=(
                "units_sold",
                "sum",
            )
        )
    )

    # Ensure every store/model pair exists.
    pairs = (
        inventory[
            ["store_id", "model_id"]
        ]
        .drop_duplicates()
    )

    baseline = pairs.merge(
        last_month,
        on=["store_id", "model_id"],
        how="left",
    )

    baseline["last_month_units"] = (
        baseline["last_month_units"]
        .fillna(0)
    )

    baseline = baseline.merge(
        inventory[
            [
                "store_id",
                "model_id",
                "current_stock",
            ]
        ],
        on=["store_id", "model_id"],
        how="left",
    )

    product_cols = [
        "model_id",
        "price",
    ]

    if "category" in products.columns:
        product_cols.append("category")

    baseline = baseline.merge(
        products[product_cols].drop_duplicates(
            "model_id"
        ),
        on="model_id",
        how="left",
    )

    # Warehouse supply.
    if "warehouse_stock" in inventory.columns:

        warehouse = (
            inventory[
                ["model_id", "warehouse_stock"]
            ]
            .copy()
        )

        warehouse["warehouse_stock"] = (
            pd.to_numeric(
                warehouse["warehouse_stock"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        warehouse = (
            warehouse
            .groupby(
                "model_id",
                as_index=False,
            )["warehouse_stock"]
            .max()
        )

    else:

        warehouse = (
            baseline[
                ["model_id"]
            ]
            .drop_duplicates()
        )

        warehouse["warehouse_stock"] = np.inf

    baseline = baseline.merge(
        warehouse,
        on="model_id",
        how="left",
    )

    baseline["price"] = pd.to_numeric(
        baseline["price"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    baseline["current_stock"] = pd.to_numeric(
        baseline["current_stock"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    baseline["warehouse_stock"] = pd.to_numeric(
        baseline["warehouse_stock"],
        errors="coerce",
    ).fillna(0)

    # Naive recommendation:
    # replenish enough to cover 7 days based on
    # last-month sales.
    baseline["recommended_units"] = np.ceil(
        baseline["last_month_units"]
        / LOOKBACK_DAYS
        * 7
        - baseline["current_stock"]
    ).clip(lower=0)

    baseline["recommended_units"] = (
        baseline["recommended_units"]
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
        .astype(int)
    )

    baseline["priority_score"] = (
        baseline["last_month_units"]
        * baseline["price"]
    )

    baseline["allocated_units"] = 0

    # Allocate separately per model so warehouse stock
    # cannot be consumed twice.
    remaining_budget = float(
        max(inventory_budget, 0)
    )

    for model_id in (
        baseline["model_id"]
        .drop_duplicates()
        .tolist()
    ):

        mask = baseline["model_id"] == model_id

        rows = (
            baseline.loc[mask]
            .sort_values(
                "priority_score",
                ascending=False,
            )
            .index
        )

        if len(rows) == 0:
            continue

        warehouse_available = _safe_float(
            baseline.loc[
                rows[0],
                "warehouse_stock",
            ],
            default=0,
        )

        if np.isinf(warehouse_available):
            warehouse_available = 10**9

        for idx in rows:

            required = int(
                baseline.loc[
                    idx,
                    "recommended_units",
                ]
            )

            price = _safe_float(
                baseline.loc[
                    idx,
                    "price",
                ]
            )

            if required <= 0:
                continue

            if warehouse_available <= 0:
                break

            if remaining_budget <= 0:
                break

            affordable = int(
                remaining_budget // max(
                    price,
                    1,
                )
            )

            allocation = min(
                required,
                int(warehouse_available),
                affordable,
            )

            if allocation <= 0:
                continue

            baseline.loc[
                idx,
                "allocated_units",
            ] = allocation

            warehouse_available -= allocation

            remaining_budget -= (
                allocation * price
            )

    baseline["allocation_value"] = (
        baseline["allocated_units"]
        * baseline["price"]
    )

    baseline["protected_sales_value"] = (
        np.minimum(
            baseline["last_month_units"]
            / LOOKBACK_DAYS
            * 7,
            baseline["allocated_units"]
            + baseline["current_stock"],
        )
        * baseline["price"]
    )

    baseline["unfilled_demand_units"] = (
        baseline["recommended_units"]
        - baseline["allocated_units"]
    ).clip(lower=0)

    baseline["unfilled_demand_value"] = (
        baseline["unfilled_demand_units"]
        * baseline["price"]
    )

    baseline["allocation_status"] = np.select(
        [
            baseline["allocated_units"]
            >= baseline["recommended_units"],
            baseline["allocated_units"] > 0,
        ],
        [
            "FULLY_ALLOCATED",
            "PARTIALLY_ALLOCATED",
        ],
        default="NOT_ALLOCATED",
    )

    baseline["reason"] = (
        "NAIVE BASELINE: allocation proportional "
        "to last-30-day store/model sales."
    )

    baseline["allocation_date"] = (
        allocation_date
    )

    columns = [
        "allocation_date",
        "store_id",
        "model_id",
        "last_month_units",
        "current_stock",
        "recommended_units",
        "allocated_units",
        "price",
        "allocation_value",
        "protected_sales_value",
        "unfilled_demand_units",
        "unfilled_demand_value",
        "priority_score",
        "allocation_status",
        "reason",
    ]

    return (
        baseline[columns]
        .sort_values(
            "priority_score",
            ascending=False,
        )
        .reset_index(drop=True)
    )