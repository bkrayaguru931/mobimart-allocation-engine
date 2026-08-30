import pandas as pd
import numpy as np


# ============================================================
# LOAD DATA
# ============================================================

stores = pd.read_csv("data/raw/stores.csv")

products = pd.read_csv(
    "data/raw/products.csv",
    parse_dates=["launch_date"]
)

events = pd.read_csv(
    "data/raw/events.csv",
    parse_dates=["date"]
)

sales = pd.read_csv(
    "data/raw/sales.csv",
    parse_dates=["date"]
)


print("=" * 70)
print("MOBIMART DATASET VALIDATION")
print("=" * 70)


# ============================================================
# BASIC DATASET CHECK
# ============================================================

print("\n\n1. BASIC DATASET CHECK")
print("-" * 70)

print(f"Stores:   {stores['store_id'].nunique()}")
print(f"Products: {products['model_id'].nunique()}")
print(f"Dates:    {sales['date'].nunique()}")

print(
    f"Date range: "
    f"{sales['date'].min().date()} → "
    f"{sales['date'].max().date()}"
)

print(f"Sales rows: {len(sales):,}")

print("\nMissing values:")

print(
    sales.isnull()
    .sum()
    .sort_values(ascending=False)
    .head(10)
)


# ============================================================
# 2. BANGALORE PREMIUM CHECK
# ============================================================

print("\n\n2. BANGALORE PREMIUM PHONE CHECK")
print("-" * 70)

sales_products = sales.merge(
    products[
        [
            "model_id",
            "price",
            "category"
        ]
    ],
    on="model_id",
    how="left"
)

sales_stores = sales_products.merge(
    stores[
        [
            "store_id",
            "city",
            "positioning"
        ]
    ],
    on="store_id",
    how="left"
)


# Premium = >= ₹45,000
premium_sales = (
    sales_stores["price"] >= 45000
)

city_premium = (
    sales_stores
    .groupby("city")
    .apply(
        lambda x: pd.Series({
            "total_units": x["units_sold"].sum(),
            "premium_units": x.loc[
                x["price"] >= 45000,
                "units_sold"
            ].sum()
        }),
        include_groups=False
    )
)

city_premium["premium_share"] = (
    city_premium["premium_units"]
    / city_premium["total_units"]
    * 100
)

print(
    city_premium
    .sort_values("premium_share", ascending=False)
    .round(2)
    .to_string()
)

blr_share = city_premium.loc[
    "Bangalore",
    "premium_share"
]

print(
    f"\nBangalore premium share: "
    f"{blr_share:.2f}%"
)

if blr_share >= 20:
    print("PASS: Bangalore has meaningful premium demand.")
else:
    print("WARNING: Bangalore premium demand is too low.")


# ============================================================
# 3. DAVANGERE BUDGET CHECK
# ============================================================

print("\n\n3. DAVANGERE BUDGET PHONE CHECK")
print("-" * 70)

davangere = sales_stores[
    sales_stores["city"] == "Davangere"
].copy()

davangere["price_band"] = pd.cut(
    davangere["price"],
    bins=[
        0,
        10000,
        15000,
        20000,
        30000,
        50000,
        np.inf
    ],
    labels=[
        "<10k",
        "10k-15k",
        "15k-20k",
        "20k-30k",
        "30k-50k",
        "50k+"
    ]
)

davangere_mix = (
    davangere
    .groupby("price_band", observed=True)["units_sold"]
    .sum()
)

davangere_mix_pct = (
    davangere_mix
    / davangere_mix.sum()
    * 100
)

print(
    davangere_mix_pct
    .round(2)
    .to_string()
)

budget_bands = [
    band
    for band in ["10k-15k", "15k-20k"]
    if band in davangere_mix_pct.index
]

budget_10_20 = davangere_mix_pct[
    budget_bands
].sum()

print(
    f"\nDavangere ₹10k–₹20k share: "
    f"{budget_10_20:.2f}%"
)

if budget_10_20 >= 30:
    print("PASS: Davangere has strong ₹10k–₹20k demand.")
