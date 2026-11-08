import secrets
import re
from datetime import datetime, timedelta

import numpy as np

from config import BRANCHES, STATUSES, ZONES
from db import get_conn, query

NEXT_STATUS = {"Placed": "Packed", "Packed": "Dispatched",
               "Dispatched": "Out for Delivery", "Out for Delivery": "Delivered"}

def _now():
    return datetime.now().replace(second=0, microsecond=0)

def _fmt(t):
    return t.isoformat(sep=" ", timespec="minutes")
def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return float(6371 * 2 * np.arcsin(np.sqrt(a)))

def next_id(table, column, prefix, width):
    """CUS-01500 → CUS-01501 (IDs are zero-padded, so text order = number order)."""
    last = query(f"SELECT {column} AS id FROM {table} ORDER BY {column} DESC LIMIT 1")
    n = int(last.id.iloc[0].split("-")[1]) + 1 if not last.empty else 1
    return f"{prefix}-{n:0{width}d}"

def normalise_phone(phone):
    """Accept 0803 123 4567, +2348031234567, 2348031234567 → 08031234567."""

    p = re.sub(r"[\s\-()]", "", phone or "")
    if p.startswith("+234"):
        p = "0" + p[4:]
    elif p.startswith("234"):
        p = "0" + p[3:]
    if not re.fullmatch(r"0[789][01]\d{8}", p):
        raise ValueError("Enter a valid phone number")
    return p

# CUSTOMERS

def add_customer(full_name, gender, phone, email, street, area, label="Home"):
    full_name = " ".join((full_name or "").split())
    if len(full_name.split()) < 2:
        raise ValueError("Enter the customer's first name and surname")
    phone = normalise_phone(phone)
    email = (email or "").strip().lower() or None
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email")
    if not (street or "").strip():
        raise ValueError("Enter a street address")
    if area not in ZONES:
        raise ValueError("Select a delivery area")
    if not query("SELECT 1 FROM customers WHERE phone = ?", (phone, )).empty:
        raise ValueError(f"A customer with {phone} already exists")
    if email and not query("SELECT 1 FROM customers WHERE email = ?", (email, )).empty:
        raise ValueError(f"A customer with {email} already exists")

    cid = next_id("customers", "customer_id", "CUS", 5)
    lat, lon, _ = ZONES[area]
    with get_conn() as conn:
        conn.execute("INSERT INTO customers values (?,?,?,?,?,?)",
                     (cid, full_name, gender, phone, email, _now().date().isoformat()))
        conn.execute("INSERT INTO addresses (customer_id, label, street, area, city, state, latitude, longitude,"
                     " is_default) VALUES (?,?,?,?,?,?,?,?,?)",
                     (cid, label, street, area, "Port Harcourt", "Rivers", lat, lon, 1))
        return cid

#--- ORDERS

def quote(address_id, items):
    """Price an order before placing it, items = [(product_id, qty), ...]."""
    addr = query("SELECT latitude, longitude, area FROM addresses WHERE address_id = ?", (address_id, ))
    if addr.empty:
        raise ValueError("SELECT a delivery address")
    a = addr.iloc[0]
    branch_id, dist = min(((b, haversine_km(v[2], v[3], a.latitude, a.longitude)) for b, v in BRANCHES.items()),
                          key=lambda x: x[1])
    dist = round(dist * 1.35 + 1.0, 2)
    fee = round(1000 + 250 * dist, -1)

    subtotal, lines = 0.0, []
    for pid, qty in items:
        p = query("SELECT name, price, stock FROM products WHERE product_id = ?", (pid, )).iloc[0]
        if qty < 1:
            raise ValueError(f"Quantity for {p['name']} must be at least 1")
        if qty > p.stock:
            raise ValueError(f"Only {p.stock} of {p['name']} left in stock")
        lines.append((pid, int(qty), float(p.price)))
        subtotal += qty * p.price
    return {"branch_id": branch_id, "branch": BRANCHES[branch_id][0], "area": a.area,
            "distance_km": dist, "fee": fee, "subtotal": subtotal, "total": subtotal + fee, "lines": lines}


def least_busy_rider():
    """Rider with least deliveries"""
    r = query("""
        SELECT r,rider_id, COUNT(d.order_id) AS active
        FROM riders r LEFT JOIN deliveries d
             ON D.rider_id = r.rider_id AND d.delivered_at IS NULL
        GROUP BY r.rider_id ORDER BY active, RANDOM() LIMIT 1""")
    return r.rider_id.iloc[0]

def create_order(customer_id, address_id, items, payment_method):
    if not items:
        raise ValueError("Add at least one product")
    q = quote(address_id, items)
    oid = next_id("orders", "order_id", "ORD", 6)
    now = _now()
    with get_conn() as conn:
        conn.execute("INSERT INTO orders values (?,?,?,?,?,?,?,?,?)",
                     (oid, customer_id, address_id, q["branch_id"], _fmt(now), payment_method,
                      round(float(q["total"]), 2), q["fee"], "Placed")) # type: ignore
        lines: list = q["lines"] #type: ignore
        for pid, qty, price in lines:
            conn.execute("INSERT INTO order_items VALUES (?,?,?,?", (oid, pid, qty, price))
            conn.execute("UPDATE products SET stock = stock - ? WHERE product_id = ?", (qty, pid))

        conn.execute("INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)",
                     (oid, least_busy_rider(), None, None, None, q["distance_km"], f"{secrets.randbelow(9000) + 1000}"))
        conn.execute("INSERT INTO tracking_events (order_id, status, event_time, note) VALUES (?,?,?,?)",
                     (oid, "Placed", _fmt(now), f"Placed - {q['area']}"))
        return oid, q

def advance_order(order_id, otp=None):
    """Advance the order"""
    o = query("""SELECT o.status, d.delivery_otp, d.distance_km, a.area
                 FROM orders o JOIN deliveries d USING(order_id) JOIN addresses a USING(address_id)
                 WHERE o.order_id = ?""", (order_id, ))

    if o.empty:
        raise ValueError("Order not found")
    o = o.iloc[0]
    new = NEXT_STATUS.get(o.status)
    if new is None:
        raise ValueError(f"Order status: {o.status}")
    if new == "Delivered" and str(otp or "").strip() != o.delivery_otp:
        raise ValueError("Wrong OTP. ask the customer for 4 digit code")

    now = _now()
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new, order_id))
        if new == "Dispatched":
            eta = now + timedelta(minutes=(10 + 4.2 * o.distance_km) * 2.1)
            conn.execute("UPDATE deliveries SET dispatched_at = ?, eta = ? WHERE order_id = ?",
                         (_fmt(now), _fmt(eta), order_id))

        if new == "Delivered":
            conn.execute("UPDATE deliveries SET delivered_at = ? WHERE order_id = ?", (_fmt(now), order_id))
        conn.execute("INSERT INTO tracking_events (order_id, status, event_time, note) VALUES (?,?,?,?)",
                     (order_id, new, _fmt(now), f"{new} - {o.area}"))
        return new

assert list(NEXT_STATUS) + ["Delivered"] == STATUSES

        