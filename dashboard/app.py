"""
MobiMart Inventory Intelligence Dashboard

"""

import os
import sys

import pandas as pd
import streamlit as st


# ============================================================
# PATH CONFIGURATION
# ============================================================

# dashboard/app.py
#       |
#       +-- parent = dashboard/
#       |
#       +-- parent.parent = MobiMart/

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")


# Make project packages importable
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="MobiMart Inventory Intelligence",
    page_icon="📦",
    layout="wide",
)


# ============================================================
# TITLE
# ============================================================

st.title("MobiMart Inventory Intelligence")

st.caption(
    "Forecast → Allocation → EOL Risk → Benchmark"
)


# ============================================================
# FILE HELPERS
# ============================================================

def load_csv(filename, directory):
    """Load a CSV and show a clear error if it is missing."""

    path = os.path.join(directory, filename)

    if not os.path.exists(path):
        st.error(
            f"Required file not found:\n\n`{path}`"
        )
        st.stop()

    return pd.read_csv(path)


def load_output(filename):
    """Load an output CSV."""

    return load_csv(filename, OUTPUT_DIR)


# ============================================================
# LOAD RAW DATA
# ============================================================

sales = load_csv(
    "sales.csv",
    RAW_DATA_DIR,
)

stores = load_csv(
    "stores.csv",
    RAW_DATA_DIR,
)

products = load_csv(
    "products.csv",
    RAW_DATA_DIR,
)

inventory = load_csv(
    "inventory.csv",
    RAW_DATA_DIR,
)

events = load_csv(
    "events.csv",
    RAW_DATA_DIR,
)


# ============================================================
# LOAD PIPELINE OUTPUTS
# ============================================================

allocation = load_output(
    "monday_allocation.csv"
)

forecast = load_output(
    "weekly_forecast.csv"
)

eol = load_output(
    "eol_recommendations.csv"
)


# Optional benchmark outputs
baseline = None
scorecard = None
mobimart_results = None
naive_results = None

baseline_path = os.path.join(
    OUTPUT_DIR,
    "baseline_allocation.csv",
)

scorecard_path = os.path.join(
    OUTPUT_DIR,
    "scorecard.csv",
)

mobimart_results_path = os.path.join(
    OUTPUT_DIR,
    "four_week_mobimart_results.csv",
)

naive_results_path = os.path.join(
    OUTPUT_DIR,
    "four_week_naive_results.csv",
)

if os.path.exists(baseline_path):
    baseline = pd.read_csv(baseline_path)

if os.path.exists(scorecard_path):
    scorecard = pd.read_csv(scorecard_path)

if os.path.exists(mobimart_results_path):
    mobimart_results = pd.read_csv(
        mobimart_results_path
    )

if os.path.exists(naive_results_path):
    naive_results = pd.read_csv(
        naive_results_path
    )


# ============================================================
# DATA PREPARATION
# ============================================================

# Add product price to allocation data if required.
#
# monday_allocation.csv already contains price_band,
# but not raw product price. The dashboard therefore
# joins products.csv using model_id.

if "price" not in allocation.columns:

    allocation = allocation.merge(
        products[
            [
                "model_id",
                "price",
                "brand",
                "family",
                "model_name",
                "category",
                "lifecycle_stage",
            ]
        ],
        on="model_id",
        how="left",
    )


# Add price to EOL data if necessary.

