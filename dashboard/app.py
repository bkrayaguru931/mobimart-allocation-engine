"""
MobiMart Owner Dashboard.

Run:

    streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st  # type: ignore[import-not-found]


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


DATA_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
)

OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "outputs",
)


st.set_page_config(
    page_title="MobiMart Owner Dashboard",
    layout="wide",
)


st.title("MobiMart Inventory Intelligence")
st.caption(
    "Forecast → Allocation → EOL Risk → Benchmark"
)


def load_csv(name):

    path = os.path.join(
        OUTPUT_DIR,
        name,
    )

    if not os.path.exists(path):
        return pd.DataFrame()

    return pd.read_csv(path)


allocation = load_csv(
    "monday_allocation.csv"
)

forecast = load_csv(
    "weekly_forecast.csv"
)

eol = load_csv(
    "eol_recommendations.csv"
)

scorecard = load_csv(
    "scorecard.csv"
)


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

st.sidebar.header(
    "MobiMart"
)

st.sidebar.write(
    "25 stores · ~60 models"
)

if allocation.empty:

    st.warning(
        "Run the allocation pipeline first:\n\n"
        "`python scripts/run_allocation.py`"
    )

    st.stop()


# ---------------------------------------------------------------------
# Capital overview
# ---------------------------------------------------------------------

st.header(
    "1. Where is my capital?"
)

allocation_value = allocation[
    "allocation_value"
].sum()

current_inventory_value = (
    allocation[
        "current_stock"
    ]
    * allocation[
        "price"
    ]
).sum()

protected_sales = allocation[
    "protected_sales_value"
].sum()

unfilled_value = allocation[
    "unfilled_demand_value"
].sum()

budget = 40_000_000

budget_used = (
    allocation_value / budget
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Current inventory value",
    f"₹{current_inventory_value:,.0f}",
)

col2.metric(
    "Monday allocation",
    f"₹{allocation_value:,.0f}",
)

col3.metric(
    "Protected sales",
    f"₹{protected_sales:,.0f}",
)

col4.metric(
    "Budget used",
    f"{budget_used:.1%}",
)


st.progress(
    min(max(budget_used, 0), 1)
)


# ---------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------

st.header(
    "2. Monday allocation"
)

store_summary = (
    allocation
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
        protected_sales=(
            "protected_sales_value",
            "sum",
        ),
        unfilled_demand=(
            "unfilled_demand_value",
            "sum",
        ),
    )
    .sort_values(
        "allocation_value",
        ascending=False,
    )
)

st.dataframe(
    store_summary,
    use_container_width=True,
)


# ---------------------------------------------------------------------
# Top recommendations
# ---------------------------------------------------------------------

st.subheader(
    "Highest-priority recommendations"
)

display_cols = [
    column
    for column in [
        "store_id",
        "model_id",
        "forecast_units",
        "current_stock",
        "stock_gap",
        "recommended_units",
        "allocated_units",
        "allocation_value",
        "protected_sales_value",
        "eol_status",
        "reason",
    ]
    if column in allocation.columns
]

st.dataframe(
    allocation[
        display_cols
    ].head(20),
    use_container_width=True,
)


# ---------------------------------------------------------------------
# EOL risk
# ---------------------------------------------------------------------

st.header(
    "3. What stock is at risk?"
)

if eol.empty:

    st.success(
        "No EOL excess-stock recommendations are currently available."
    )

else:

    eol_value = eol[
        "excess_inventory_value"
    ].sum()

    markdown_loss = eol[
        "markdown_loss"
    ].sum()

    recommended_cost = eol[
        "recommended_cost"
    ].sum()

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "EOL excess inventory",
        f"₹{eol_value:,.0f}",
    )

    c2.metric(
        "Potential markdown loss",
        f"₹{markdown_loss:,.0f}",
    )

    c3.metric(
        "Recommended intervention cost",
        f"₹{recommended_cost:,.0f}",
    )

    action_summary = (
        eol
        .groupby(
            "recommended_action",
            as_index=False,
        )
        .agg(
            lines=(
                "model_id",
                "size",
            ),
            excess_units=(
                "excess_units",
                "sum",
            ),
            inventory_value=(
                "excess_inventory_value",
                "sum",
            ),
            cost=(
                "recommended_cost",
                "sum",
            ),
        )
    )

    st.subheader(
        "Recommended EOL actions"
    )

    st.dataframe(
        action_summary,
        use_container_width=True,
    )

    st.subheader(
        "Highest-value EOL risks"
    )

    eol_cols = [
        column
        for column in [
            "store_id",
            "model_id",
            "eol_status",
            "current_stock",
            "forecast_units",
            "excess_units",
            "excess_inventory_value",
            "transfer_destination",
            "hold_cost",
            "transfer_cost",
            "markdown_loss",
            "recommended_action",
            "recommended_cost",
            "reason",
        ]
        if column in eol.columns
    ]

    st.dataframe(
        eol.sort_values(
            "excess_inventory_value",
            ascending=False,
        )[eol_cols].head(30),
        use_container_width=True,
    )


# ---------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------

st.header(
    "4. Does MobiMart beat the obvious baseline?"
)

if scorecard.empty:

    st.info(
        "Run `python scripts/run_backtest.py` "
        "to generate the four-week benchmark."
    )

else:

    st.dataframe(
        scorecard,
        use_container_width=True,
    )

    winners = scorecard[
        "winner"
    ].value_counts()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "MobiMart wins",
        int(winners.get("MobiMart", 0)),
    )

    col2.metric(
        "Naive wins",
        int(winners.get("Naive", 0)),
    )

    col3.metric(
        "Ties",
        int(winners.get("Tie", 0)),
    )


# ---------------------------------------------------------------------
# Four-week results
# ---------------------------------------------------------------------

four_week = load_csv(
    "four_week_mobimart_results.csv"
)

four_week_naive = load_csv(
    "four_week_naive_results.csv"
)

st.header(
    "5. Four-week performance"
)

if not four_week.empty:

    performance_cols = [
        column
        for column in [
            "week",
            "stockout_rate",
            "weeks_of_cover",
            "dead_stock_pct",
            "markdown_loss",
            "capital_turns",
            "sales_value",
            "protected_sales_value",
            "lost_sales_value",
        ]
        if column in four_week.columns
    ]

    st.subheader(
        "MobiMart"
    )

    st.dataframe(
        four_week[
            performance_cols
        ],
        use_container_width=True,
    )

if not four_week_naive.empty:

    st.subheader(
        "Naive baseline"
    )

    performance_cols = [
        column
        for column in [
            "week",
            "stockout_rate",
            "weeks_of_cover",
            "dead_stock_pct",
            "markdown_loss",
            "capital_turns",
            "sales_value",
            "protected_sales_value",
            "lost_sales_value",
        ]
        if column in four_week_naive.columns
    ]

    st.dataframe(
        four_week_naive[
            performance_cols
        ],
        use_container_width=True,
    )


# ---------------------------------------------------------------------
# Methodology
# ---------------------------------------------------------------------

st.header(
    "Methodology"
)

st.markdown(
    """
**Forecast**

Seven-day store x model forecast using historical demand,
weekday effects, event effects and product lifecycle.

**Allocation**

The optimizer prioritises demand gaps using stockout economics,
price band, lifecycle and store-specific price-band affinity.

**EOL**

Excess stock approaching/past successor launch is compared
across hold, transfer and markdown using rupee costs.

**Baseline**

Naive allocation proportional to each store/model's previous
30-day sales.

**Backtest**

Four historical weekly planning points are evaluated against
the subsequent seven days of observed sales.

The benchmark is explicitly counterfactual because the supplied
dataset contains a current inventory snapshot rather than
historical inventory snapshots.
"""
)