"""
Run MobiMart's four-week historical comparison.

Usage:

    python scripts/run_backtest.py

Outputs:

    outputs/baseline_allocation.csv
    outputs/four_week_results.csv
    outputs/scorecard.csv
"""

from __future__ import annotations

import os
import sys

import pandas as pd


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )


from allocation.forecast import (
    generate_weekly_forecast,
)

from allocation.allocator import (
    allocate_inventory,
)

from allocation.eol import (
    generate_eol_recommendations,
)

from optimizer.baseline import (
    generate_naive_allocation,
)

from optimizer.evaluation import (
    evaluate_allocation,
    compare_allocators,
)


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


def load_data():

    sales = pd.read_csv(
        os.path.join(
            DATA_DIR,
            "sales.csv",
        )
    )

    stores = pd.read_csv(
        os.path.join(
            DATA_DIR,
            "stores.csv",
        )
    )

    products = pd.read_csv(
        os.path.join(
            DATA_DIR,
            "products.csv",
        )
    )

    events = pd.read_csv(
        os.path.join(
            DATA_DIR,
            "events.csv",
        )
    )

    inventory = pd.read_csv(
        os.path.join(
            DATA_DIR,
            "inventory.csv",
        )
    )

    sales["date"] = pd.to_datetime(
        sales["date"]
    )

    events["date"] = pd.to_datetime(
        events["date"]
    )

    products["launch_date"] = pd.to_datetime(
        products["launch_date"],
        errors="coerce",
    )

    if "successor_launch_date" in products:

        products[
            "successor_launch_date"
        ] = pd.to_datetime(
            products[
                "successor_launch_date"
            ],
            errors="coerce",
        )

    return (
        sales,
        stores,
        products,
        events,
        inventory,
    )


def run():

    (
        sales,
        stores,
        products,
        events,
        inventory,
    ) = load_data()

    latest_date = sales[
        "date"
    ].max()

    # Four Mondays ending before the final
    # observed week.
    last_monday = (
        latest_date
        - pd.Timedelta(
            days=latest_date.weekday()
        )
    )

    monday_dates = [
        last_monday
        - pd.Timedelta(days=7 * i)
        for i in range(4, 0, -1)
    ]

    optimized_weekly = []
    baseline_weekly = []

    all_baseline = []
    all_eol = []

    print("=" * 70)
    print("MOBIMART FOUR-WEEK BACKTEST")
    print("=" * 70)

    for monday in monday_dates:

        monday = pd.Timestamp(
            monday
        )

        evaluation_start = monday
        evaluation_end = (
            monday
            + pd.Timedelta(days=6)
        )

        print(
            f"\nWeek: "
            f"{evaluation_start.date()} "
            f"→ "
            f"{evaluation_end.date()}"
        )

        historical_sales = sales[
            sales["date"] < monday
        ].copy()

        if historical_sales.empty:
            continue

        # -------------------------------------------------------------
        # Optimized allocator
        # -------------------------------------------------------------

        forecast = generate_weekly_forecast(
            sales_df=historical_sales,
            stores_df=stores,
            products_df=products,
            events_df=events,
            forecast_date=monday,
        )

        optimized = allocate_inventory(
            forecast_df=forecast,
            inventory_df=inventory,
            products_df=products,
            stores_df=stores,
            forecast_date=monday,
        )

        eol = generate_eol_recommendations(
            optimized
        )

        if not eol.empty:
            eol["allocation_date"] = monday
            all_eol.append(eol)

        # -------------------------------------------------------------
        # Naive baseline
        # -------------------------------------------------------------

        baseline = generate_naive_allocation(
            sales_df=historical_sales,
            inventory_df=inventory,
            products_df=products,
            allocation_date=monday,
        )

        baseline["allocation_date"] = monday

        all_baseline.append(
            baseline
        )

        # -------------------------------------------------------------
        # Evaluate against actual next 7 days
        # -------------------------------------------------------------

        optimized_metrics = evaluate_allocation(
            allocation_df=optimized,
            sales_df=sales,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )

        baseline_metrics = evaluate_allocation(
            allocation_df=baseline,
            sales_df=sales,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )

        optimized_metrics[
            "week"
        ] = monday.date()

        baseline_metrics[
            "week"
        ] = monday.date()

        optimized_weekly.append(
            optimized_metrics
        )

        baseline_weekly.append(
            baseline_metrics
        )

        print(
            f"  MobiMart stockout: "
            f"{optimized_metrics['stockout_rate']:.2%}"
        )

        print(
            f"  Naive stockout:    "
            f"{baseline_metrics['stockout_rate']:.2%}"
        )

    # -----------------------------------------------------------------
    # Save raw outputs
    # -----------------------------------------------------------------

    if all_baseline:

        baseline_output = pd.concat(
            all_baseline,
            ignore_index=True,
        )

        baseline_output.to_csv(
            os.path.join(
                OUTPUT_DIR,
                "baseline_allocation.csv",
            ),
            index=False,
        )

    if all_eol:

        eol_output = pd.concat(
            all_eol,
            ignore_index=True,
        )

        eol_output.to_csv(
            os.path.join(
                OUTPUT_DIR,
                "eol_recommendations.csv",
            ),
            index=False,
        )

    # -----------------------------------------------------------------
    # Aggregate four-week metrics
    # -----------------------------------------------------------------

    optimized_df = pd.DataFrame(
        optimized_weekly
    )

    baseline_df = pd.DataFrame(
        baseline_weekly
    )

    optimized_metrics = {
        column: optimized_df[column].mean()
        for column in [
            "stockout_rate",
            "weeks_of_cover",
            "dead_stock_pct",
            "markdown_loss",
            "capital_turns",
            "sales_value",
            "protected_sales_value",
            "lost_sales_value",
            "ending_inventory_value",
        ]
        if column in optimized_df.columns
    }

    baseline_metrics = {
        column: baseline_df[column].mean()
        for column in [
            "stockout_rate",
            "weeks_of_cover",
            "dead_stock_pct",
            "markdown_loss",
            "capital_turns",
            "sales_value",
            "protected_sales_value",
            "lost_sales_value",
            "ending_inventory_value",
        ]
        if column in baseline_df.columns
    }

    scorecard = compare_allocators(
        optimized_metrics,
        baseline_metrics,
    )

    optimized_df.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "four_week_mobimart_results.csv",
        ),
        index=False,
    )

    baseline_df.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "four_week_naive_results.csv",
        ),
        index=False,
    )

    scorecard.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "scorecard.csv",
        ),
        index=False,
    )

    # -----------------------------------------------------------------
    # Console report
    # -----------------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("FOUR-WEEK SCORECARD")
    print("=" * 70)

    print(
        scorecard.to_string(
            index=False
        )
    )

    print("\nOutputs:")

    print(
        "  outputs/baseline_allocation.csv"
    )

    print(
        "  outputs/eol_recommendations.csv"
    )

    print(
        "  outputs/four_week_mobimart_results.csv"
    )

    print(
        "  outputs/four_week_naive_results.csv"
    )

    print(
        "  outputs/scorecard.csv"
    )


if __name__ == "__main__":
    run()