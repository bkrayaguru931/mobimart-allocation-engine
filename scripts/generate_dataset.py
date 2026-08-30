import os
import random

import numpy as np
import pandas as pd
from faker import Faker


# ============================================================
# CONFIG
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
Faker.seed(SEED)

OUTPUT_DIR = "data/raw"

START_DATE = pd.Timestamp("2025-08-01")
END_DATE = pd.Timestamp("2026-07-31")

DATES = pd.date_range(
    START_DATE,
    END_DATE,
    freq="D"
)


# ============================================================
# HELPERS
# ============================================================

def weighted_choice(options, weights):
    return random.choices(
        options,
        weights=weights,
        k=1
    )[0]


def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(value, maximum)
    )


# ============================================================
# 1. STORES
# ============================================================

def generate_stores():

    store_definitions = [

        # Bangalore
        ("BLR01", "Bangalore", "Tier-1", "Jayanagar", "Premium"),
        ("BLR02", "Bangalore", "Tier-1", "Koramangala", "Premium"),
        ("BLR03", "Bangalore", "Tier-1", "Whitefield", "Premium"),
        ("BLR04", "Bangalore", "Tier-1", "Indiranagar", "Premium"),
        ("BLR05", "Bangalore", "Tier-1", "Mall", "Premium"),
        ("BLR06", "Bangalore", "Tier-1", "Residential", "Mixed"),
        ("BLR07", "Bangalore", "Tier-1", "Electronic Market", "Mixed"),
        ("BLR08", "Bangalore", "Tier-1", "Outer Ring Road", "Mixed"),

        # Tier 2
        ("MYS01", "Mysore", "Tier-2", "City Center", "Mixed"),
        ("MYS02", "Mysore", "Tier-2", "Residential", "Budget"),

        ("HUB01", "Hubli", "Tier-2", "City Center", "Mixed"),
        ("HUB02", "Hubli", "Tier-2", "Market", "Budget"),

        ("TUM01", "Tumkur", "Tier-2", "City Center", "Budget"),
        ("TUM02", "Tumkur", "Tier-2", "Residential", "Budget"),

        ("DAV01", "Davangere", "Tier-2", "City Center", "Budget"),
        ("DAV02", "Davangere", "Tier-2", "Market", "Budget"),

        ("BEL01", "Belgaum", "Tier-2", "City Center", "Mixed"),

        ("MAN01", "Mangalore", "Tier-2", "Mall", "Premium"),
        ("MAN02", "Mangalore", "Tier-2", "Residential", "Mixed"),

        ("SHI01", "Shivamogga", "Tier-2", "City Center", "Budget"),
        ("UDU01", "Udupi", "Tier-2", "City Center", "Mixed"),
        ("KAL01", "Kalaburagi", "Tier-2", "Market", "Budget"),

        # Tier 3
        ("HOS01", "Hassan", "Tier-3", "City Center", "Budget"),
        ("CHI01", "Chitradurga", "Tier-3", "Market", "Budget"),
        ("KOP01", "Koppal", "Tier-3", "Market", "Budget"),
    ]

    city_income = {

        "Bangalore": 85000,
        "Mysore": 50000,
        "Hubli": 45000,
        "Tumkur": 40000,
        "Davangere": 38000,
        "Belgaum": 43000,
        "Mangalore": 60000,
        "Shivamogga": 42000,
        "Udupi": 50000,
        "Kalaburagi": 35000,
        "Hassan": 37000,
        "Chitradurga": 34000,
        "Koppal": 32000,
    }

    location_multiplier = {

        # Bangalore
        "Jayanagar": 1.25,
        "Koramangala": 1.40,
        "Whitefield": 1.35,
        "Indiranagar": 1.40,
        "Mall": 1.50,
        "Residential": 0.90,
        "Electronic Market": 1.20,
        "Outer Ring Road": 0.95,

        # Tier-2 / Tier-3
        "City Center": 1.15,
        "Market": 1.00,
    }

    stores = []

    for (
        store_id,
        city,
        tier,
        location,
        positioning
    ) in store_definitions:

        if city == "Bangalore":

            base_footfall = random.randint(
                900,
                1500
            )

            store_size = random.randint(
                1500,
                3000
            )

        else:

            base_footfall = random.randint(
                350,
                850
            )

            store_size = random.randint(
                800,
                1800
            )

        footfall = int(
            base_footfall
            * location_multiplier[location]
        )

        if positioning == "Premium":

            premium_affinity = random.uniform(
                0.75,
                0.95
            )

            budget_affinity = random.uniform(
                0.15,
                0.35
            )

        elif positioning == "Budget":

            premium_affinity = random.uniform(
                0.05,
                0.20
            )

            budget_affinity = random.uniform(
                0.75,
                0.95
            )

        else:

            premium_affinity = random.uniform(
                0.40,
                0.65
            )

            budget_affinity = random.uniform(
                0.45,
                0.70
            )

        stores.append({

            "store_id": store_id,

            "city": city,

            "tier": tier,

            "location_type": location,

            "positioning": positioning,

            "store_size_sqft": store_size,

            "daily_footfall": footfall,

            "catchment_income": city_income[city],

            "premium_affinity": round(
                premium_affinity,
                3
            ),

            "budget_affinity": round(
                budget_affinity,
                3
            ),
        })

    return pd.DataFrame(stores)


