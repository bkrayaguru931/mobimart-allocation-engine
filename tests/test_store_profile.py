from allocation.store_profile import get_store_price_band_fit


def test_davangere_budget_affinity_is_high():
    assert get_store_price_band_fit("Davangere", "Budget") == 1.30


def test_bangalore_premium_affinity_is_high():
    assert get_store_price_band_fit("Bangalore", "Premium") == 1.30


def test_unknown_store_and_band_use_neutral_fit():
    assert get_store_price_band_fit("UnknownCity", "UnknownBand") == 1.0
