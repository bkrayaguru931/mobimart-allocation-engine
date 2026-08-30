# allocation/forecast.py

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

FORECAST_HORIZON_DAYS = 7
HISTORY_DAYS = 56
RECENT_DAYS = 28

MIN_FORECAST = 0.05


# ============================================================
# HELPERS
# ============================================================

def _weighted_daily_demand(daily_units):
    """
    Calculate a weighted average daily demand.

    More recent days receive higher weight.
    """

    daily_units = daily_units.sort_index()

    if daily_units.empty:
        return 0.0

    n = len(daily_units)

    # Older observations get lower weights.
    weights = np.linspace(0.5, 1.5, n)

    return float(
        np.average(
            daily_units.values,
            weights=weights
        )
    )


def _get_event_multiplier(
    date,
    events_df
):
    """
    Return the demand multiplier for a date.

    If multiple events overlap, use the largest multiplier.
    """

    if events_df is None or events_df.empty:
        return 1.0

    matches = events_df[
        events_df["date"] == date
    ]

    if matches.empty:
        return 1.0

    return float(
        matches["demand_multiplier"].max()
    )


def _lifecycle_adjustment(
    current_date,
    product
):
    """
    Adjust forecast based on product lifecycle.

    Before launch:
        no demand

    Normal product:
        1.0

    Near successor:
        demand gradually reduced

    After successor:
        demand significantly reduced
    """

    launch_date = product.get(
        "launch_date",
        pd.NaT
    )

    successor_date = product.get(
        "successor_launch_date",
        pd.NaT
    )

    if pd.notna(launch_date):

        days_since_launch = (
            current_date - launch_date
        ).days

        if days_since_launch < 0:
            return 0.0

    if pd.isna(successor_date):
        return 1.0

    days_from_successor = (
        current_date - successor_date
    ).days

    # Far from successor
    if days_from_successor < -60:
        return 1.0

    # Rumoured / approaching
    if -60 <= days_from_successor < -30:
        return 0.95

    # Successor coming soon
    if -30 <= days_from_successor < 0:
        return 0.90

    # Successor launched
    if 0 <= days_from_successor < 30:
        return 0.80

    # 1–2 months after successor
    if 30 <= days_from_successor < 60:
        return 0.70

    # 2–3 months after successor
    if 60 <= days_from_successor < 90:
        return 0.60

    # Mature predecessor
    return 0.55


def _day_of_week_factor(
    historical_sales
):
    """
    Estimate weekday/weekend behaviour.

    Falls back to 1.0 when insufficient history exists.
    """

    if historical_sales.empty:
        return 1.0

    historical_sales = historical_sales.copy()

    historical_sales["weekday"] = (
        historical_sales.index.dayofweek
    )

    current_weekday = (
        historical_sales.index[-1].dayofweek
    )

    overall_mean = (
        historical_sales["units_sold"].mean()
    )

    if overall_mean <= 0:
        return 1.0

    weekday_mean = (
        historical_sales[
            historical_sales["weekday"]
            == current_weekday
        ]["units_sold"]
        .mean()
    )

    if pd.isna(weekday_mean):
        return 1.0

    return float(
        np.clip(
            weekday_mean / overall_mean,
            0.75,
            1.35
        )
    )


# ============================================================
# MAIN FORECAST
# ============================================================

