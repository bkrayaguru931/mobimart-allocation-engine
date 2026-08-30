````markdown
# MobiMart — Demand Forecasting & Inventory Allocation System

MobiMart is a demand forecasting and inventory allocation system designed to help a retail business distribute limited warehouse inventory across multiple stores.

The system combines **7-day demand forecasting, product lifecycle awareness, store-product fit, priority scoring, and constraint-aware allocation** to generate practical replenishment recommendations.

The final output identifies **which products should be allocated to which stores, how many units should be allocated, the expected allocation value, and the remaining unfilled demand**.

---

## 1. Problem Statement

MobiMart operates multiple retail stores selling a large portfolio of mobile phone models.

Every week, the business needs to answer:

- How much demand should we expect for each product at each store?
- Which stores are most likely to run out of stock?
- Which products deserve priority when inventory is limited?
- How should warehouse inventory be distributed across stores?
- How should product lifecycle status affect allocation decisions?
- How should store-specific preferences affect prioritization?
- How can allocation remain within warehouse inventory and business budget constraints?

A simple rule such as:

> "Send inventory to stores with the highest demand"

is insufficient because inventory is constrained and different products have different business value.

MobiMart therefore uses a multi-stage pipeline:

```text
Historical Sales
      │
      ▼
Demand Forecasting
      │
      ▼
Store / Product Context
      │
      ▼
Priority Scoring
      │
      ▼
Constraint-Aware Allocation
      │
      ▼
Allocation Recommendations
````

---

# 2. Key Features

### Demand Forecasting

* Generates a **7-day demand forecast**.
* Forecasts demand at the **store × product** level.
* Uses historical sales patterns and contextual information.
* Applies product lifecycle factors where applicable.

### Store Profiling

Store-specific product fit is incorporated into allocation priority.

Examples include:

* Premium-product affinity
* Budget-product affinity
* Neutral fallback for unknown combinations

This prevents the allocator from treating every store as identical.

### Product Lifecycle Awareness

Products can have lifecycle states such as:

* Normal
* Post-successor / EOL-related

Post-successor products are prevented from receiving fresh allocation.

### Priority Scoring

Each store-product combination receives a priority score based on factors such as:

* Forecast demand
* Stock gap
* Expected sales value
* Store-product fit
* Product lifecycle
* Stockout risk

### Constraint-Aware Allocation

The allocator respects important business constraints:

* Warehouse inventory availability
* Recommended allocation quantity
* Chain-level budget
* Product lifecycle restrictions

The allocator therefore cannot allocate more inventory than is available or recommended.

---

# 3. System Architecture

```text
                    ┌─────────────────────┐
                    │   Historical Sales  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Forecasting Engine  │
                    │     forecast.py     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Store Profiles    │
                    │  store_profile.py   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Priority Scoring   │
                    │     scoring.py      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Allocation Engine   │
                    │    allocator.py     │
                    └──────────┬──────────┘
                               │
                               ▼
              ┌──────────────────────────────────┐
              │      monday_allocation.csv       │
              │      weekly_forecast.csv         │
              └──────────────────────────────────┘
```

---

# 4. Project Structure

```text
MobiMart/
│
├── allocation/
│   ├── __init__.py
│   ├── allocator.py
│   ├── forecast.py
│   ├── scoring.py
│   └── store_profile.py
│
├── data/
│   └── raw/
│       ├── events.csv
│       ├── inventory.csv
│       ├── products.csv
│       ├── sales.csv
│       └── stores.csv
│
├── outputs/
│   ├── monday_allocation.csv
│   └── weekly_forecast.csv
│
├── scripts/
│   ├── generate_dataset.py
│   ├── generate_inventory.py
│   ├── run_allocation.py
│   └── validate_dataset.py
│
├── tests/
│   ├── test_allocator.py
│   ├── test_integration.py
│   ├── test_scoring.py
│   └── test_store_profile.py
│
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

# 5. Data

The project uses the following input datasets.

## `sales.csv`

Historical sales observations.

Key fields include:

```text
date
store_id
model_id
units_sold
selling_price
revenue
```

This dataset provides the historical demand signal used by the forecasting pipeline.

---

## `products.csv`

Product-level information such as:

* Product/model identifier
* Product price
* Lifecycle information
* Successor relationships

Lifecycle information is used to prevent inappropriate replenishment of products that have moved beyond their active selling lifecycle.

---

## `stores.csv`

