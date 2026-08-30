import pandas as pd

from allocation.allocator import allocate_inventory, get_eol_status


def make_inputs(warehouse_stock=100, price=12000, city="Davangere", successor=None):
    forecast = pd.DataFrame([
        {
            "store_id": "STORE01",
            "model_id": "MODEL01",
            "forecast_units": 10.0,
            "avg_event_multiplier": 1.0,
            "avg_lifecycle_factor": 1.0,
        }
    ])

    inventory = pd.DataFrame([
        {
            "store_id": "STORE01",
            "model_id": "MODEL01",
            "current_stock": 0,
            "warehouse_stock": warehouse_stock,
        }
    ])

    products = pd.DataFrame([
        {
            "model_id": "MODEL01",
            "price": price,
            "category": "Budget",
            "successor_launch_date": successor,
        }
    ])

    stores = pd.DataFrame([
        {
            "store_id": "STORE01",
            "city": city,
        }
    ])

    return forecast, inventory, products, stores


def test_allocation_never_exceeds_warehouse_stock():
    inputs = make_inputs(warehouse_stock=3)
    result = allocate_inventory(*inputs, forecast_date="2026-08-29")

    row = result.iloc[0]
    assert row["allocated_units"] <= 3


def test_allocation_never_exceeds_budget():
    inputs = make_inputs(warehouse_stock=100, price=12000)
    result = allocate_inventory(
        *inputs,
        forecast_date="2026-08-29",
        inventory_budget=25000,
    )

    assert result["allocation_value"].sum() <= 25000


def test_allocation_never_exceeds_recommended_units():
    inputs = make_inputs(warehouse_stock=100)
    result = allocate_inventory(*inputs, forecast_date="2026-08-29")

    assert (result["allocated_units"] <= result["recommended_units"]).all()


def test_post_successor_product_gets_no_fresh_allocation():
    inputs = make_inputs(successor="2026-08-01")
    result = allocate_inventory(*inputs, forecast_date="2026-08-29")

    row = result.iloc[0]
    assert row["eol_status"] == "post_successor"
    assert row["recommended_units"] == 0
    assert row["allocated_units"] == 0
    assert row["allocation_status"] == "EOL_HOLD"


def test_store_profile_is_used_in_allocator():
    forecast, inventory, products, stores = make_inputs(city="Davangere")
    davangere = allocate_inventory(
        forecast, inventory, products, stores,
        forecast_date="2026-08-29",
    )

    _, _, _, bangalore_stores = make_inputs(city="Bangalore")
    bangalore = allocate_inventory(
        forecast, inventory, products, bangalore_stores,
        forecast_date="2026-08-29",
    )

    assert davangere.iloc[0]["store_price_band_fit"] == 1.30
    assert bangalore.iloc[0]["store_price_band_fit"] == 0.95
    assert davangere.iloc[0]["priority_score"] > bangalore.iloc[0]["priority_score"]


def test_eol_status_boundaries():
    forecast_date = pd.Timestamp("2026-08-29")

    assert get_eol_status(forecast_date, pd.NaT) == "normal"
    assert get_eol_status(forecast_date, "2026-10-29") == "normal"
    assert get_eol_status(forecast_date, "2026-10-28") == "approaching"
    assert get_eol_status(forecast_date, "2026-09-28") == "near"
    assert get_eol_status(forecast_date, "2026-08-28") == "post_successor"
