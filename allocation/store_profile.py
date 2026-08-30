# allocation/store_profile.py

STORE_PRICE_BAND_FIT = {

    "Davangere": {
        "Keypad": 1.15,
        "Budget": 1.30,
        "Upper-mid": 1.10,
        "Mid-range": 0.95,
        "Flagship": 0.85,
        "Premium": 0.75,
    },

    "Bangalore": {
        "Keypad": 0.85,
        "Budget": 0.95,
        "Upper-mid": 1.05,
        "Mid-range": 1.10,
        "Flagship": 1.20,
        "Premium": 1.30,
    },

    "default": {
        "Keypad": 1.00,
        "Budget": 1.00,
        "Upper-mid": 1.00,
        "Mid-range": 1.00,
        "Flagship": 1.00,
        "Premium": 1.00,
    },
}


def get_store_price_band_fit(
    city,
    price_band
):
    """
    Return store-specific demand affinity.
    """

    profile = STORE_PRICE_BAND_FIT.get(
        city,
        STORE_PRICE_BAND_FIT["default"]
    )

    return profile.get(
        price_band,
        1.0
    )