# ============================================================
# 2. PRODUCT GENERATIONS
# ============================================================

def generate_products():

    # Each family represents a real-world phone line.
    # Successive generations cannibalize previous generations.

    families = [

        # Keypad
        ("Nokia", "Keypad", "Keypad", 7000),
        ("Samsung", "Guru", "Keypad", 6500),
        ("Lava", "Keypad", "Keypad", 7500),

        # Budget
        ("Samsung", "Galaxy M", "Budget", 12000),
        ("Xiaomi", "Redmi Note", "Budget", 14000),
        ("Realme", "C Series", "Budget", 11000),
        ("Vivo", "Y Series", "Budget", 13000),

        # Mid-range
        ("Samsung", "Galaxy A", "Mid-range", 24000),
        ("Vivo", "V Series", "Mid-range", 28000),
        ("OnePlus", "Nord", "Mid-range", 26000),

        # Upper-mid
        ("Xiaomi", "Redmi Pro", "Upper-mid", 28000),
        ("Realme", "GT", "Upper-mid", 32000),
        ("Oppo", "Reno", "Upper-mid", 35000),
        ("Motorola", "Edge", "Upper-mid", 35000),

        # Premium
        ("OnePlus", "Number", "Premium", 50000),
        ("Nothing", "Phone", "Premium", 42000),

        # Flagship
        ("Samsung", "Galaxy S", "Flagship", 85000),
        ("Samsung", "Galaxy Z", "Flagship", 120000),
        ("Apple", "iPhone", "Flagship", 95000),
    ]

    products = []

    model_counter = 1

    # We want approximately 60 products.
    # Each family gets 3–4 generations.

    for family_index, (
        brand,
        family_name,
        category,
        base_price
    ) in enumerate(families):

        generations = 3

        # Some important families get 4 generations
        if family_index < 3:
            generations = 4
        else:
            generations = 3

        for generation in range(generations):

            # Generate launch dates across the dataset.
            #
            # Older generation:
            # Aug–Oct 2025
            #
            # New generation:
            # Jan–Jun 2026

            launch_offsets = {
                0: random.randint(-150, -60),
                1: random.randint(20, 100),
                2: random.randint(130, 220),
                3: random.randint(230, 310),
            }

            launch_date = (
                START_DATE
                + pd.Timedelta(
                    days=launch_offsets[generation]
                )
            )

            # Small yearly price progression
            price = base_price * (
                1 + generation * 0.04
            )

            # Round to realistic Indian pricing
            price = int(
                round(price / 500)
                * 500
            )

            model_id = (
                f"MOD{model_counter:03d}"
            )

            model_name = (
                f"{brand} "
                f"{family_name} "
                f"{generation + 1}"
            )

            products.append({

                "model_id": model_id,

                "brand": brand,

                "family": family_name,

                "model_name": model_name,

                "category": category,

                "price": price,

                "launch_date": launch_date,

                "generation": generation + 1,
            })

            model_counter += 1

    products_df = pd.DataFrame(products)

    # ========================================================
    # Assign successor models
    # ========================================================

    products_df[
        "successor_model_id"
    ] = None

    products_df[
        "successor_launch_date"
    ] = pd.NaT

    for family in products_df["family"].unique():

        family_products = (
            products_df[
                products_df["family"] == family
            ]
            .sort_values("generation")
        )

        ids = family_products[
            "model_id"
        ].tolist()

        for i in range(len(ids) - 1):

            current_id = ids[i]
            successor_id = ids[i + 1]

            successor_date = family_products[
                family_products["model_id"]
                == successor_id
            ]["launch_date"].iloc[0]

            products_df.loc[
                products_df["model_id"]
                == current_id,
                "successor_model_id"
            ] = successor_id

            products_df.loc[
                products_df["model_id"]
                == current_id,
                "successor_launch_date"
            ] = successor_date

    # ========================================================
    # Lifecycle stage
    # ========================================================

    today = END_DATE

    def lifecycle(row):

        today = END_DATE

        launch_date = row["launch_date"]

        successor_date = row[
            "successor_launch_date"
        ]

        age = (
            today - launch_date
        ).days

        # ---------------------------------------------
        # Product has not launched yet
        # ---------------------------------------------

        if age < 0:

            return "Upcoming"

        # ---------------------------------------------
        # Successor exists
        # ---------------------------------------------

        if not pd.isna(successor_date):

            days_to_successor = (
                successor_date - today
            ).days

            # Successor already launched
            if days_to_successor < 0:

                return "Post-Successor"

            # Successor launches within 30 days
            if days_to_successor <= 30:

                return "EOL-Risk"

            # Successor launches within 90 days
            if days_to_successor <= 90:

                return "Late-Life"

        # ---------------------------------------------
        # Normal lifecycle
        # ---------------------------------------------

        if age < 45:

            return "Launch"

        if age < 90:

            return "Growth"

        if age < 180:

            return "Mature"

        return "Late-Life"
    products_df[
        "lifecycle_stage"
    ] = products_df.apply(
        lifecycle,
        axis=1
    )

    return products_df