if (
    "price" not in eol.columns
    and "model_id" in eol.columns
):

    eol = eol.merge(
        products[
            [
                "model_id",
                "price",
                "brand",
                "family",
                "model_name",
            ]
        ],
        on="model_id",
        how="left",
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("MobiMart")

st.sidebar.write(
    "Inventory intelligence for weekly "
    "forecasting, allocation and EOL decisions."
)

st.sidebar.divider()

st.sidebar.write(
    f"Stores: **{stores['store_id'].nunique():,}**"
)

st.sidebar.write(
    f"Models: **{products['model_id'].nunique():,}**"
)

st.sidebar.write(
    f"Sales rows: **{len(sales):,}**"
)

st.sidebar.write(
    f"Allocation lines: **{len(allocation):,}**"
)


# ============================================================
# 1. WHERE IS MY CAPITAL?
# ============================================================

st.header("1. Where is my capital?")

col1, col2, col3, col4 = st.columns(4)


# Current inventory value

inventory_value = 0.0

if (
    "current_stock" in allocation.columns
    and "price" in allocation.columns
):

    inventory_value = (
        allocation["current_stock"].fillna(0)
        * allocation["price"].fillna(0)
    ).sum()


# Allocated capital

allocated_capital = 0.0

if "allocation_value" in allocation.columns:
    allocated_capital = allocation[
        "allocation_value"
    ].fillna(0).sum()


# Unfilled demand

unfilled_value = 0.0

if "unfilled_demand_value" in allocation.columns:
    unfilled_value = allocation[
        "unfilled_demand_value"
    ].fillna(0).sum()


# Protected sales

protected_sales = 0.0

if "protected_sales_value" in allocation.columns:
    protected_sales = allocation[
        "protected_sales_value"
    ].fillna(0).sum()


col1.metric(
    "Inventory Value",
    f"₹{inventory_value:,.0f}",
)

col2.metric(
    "Monday Allocation",
    f"₹{allocated_capital:,.0f}",
)

col3.metric(
    "Protected Sales",
    f"₹{protected_sales:,.0f}",
)

col4.metric(
    "Unfilled Demand Value",
    f"₹{unfilled_value:,.0f}",
)


# ------------------------------------------------------------
# Capital by store
# ------------------------------------------------------------

st.subheader("Capital by store")

capital_by_store = (
    allocation
    .groupby(
        "store_id",
        as_index=False,
    )
    .agg(
        inventory_value=(
            "current_stock",
            lambda x: 0,
        )
        if "price" not in allocation.columns
        else (
            "current_stock",
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
)


# Recalculate inventory value correctly
# because price varies by model.

inventory_by_store = (
    allocation.assign(
        inventory_value=(
            allocation["current_stock"].fillna(0)
            * allocation["price"].fillna(0)
        )
    )
    .groupby(
        "store_id",
        as_index=False,
    )["inventory_value"]
    .sum()
)

capital_by_store = capital_by_store.drop(
    columns=["inventory_value"],
    errors="ignore",
)

capital_by_store = capital_by_store.merge(
    inventory_by_store,
    on="store_id",
    how="left",
)

capital_by_store = capital_by_store[
    [
        "store_id",
        "inventory_value",
        "allocation_value",
        "protected_sales",
        "unfilled_demand",
    ]
].sort_values(
    "inventory_value",
    ascending=False,
)

st.dataframe(
    capital_by_store,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 2. WHERE IS STOCK AT RISK?
# ============================================================

st.header("2. What stock is at risk?")

eol_col1, eol_col2, eol_col3, eol_col4 = st.columns(4)


if "risk_flag" in eol.columns:
    at_risk = eol[
        eol["risk_flag"].astype(str).str.lower()
        == "true"
    ]
else:
    # Fallback: anything that isn't HOLD.
    if "recommendation" in eol.columns:
        at_risk = eol[
            eol["recommendation"]
            .astype(str)
            .str.upper()
            != "HOLD"
        ]
    else:
        at_risk = eol.copy()


eol_lines = len(at_risk)


# Find likely value columns dynamically.

excess_value = 0.0
markdown_loss = 0.0
recommended_cost = 0.0

for col in [
    "excess_inventory_value",
    "excess_value",
]:
    if col in eol.columns:
        excess_value = eol[col].fillna(0).sum()
        break


for col in [
    "markdown_loss",
    "markdown_cost",
    "markdown_exposure",
]:
    if col in eol.columns:
        markdown_loss = eol[col].fillna(0).sum()
        break


for col in [
    "recommended_cost",
    "recommendation_cost",
    "total_cost",
]:
    if col in eol.columns:
        recommended_cost = eol[col].fillna(0).sum()
        break


eol_col1.metric(
    "At-Risk Lines",
    f"{eol_lines:,}",
)

eol_col2.metric(
    "Excess Inventory",
    f"₹{excess_value:,.0f}",
)

eol_col3.metric(
    "Markdown Exposure",
    f"₹{markdown_loss:,.0f}",
)

eol_col4.metric(
    "Recommended EOL Cost",
    f"₹{recommended_cost:,.0f}",
)


# ------------------------------------------------------------
# EOL recommendations
# ------------------------------------------------------------

st.subheader("EOL recommendations")

if "recommendation" in eol.columns:

    recommendation_summary = (
        eol.groupby(
            "recommendation",
            as_index=False,
        )
        .size()
        .rename(columns={"size": "lines"})
        .sort_values(
            "lines",
            ascending=False,
        )
    )

    st.dataframe(
        recommendation_summary,
        use_container_width=True,
        hide_index=True,
    )


# Show detailed EOL table

preferred_eol_columns = [
    "store_id",
    "model_id",
    "eol_status",
    "recommendation",
    "current_stock",
    "excess_units",
    "price",
    "excess_inventory_value",
    "markdown_loss",
    "transfer_cost",
    "hold_cost",
    "recommended_cost",
    "reason",
]

available_eol_columns = [
    c
    for c in preferred_eol_columns
    if c in eol.columns
]

if available_eol_columns:

    st.dataframe(
        eol[
            available_eol_columns
        ].sort_values(
            "recommended_cost",
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 3. ALLOCATION RECOMMENDATIONS
# ============================================================

st.header("3. What should each store receive?")

allocation_col1, allocation_col2, allocation_col3 = st.columns(3)


total_allocated_units = allocation[
    "allocated_units"
].fillna(0).sum()


allocation_lines = (
    allocation[
        "allocated_units"
    ].fillna(0)
    > 0
).sum()


priority_lines = 0

if "priority_score" in allocation.columns:

    priority_lines = (
        allocation["priority_score"]
        .fillna(0)
        > allocation["priority_score"]
        .fillna(0)
        .median()
    ).sum()


allocation_col1.metric(
    "Allocated Units",
    f"{total_allocated_units:,.0f}",
)

allocation_col2.metric(
    "Allocation Lines",
    f"{allocation_lines:,}",
)

allocation_col3.metric(
    "Priority Lines",
    f"{priority_lines:,}",
)


# ------------------------------------------------------------
# Top recommendations
# ------------------------------------------------------------

st.subheader(
    "Top allocation recommendations"
)

top_columns = [
    "store_id",
    "model_id",
    "forecast_units",
    "current_stock",
    "stock_gap",
    "recommended_units",
    "allocated_units",
    "allocation_value",
    "protected_sales_value",
    "lost_sale_value",
    "priority_score",
    "price_band",
    "city",
    "eol_status",
    "reason",
]

available_columns = [
    c
    for c in top_columns
    if c in allocation.columns
]

if "priority_score" in allocation.columns:

    top_allocation = (
        allocation
        .sort_values(
            "priority_score",
            ascending=False,
        )
        .head(20)
    )

else:

    top_allocation = (
        allocation
        .sort_values(
            "allocation_value",
            ascending=False,
        )
        .head(20)
    )


st.dataframe(
    top_allocation[
        available_columns
    ],
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 4. FORECAST OVERVIEW
# ============================================================

st.header("4. Forecast overview")

forecast_col1, forecast_col2, forecast_col3 = st.columns(3)

forecast_units = forecast[
    "forecast_units"
].fillna(0).sum()

forecast_models = forecast[
    "model_id"
].nunique()

forecast_stores = forecast[
    "store_id"
].nunique()


forecast_col1.metric(
    "Forecast Units",
    f"{forecast_units:,.0f}",
)

forecast_col2.metric(
    "Models",
    f"{forecast_models:,}",
)

forecast_col3.metric(
    "Stores",
    f"{forecast_stores:,}",
)


# ------------------------------------------------------------
# Forecast by model
# ------------------------------------------------------------

forecast_by_model = (
    forecast
    .groupby(
        "model_id",
        as_index=False,
    )
    .agg(
        forecast_units=(
            "forecast_units",
            "sum",
        ),
        stores=(
            "store_id",
            "nunique",
        ),
    )
    .sort_values(
        "forecast_units",
        ascending=False,
    )
    .head(20)
)

st.subheader(
    "Top 20 models by forecast demand"
)

st.bar_chart(
    forecast_by_model.set_index(
        "model_id"
    )["forecast_units"]
)


# ============================================================
# 5. FOUR-WEEK BENCHMARK
# ============================================================

st.header(
    "5. Did MobiMart beat the naive baseline?"
)

if scorecard is not None:

    st.dataframe(
        scorecard,
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # Highlight winners
    # --------------------------------------------------------

    if "winner" in scorecard.columns:

        wins = (
            scorecard["winner"]
            .astype(str)
            .str.lower()
            == "mobi_mart"
        ).sum()

        naive_wins = (
            scorecard["winner"]
            .astype(str)
            .str.lower()
            .str.contains("naive")
        ).sum()

        win_col1, win_col2 = st.columns(2)

        win_col1.metric(
            "MobiMart Metric Wins",
            f"{wins}",
        )

        win_col2.metric(
            "Naive Metric Wins",
            f"{naive_wins}",
        )


else:

    st.info(
        "Run `python scripts/run_backtest.py` "
        "to generate the four-week benchmark."
    )


# ------------------------------------------------------------
# Weekly benchmark results
# ------------------------------------------------------------

if (
    mobimart_results is not None
    and naive_results is not None
):

    st.subheader(
        "Four-week rolling results"
    )

    if "week_start" in mobimart_results.columns:

        mobi_plot = mobimart_results.copy()
        naive_plot = naive_results.copy()

        if "sales_value" in mobi_plot.columns:

            comparison = pd.DataFrame(
                {
                    "MobiMart": mobi_plot[
                        "sales_value"
                    ].values,
                    "Naive": naive_plot[
                        "sales_value"
                    ].values,
                },
                index=mobi_plot[
                    "week_start"
                ],
            )

            st.line_chart(
                comparison
            )


# ============================================================
# 6. BUSINESS SUMMARY
# ============================================================

st.header("6. Owner summary")

summary_col1, summary_col2 = st.columns(2)


with summary_col1:

    st.subheader(
        "Capital"
    )

    st.write(
        f"- Current inventory value: "
        f"₹{inventory_value:,.0f}"
    )

    st.write(
        f"- Monday allocation: "
        f"₹{allocated_capital:,.0f}"
    )

    st.write(
        f"- Protected sales: "
        f"₹{protected_sales:,.0f}"
    )

    st.write(
        f"- Unfilled demand value: "
        f"₹{unfilled_value:,.0f}"
    )


with summary_col2:

    st.subheader(
        "Risk"
    )

    st.write(
        f"- EOL at-risk lines: "
        f"{eol_lines:,}"
    )

    st.write(
        f"- Excess inventory: "
        f"₹{excess_value:,.0f}"
    )

    st.write(
        f"- Markdown exposure: "
        f"₹{markdown_loss:,.0f}"
    )

    st.write(
        f"- Recommended EOL cost: "
        f"₹{recommended_cost:,.0f}"
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "MobiMart Inventory Intelligence | "
    "Forecast → Allocation → EOL Risk → Benchmark"
)

st.caption(
    f"Data source: {RAW_DATA_DIR}"
)