else:
    print(
        "WARNING: Davangere ₹10k–₹20k demand "
        "may need stronger differentiation."
    )
# ============================================================
# 4. FESTIVAL SPIKE CHECK
# ============================================================

print("\n\n4. FESTIVAL SPIKE CHECK")
print("-" * 70)

daily_sales = (
    sales
    .groupby("date")["units_sold"]
    .sum()
)

# Focus strictly on major shopping peak events (Dussehra & Diwali)
festival_event_types = [
    "Dussehra",
    "Diwali"
]

festival_dates = events[
    events["event_type"].isin(festival_event_types)
]["date"].unique()

festival_dates = pd.to_datetime(festival_dates)

# Exclude ALL event dates from normal baseline to prevent baseline inflation
all_event_dates = pd.to_datetime(events["date"].unique())

normal_days = daily_sales[
    ~daily_sales.index.isin(all_event_dates)
]

festival_days = daily_sales[
    daily_sales.index.isin(festival_dates)
]

normal_avg = normal_days.mean()
festival_avg = festival_days.mean()

festival_multiplier = festival_avg / normal_avg

print(f"Normal daily units:   {normal_avg:,.0f}")
print(f"Festival daily units: {festival_avg:,.0f}")
print(
    f"Festival multiplier:  {festival_multiplier:.2f}x"
)

if 3 <= festival_multiplier <= 4:
    print("PASS: Festival demand is realistically 3–4x normal.")
elif festival_multiplier >= 2:
    print("WARNING: Festival spike exists but is outside the 3–4x target.")
else:
    print("WARNING: Festival spike is too weak.")
# ============================================================
# 5. SUCCESSOR CANNIBALIZATION CHECK
# ============================================================

print("\n\n5. SUCCESSOR CANNIBALIZATION CHECK")
print("-" * 70)

products_with_successor = products[
    products["successor_model_id"].notna()
].copy()

cannibalization_results = []
for _, product in products_with_successor.iterrows():

    old_id = product["model_id"]
    new_id = product["successor_model_id"]

    old_sales = sales[
        sales["model_id"] == old_id
    ]

    new_sales = sales[
        sales["model_id"] == new_id
    ]

    # Find successor launch date
    successor_row = products[
        products["model_id"] == new_id
    ]

    if successor_row.empty:
        continue

    successor_launch_date = (
        successor_row["launch_date"].iloc[0]
    )

    # Sales before successor launch
    before = old_sales[
        old_sales["date"]
        < successor_launch_date
    ]

    # Sales after successor launch
    after = old_sales[
        old_sales["date"]
        >= successor_launch_date
    ]

    if len(before) == 0 or len(after) == 0:
        continue

    before_daily = (
        before["units_sold"].sum()
        / before["date"].nunique()
    )

    after_daily = (
        after["units_sold"].sum()
        / after["date"].nunique()
    )

    if before_daily <= 0:
        continue

    decline = (
        1
        - after_daily / before_daily
    ) * 100

    cannibalization_results.append({

        "old_model": old_id,

        "successor": new_id,

        "successor_launch_date":
            successor_launch_date,

        "before_daily":
            before_daily,

        "after_daily":
            after_daily,

        "decline_pct":
            decline
    })

cannibalization_df = pd.DataFrame(
    cannibalization_results
)

if len(cannibalization_df) > 0:

    print(
        cannibalization_df
        .sort_values("decline_pct", ascending=False)
        .head(15)
        .round(2)
        .to_string(index=False)
    )

    average_decline = (
        cannibalization_df["decline_pct"]
        .mean()
    )

    print(
        f"\nAverage predecessor decline: "
        f"{average_decline:.2f}%"
    )

    if average_decline > 10:
        print(
            "PASS: Successor cannibalization is visible."
        )
    else:
        print(
            "WARNING: Cannibalization effect is weak."
        )

else:

    print(
        "WARNING: No valid successor relationships found."
    )


# ============================================================
# 6. SLOW-MOVING PRODUCTS
# ============================================================

print("\n\n6. SLOW-MOVING PRODUCT CHECK")
print("-" * 70)

