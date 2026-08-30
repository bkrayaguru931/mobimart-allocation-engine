"""
MobiMart evaluation and scorecard.

Compares the intelligent allocator against the naive
last-month-sales baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        if not np.isfinite(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def _actual_demand(
    sales_df,
    start_date,
    end_date,
):
    sales = sales_df.copy()

    sales["date"] = pd.to_datetime(
        sales["date"]
    )

    mask = (
        (sales["date"] >= pd.Timestamp(start_date))
        & (sales["date"] <= pd.Timestamp(end_date))
    )

    actual = (
        sales.loc[mask]
        .groupby(
            ["store_id", "model_id"],
            as_index=False,
        )["units_sold"]
        .sum()
        .rename(
            columns={
                "units_sold": "actual_units"
            }
        )
    )

    return actual


def evaluate_allocation(
    allocation_df,
    sales_df,
    evaluation_start,
    evaluation_end,
):
    """
    Evaluate an allocation plan against actual sales.

    Metrics:
        stockout rate
        weeks of cover
        dead-stock percentage
        markdown loss
        capital turns
        protected sales
        unfilled demand
    """

    df = allocation_df.copy()

    actual = _actual_demand(
        sales_df,
        evaluation_start,
        evaluation_end,
    )

    df = df.merge(
        actual,
        on=["store_id", "model_id"],
        how="left",
    )

    df["actual_units"] = (
        df["actual_units"]
        .fillna(0)
        .clip(lower=0)
    )

    df["current_stock"] = pd.to_numeric(
        df["current_stock"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    df["allocated_units"] = pd.to_numeric(
        df["allocated_units"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    df["price"] = pd.to_numeric(
        df["price"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    available_units = (
        df["current_stock"]
        + df["allocated_units"]
    )

    # ---------------------------------------------------------------
    # Stockout
    # ---------------------------------------------------------------

    df["stockout_units"] = (
        df["actual_units"]
        - available_units
    ).clip(lower=0)

    demand_total = df[
        "actual_units"
    ].sum()

    stockout_units = df[
        "stockout_units"
    ].sum()

    stockout_rate = (
        stockout_units / demand_total
        if demand_total > 0
        else 0.0
    )

    # ---------------------------------------------------------------
    # Ending inventory
    # ---------------------------------------------------------------

    df["ending_stock"] = (
        available_units
        - df["actual_units"]
    ).clip(lower=0)

    ending_value = (
        df["ending_stock"]
        * df["price"]
    ).sum()

    average_weekly_demand = (
        df["actual_units"].sum()
        / 4.0
    )

    weeks_of_cover = (
        ending_value
        / max(
            (
                df["actual_units"]
                * df["price"]
            ).sum()
            / 4.0,
            1.0,
        )
    )

    # ---------------------------------------------------------------
    # Dead stock
    # ---------------------------------------------------------------

    dead_stock_units = df.loc[
        (
            (df["ending_stock"] > 0)
            & (df["actual_units"] <= 0)
        ),
        "ending_stock",
    ].sum()

    ending_units = df[
        "ending_stock"
    ].sum()

    dead_stock_pct = (
        dead_stock_units / ending_units
        if ending_units > 0
        else 0.0
    )

    # ---------------------------------------------------------------
    # Capital turns
    # ---------------------------------------------------------------

    sales_value = (
        df["actual_units"]
        * df["price"]
    ).sum()

    average_inventory_value = (
        (
            df["current_stock"]
            + df["allocated_units"]
            + df["ending_stock"]
        )
        / 2.0
        * df["price"]
    ).sum()

    capital_turns = (
        sales_value
        / max(
            average_inventory_value,
            1.0,
        )
        * 13
    )

    # Annualised from a four-week observation window.

    # ---------------------------------------------------------------
    # Protected / lost sales
    # ---------------------------------------------------------------

    protected_sales = (
        np.minimum(
            df["actual_units"],
            available_units,
        )
        * df["price"]
    ).sum()

    lost_sales = (
        df["stockout_units"]
        * df["price"]
    ).sum()

    # ---------------------------------------------------------------
    # Markdown loss
    # ---------------------------------------------------------------

    if "markdown_loss" in df.columns:
        markdown_loss = df[
            "markdown_loss"
        ].sum()
    else:
        markdown_loss = 0.0

    return {
        "evaluation_start": pd.Timestamp(
            evaluation_start
        ),
        "evaluation_end": pd.Timestamp(
            evaluation_end
        ),
        "stockout_rate": float(
            stockout_rate
        ),
        "weeks_of_cover": float(
            weeks_of_cover
        ),
        "dead_stock_pct": float(
            dead_stock_pct
        ),
        "markdown_loss": float(
            markdown_loss
        ),
        "capital_turns": float(
            capital_turns
        ),
        "sales_value": float(
            sales_value
        ),
        "protected_sales_value": float(
            protected_sales
        ),
        "lost_sales_value": float(
            lost_sales
        ),
        "ending_inventory_value": float(
            ending_value
        ),
    }


def compare_allocators(
    optimized_metrics,
    baseline_metrics,
):
    """
    Create a transparent optimized-vs-baseline scorecard.

    Lower is better for:
        stockout_rate
        weeks_of_cover
        dead_stock_pct
        markdown_loss
        lost_sales_value

    Higher is better for:
        capital_turns
        protected_sales_value
        sales_value
    """

    metric_rules = {
        "stockout_rate": "lower",
        "weeks_of_cover": "lower",
        "dead_stock_pct": "lower",
        "markdown_loss": "lower",
        "capital_turns": "higher",
        "protected_sales_value": "higher",
        "lost_sales_value": "lower",
        "sales_value": "higher",
    }

    rows = []

    for metric, direction in metric_rules.items():

        optimized = _safe_float(
            optimized_metrics.get(metric)
        )

        baseline = _safe_float(
            baseline_metrics.get(metric)
        )

        if direction == "higher":

            winner = (
                "MobiMart"
                if optimized > baseline
                else "Naive"
                if baseline > optimized
                else "Tie"
            )

            delta = optimized - baseline

        else:

            winner = (
                "MobiMart"
                if optimized < baseline
                else "Naive"
                if baseline < optimized
                else "Tie"
            )

            delta = baseline - optimized

        rows.append(
            {
                "metric": metric,
                "direction": direction,
                "mobi_mart": optimized,
                "naive_baseline": baseline,
                "delta_in_mobimart_favour": delta,
                "winner": winner,
            }
        )

    return pd.DataFrame(rows)


def evaluate_four_weeks(
    weekly_results,
):
    """
    Aggregate four weekly evaluation dictionaries.
    """

    if not weekly_results:
        return pd.DataFrame()

    return pd.DataFrame(
        weekly_results
    )