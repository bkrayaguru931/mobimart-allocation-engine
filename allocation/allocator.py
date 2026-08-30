# allocation/allocator.py

import numpy as np
import pandas as pd

from allocation.scoring import calculate_priority_score, get_price_band
from allocation.store_profile import get_store_price_band_fit


# ============================================================
# CONFIGURATION
# ============================================================

INVENTORY_BUDGET = 40_000_000       # ₹4 crore

FORECAST_DAYS = 7

MIN_STOCK_COVER_DAYS = 2
TARGET_STOCK_COVER_DAYS = 10
MAX_STOCK_COVER_DAYS = 21

# ============================================================
# HELPERS
# ============================================================

def get_price_band(price):
    """
    Convert product price into a business price band.
    """

    try:
        price = float(price)
    except (TypeError, ValueError):
        return "Budget"

    if price < 10_000:
        return "Keypad"

    if price < 15_000:
        return "Budget"

    if price < 25_000:
        return "Upper-mid"

    if price < 45_000:
        return "Mid-range"

    if price < 75_000:
        return "Flagship"

    return "Premium"


def get_eol_status(
    forecast_date,
    successor_launch_date
):
    """
    Determine product lifecycle proximity to successor.

    Returns
    -------
    normal
    approaching
    near
    post_successor
    """

    if pd.isna(successor_launch_date):
        return "normal"

    days = (
        pd.Timestamp(successor_launch_date)
        - pd.Timestamp(forecast_date)
    ).days

    if days > 60:
        return "normal"

    if 30 < days <= 60:
        return "approaching"

    if 0 <= days <= 30:
        return "near"

    return "post_successor"


def _safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    try:
        value = float(value)

        if not np.isfinite(value):
            return default

        return value

    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    """
    Safely convert a value to integer.
    """

    try:
        value = int(float(value))
        return value

    except (TypeError, ValueError):
        return default


# ============================================================
# MAIN ALLOCATION ENGINE
# ============================================================

