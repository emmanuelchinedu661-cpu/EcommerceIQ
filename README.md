# EcommerceIQ: E-commerce & Home-Delivery Analytics (Port Harcourt)

An end-to-end analytics project for a multi-branch e-commerce business in Port Harcourt, Nigeria.
It covers the full pipeline: **SQL database → synthetic data → ETL → machine learning → interactive dashboard**,
plus a working **order tracker** and **store admin** so the app can run like a real store.

> All customers, orders and riders are **synthetic demo data**. Store and brand names are used for illustration only.

---

## Features

| Page | What it does |
|---|---|
| **Sales** | Revenue, orders and units KPIs; monthly revenue by category and by branch; store ranking; payment mix; top 10 products |
| **Customers** | RFM segmentation (Champion, Loyal, Regular, At Risk); recency vs spend; gender split and lifetime spend; top customers |
| **Logistics** | Delivery time, on-time rate and distance KPIs; branch performance; late-rate map by delivery zone; day × hour demand heatmap; rider leaderboard |
| **Order Tracker** | Search by customer name, phone, email or ID, or by order ID; see goods, rider, ETA, route map and tracking timeline. The delivery OTP is masked by default |
| **Store Admin** | Add customers (validated phone and email), place orders with a live price quote (nearest branch, distance-based delivery fee, stock check), and move orders through each stage. Delivery requires the customer's OTP |
| **Late-Delivery Predictor** | Predicts the probability of a late delivery from order details, with feature importance |

A sidebar **branch filter** applies to every page. Leave it empty to see all branches.

---

## Tech stack

- **Python 3.12**: pandas, NumPy
- **SQLite**: relational schema with foreign keys and indexes; parameterised queries throughout
- **scikit-learn**: preprocessing pipelines; Logistic Regression vs Gradient Boosting
- **Streamlit**: multi-page dashboard
- **Plotly**: interactive charts and OpenStreetMap maps

---

## How it works

```
schema.sql ─► seed.py ─► SQLite DB ─► pipeline.py ─► analytics tables ─► model.py ─► app.py
              (demo data)              (ETL)          (fact & dim tables)  (ML)       (dashboard)
```

1. **Seed** (`src/seed.py`): generates 1,500 customers, 40 riders, 120 products and 9,000 orders across
   3 branches and 10 delivery zones (Jan 2025 to today). Delivery times depend on distance, zone traffic,
   rush hour, rainy season, basket size, vehicle and rider skill, plus random real-world noise.
2. **Pipeline** (`src/pipeline.py`): extract → validate (data-quality checks) → transform → load.
   Builds `fact_sales`, `fact_delivery` (with engineered features) and `dim_customer_rfm`.
3. **Model** (`src/model.py`): trains two classifiers to predict late deliveries and keeps the one with the higher ROC-AUC.
4. **Store engine** (`src/store.py`): business logic for adding customers, quoting, placing and advancing orders.
   It is kept separate from the UI.

---

## Model results

| Model | ROC-AUC |
|---|---|
| Logistic Regression | 0.721 |
| **Gradient Boosting (selected)** | **0.826** |

- Late rate: **24.3%** of deliveries.
- Gradient Boosting performs better because lateness comes from **interacting** factors
  (long distance × rush hour × rainy season), which tree models capture and a linear model cannot.
- Features are limited to what is known **before** dispatch, so there is no target leakage.

---

## Getting started

```bash
# 1. Clone and enter the project
git clone https://github.com/emmanuelchinedu661-cpu/EcommerceIQ.git
cd EcommerceIQ

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Build the database, run the ETL and train the model
python run_all.py --reset

# 5. Launch the dashboard
streamlit run app.py
```

`python run_all.py` without `--reset` keeps your existing data, including customers and orders added
through Store Admin, and only re-runs the pipeline and model.

---

## Project structure

```
EcommerceIQ/
├── .streamlit/config.toml   # theme
├── assets/                  # logo and page icons
├── data/                    # SQLite database (generated)
├── db/schema.sql            # table definitions
├── models/                  # trained model (generated)
├── src/
│   ├── config.py            # paths, branches, delivery zones, order stages
│   ├── db.py                # connection and query helpers
│   ├── seed.py              # synthetic data generator
│   ├── pipeline.py          # ETL
│   ├── model.py             # late-delivery model
│   └── store.py             # store operations engine
├── app.py                   # Streamlit dashboard
├── run_all.py               # one-command build
└── requirements.txt
```

---

## Screenshots

_Add screenshots here, for example:_

```markdown
![Sales](assets/screenshots/sales.png)
![Logistics](assets/screenshots/logistics.png)
![Order Tracker](assets/screenshots/tracker.png)
```

---

## Credits

- Page icons: [Flaticon](https://www.flaticon.com) and [Icons8](https://icons8.com)
- UI icons: [Google Material Symbols](https://fonts.google.com/icons) (built into Streamlit)
- Map tiles: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors

---

## Author

**Imo Emmanuel Chinedu (Lex)**, Data Analyst & Developer, Port Harcourt, Nigeria
GitHub: [emmanuelchinedu661-cpu](https://github.com/emmanuelchinedu661-cpu)
