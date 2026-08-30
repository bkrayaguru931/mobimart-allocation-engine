"""
MobiMart End-of-Life Decision Engine.

Evaluates stock belonging to products approaching or past
their successor launch date.

For excess EOL stock, the engine compares:

    HOLD
    TRANSFER
    MARKDOWN

Every option is expressed in rupees and the lowest-cost
feasible option becomes the recommendation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Business assumptions
# ---------------------------------------------------------------------

TRANSFER_COST_PER_UNIT = 550.0

# Weekly carrying/opportunity cost of capital tied in stock.
HOLD_CARRYING_RATE = 0.02

MARKDOWN_RATE = {
    "approaching": 0.15,
    "near": 0.20,
    "post_successor": 0.30,
}

# Do not recommend an EOL action for tiny/no excess.
MIN_EXCESS_UNITS = 1


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _safe_float(value, default=0.0):
    try:
        value = float(value)
        if not np.isfinite(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalise_eol_status(value):
    value = str(value).strip().lower()

    aliases = {
        "normal": "normal",
        "approaching": "approaching",
        "near": "near",
        "post_successor": "post_successor",
        "post-successor": "post_successor",
        "eol-risk": "near",
        "late-life": "approaching",
    }

    return aliases.get(value, value)


# ---------------------------------------------------------------------
# EOL calculations
# ---------------------------------------------------------------------

def calculate_eol_options(
    current_stock,
    forecast_units,
    price,
    eol_status,
    has_transfer_destination=False,
):
    """
    Calculate the economic cost of HOLD, TRANSFER and MARKDOWN.

    Parameters
    ----------
    current_stock:
        Current units at the store.

    forecast_units:
        Expected demand over the next 7 days.

    price:
        Selling price per unit.

    eol_status:
        normal / approaching / near / post_successor

    has_transfer_destination:
        Whether another store has a meaningful demand gap.

    Returns
    -------
    dict
    """

    current_stock = max(_safe_float(current_stock), 0.0)
    forecast_units = max(_safe_float(forecast_units), 0.0)
    price = max(_safe_float(price), 0.0)

    eol_status = _normalise_eol_status(eol_status)

    # Keep approximately one week's demand at the store.
    protected_stock = forecast_units

    excess_units = max(
        current_stock - protected_stock,
        0.0,
    )

    excess_value = excess_units * price

    # Normal products do not require EOL liquidation.
    if eol_status == "normal" or excess_units < MIN_EXCESS_UNITS:
        return {
            "excess_units": excess_units,
            "excess_value": excess_value,
            "hold_cost": 0.0,
            "transfer_cost": np.inf,
            "markdown_rate": 0.0,
            "markdown_loss": 0.0,
            "markdown_recovery": excess_value,
            "recommended_action": "HOLD",
            "recommended_cost": 0.0,
        }

    # -----------------------------------------------------------------
    # HOLD
    # -----------------------------------------------------------------
    #
    # Holding EOL inventory has an opportunity/carrying cost because
    # capital remains trapped while the product loses commercial value.
    #
    eol_risk_multiplier = {
        "approaching": 1.0,
        "near": 1.5,
        "post_successor": 2.0,
    }.get(eol_status, 1.0)

    hold_cost = (
        excess_value
        * HOLD_CARRYING_RATE
        * eol_risk_multiplier
    )

    # -----------------------------------------------------------------
    # TRANSFER
    # -----------------------------------------------------------------

    if has_transfer_destination:
        transfer_cost = (
            excess_units
            * TRANSFER_COST_PER_UNIT
        )
    else:
        transfer_cost = np.inf

    # -----------------------------------------------------------------
    # MARKDOWN
    # -----------------------------------------------------------------

    markdown_rate = MARKDOWN_RATE.get(
        eol_status,
        0.20,
    )

    markdown_loss = (
        excess_value
        * markdown_rate
    )

    markdown_recovery = (
        excess_value
        - markdown_loss
    )

    # -----------------------------------------------------------------
    # Choose lowest-cost feasible option
    # -----------------------------------------------------------------

    options = {
        "HOLD": hold_cost,
        "TRANSFER": transfer_cost,
        "MARKDOWN": markdown_loss,
    }

    recommended_action = min(
        options,
        key=options.get,
    )

    recommended_cost = options[
        recommended_action
    ]

    return {
        "excess_units": excess_units,
        "excess_value": excess_value,
        "hold_cost": float(hold_cost),
        "transfer_cost": float(transfer_cost),
        "markdown_rate": float(markdown_rate),
        "markdown_loss": float(markdown_loss),
        "markdown_recovery": float(markdown_recovery),
        "recommended_action": recommended_action,
        "recommended_cost": float(recommended_cost),
    }


# ---------------------------------------------------------------------
# Transfer opportunity detection
# ---------------------------------------------------------------------

def _build_transfer_demand(
    allocation_df,
):
    """
    Identify stores that have a meaningful demand gap
    for a model.

    The allocation dataframe already contains forecast and
    current-stock information.
    """

    df = allocation_df.copy()

    df["forecast_units"] = pd.to_numeric(
        df["forecast_units"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    df["current_stock"] = pd.to_numeric(
        df["current_stock"],
        errors="coerce",
    ).fillna(0).clip(lower=0)

    df["demand_gap"] = (
        df["forecast_units"]
        - df["current_stock"]
    ).clip(lower=0)

    return df


# ---------------------------------------------------------------------
# Main EOL engine
# ---------------------------------------------------------------------

def generate_eol_recommendations(
    allocation_df,
):
    """
    Generate EOL recommendations from Monday allocation output.

    Expected columns
    ----------------
    store_id
    model_id
    forecast_units
    current_stock
    price
    eol_status

    Optional
    --------
    city
    successor_launch_date
    """

    required = {
        "store_id",
        "model_id",
        "forecast_units",
        "current_stock",
        "price",
        "eol_status",
    }

    missing = required - set(
        allocation_df.columns
    )

    if missing:
        raise ValueError(
            f"allocation_df missing columns: {missing}"
        )

    df = allocation_df.copy()

    demand_df = _build_transfer_demand(df)

    recommendations = []

    for _, row in df.iterrows():

        status = _normalise_eol_status(
            row["eol_status"]
        )

        if status == "normal":
            continue

        store_id = row["store_id"]
        model_id = row["model_id"]

        current_stock = _safe_float(
            row["current_stock"]
        )

        forecast_units = _safe_float(
            row["forecast_units"]
        )

        price = _safe_float(
            row["price"]
        )

        # -------------------------------------------------------------
        # Find another store that needs this model.
        # -------------------------------------------------------------

        candidates = demand_df[
            (demand_df["model_id"] == model_id)
            & (demand_df["store_id"] != store_id)
            & (demand_df["demand_gap"] > 0)
        ].copy()

        candidates = candidates.sort_values(
            "demand_gap",
            ascending=False,
        )

        has_destination = not candidates.empty

        options = calculate_eol_options(
            current_stock=current_stock,
            forecast_units=forecast_units,
            price=price,
            eol_status=status,
            has_transfer_destination=has_destination,
        )

        if options["excess_units"] < MIN_EXCESS_UNITS:
            continue

        transfer_destination = None
        transfer_demand = 0.0

        if has_destination:
            destination = candidates.iloc[0]

            transfer_destination = destination[
                "store_id"
            ]

            transfer_demand = _safe_float(
                destination["demand_gap"]
            )

        action = options[
            "recommended_action"
        ]

        # -------------------------------------------------------------
        # Human-readable reasoning
        # -------------------------------------------------------------

        if action == "TRANSFER":

            reason = (
                f"TRANSFER {options['excess_units']:.0f} units "
                f"to {transfer_destination}: "
                f"destination has {transfer_demand:.1f} units "
                f"of demand gap; transfer cost is "
                f"₹{options['transfer_cost']:,.0f}, "
                f"below the estimated markdown loss of "
                f"₹{options['markdown_loss']:,.0f}."
            )

        elif action == "MARKDOWN":

            reason = (
                f"MARKDOWN {options['excess_units']:.0f} excess units "
                f"at {options['markdown_rate'] * 100:.0f}%: "
                f"estimated markdown loss is "
                f"₹{options['markdown_loss']:,.0f} "
                f"versus hold cost of "
                f"₹{options['hold_cost']:,.0f}."
            )

        else:

            reason = (
                f"HOLD {options['excess_units']:.0f} units: "
                f"estimated carrying/opportunity cost is "
                f"₹{options['hold_cost']:,.0f}, "
                f"lower than available liquidation alternatives."
            )

        recommendations.append(
            {
                "store_id": store_id,
                "model_id": model_id,
                "eol_status": status,
                "current_stock": current_stock,
                "forecast_units": forecast_units,
                "excess_units": options["excess_units"],
                "price": price,
                "excess_inventory_value": options[
                    "excess_value"
                ],
                "transfer_destination": transfer_destination,
                "transfer_demand_gap": transfer_demand,
                "hold_cost": options["hold_cost"],
                "transfer_cost": options["transfer_cost"],
                "markdown_rate": options["markdown_rate"],
                "markdown_loss": options["markdown_loss"],
                "markdown_recovery": options["markdown_recovery"],
                "recommended_action": action,
                "recommended_cost": options[
                    "recommended_cost"
                ],
                "reason": reason,
            }
        )

    result = pd.DataFrame(
        recommendations
    )

    if result.empty:
        return pd.DataFrame(
            columns=[
                "store_id",
                "model_id",
                "eol_status",
                "current_stock",
                "forecast_units",
                "excess_units",
                "price",
                "excess_inventory_value",
                "transfer_destination",
                "transfer_demand_gap",
                "hold_cost",
                "transfer_cost",
                "markdown_rate",
                "markdown_loss",
                "markdown_recovery",
                "recommended_action",
                "recommended_cost",
                "reason",
            ]
        )

    return (
        result
        .sort_values(
            [
                "recommended_cost",
                "excess_inventory_value",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )


def eol_summary(eol_df):
    """
    Return owner-level EOL summary.
    """

    if eol_df.empty:
        return {
            "at_risk_lines": 0,
            "excess_units": 0,
            "excess_inventory_value": 0.0,
            "hold_cost": 0.0,
            "transfer_cost": 0.0,
            "markdown_loss": 0.0,
            "recommended_cost": 0.0,
        }

    finite_transfer = eol_df[
        np.isfinite(
            eol_df["transfer_cost"]
        )
    ]

    return {
        "at_risk_lines": int(len(eol_df)),
        "excess_units": float(
            eol_df["excess_units"].sum()
        ),
        "excess_inventory_value": float(
            eol_df["excess_inventory_value"].sum()
        ),
        "hold_cost": float(
            eol_df["hold_cost"].sum()
        ),
        "transfer_cost": float(
            finite_transfer["transfer_cost"].sum()
        ),
        "markdown_loss": float(
            eol_df["markdown_loss"].sum()
        ),
        "recommended_cost": float(
            eol_df["recommended_cost"].sum()
        ),
    }