import random
from datetime import datetime, timedelta


import numpy as np
import pandas as pd

from config import BRANCHES, ZONES, STATUSES
from db import get_conn, init_db

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

N_CUSTOMERS, N_RIDERS, N_ORDERS = 1500, 40 ,9000
START = datetime(2025, 1, 1)
END = datetime.now().replace(second=0, microsecond=0)

MALE_NAMES = ["Chinedu", "Emeka", "Ifeanyi", "Obinna", "Chukwudi", "Ikenna", "Nnamdi", "Kingsley",
              "Victor", "Samuel", "Daniel", "Michael", "David", "Godwin", "Felix", "Dagogo", "Tekena",
              "Tunde", "Segun", "Kunle", "Babajide", "Chidi", "Ebuka", "Peter", "John", "Joseph",
              "Paul", "Stanley", "Henry", "Anthony"]
FEMALE_NAMES = ["Ngozi", "Chioma", "Amaka", "Nkechi", "Adaeze", "Chiamaka", "Uloma", "Ifeoma",
                "Blessing", "Precious", "Grace", "Joy", "Esther", "Ruth", "Ibiso", "Funmilayo",
                "Yetunde", "Kemi", "Bisi", "Mary", "Deborah", "Rebecca", "Comfort", "Patience",
                "Gloria", "Juliet", "Ogechi", "Obiageli", "Nneka", "Ifunnaya"]
SURNAMES = ["Okafor", "Amadi", "Briggs", "Nwosu", "George", "Iyalla", "Eze", "Ogbonna", "Horsfall",
            "Okoro", "West", "Jack", "Dappa", "Obi", "Igwe", "Okeke", "Nwankwo", "Nwachukwu",
            "Okonkwo", "Wokoma", "Harry", "Pepple", "Kalu", "Okpara", "Adeyemi", "Bello", "Ogunleye",
            "Lawson", "Abbey", "Ekeh"]
STREETS = ["Aba Road", "Olu Obasanjo Rd", "Stadium Rd", "Ikwerre Rd", "Peter Odili Rd",
           "Tombia St", "Elekahia Rd", "Woji Rd", "Okporo Rd", "Rumuola Rd"]

CATALOG = {
    "Electronic":     (["Shoprite Tech", "Slot", "Samsung Store"], 25000, 650000),
    "Fashion":        (["Mr Price", "Woodin", "Jumia Fashion Hub"], 4000, 60000),
    "Groceries":      (["Shoprite", "Spar"], 800, 25000),
    "Home & Kitchen": (["HomeStyle", "Game"], 3000, 180000),
    "Beauty":         (["Beauty Zone", "Mr Price"], 1500, 35000),
    "Sports":         (["Sports Arena", "Decathlon PH"], 5000, 150000),
}
PAYMENT = ["Bank Card", "Bank Transfer", "Pay on Delivery", "USSD"]
VEHICLES = {"Motorbike": 1.0, "Tricycle": 1.15, "Van": 1.25}
QTY_RULES = {
    "Groceries":             ([1, 2, 3, 4, 5, 6], [.20, .25, .20, .15, .10, .10]),
    "Beauty":                ([1, 2, 3],           [.60, .30, .10]),
    "Fashion":               ([1, 2],              [.80, .20]),
    "Home & Kitchen":        ([1, 2],              [.90, .10]),
    "Sports":                ([1, 2],              [.90, .10]),
    "Electronic":            ([1, 2],              [.97, .03]),
}

def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians,(lat1,lon1,lat2,lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))

def unique_people(n):
    """Return n unique (full_name, gender) pairs; gender always matches the first name."""
    pool = [(f"{f} {s}", "Male") for f in MALE_NAMES for s in SURNAMES] + \
           [(f"{f} {s}", "Female") for f in FEMALE_NAMES for s in SURNAMES]
    return random.sample(pool, n)

PEOPLE = unique_people(N_CUSTOMERS + N_RIDERS)

def make_customers():
    rows, addrs, aid = [], [], 1
    for i, (name, gender) in enumerate(PEOPLE[:N_CUSTOMERS], start=1):
        cid = f"CUS-{i:05d}"
        rows.append((cid, name, gender, f"080{rng.integers(10_000_000, 99_999_999)}",
                     f"{name.lower().replace(' ', '.')}{i}@mail.com"))
        for j, label in enumerate(["Home", "Office"][: rng.choice([1, 2], p=[0.7, 0.3])]):
            area = random.choice(list(ZONES))
            lat, lon, _ = ZONES[area]
            addrs.append((aid, cid, label, f"{rng.integers(1, 120)} {random.choice(STREETS)}",
                          area, "Port Harcourt", "Rivers",
                          lat + rng.normal(0, 0.006), lon + rng.normal(0, 0.006), int(j == 0)))
            aid += 1

    return rows, addrs

def make_products():
    rows, pid = [], 1
    for cat, (stores, lo, hi) in CATALOG.items():
        for k in range(20):
            price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), -1)
            rows.append((f"PRD-{pid:04d}", f"{cat} item {k + 1}", cat, random.choice(stores),
                         price, int(rng.integers(5, 300))))
            pid += 1

    return rows

def make_riders():
    names = [name for name, _ in PEOPLE[N_CUSTOMERS:]]
    return [(f"RDR-{i:03d}", names[i - 1],
             f"070{rng.integers(10_000_000, 99_999_999)}",
             random.choices(list(VEHICLES), weights=[0.7, 0.2, 0.1])[0])
            for i in range(1, N_RIDERS + 1)]