def allocate_inventory(
    forecast_df,
    inventory_df,
    products_df,
    stores_df=None,
    forecast_date=None,
    inventory_budget=INVENTORY_BUDGET
):
    """
    Allocate warehouse inventory to stores.

    Parameters
    ----------
    forecast_df:
        Output from allocation/forecast.py.

        Required columns:

            store_id
            model_id
            forecast_units

        Optional:

            avg_event_multiplier
            avg_lifecycle_factor
            lifecycle_factor

    inventory_df:
        Current inventory.

        Required columns:

            store_id
            model_id
            current_stock

        Optional:

            warehouse_stock

    products_df:
        Product master.

        Required:

            model_id
            price

        Optional:

            category
            successor_launch_date

    forecast_date:
        Monday allocation date.

    inventory_budget:
        Maximum inventory value.

    Returns
    -------
    DataFrame
        Store × model allocation recommendations.
    """

    # ========================================================
    # COPY INPUTS
    # ========================================================

    forecast = forecast_df.copy()
    inventory = inventory_df.copy()
    products = products_df.copy()

    stores = None if stores_df is None else stores_df.copy()

    # ========================================================
    # VALIDATION
    # ========================================================

    required_forecast = {
        "store_id",
        "model_id",
        "forecast_units",
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

    missing = (
        required_forecast
        - set(forecast.columns)
    )

    if missing:
        raise ValueError(
            f"forecast_df missing columns: {missing}"
        )

    missing = (
        required_inventory
        - set(inventory.columns)
    )

    if missing:
        raise ValueError(
            f"inventory_df missing columns: {missing}"
        )

    missing = (
        required_products
        - set(products.columns)
    )

    if missing:
        raise ValueError(
            f"products_df missing columns: {missing}"
        )

    # Store profiles are optional for backward compatibility.
    # When supplied, city-level price-band affinity influences
    # allocation priority.
    if stores is not None:

        if "store_id" not in stores.columns:
            raise ValueError("stores_df missing columns: {'store_id'}")

        if "city" not in stores.columns:
            raise ValueError("stores_df missing columns: {'city'}")

        stores_info = (
            stores[["store_id", "city"]]
            .drop_duplicates("store_id")
            .copy()
        )

    else:

        stores_info = None

    # ========================================================
    # NORMALIZE FORECAST
    # ========================================================

    forecast["forecast_units"] = (
        pd.to_numeric(
            forecast["forecast_units"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    # --------------------------------------------------------
    # Forecast date
    # --------------------------------------------------------

    if forecast_date is None:

        if "forecast_date" in forecast.columns:

            forecast_date = pd.to_datetime(
                forecast["forecast_date"],
                errors="coerce"
            ).min()

        else:

            forecast_date = pd.Timestamp.today()

    forecast_date = pd.Timestamp(
        forecast_date
    )

    # ========================================================
    # NORMALIZE INVENTORY
    # ========================================================

    inventory["current_stock"] = (
        pd.to_numeric(
            inventory["current_stock"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    # --------------------------------------------------------
    # Store-level current inventory
    # --------------------------------------------------------

    inventory_store = (
        inventory[
            [
                "store_id",
                "model_id",
                "current_stock"
            ]
        ]
        .groupby(
            [
                "store_id",
                "model_id"
            ],
            as_index=False
        )
        .sum()
    )

    # ========================================================
    # WAREHOUSE INVENTORY
    # ========================================================

    if "warehouse_stock" in inventory.columns:

        warehouse = (
            inventory[
                [
                    "model_id",
                    "warehouse_stock"
                ]
            ]
            .copy()
        )

        warehouse["warehouse_stock"] = (
            pd.to_numeric(
                warehouse["warehouse_stock"],
                errors="coerce"
            )
            .fillna(0)
            .clip(lower=0)
        )

        # Use MAX because warehouse stock may be repeated
        # for every store/model row in the source data.
        warehouse = (
            warehouse
            .groupby(
                "model_id",
                as_index=False
            )["warehouse_stock"]
            .max()
        )

    else:

        # If warehouse stock is not explicitly provided,
        # assume supply is unconstrained and let the budget
        # determine allocation.
        warehouse = (
            forecast[
                ["model_id"]
            ]
            .drop_duplicates()
            .copy()
        )

        warehouse["warehouse_stock"] = np.inf

    # ========================================================
    # PRODUCT INFORMATION
    # ========================================================

    product_columns = [
        "model_id",
        "price"
    ]

    if "category" in products.columns:
        product_columns.append(
            "category"
        )

    if "successor_launch_date" in products.columns:
        product_columns.append(
            "successor_launch_date"
        )

    products_info = (
        products[
            product_columns
        ]
        .drop_duplicates(
            "model_id"
        )
        .copy()
    )

    products_info["price"] = (
        pd.to_numeric(
            products_info["price"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    # ========================================================
    # MERGE FORECAST + INVENTORY + PRODUCT
    # ========================================================

    allocation = forecast.merge(
        inventory_store,
        on=[
            "store_id",
            "model_id"
        ],
        how="left"
    )

    allocation = allocation.merge(
        products_info,
        on="model_id",
        how="left"
    )

    allocation = allocation.merge(
        warehouse,
        on="model_id",
        how="left"
    )

    # --------------------------------------------------------
    # Store profile
    # --------------------------------------------------------

    if stores_info is not None:

        allocation = allocation.merge(
            stores_info,
            on="store_id",
            how="left"
        )

    else:

        allocation["city"] = "default"

    # ========================================================
    # DEFAULT VALUES
    # ========================================================

    allocation["current_stock"] = (
        pd.to_numeric(
            allocation["current_stock"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    allocation["price"] = (
        pd.to_numeric(
            allocation["price"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    allocation["warehouse_stock"] = (
        pd.to_numeric(
            allocation["warehouse_stock"],
            errors="coerce"
        )
    )

    allocation["warehouse_stock"] = (
        allocation["warehouse_stock"]
        .fillna(0)
        .clip(lower=0)
    )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    if "lifecycle_factor" not in allocation.columns:

        if "avg_lifecycle_factor" in allocation.columns:

            allocation[
                "lifecycle_factor"
            ] = allocation[
                "avg_lifecycle_factor"
            ]

        else:

            allocation[
                "lifecycle_factor"
            ] = 1.0

    allocation[
        "lifecycle_factor"
    ] = (
        pd.to_numeric(
            allocation["lifecycle_factor"],
            errors="coerce"
        )
        .fillna(1.0)
        .clip(
            lower=0.10,
            upper=1.0
        )
    )

    # --------------------------------------------------------
    # Event multiplier
    # --------------------------------------------------------

    if "avg_event_multiplier" not in allocation.columns:

        allocation[
            "avg_event_multiplier"
        ] = 1.0

    allocation[
        "avg_event_multiplier"
    ] = (
        pd.to_numeric(
            allocation[
                "avg_event_multiplier"
            ],
            errors="coerce"
        )
        .fillna(1.0)
    )

    # ========================================================
    # CATEGORY
    # ========================================================

    if "category" not in allocation.columns:

        allocation["category"] = (
            allocation["price"]
            .apply(get_price_band)
        )

    allocation["category"] = (
        allocation["category"]
        .fillna("")
        .astype(str)
    )

    # ========================================================
    # TARGET STOCK
    # ========================================================

    allocation["target_stock"] = (
        allocation["forecast_units"]
        * TARGET_STOCK_COVER_DAYS
        / FORECAST_DAYS
    )

    # Hard maximum stock cover.
    max_target = (
        allocation["forecast_units"]
        * MAX_STOCK_COVER_DAYS
        / FORECAST_DAYS
    )

    allocation["target_stock"] = (
        allocation["target_stock"]
        .clip(
            lower=0
        )
    )

    allocation["target_stock"] = np.minimum(
        allocation["target_stock"],
        max_target
    )

    # ========================================================
    # STOCK GAP
    # ========================================================

    allocation["stock_gap"] = (
        allocation["target_stock"]
        - allocation["current_stock"]
    ).clip(
        lower=0
    )

    # ========================================================
    # EOL STATUS
    # ========================================================

    if "successor_launch_date" in allocation.columns:

        allocation["successor_launch_date"] = (
            pd.to_datetime(
                allocation[
                    "successor_launch_date"
                ],
                errors="coerce"
            )
        )

        allocation["eol_status"] = (
            allocation[
                "successor_launch_date"
            ]
            .apply(
                lambda x:
                get_eol_status(
                    forecast_date,
                    x
                )
            )
        )

    else:

        allocation["eol_status"] = "normal"

    # ========================================================
    # PRIORITY SCORE
    # ========================================================

    allocation["price_band"] = allocation["price"].apply(get_price_band)

    allocation["store_price_band_fit"] = allocation.apply(
        lambda row: get_store_price_band_fit(
            row["city"],
            row["price_band"]
        ),
        axis=1
    )

    score_results = allocation.apply(
        lambda row:
        calculate_priority_score(
            forecast_units=row["forecast_units"],
            current_stock=row["current_stock"],
            price=row["price"],
            category=row["category"],
            lifecycle_factor=row["lifecycle_factor"],
            eol_status=row["eol_status"],
            store_price_band_fit=row["store_price_band_fit"],
            price_band=row["price_band"]
        ),
        axis=1
    )

    allocation[
        "priority_score"
    ] = score_results.apply(
        lambda x: x[0]
    )

    allocation[
        "stock_gap"
    ] = score_results.apply(
        lambda x: x[1]
    )

    allocation[
        "lost_sale_value"
    ] = score_results.apply(
        lambda x: x[2]
    )

    allocation[
        "minimum_gap"
    ] = score_results.apply(
        lambda x: x[3]
    )

    allocation[
        "price_band"
    ] = score_results.apply(
        lambda x: x[4]
    )

    # ========================================================
    # INITIAL RECOMMENDATION
    # ========================================================

    allocation[
        "recommended_units"
    ] = np.floor(
        allocation["stock_gap"]
    ).astype(int)

    allocation[
        "recommended_units"
    ] = (
        allocation["recommended_units"]
        .clip(lower=0)
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do not allocate fresh stock to products whose successor
    # has already launched.
    # --------------------------------------------------------

    allocation.loc[
        allocation["eol_status"]
        == "post_successor",
        "recommended_units"
    ] = 0

    # ========================================================
    # ALLOCATION INITIALIZATION
    # ========================================================

    allocation[
        "allocated_units"
    ] = 0

    # ========================================================
    # SORT BY PRIORITY
    # ========================================================

    allocation = (
        allocation
        .sort_values(
            [
                "priority_score",
                "lost_sale_value",
                "forecast_units"
            ],
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )

    # ========================================================
    # WAREHOUSE STATE
    # ========================================================

    warehouse_remaining = (
        allocation[
            [
                "model_id",
                "warehouse_stock"
            ]
        ]
        .drop_duplicates(
            "model_id"
        )
        .set_index(
            "model_id"
        )[
            "warehouse_stock"
        ]
        .to_dict()
    )

    # ========================================================
    # BUDGET STATE
    # ========================================================

    budget_remaining = max(
        _safe_float(
            inventory_budget
        ),
        0
    )

    # ========================================================
    # ALLOCATE
    # ========================================================

    for idx, row in allocation.iterrows():

        requested_units = _safe_int(
            row["recommended_units"]
        )

        if requested_units <= 0:
            continue

        model_id = row[
            "model_id"
        ]

        price = _safe_float(
            row["price"]
        )

        # ----------------------------------------------------
        # EOL protection
        # ----------------------------------------------------

        if row["eol_status"] == "post_successor":
            continue

        # ----------------------------------------------------
        # Warehouse availability
        # ----------------------------------------------------

        warehouse_available = (
            warehouse_remaining.get(
                model_id,
                0
            )
        )

        if np.isfinite(
            warehouse_available
        ):

            warehouse_available = max(
                int(
                    warehouse_available
                ),
                0
            )

            units = min(
                requested_units,
                warehouse_available
            )

        else:

            units = requested_units

        # ----------------------------------------------------
        # Budget availability
        # ----------------------------------------------------

        if price > 0:

            budget_units = int(
                budget_remaining
                / price
            )

            units = min(
                units,
                budget_units
            )

        else:

            # Product with zero price has no monetary
            # allocation cost.
            units = units

        if units <= 0:
            continue

        # ----------------------------------------------------
        # Commit allocation
        # ----------------------------------------------------

        allocation.at[
            idx,
            "allocated_units"
        ] = int(units)

        # ----------------------------------------------------
        # Reduce warehouse stock
        # ----------------------------------------------------

        if np.isfinite(
            warehouse_available
        ):

            warehouse_remaining[
                model_id
            ] = (
                warehouse_available
                - units
            )

        # ----------------------------------------------------
        # Reduce budget
        # ----------------------------------------------------

        budget_remaining -= (
            units
            * price
        )

        budget_remaining = max(
            budget_remaining,
            0
        )

    # ========================================================
    # POST-ALLOCATION METRICS
    # ========================================================

    allocation[
        "allocation_value"
    ] = (
        allocation[
            "allocated_units"
        ]
        * allocation[
            "price"
        ]
    )

    # --------------------------------------------------------
    # Protected sales
    # --------------------------------------------------------

    allocation[
        "protected_sales_value"
    ] = (
        np.minimum(
            allocation[
                "allocated_units"
            ],
            allocation[
                "forecast_units"
            ]
        )
        * allocation[
            "price"
        ]
    )

    # --------------------------------------------------------
    # Remaining demand
    # --------------------------------------------------------

    allocation[
        "unfilled_demand_units"
    ] = (
        allocation[
            "forecast_units"
        ]
        - allocation[
            "current_stock"
        ]
        - allocation[
            "allocated_units"
        ]
    ).clip(
        lower=0
    )

    allocation[
        "unfilled_demand_value"
    ] = (
        allocation[
            "unfilled_demand_units"
        ]
        * allocation[
            "price"
        ]
    )

    # ========================================================
    # ALLOCATION STATUS
    # ========================================================

    def get_allocation_status(row):

        allocated = _safe_int(
            row["allocated_units"]
        )

        recommended = _safe_int(
            row["recommended_units"]
        )

        if row["eol_status"] == "post_successor":

            return "EOL_HOLD"

        if recommended <= 0:

            return "NO_REPLENISHMENT_NEEDED"

        if allocated >= recommended:

            return "FULLY_ALLOCATED"

        if allocated > 0:

            return "PARTIALLY_ALLOCATED"

        return "NOT_ALLOCATED"

    allocation[
        "allocation_status"
    ] = allocation.apply(
        get_allocation_status,
        axis=1
    )

    # ========================================================
    # REASON
    # ========================================================

    def build_reason(row):

        allocated = _safe_int(
            row["allocated_units"]
        )

        recommended = _safe_int(
            row["recommended_units"]
        )

        # ----------------------------------------------------
        # EOL
        # ----------------------------------------------------

        if row["eol_status"] == "post_successor":

            return (
                "EOL HOLD: successor already launched; "
                "avoid additional predecessor inventory."
            )

        # ----------------------------------------------------
        # No gap
        # ----------------------------------------------------

        if row["stock_gap"] <= 0:

            return (
                "HOLD: current stock covers "
                "the target forecast requirement."
            )

        # ----------------------------------------------------
        # Fully allocated
        # ----------------------------------------------------

        if (
            allocated > 0
            and allocated >= recommended
        ):

            if row["avg_event_multiplier"] >= 2.5:

                return (
                    "FESTIVAL PRIORITY: elevated demand; "
                    "allocation protects expected sales."
                )

            if row["lost_sale_value"] > 100_000:

                return (
                    "HIGH PRIORITY: stockout risk and "
                    f"₹{row['lost_sale_value']:,.0f} "
                    "potential lost-sale value."
                )

            return (
                "NORMAL REPLENISHMENT: "
                "forecast demand exceeds current stock."
            )

        # ----------------------------------------------------
        # Partial allocation
        # ----------------------------------------------------

        if allocated > 0:

            return (
                "PARTIAL: demand requires more stock, "
                "but warehouse/budget constraints limited "
                "the allocation."
            )

        # ----------------------------------------------------
        # Nothing allocated
        # ----------------------------------------------------

        if row["price"] <= 0:

            return (
                "NOT ALLOCATED: invalid or zero product price."
            )

        return (
            "NOT ALLOCATED: higher-priority demand consumed "
            "available inventory or budget."
        )

    allocation["reason"] = allocation.apply(
        build_reason,
        axis=1
    )

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    output_columns = [

        # Identity
        "store_id",
        "model_id",

        # Demand
        "forecast_units",

        # Existing stock
        "current_stock",

        # Requirement
        "target_stock",
        "stock_gap",

        # Allocation
        "recommended_units",
        "allocated_units",
        "allocation_value",

        # Business impact
        "protected_sales_value",
        "lost_sale_value",

        # Remaining demand
        "unfilled_demand_units",
        "unfilled_demand_value",

        # Scoring
        "priority_score",
        "price_band",
        "store_price_band_fit",

        # Context
        "avg_event_multiplier",
        "lifecycle_factor",
        "city",
        "eol_status",

        # Decision explanation
        "allocation_status",
        "reason",
    ]

    # Keep only columns that exist.
    output_columns = [
        column
        for column in output_columns
        if column in allocation.columns
    ]

    result = (
        allocation[
            output_columns
        ]
        .sort_values(
            [
                "priority_score",
                "lost_sale_value"
            ],
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )

    return result


# ============================================================
# ALLOCATION SUMMARY
# ============================================================

def allocation_summary(
    allocation_df,
    inventory_budget=INVENTORY_BUDGET
):
    """
    Generate owner-level summary for the
    Monday allocation decision.
    """

    total_value = (
        allocation_df[
            "allocation_value"
        ].sum()
    )

    protected_sales = (
        allocation_df[
            "protected_sales_value"
        ].sum()
    )

    unfilled_value = (
        allocation_df[
            "unfilled_demand_value"
        ].sum()
    )

    units = (
        allocation_df[
            "allocated_units"
        ].sum()
    )

    # --------------------------------------------------------
    # Priority lines
    # --------------------------------------------------------

    high_priority = allocation_df[
        allocation_df[
            "priority_score"
        ] > 0
    ]

    # --------------------------------------------------------
    # Status counts
    # --------------------------------------------------------

    fully_allocated = (
        allocation_df[
            allocation_df[
                "allocation_status"
            ] == "FULLY_ALLOCATED"
        ]
    )

    partially_allocated = (
        allocation_df[
            allocation_df[
                "allocation_status"
            ] == "PARTIALLY_ALLOCATED"
        ]
    )

    eol_hold = (
        allocation_df[
            allocation_df[
                "allocation_status"
            ] == "EOL_HOLD"
        ]
    )

    # --------------------------------------------------------
    # Budget
    # --------------------------------------------------------

    budget = max(
        _safe_float(
            inventory_budget
        ),
        1
    )

    budget_used_pct = (
        total_value
        / budget
        * 100
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    return {

        "allocated_units":
            int(units),

        "allocation_value":
            float(total_value),

        "protected_sales_value":
            float(protected_sales),

        "unfilled_demand_value":
            float(unfilled_value),

        "budget_used_pct":
            float(budget_used_pct),

        "high_priority_lines":
            int(len(high_priority)),

        "fully_allocated_lines":
            int(len(fully_allocated)),

        "partially_allocated_lines":
            int(len(partially_allocated)),

        "eol_hold_lines":
            int(len(eol_hold)),

        "total_lines":
            int(len(allocation_df)),
    }