# ============================================================
# 3. FESTIVAL EVENTS
# ============================================================

def generate_events():

    events = []

   
    for date in pd.date_range(
        "2025-10-01",
        "2025-10-12"
    ):

        events.append({
            "date": date,
            "event_type": "Dussehra",
            "demand_multiplier": 4.2,
        })

    
    for date in pd.date_range(
        "2025-10-15",
        "2025-11-15"
    ):

        if pd.Timestamp("2025-10-22") <= date <= pd.Timestamp("2025-11-10"):
            multiplier = 4.8
        else:
            multiplier = 5.2

        events.append({
            "date": date,
            "event_type": "Diwali",
            "demand_multiplier": multiplier,
        })

    # --------------------------------------------------------
    # New Year
    # --------------------------------------------------------

    for date in pd.date_range(
        "2025-12-26",
        "2026-01-02"
    ):

        events.append({
            "date": date,
            "event_type": "New Year",
            "demand_multiplier": 1.5,
        })

    # --------------------------------------------------------
    # Ugadi
    # --------------------------------------------------------

    for date in pd.date_range(
        "2026-03-15",
        "2026-03-25"
    ):

        events.append({
            "date": date,
            "event_type": "Ugadi",
            "demand_multiplier": 1.8,
        })

    return pd.DataFrame(events)

# ============================================================
# 4. LIFECYCLE DEMAND
# ============================================================

def lifecycle_multiplier(days_since_launch):

    if days_since_launch < 0:

        return 0.0

    # Launch
    if days_since_launch <= 14:

        return 0.65

    # Growth
    if days_since_launch <= 42:

        return 1.00

    # Peak
    if days_since_launch <= 70:

        return 1.25

    # Mature
    if days_since_launch <= 120:

        return 1.05

    # Decline
    if days_since_launch <= 180:

        return 0.75

    # Late life
    return 0.45