Store-level information used by the allocation system.

Stores are treated individually rather than assuming that all stores have identical demand characteristics.

---

## `inventory.csv`

Current inventory information used to determine:

* Current stock
* Available warehouse inventory
* Stock gaps
* Allocation constraints

---

## `events.csv`

Contextual events that can influence demand forecasting.

---

# 6. Forecasting Pipeline

The forecasting module is implemented in:

```text
allocation/forecast.py
```

The pipeline produces a 7-day forecast for every relevant:

```text
store × model
```

combination.

The resulting forecast is written to:

```text
outputs/weekly_forecast.csv
```

The output contains forecast-related information including:

* `store_id`
* `model_id`
* `forecast_units`
* Lifecycle-related forecast information
* Other forecasting features used by the allocator

Example scale from the validated run:

```text
Forecast rows:       1,500
Forecast horizon:    7 days
Total forecast:      ~1,974 units
```

---

# 7. Store-Product Fit

The store profiling logic is implemented in:

```text
allocation/store_profile.py
```

The purpose of store profiling is to capture the fact that different stores can have different product preferences.

For example:

```text
Premium-oriented store
        │
        └── Higher fit for expensive products

Budget-oriented store
        │
        └── Higher fit for lower-priced products
```

The fit score is incorporated into the allocator's priority calculation.

Unknown store/product combinations receive a neutral fallback rather than causing the pipeline to fail.

---

# 8. Priority Scoring

Priority scoring is implemented in:

```text
allocation/scoring.py
```

The scoring layer combines business signals into a priority score for each allocation candidate.

Conceptually:

```text
Priority
   │
   ├── Demand
   ├── Stock Gap
   ├── Expected Sales Value
   ├── Stockout Risk
   ├── Store-Product Fit
   └── Lifecycle Status
```

The purpose is not simply to maximize forecast demand.

The system attempts to prioritize allocations where additional inventory is most useful from a business perspective.

---

# 9. Allocation Engine

The main allocation logic is implemented in:

```text
allocation/allocator.py
```

For every store-product combination, the allocator considers:

```text
Forecast Demand
       +
Current Stock
       +
Recommended Units
       +
Product Price
       +
Store Fit
       +
Lifecycle Status
       +
Business Constraints
       │
       ▼
Allocation Priority
```

The allocator then distributes available inventory according to priority while respecting the configured constraints.

---

# 10. Important Business Rules

## Warehouse Stock Constraint

The allocator must never distribute more units than are available in the warehouse.

```text
Total Allocated ≤ Available Warehouse Stock
```

---

## Recommended Allocation Constraint

An individual store-product allocation cannot exceed its recommended allocation quantity.

```text
Allocated Units ≤ Recommended Units
```

---

## Budget Constraint

The total allocation value must remain within the configured chain-level budget.

```text
Total Allocation Value ≤ Budget
```

---

## EOL / Successor Constraint

Products that are classified as post-successor are not given fresh allocation.

```text
post_successor
      │
      └── allocated_units = 0
```

This prevents scarce inventory from being invested into products that have already transitioned to successor models.

---

# 11. Running the Pipeline

From the project root:

```powershell
python scripts/run_allocation.py
```

The pipeline performs:

```text
1. Load input data
2. Generate 7-day forecast
3. Save weekly forecast
4. Run inventory allocator
5. Save allocation recommendations
6. Print allocation summary
7. Print store-level allocation summary
```

Expected output files:

```text
outputs/
├── weekly_forecast.csv
└── monday_allocation.csv
```

---

# 12. Running the Dataset Generation Scripts

If you need to regenerate the synthetic dataset:

```powershell
python scripts/generate_dataset.py
```

To generate inventory:

```powershell
python scripts/generate_inventory.py
```

To validate the dataset:

```powershell
python scripts/validate_dataset.py
```

These scripts are useful when reproducing the project from scratch.

---

# 13. Running Tests

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the complete test suite:

```powershell
python -m pytest -v
```

The project currently contains **20 automated tests** covering both individual components and real-data integration.

Latest validated result:

```text
20 passed in 29.86s
```

---

# 14. Test Coverage

The test suite covers the following areas.

### Allocator Tests

* Allocation does not exceed warehouse stock
* Allocation does not exceed budget
* Allocation does not exceed recommended units
* Post-successor products receive no fresh allocation
* Store profiles are integrated into allocation
* EOL status boundaries behave correctly

