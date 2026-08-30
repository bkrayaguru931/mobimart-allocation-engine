import pandas as pd

from allocation.eol import (
    calculate_eol_options,
    generate_eol_recommendations,
)


def test_post_successor_has_higher_markdown_rate():

    near = calculate_eol_options(
        current_stock=20,
        forecast_units=5,
        price=20000,
        eol_status="near",
        has_transfer_destination=False,
    )

    post = calculate_eol_options(
        current_stock=20,
        forecast_units=5,
        price=20000,
        eol_status="post_successor",
        has_transfer_destination=False,
    )

    assert post["markdown_rate"] > near[
        "markdown_rate"
    ]


def test_transfer_is_selected_when_cheaper():

    result = calculate_eol_options(
        current_stock=20,
        forecast_units=5,
        price=20000,
        eol_status="post_successor",
        has_transfer_destination=True,
    )

    assert result[
        "recommended_action"
    ] == "TRANSFER"


def test_normal_product_is_held():

    result = calculate_eol_options(
        current_stock=20,
        forecast_units=5,
        price=20000,
        eol_status="normal",
        has_transfer_destination=False,
    )

    assert result[
        "recommended_action"
    ] == "HOLD"


def test_eol_recommendation_contains_rupee_costs():

    allocation = pd.DataFrame(
        [
            {
                "store_id": "DAV01",
                "model_id": "MOD056",
                "forecast_units": 2,
                "current_stock": 20,
                "price": 20000,
                "eol_status": "post_successor",
            },
            {
                "store_id": "BLR01",
                "model_id": "MOD056",
                "forecast_units": 15,
                "current_stock": 2,
                "price": 20000,
                "eol_status": "normal",
            },
        ]
    )

    result = generate_eol_recommendations(
        allocation
    )

    assert len(result) == 1

    required = {
        "hold_cost",
        "transfer_cost",
        "markdown_loss",
        "recommended_cost",
        "recommended_action",
        "reason",
    }

    assert required.issubset(
        result.columns
    )