product_sales = (
    sales
    .groupby("model_id")
    .agg(
        units_sold=("units_sold", "sum"),
        revenue=("revenue", "sum")
    )
    .sort_values("units_sold")
)

print(
    "\nBottom 10 products by units sold:"
)

print(
    product_sales
    .head(10)
    .to_string()
)

slow_threshold = product_sales[
    "units_sold"
].quantile(0.20)

slow_products = product_sales[
    product_sales["units_sold"] <= slow_threshold
]

slow_share = (
    len(slow_products)
    / len(product_sales)
    * 100
)

print(
    f"\nSlow-moving products: "
    f"{len(slow_products)}"
)

print(
    f"Share of product catalogue: "
    f"{slow_share:.2f}%"
)

if slow_share >= 15:
    print("PASS: There are slow-moving products.")
else:
    print("WARNING: Product portfolio may be too uniformly successful.")


# ============================================================
# 7. PRODUCT DISTRIBUTION CHECK
# ============================================================

print("\n\n7. PRODUCT PORTFOLIO CHECK")
print("-" * 70)

print(
    products["category"]
    .value_counts()
    .to_string()
)

print("\nPrice distribution:")

print(
    products["price"]
    .describe()
    .round(2)
    .to_string()
)

print("\nProducts by price band:")

price_bands = pd.cut(
    products["price"],
    bins=[
        0,
        10000,
        15000,
        25000,
        45000,
        75000,
        np.inf
    ],
    labels=[
        "<10k",
        "10k-15k",
        "15k-25k",
        "25k-45k",
        "45k-75k",
        "75k+"
    ]
)

print(
    price_bands
    .value_counts()
    .sort_index()
    .to_string()
)


# ============================================================
# 8. REVENUE / BUSINESS SCALE CHECK
# ============================================================

print("\n\n8. BUSINESS SCALE CHECK")
print("-" * 70)

total_units = sales["units_sold"].sum()
total_revenue = sales["revenue"].sum()

avg_daily_units = (
    sales
    .groupby("date")["units_sold"]
    .sum()
    .mean()
)

avg_daily_revenue = (
    sales
    .groupby("date")["revenue"]
    .sum()
    .mean()
)

annual_revenue = total_revenue

avg_monthly_revenue = (
    sales
    .groupby(
        sales["date"].dt.to_period("M")
    )["revenue"]
    .sum()
    .mean()
)

print(f"Total annual units:       {total_units:,.0f}")
print(f"Total annual revenue:     ₹{annual_revenue:,.0f}")
print(f"Average monthly revenue:  ₹{avg_monthly_revenue:,.0f}")
print(f"Average daily units:      {avg_daily_units:,.0f}")
print(f"Average daily revenue:    ₹{avg_daily_revenue:,.0f}")

revenue_per_store = (
    annual_revenue / stores["store_id"].nunique()
)

print(
    f"\nAverage annual revenue/store: "
    f"₹{revenue_per_store:,.0f}"
)

# Inventory budget
inventory_budget = 40_000_000

print(
    f"\nInventory budget: "
    f"₹{inventory_budget:,.0f}"
)

print(
    f"Inventory budget / annual revenue: "
    f"{inventory_budget / annual_revenue * 100:.2f}%"
)


# ============================================================
# 9. STORE MIX CHECK
# ============================================================

print("\n\n9. STORE DIFFERENTIATION CHECK")
print("-" * 70)

store_sales = (
    sales_stores
    .groupby(["city", "store_id"])
    .apply(
        lambda x: pd.Series({
            "units": x["units_sold"].sum(),
            "revenue": x["revenue"].sum(),
            "avg_phone_price": np.average(
                x["price"],
                weights=x["units_sold"]
            )
        }),
        include_groups=False
    )
    .reset_index()
)

print(
    store_sales
    .sort_values("avg_phone_price", ascending=False)
    .head(10)
    .round(2)
    .to_string(index=False)
)

print("\nLowest average selling-price stores:")

print(
    store_sales
    .sort_values("avg_phone_price")
    .head(10)
    .round(2)
    .to_string(index=False)
)


# ============================================================
# FINAL
# ============================================================

print("\n\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)