# ============================================================
# 5. SUCCESSOR CANNIBALIZATION
# ============================================================
def cannibalization_multiplier(
    current_date,
    successor_launch_date
):

    if pd.isna(successor_launch_date):
        return 1.0

    days_from_successor = (
        current_date - successor_launch_date
    ).days

    # More than 60 days before successor
    if days_from_successor < -60:
        return 1.0

    # Rumour phase
    if -60 <= days_from_successor < -30:
        return 0.98

    # Confirmed / approaching
    if -30 <= days_from_successor < 0:
        return 0.95

    # Successor just launched
    if 0 <= days_from_successor < 30:
        return 0.85

    # 1–2 months after
    if 30 <= days_from_successor < 60:
        return 0.75

    # 2–3 months after
    if 60 <= days_from_successor < 90:
        return 0.68

    # Long after successor
    return 0.62

# ============================================================
# 6. STORE × PRODUCT AFFINITY
# ============================================================

def calculate_affinity(
    store,
    product
):

    price = product["price"]

    premium = store[
        "premium_affinity"
    ]

    budget = store[
        "budget_affinity"
    ]

    # --------------------------------------------------------
    # Budget
    # --------------------------------------------------------

    if price < 15000:

        affinity = budget

    # --------------------------------------------------------
    # Mid-range
    # --------------------------------------------------------

    elif price < 40000:

        affinity = (
            budget * 0.45
            + premium * 0.35
            + 0.20
        )

    # --------------------------------------------------------
    # Premium
    # --------------------------------------------------------

    else:

        affinity = premium

    # --------------------------------------------------------
    # Brand effects
    # --------------------------------------------------------

    brand_multiplier = {

        "Samsung": 1.15,

        "Apple": 0.85,

        "OnePlus": 1.05,

        "Xiaomi": 1.10,

        "Vivo": 1.08,

        "Oppo": 1.00,

        "Realme": 1.08,

        "Motorola": 0.95,

        "Nothing": 0.80,
    }

    affinity *= brand_multiplier.get(
        product["brand"],
        1.0
    )

    return max(
        0.05,
        affinity
    )


# ============================================================
# 7. GENERATE SALES
# ============================================================
def generate_sales(
    stores_df,
    products_df,
    events_df
):

    sales = []

    # ========================================================
    # EVENT LOOKUP
    # ========================================================

    event_lookup = dict(
        zip(
            events_df["date"],
            events_df["demand_multiplier"]
        )
    )

    # ========================================================
    # BRAND POPULARITY
    # ========================================================

    brand_popularity = {

        "Samsung": 1.15,
        "Apple": 0.85,
        "OnePlus": 1.05,
        "Xiaomi": 1.10,
        "Vivo": 1.08,
        "Oppo": 1.00,
        "Realme": 1.08,
        "Motorola": 0.95,
        "Nothing": 0.75,
    }

    # ========================================================
    # STORE LOOP
    # ========================================================

    for _, store in stores_df.iterrows():

        print(
            f"Generating sales for "
            f"{store['store_id']}..."
        )

        # ====================================================
        # PRODUCT LOOP
        # ====================================================

        for _, product in products_df.iterrows():

            # ------------------------------------------------
            # Store × Product affinity
            # ------------------------------------------------

            affinity = calculate_affinity(
                store,
                product
            )

            price = product["price"]

            # ------------------------------------------------
            # Price sensitivity
            # ------------------------------------------------

            if price < 10000:

                price_factor = 1.35

            elif price < 15000:

                price_factor = 1.25

            elif price < 25000:

                price_factor = 1.05

            elif price < 45000:

                price_factor = 0.90

            elif price < 75000:

                price_factor = 0.75

            else:

                price_factor = 0.60

            # ------------------------------------------------
            # Footfall
            # ------------------------------------------------

            footfall_factor = (
                store["daily_footfall"]
                / 1000
            )

            # ------------------------------------------------
            # Base demand
            # ------------------------------------------------

            base_demand = (

                footfall_factor

                * affinity

                * price_factor

                * random.uniform(
                    0.55,
                    1.25
                )
            )

            # ------------------------------------------------
            # Brand popularity
            # ------------------------------------------------

            base_demand *= (
                brand_popularity.get(
                    product["brand"],
                    1.0
                )
            )

            # ------------------------------------------------
            # Product lifecycle dates
            # ------------------------------------------------

            launch_date = product[
                "launch_date"
            ]

            successor_date = product[
                "successor_launch_date"
            ]

            # =================================================
            # DAILY SALES LOOP
            # =================================================

            for date in DATES:

                # ------------------------------------------------
                # Lifecycle
                # ------------------------------------------------

                days_since_launch = (
                    date - launch_date
                ).days

                lifecycle = (
                    lifecycle_multiplier(
                        days_since_launch
                    )
                )

                # Product not yet launched / completely dead
                if lifecycle <= 0:

                    continue

                # ------------------------------------------------
                # Festival
                # ------------------------------------------------

                festival_multiplier = (
                    event_lookup.get(
                        date,
                        1.0
                    )
                )

                # ------------------------------------------------
                # Weekend
                # ------------------------------------------------

                weekend_multiplier = (
                    1.20
                    if date.dayofweek >= 5
                    else 1.0
                )

                # ------------------------------------------------
                # Successor cannibalization
                # ------------------------------------------------

                cannibalization = (
                    cannibalization_multiplier(
                        date,
                        successor_date
                    )
                )

                # ------------------------------------------------
                # Random demand noise
                # ------------------------------------------------

                noise = np.random.lognormal(
                    mean=0,
                    sigma=0.22
                )

                # =================================================
                # EXPECTED DEMAND
                # =================================================

                expected_demand = (

                    base_demand

                    * lifecycle

                    * cannibalization

                    * festival_multiplier

                    * weekend_multiplier

                    * noise
                )

                # ------------------------------------------------
                # Generate integer demand
                # ------------------------------------------------

                units = np.random.poisson(
                    max(
                        expected_demand,
                        0
                    )
                )

                units = int(units)

                # ------------------------------------------------
                # Ignore zero-demand rows
                # ------------------------------------------------

                if units <= 0:

                    continue

                # ------------------------------------------------
                # Revenue
                # ------------------------------------------------

                revenue = (
                    units
                    * price
                )

                # ------------------------------------------------
                # Save observation
                # ------------------------------------------------

                sales.append({

                    "date":
                        date,

                    "store_id":
                        store["store_id"],

                    "model_id":
                        product["model_id"],

                    "units_sold":
                        units,

                    "selling_price":
                        price,

                    "revenue":
                        revenue,
                })

    # ========================================================
    # RETURN DATAFRAME
    # ========================================================

    return pd.DataFrame(sales)
