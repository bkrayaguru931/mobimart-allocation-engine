from allocation.scoring import calculate_priority_score, get_price_band


def test_price_band_boundaries():
    assert get_price_band(9999) == "Keypad"
    assert get_price_band(10000) == "Budget"
    assert get_price_band(15000) == "Upper-mid"
    assert get_price_band(25000) == "Mid-range"
    assert get_price_band(45000) == "Flagship"
    assert get_price_band(75000) == "Premium"


def test_store_fit_changes_priority_score():
    base = calculate_priority_score(
        forecast_units=10,
        current_stock=0,
        price=12000,
        category="Budget",
        lifecycle_factor=1.0,
        eol_status="normal",
        store_price_band_fit=1.0,
        price_band="Budget",
    )[0]

    boosted = calculate_priority_score(
        forecast_units=10,
        current_stock=0,
        price=12000,
        category="Budget",
        lifecycle_factor=1.0,
        eol_status="normal",
        store_price_band_fit=1.30,
        price_band="Budget",
    )[0]

    assert boosted > base


def test_post_successor_priority_is_lower_than_normal():
    normal = calculate_priority_score(
        forecast_units=10,
        current_stock=0,
        price=20000,
        category="Upper-mid",
        lifecycle_factor=1.0,
        eol_status="normal",
        store_price_band_fit=1.0,
        price_band="Upper-mid",
    )[0]

    post_successor = calculate_priority_score(
        forecast_units=10,
        current_stock=0,
        price=20000,
        category="Upper-mid",
        lifecycle_factor=1.0,
        eol_status="post_successor",
        store_price_band_fit=1.0,
        price_band="Upper-mid",
    )[0]

    assert post_successor < normal