def make_orders(customers, addresses, products, riders):
    addr_df = pd.DataFrame(addresses, columns=["address_id", "customer_id", "label", "street",
                                               "area", "city", "state", "lat", "lon", "is_default"])
    by_cust = addr_df.groupby("customer_id")
    prod_df = pd.DataFrame(products, columns=["product_id", "name", "category", "stores", "price", "stock"])
    rider_skill = {r[0]: rng.normal(1.0, 0.12) for r in riders}
    loyalty = np.clip(rng.pareto(1.5, N_CUSTOMERS) + 1, 1, 12)
    cust_ids = [c[0] for c in customers]
    span = (END - START).total_seconds()

    orders, items, delivs, events = [], [], [], []
    for n in range(1, N_ORDERS + 1):
        oid = f"ORD-{n:06d}"
        cid = random.choices(cust_ids, weights=loyalty)[0]
        addr = by_cust.get_group(cid).sample(1, random_state=n).iloc[0]
        if n > N_ORDERS - 60:
            t = END - timedelta(minutes=float(rng.uniform(5, 240)))
        else:
            t = START + timedelta(seconds=float(rng.uniform(0, span - 86400)))
            t = t.replace(hour=int(rng.choice(range(8, 22))))

        basket = prod_df.sample(int(rng.choice([1, 2, 3, 4, 5], p=[.4, .25, .17, .1, .08])), random_state=n)
        subtotal = 0
        for _, p in basket.iterrows():
            qtys, chances = QTY_RULES[p.category]
            q = int(rng.choice(qtys, p=chances))
            items.append((oid, p.product_id, q, p.price))
            subtotal += q * p.price

        branch_id, dist = min(((b, haversine_km(v[2], v[3], addr.lat, addr.lon)) for b, v in BRANCHES.items()),
                              key=lambda x: x[1])
        dist = float(dist) * 1.35 + 1.0
        fee = round(1000 + 250 * dist, -1)
        rider = random.choice(riders)

        packed = t + timedelta(minutes=float(rng.uniform(10, 45)))
        dispatched = packed + timedelta(minutes=float(rng.uniform(5, 40)))
        traffic = ZONES[addr.area][2]
        rush = 1.35 if t.hour in (7, 8, 16, 17, 18) else 1.0
        rain = 1.25 if t.month in (5, 6, 7, 8, 9) else 1.0
        bulky = 1 + 0.04 * len(basket)
        mins = ((8 + 4.2 * dist) * traffic * rush * rain * bulky * VEHICLES[rider[3]] * rider_skill[rider[0]]
                * rng.lognormal(0, 0.25))
        eta = dispatched + timedelta(minutes=(10 + 4.2 * dist) * 2.1)
        delivered = dispatched + timedelta(minutes=float(mins))

        steps = [t, packed, dispatched, dispatched + timedelta(minutes=5), delivered]
        done = [s for s in steps if s <=END]
        status = STATUSES[len(done) - 1]
        if rng.random() < 0.02 and status == "Delivered":
            status = "Returned"

        orders.append((oid, cid, int(addr.address_id), branch_id, t.isoformat(sep=" ", timespec="minutes"),
                       random.choice(PAYMENT), round(subtotal + fee, 2), fee, status))
        delivs.append((oid, rider[0],
                       dispatched.isoformat(sep=" ", timespec="minutes") if dispatched <= END else None,
                       eta.isoformat(sep=" ", timespec="minutes"),
                       delivered.isoformat(sep=" ", timespec="minutes") if delivered <= END else None,
                       round(dist, 2), f"{rng.integers(1000, 9999)}"))
        for s, ts in zip(STATUSES, done):
            events.append((oid, s, ts.isoformat(sep=" ", timespec="minutes"), f"{s} - {addr.area}"))
        if status == "Returned":
            events.append((oid, "Returned", (delivered + timedelta(days=2)).isoformat(sep=" ", timespec="minutes"),
                           "Customer return"))
    return orders, items, delivs, events

def add_signup_dates(customers, orders):
    """Signup falls between launch and the customer's first order"""
    first_order = {}
    for o in orders:
        t = datetime.fromisoformat(o[4])
        first_order[o[1]] = min(first_order.get(o[1], t), t)
    out = []
    for c in customers:
        latest = first_order.get(c[0], END)
        signup = START + timedelta(seconds=float(rng.uniform(0, (latest - START).total_seconds()))) #type: ignore
        out.append((*c, signup.date().isoformat()))
    return out
def run():
    init_db(reset=True)
    customers, addresses = make_customers()
    products, riders = make_products(), make_riders()
    orders, items, delivs, events = make_orders(customers, addresses, products, riders)
    customers = add_signup_dates(customers, orders)
    with get_conn() as c:
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)
        c.executemany("INSERT INTO addresses VALUES (?,?,?,?,?,?,?,?,?,?)", addresses)
        c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products)
        c.executemany("INSERT INTO branches VALUES (?,?,?,?,?)", [(k, *v) for k, v in BRANCHES.items()])
        c.executemany("INSERT INTO riders VALUES (?,?,?,?)", riders)
        c.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)
        c.executemany("INSERT INTO order_items VALUES (?,?,?,?)", items)
        c.executemany("INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)", delivs)
        c.executemany("INSERT INTO tracking_events (order_id, status, event_time, note) VALUES (?,?,?,?)", events)
    print(f"Seeded {len(customers)} customers, {len(products)} products, "
          f"{len(orders)} orders, {len(events)} tracking events")

if __name__ == "__main__":
    run()