# ============================================================
# 8. MAIN
# ============================================================

def main():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    print(
        "\nGenerating stores..."
    )

    stores_df = generate_stores()

    print(
        "Generating products..."
    )

    products_df = generate_products()

    print(
        "Generating events..."
    )

    events_df = generate_events()

    print(
        "Generating sales..."
    )

    sales_df = generate_sales(
        stores_df,
        products_df,
        events_df
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    stores_df.to_csv(
        f"{OUTPUT_DIR}/stores.csv",
        index=False
    )

    products_df.to_csv(
        f"{OUTPUT_DIR}/products.csv",
        index=False
    )

    events_df.to_csv(
        f"{OUTPUT_DIR}/events.csv",
        index=False
    )

    sales_df.to_csv(
        f"{OUTPUT_DIR}/sales.csv",
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("MOBIMART V2 DATASET GENERATED")
    print("=" * 70)

    print(
        f"\nStores: "
        f"{stores_df['store_id'].nunique()}"
    )

    print(
        f"Products: "
        f"{products_df['model_id'].nunique()}"
    )

    print(
        f"Sales rows: "
        f"{len(sales_df):,}"
    )

    print(
        f"Date range: "
        f"{START_DATE.date()} → "
        f"{END_DATE.date()}"
    )

    print(
        f"\nTotal units sold: "
        f"{sales_df['units_sold'].sum():,}"
    )

    print(
        f"Total revenue: "
        f"₹{sales_df['revenue'].sum():,.0f}"
    )

    print(
        "\nProduct lifecycle:"
    )

    print(
        products_df[
            "lifecycle_stage"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\nSuccessor relationships:"
    )

    print(
        products_df[
            "successor_model_id"
        ]
        .notna()
        .sum()
    )

    print(
        "\nFiles created:"
    )

    print(
        f"  {OUTPUT_DIR}/stores.csv"
    )

    print(
        f"  {OUTPUT_DIR}/products.csv"
    )

    print(
        f"  {OUTPUT_DIR}/events.csv"
    )

    print(
        f"  {OUTPUT_DIR}/sales.csv"
    )


if __name__ == "__main__":

    main()