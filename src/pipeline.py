"""ETL: extract from SQLITE → validate → transform → load analytics tables."""

import pandas as pd

from db import get_conn, query

def extract():
    return {
        "orders": query("SELECT * FROM orders"),
        "items": query("SELECT * FROM order_items"),
        "products": query("SELECT * FROM products"),
        "deliv": query("SELECT * FROM deliveries"),
        "addr": query("SELECT * FROM addresses"),
        "riders": query("SELECT * FROM riders"),
        "branches": query("SELECT branch_id, name AS branch FROM branches"),
    }

def validate(d):
    checks  = {
        "orders without customer": d["orders"].customer_id.isna().sum(),
        "items with qty <= 0": (d["items"].quantity <= 0).sum(),
        "delivered before dispatch": (pd.to_datetime(d["deliv"].delivered_at)
                                      < pd.to_datetime(d["deliv"].dispatched_at)).sum(),
        "duplicate order ids": d["orders"].order_id.duplicated().sum(),
    }
    for name, n in checks.items():
        print(f" [{'OK ' if n == 0 else 'WARN'}] {name}: {n}")
    return checks

def transform(d):
    o = d["orders"].copy()
    o["order_date"] = pd.to_datetime(o.order_date)
    o = o.merge(d["branches"], on="branch_id", how="left")

    items = d["items"].merge(d["products"][["product_id", "category", "store"]], on="product_id")
    items["line_total"] = items.quantity * items.unit_price

    sales = items.merge(o[["order_id", "order_date", "branch"]], on="order_id")
    sales["day"] = sales.order_date.dt.date
    fact_sales = (sales.groupby(["day", "branch", "store", "category"], as_index=False)
                  .agg(revenue=("line_total", "sum"), units=("quantity", "sum"),
                       orders=("order_id", "nunique")))

    dv = d["deliv"].merge(o[["order_id", "order_date", "address_id", "branch", "status"]], on="order_id")
    dv = dv.merge(d["addr"][["address_id", "area"]], on="address_id")
    dv = dv.merge(d["riders"][["rider_id", "vehicle"]], on="rider_id")
    for col in ["dispatched_at", "eta", "delivered_at"]:
        dv[col] = pd.to_datetime(dv[col])
    dv["delivery_mins"] = (dv.delivered_at - dv.dispatched_at).dt.total_seconds() / 60
    dv["is_late"] = (dv.delivered_at > dv.eta).astype("Int64").where(dv.delivered_at.notna())
    n_items = items.groupby("order_id").quantity.sum().rename("n_items")
    dv = dv.merge(n_items, on="order_id", how="left")
    dv["order_hour"] = dv.order_date.dt.hour
    dv["order_month"] = dv.order_date.dt.month
    dv["order_dow"] = dv.order_date.dt.dayofweek
    dv["promised_mins"] = (dv.eta - dv.dispatched_at).dt.total_seconds() / 60
    fact_delivery = dv.drop(columns=["address_id"])

    snap = o.order_date.max() + pd.Timedelta(days=1)
    rfm = (o.groupby("customer_id")
           .agg(last_order=("order_date", "max"), frequency=("order_id", "count"),
                monetary=("total_amount", "sum")).reset_index())
    rfm["recency_days"] = (snap - rfm.last_order).dt.days
    rfm["R"] = pd.qcut(rfm.recency_days.rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm.frequency.rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["M"] = pd.qcut(rfm.monetary.rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    score = rfm.R + rfm.F + rfm.M
    rfm["segment"] = pd.cut(score, [0, 5, 8, 10, 12],
                            labels=["At Risk", "Regular", "Loyal", "Champion"]).astype(str)
    return  {"fact_sales": fact_sales, "fact_delivery": fact_delivery, "dim_customer_rfm": rfm}

def load(tables):
    with get_conn() as c:
        for name, df in tables.items():
            df.to_sql(name, c, if_exists="replace", index=False)
            print(f" loaded {name}: {len(df):,} rows")

def run():
    print("Extract"); d = extract()
    print("Validate"); validate(d)
    print("Transform"); t = transform(d)
    print("Load"); load(t)

if __name__ == "__main__":
    run()