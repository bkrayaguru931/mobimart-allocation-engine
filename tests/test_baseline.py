import pandas as pd

from optimizer.baseline import (
    generate_naive_allocation,
)


def test_baseline_allocates_to_previous_sales():

    sales = pd.DataFrame(
        [
            {
                "date": "2026-07-01",
                "store_id": "A",
                "model_id": "M1",
                "units_sold": 10,
            },
            {
                "date": "2026-07-02",
                "store_id": "A",
                "model_id": "M1",
                "units_sold": 10,
            },
            {
                "date": "2026-07-01",
                "store_id": "B",
                "model_id": "M1",
                "units_sold": 1,
            },
        ]
    )

    inventory = pd.DataFrame(
        [
            {
                "store_id": "A",
                "model_id": "M1",
                "current_stock": 0,
                "warehouse_stock": 20,
            },
            {
                "store_id": "B",
                "model_id": "M1",
                "current_stock": 0,
                "warehouse_stock": 20,
            },
        ]
    )

    products = pd.DataFrame(
        [
            {
                "model_id": "M1",
                "price": 10000,
            }
        ]
    )

    result = generate_naive_allocation(
        sales_df=sales,
        inventory_df=inventory,
        products_df=products,
        allocation_date="2026-07-31",
    )

    a = result.loc[
        result["store_id"] == "A",
        "allocated_units",
    ].iloc[0]

    b = result.loc[
        result["store_id"] == "B",
        "allocated_units",
    ].iloc[0]

    assert a >= b


def test_baseline_never_exceeds_warehouse():

    sales = pd.DataFrame(
        [
            {
                "date": "2026-07-01",
                "store_id": "A",
                "model_id": "M1",
                "units_sold": 100,
            },
        ]
    )

    inventory = pd.DataFrame(
        [
            {
                "store_id": "A",
                "model_id": "M1",
                "current_stock": 0,
                "warehouse_stock": 3,
            },
        ]
    )

    products = pd.DataFrame(
        [
            {
                "model_id": "M1",
                "price": 10000,
            }
        ]
    )

    result = generate_naive_allocation(
        sales_df=sales,
        inventory_df=inventory,
        products_df=products,
        allocation_date="2026-07-31",
    )

    assert (
        result["allocated_units"].sum()
        <= 3
    )