def generate_forecast(
    sales_df,
    stores_df,
    products_df,
    events_df,
    forecast_date=None,
    horizon_days=FORECAST_HORIZON_DAYS
):
    """
    Generate store × model demand forecasts.

    Parameters
    ----------
    sales_df:
        Historical sales containing:
        date, store_id, model_id, units_sold

    stores_df:
        Store master data.

    products_df:
        Product master data.

    events_df:
        Festival/event calendar.

    forecast_date:
        Date from which the forecast begins.
        Defaults to the day after the latest sales date.

    horizon_days:
        Number of days to forecast.

    Returns
    -------
    DataFrame

        store_id
        model_id
        forecast_date
        forecast_units
        daily_forecast
        event_multiplier
        lifecycle_factor
        weekday_factor
    """

    sales = sales_df.copy()

    sales["date"] = pd.to_datetime(
        sales["date"]
    )

    events = events_df.copy()

    if not events.empty:
        events["date"] = pd.to_datetime(
            events["date"]
        )

    products = products_df.copy()

    products["launch_date"] = pd.to_datetime(
        products["launch_date"],
        errors="coerce"
    )

    if "successor_launch_date" in products.columns:
        products["successor_launch_date"] = (
            pd.to_datetime(
                products[
                    "successor_launch_date"
                ],
                errors="coerce"
            )
        )

    # --------------------------------------------------------
    # Forecast start date
    # --------------------------------------------------------

    if forecast_date is None:

        forecast_date = (
            sales["date"].max()
            + pd.Timedelta(days=1)
        )

    forecast_date = pd.Timestamp(
        forecast_date
    )

    forecast_dates = pd.date_range(
        forecast_date,
        periods=horizon_days,
        freq="D"
    )

    # --------------------------------------------------------
    # Restrict history
    # --------------------------------------------------------

    history_start = (
        forecast_date
        - pd.Timedelta(days=HISTORY_DAYS)
    )

    history = sales[
        sales["date"] >= history_start
    ].copy()

    # --------------------------------------------------------
    # Aggregate daily sales
    # --------------------------------------------------------

    daily_sales = (
        history
        .groupby(
            [
                "store_id",
                "model_id",
                "date"
            ]
        )["units_sold"]
        .sum()
        .reset_index()
    )

    results = []

    # ========================================================
    # STORE × PRODUCT
    # ========================================================

    for _, store in stores_df.iterrows():

        store_id = store["store_id"]

        for _, product in products.iterrows():

            model_id = product["model_id"]

            pair_history = daily_sales[
                (
                    daily_sales["store_id"]
                    == store_id
                )
                &
                (
                    daily_sales["model_id"]
                    == model_id
                )
            ].copy()

            # ------------------------------------------------
            # Create complete daily series
            # ------------------------------------------------

            history_dates = pd.date_range(
                history_start,
                forecast_date - pd.Timedelta(days=1),
                freq="D"
            )

            if not pair_history.empty:

                # Keep only the numeric demand column.
                # This prevents pandas from trying to fill
                # string/object columns with integer 0.
                pair_history = (
                    pair_history[
                        [
                            "date",
                            "units_sold"
                        ]
                    ]
                    .set_index("date")
                    .reindex(history_dates)
                )

                # Missing dates mean zero sales.
                pair_history["units_sold"] = (
                    pd.to_numeric(
                        pair_history["units_sold"],
                        errors="coerce"
                    )
                    .fillna(0)
                )

                pair_history.index.name = "date"

            else:

                pair_history = pd.DataFrame(
                    {
                        "units_sold": np.zeros(
                            len(history_dates),
                            dtype=float
                        )
                    },
                    index=history_dates
                )

                pair_history.index.name = "date"
            # ------------------------------------------------
            # Recent demand
            # ------------------------------------------------

            recent_history = pair_history[
                pair_history.index
                >= (
                    forecast_date
                    - pd.Timedelta(
                        days=RECENT_DAYS
                    )
                )
            ]

            recent_mean = (
                recent_history[
                    "units_sold"
                ].mean()
            )

            # ------------------------------------------------
            # Weighted historical demand
            # ------------------------------------------------

            weighted_mean = _weighted_daily_demand(
                pair_history["units_sold"]
            )

            # ------------------------------------------------
            # Blend recent + historical
            #
            # Recent demand gets more importance.
            # ------------------------------------------------

            if recent_mean > 0:

                baseline_daily = (
                    0.70 * recent_mean
                    + 0.30 * weighted_mean
                )

            else:

                baseline_daily = (
                    weighted_mean
                )

            # ------------------------------------------------
            # If there is no history for this pair,
            # leave a very small fallback.
            # ------------------------------------------------

            if baseline_daily <= 0:

                baseline_daily = (
                    max(
                        sales[
                            sales["model_id"]
                            == model_id
                        ]["units_sold"]
                        .mean()
                        / max(
                            sales[
                                sales["model_id"]
                                == model_id
                            ]["store_id"]
                            .nunique(),
                            1
                        ),
                        MIN_FORECAST
                    )
                )

            # ------------------------------------------------
            # Weekday factor
            # ------------------------------------------------

            weekday_factor = (
                _day_of_week_factor(
                    pair_history[
                        ["units_sold"]
                    ]
                )
            )

            # ------------------------------------------------
            # Forecast each day
            # ------------------------------------------------

            for target_date in forecast_dates:

                # --------------------------------------------
                # Festival effect
                # --------------------------------------------

                event_multiplier = (
                    _get_event_multiplier(
                        target_date,
                        events
                    )
                )

                # --------------------------------------------
                # Lifecycle effect
                # --------------------------------------------

                lifecycle_factor = (
                    _lifecycle_adjustment(
                        target_date,
                        product
                    )
                )

                # --------------------------------------------
                # Weekend factor
                # --------------------------------------------

                weekend_factor = (
                    1.20
                    if target_date.dayofweek >= 5
                    else 1.0
                )

                # --------------------------------------------
                # Expected demand
                # --------------------------------------------

                daily_forecast = (
                    baseline_daily
                    * weekday_factor
                    * weekend_factor
                    * event_multiplier
                    * lifecycle_factor
                )

                daily_forecast = max(
                    daily_forecast,
                    MIN_FORECAST
                )

                results.append({

                    "store_id":
                        store_id,

                    "model_id":
                        model_id,

                    "forecast_date":
                        target_date,

                    "forecast_units":
                        daily_forecast,

                    "daily_forecast":
                        daily_forecast,

                    "event_multiplier":
                        event_multiplier,

                    "lifecycle_factor":
                        lifecycle_factor,

                    "weekday_factor":
                        weekday_factor,
                })

    forecast = pd.DataFrame(
        results
    )

    return forecast


# ============================================================
# WEEKLY FORECAST
# ============================================================

def generate_weekly_forecast(
    sales_df,
    stores_df,
    products_df,
    events_df,
    forecast_date=None
):
    """
    Generate a 7-day forecast aggregated to
    store × model level.

    This is the output the allocation engine
    can consume.
    """

    daily_forecast = generate_forecast(
        sales_df=sales_df,
        stores_df=stores_df,
        products_df=products_df,
        events_df=events_df,
        forecast_date=forecast_date,
        horizon_days=7
    )

    weekly = (
        daily_forecast
        .groupby(
            [
                "store_id",
                "model_id"
            ],
            as_index=False
        )
        .agg(
            forecast_units=(
                "forecast_units",
                "sum"
            ),

            avg_event_multiplier=(
                "event_multiplier",
                "mean"
            ),

            avg_lifecycle_factor=(
                "lifecycle_factor",
                "mean"
            )
        )
    )

    return weekly