### Integration Tests

* Real-data pipeline produces the expected output scale
* Real-data allocation respects warehouse stock
* Real-data allocation respects recommended units
* Real-data allocation respects chain budget
* EOL products are not allocated
* Store profiles are applied
* Required business output columns are present
* Store/model combinations are unique

### Scoring Tests

* Price-band boundaries
* Store fit changes priority score
* Post-successor products receive lower priority than normal products

### Store Profile Tests

* Davangere budget affinity
* Bangalore premium affinity
* Neutral fallback for unknown combinations

---

# 15. Output Files

## `weekly_forecast.csv`

Contains the generated 7-day demand forecast.

The forecast is produced at the:

```text
store × model
```

level.

---

## `monday_allocation.csv`

Contains the final allocation recommendation.

Important business columns include:

```text
store_id
model_id
forecast_units
current_stock
stock_gap
allocated_units
allocation_value
priority_score
eol_status
reason
```

These fields make the output directly interpretable by a business user.

---

# 16. Example Allocation Output

A typical recommendation looks conceptually like:

```text
Store     Model      Forecast    Stock    Allocation    Priority
-----------------------------------------------------------------
BLR05     MOD054       13.16       14         4          High
BLR01     MOD057        4.39        3         3          High
BLR03     MOD057        7.00        7         2          High
BLR02     MOD039        7.94        4         7          High
```

The final output also provides a human-readable reason for the allocation decision.

For example:

```text
HIGH PRIORITY: stockout risk protects potential sales.
```

or:

```text
NORMAL REPLENISHMENT: forecast demand exceeds current stock.
```

---

# 17. Validated Pipeline Result

A complete run of the current pipeline produced:

```text
Forecast rows:              1,500
Total forecast units:       1,974.24

Allocated units:              352
Allocation value:        ₹9,396,000
Protected sales value:   ₹9,208,809
Unfilled demand value:   ₹7,893,542

Budget used:                  23.49%
Priority lines:                  772
Total allocation lines:       1,500
```

Lifecycle handling was also validated:

```text
Lifecycle Status       Lines       Allocated Units
---------------------------------------------------
normal                   450             352
post_successor         1,050               0
```

The results above are from the current generated dataset and are provided as an example of the pipeline's behavior, not as production performance benchmarks.

---

# 18. Design Principles

The project follows several important principles.

### Constraint First

The allocator should produce recommendations that are operationally feasible rather than mathematically attractive but impossible to execute.

### Business-Aware Scoring

Demand alone is not sufficient. Store fit, stockout risk, product lifecycle, and expected value are incorporated into prioritization.

### Lifecycle Awareness

Inventory should not automatically be pushed toward products that have already transitioned to successor models.

### Explainability

Each recommendation contains a reason so that an allocation decision can be understood and reviewed.

### Modular Architecture

Forecasting, scoring, store profiling, and allocation are separated into independent modules.

This makes the system easier to test and extend.

---

# 19. Reproducibility

To reproduce the project:

```powershell
# Clone the repository
git clone <repository-url>

# Enter the project
cd MobiMart

# Install dependencies
python -m pip install -r requirements.txt

# Run the pipeline
python scripts/run_allocation.py

# Run all tests
python -m pytest -v
```

---

# 20. Future Improvements

Potential extensions include:

* More advanced time-series forecasting models
* Forecast confidence intervals
* Automated model selection
* Multi-week allocation planning
* Store-level inventory capacity constraints
* Supplier lead-time modeling
* Safety-stock optimization
* Transfer optimization between stores
* Integer programming / linear programming optimization
* Service-level optimization
* Forecast accuracy monitoring
* Historical backtesting
* Production API and dashboard

These are intentionally outside the current implementation so that the core forecasting and allocation pipeline remains focused and testable.

---

# 21. Technology Stack

* **Python**
* **Pandas**
* **NumPy**
* **Pytest**
* CSV-based data pipeline

The project is structured as a modular Python application with automated unit and integration testing.

---

# 22. Quick Start

The shortest path to run the project is:

```powershell
python -m pip install -r requirements.txt
python scripts/run_allocation.py
python -m pytest -v
```

Successful execution should produce:

```text
outputs/weekly_forecast.csv
outputs/monday_allocation.csv
```

and the test suite should report:

```text
20 passed
```

---

## Author

**Babykrishna Rayaguru**

M.Tech — Computer Science & Engineering (Artificial Intelligence)

```

