# allocation/scoring.py

"""
Allocation scoring logic for MobiMart.

This module keeps business scoring rules separate from the
allocation engine so the scoring model can be tuned independently.
"""

import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

FORECAST_DAYS = 7
TARGET_STOCK_COVER_DAYS = 10
MAX_STOCK_COVER_DAYS = 21
MIN_STOCK_COVER_DAYS = 2


STOCKOUT_PENALTY = {
    "Keypad": 1.50,
    "Budget": 1.40,
    "Upper-mid": 1.15,
    "Mid-range": 1.10,
    "Flagship": 0.80,
    "Premium": 0.75,
}


EOL_PENALTY = {
    "normal": 1.00,
    "approaching": 0.75,
    "near": 0.45,
    "post_successor": 0.20,
}


PRICE_BAND_WEIGHT = {
    "Keypad": 1.10,
    "Budget": 1.10,
    "Upper-mid": 1.05,
    "Mid-range": 1.00,
    "Flagship": 0.90,
    "Premium": 0.85,
}


# Store affinity is intentionally a moderate multiplier rather
# than a dominant factor. Demand and stockout risk remain primary.
STORE_FIT_MIN = 0.75
STORE_FIT_MAX = 1.30


# ============================================================
# HELPERS
# ============================================================


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        if not np.isfinite(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def get_price_band(price):
    """Convert product price into a business price band."""

    price = _safe_float(price)

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


# ============================================================
# PRIORITY SCORE
# ============================================================


def calculate_priority_score(
    forecast_units,
    current_stock,
    price,
    category,
    lifecycle_factor,
    eol_status,
    store_price_band_fit=1.0,
    price_band=None,
):
    """
    Calculate allocation priority.

    Higher score means the store/model combination should be
    considered earlier for scarce warehouse inventory.

    Score components:
        - target stock gap
        - minimum stock-cover urgency
        - stockout risk
        - product price band
        - product lifecycle
        - EOL status
        - store-specific price-band affinity

    Store affinity is deliberately applied as a multiplier after
    the demand/risk components so it influences allocation without
    overwhelming actual demand.
    """

    forecast_units = max(_safe_float(forecast_units), 0.0)
    current_stock = max(_safe_float(current_stock), 0.0)
    price = max(_safe_float(price), 0.0)

    lifecycle_factor = max(
        _safe_float(lifecycle_factor, default=1.0),
        0.10,
    )

    store_price_band_fit = _safe_float(
        store_price_band_fit,
        default=1.0,
    )
    store_price_band_fit = float(
        np.clip(
            store_price_band_fit,
            STORE_FIT_MIN,
            STORE_FIT_MAX,
        )
    )

    if price_band is None:
        price_band = get_price_band(price)

    # --------------------------------------------------------
    # Target inventory
    # --------------------------------------------------------

    target_stock = (
        forecast_units
        * TARGET_STOCK_COVER_DAYS
        / FORECAST_DAYS
    )

    max_target_stock = (
        forecast_units
        * MAX_STOCK_COVER_DAYS
        / FORECAST_DAYS
    )

    target_stock = min(target_stock, max_target_stock)

    stock_gap = max(
        target_stock - current_stock,
        0.0,
    )

    # --------------------------------------------------------
    # Minimum stock-cover pressure
    # --------------------------------------------------------

    minimum_stock = (
        forecast_units
        * MIN_STOCK_COVER_DAYS
        / FORECAST_DAYS
    )

    minimum_gap = max(
        minimum_stock - current_stock,
        0.0,
    )

    # --------------------------------------------------------
    # Stockout pressure
    # --------------------------------------------------------

    stockout_pressure = (
        max(forecast_units - current_stock, 0.0)
        / max(forecast_units, 1.0)
    )

    stockout_penalty = STOCKOUT_PENALTY.get(
        category,
        STOCKOUT_PENALTY.get(price_band, 1.0),
    )

    price_band_weight = PRICE_BAND_WEIGHT.get(
        price_band,
        1.0,
    )

    # --------------------------------------------------------
    # Potential lost-sale value
    # --------------------------------------------------------

    lost_sale_value = (
        forecast_units
        * price
        * stockout_pressure
        * stockout_penalty
    )

    # --------------------------------------------------------
    # EOL factor
    # --------------------------------------------------------

    eol_factor = EOL_PENALTY.get(eol_status, 1.0)

    # --------------------------------------------------------
    # Priority score
    # --------------------------------------------------------

    base_score = (
        stock_gap
        * max(price, 1.0)
        * stockout_penalty
        * lifecycle_factor
        * eol_factor
        * price_band_weight
    )

    urgency_bonus = (
        minimum_gap
        * max(price, 1.0)
        * stockout_penalty
        * 1.25
    )

    priority_score = (
        (base_score + urgency_bonus)
        * store_price_band_fit
    )

    return (
        float(priority_score),
        float(stock_gap),
        float(lost_sale_value),
        float(minimum_gap),
        price_band,
    )
