"""End-to-end integration tests for the real MobiMart dataset."""

from pathlib import Path

import pandas as pd
import pytest

from allocation.allocator import INVENTORY_BUDGET, allocate_inventory
from allocation.forecast import generate_weekly_forecast


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"


@pytest.fixture(scope="session")
def real_pipeline():
    """Run the real-data forecast → allocation pipeline once per test run."""
    sales_df = pd.read_csv(DATA_DIR / "sales.csv")
    stores_df = pd.read_csv(DATA_DIR / "stores.csv")
    products_df = pd.read_csv(DATA_DIR / "products.csv")
    events_df = pd.read_csv(DATA_DIR / "events.csv")
    inventory_df = pd.read_csv(DATA_DIR / "inventory.csv")

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    events_df["date"] = pd.to_datetime(events_df["date"])
    products_df["launch_date"] = pd.to_datetime(
        products_df["launch_date"], errors="coerce"
    )
    products_df["successor_launch_date"] = pd.to_datetime(
        products_df["successor_launch_date"], errors="coerce"
    )

    forecast_df = generate_weekly_forecast(
        sales_df=sales_df,
        stores_df=stores_df,
        products_df=products_df,
        events_df=events_df,
    )

    allocation_df = allocate_inventory(
        forecast_df=forecast_df,
        inventory_df=inventory_df,
        products_df=products_df,
        stores_df=stores_df,
    )

    return {
        "sales": sales_df,
        "stores": stores_df,
        "products": products_df,
        "inventory": inventory_df,
        "forecast": forecast_df,
        "allocation": allocation_df,
    }



def test_real_data_pipeline_produces_expected_scale(real_pipeline):
    assert len(real_pipeline["stores"]) == 25
    assert len(real_pipeline["products"]) == 60
    assert len(real_pipeline["sales"]) > 100_000
    assert 0 < len(real_pipeline["inventory"]) <= 25 * 60
    assert real_pipeline["inventory"].duplicated(
        subset=["store_id", "model_id"]
    ).sum() == 0

    # 25 stores × 60 products = 1,500 forecast/allocation lines.
    assert len(real_pipeline["forecast"]) == 1_500
    assert len(real_pipeline["allocation"]) == 1_500

    assert real_pipeline["forecast"]["forecast_units"].ge(0).all()
    assert real_pipeline["allocation"]["allocated_units"].ge(0).all()



def test_real_data_allocation_respects_warehouse_stock(real_pipeline):
    allocation_df = real_pipeline["allocation"]
    inventory_df = real_pipeline["inventory"]

    # warehouse_stock is a model-level pool. The allocator may not emit
    # that repeated pool column in the final store-level output, so verify
    # total allocated units per model against the real warehouse stock.
    warehouse_by_model = (
        inventory_df
        .groupby("model_id")["warehouse_stock"]
        .max()
    )

    allocated_by_model = (
        allocation_df
        .groupby("model_id")["allocated_units"]
        .sum()
    )

    common_models = allocated_by_model.index.intersection(
        warehouse_by_model.index
    )

    assert len(common_models) == len(warehouse_by_model)
    assert (
        allocated_by_model.loc[common_models]
        <= warehouse_by_model.loc[common_models]
    ).all()



def test_real_data_allocation_respects_recommended_units(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    assert (
        allocation_df["allocated_units"]
        <= allocation_df["recommended_units"]
    ).all()



def test_real_data_allocation_respects_chain_budget(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    total_value = allocation_df["allocation_value"].sum()

    assert total_value <= INVENTORY_BUDGET



def test_real_data_eol_products_are_not_allocated(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    post_successor = allocation_df[
        allocation_df["eol_status"] == "post_successor"
    ]

    assert len(post_successor) > 0
    assert post_successor["allocated_units"].sum() == 0
    assert post_successor["allocation_value"].sum() == 0



def test_real_data_store_profiles_are_applied(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    davangere_budget = allocation_df[
        (allocation_df["city"] == "Davangere")
        & (allocation_df["price_band"] == "Budget")
    ]
    bangalore_premium = allocation_df[
        (allocation_df["city"] == "Bangalore")
        & (allocation_df["price_band"] == "Premium")
    ]

    assert not davangere_budget.empty
    assert not bangalore_premium.empty

    assert davangere_budget["store_price_band_fit"].eq(1.30).all()
    assert bangalore_premium["store_price_band_fit"].eq(1.30).all()



def test_real_data_output_has_required_business_columns(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    required_columns = {
        "store_id",
        "model_id",
        "forecast_units",
        "current_stock",
        "target_stock",
        "stock_gap",
        "recommended_units",
        "allocated_units",
        "allocation_value",
        "protected_sales_value",
        "lost_sale_value",
        "unfilled_demand_units",
        "unfilled_demand_value",
        "priority_score",
        "price_band",
        "store_price_band_fit",
        "city",
        "eol_status",
        "allocation_status",
        "reason",
    }

    assert required_columns.issubset(allocation_df.columns)



def test_real_data_output_has_unique_store_model_lines(real_pipeline):
    allocation_df = real_pipeline["allocation"]

    duplicate_count = allocation_df.duplicated(
        subset=["store_id", "model_id"]
    ).sum()

    assert duplicate_count == 0
