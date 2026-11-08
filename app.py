import sys
from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.pipeline import Pipeline

sys.path.append(str(Path(__file__).parent / "src"))

from config import BRANCHES, CITY_CENTER, MODEL_PATH, ZONES
from db import query
from model import  CAT, predict
from store import   NEXT_STATUS, add_customer, advance_order, create_order, quote

ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "lex.png"
ICONS = ASSETS / "icons"

st.set_page_config(page_title="EcommerceIQ", layout="wide",
                   page_icon=str(LOGO) if LOGO.exists() else ":material/storefront:")

if LOGO.exists():
    st.logo(str(LOGO), size="large")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SEG_COLORS = {"Champion": "#2EC4B6", "Loyal": "#4C9AFF", "Regular": "#A0AEC0", "At Risk": "#FF6B6B"}
SEG_ORDER = {"segment": list(SEG_COLORS)}
BRANCH_NAMES = [v[0] for v in BRANCHES.values()]
BRANCH_MAP = pd.DataFrame([{"branch": v[0], "area": v[1], "lat": v[2], "lon": v[3]} for v in BRANCHES.values()])

@st.cache_data
def q(sql, params=()):
    return query(sql, params)

@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)
def header(title, icon_file, material):
    """Page heading with your downloaded icon if present, else a material icon. """
    path = ICONS / icon_file
    if path.exists():
        co1, co2 = st.columns([1, 14], vertical_alignment="center")
        co1.image(str(path), width=48)
        co2.header(title)
    else:
        st.header(f":material/{material}: {title}")

PAGES = {
    "Sales": ":material/payments: Sales",
    "Customers": ":material/group: Customers",
    "Logistics": ":material/local_shipping: Logistics",
    "Order Tracker": ":material/package_2: Order Tracker",
    "Store Admin": ":material/edit_note: Store Admin",
    "Late-Delivery Predictor": ":material/insights: Late-Delivery Predictor",
}

page = st.sidebar.radio("Page", list(PAGES), format_func=lambda p: PAGES[p])
picked = st.sidebar.multiselect("Branch", BRANCH_NAMES, placeholder="All branches (pick to filter)")
branches = picked or BRANCH_NAMES

st.title("EcommerceIQ - Port Harcourt")

if page == "Sales":
    header("Sales", "sales.png", "payments")
    s = q("SELECT * FROM fact_sales")
    s = s[s.branch.isin(branches)]
    s["day"] = pd.to_datetime(s.day)
    orders_n = q("SELECT b.name AS branch, COUNT(*) AS n FROM orders o JOIN branches b USING(branch_id) "
                 "GROUP BY b.name")
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue", f"₦{s.revenue.sum() / 1e6:,.1f}M")
    c2.metric("Orders", f"{orders_n[orders_n.branch.isin(branches)].n.sum():,}")
    c3.metric("Units sold", f"{s.units.sum():,}")

    monthly = s.groupby([pd.Grouper(key="day", freq="MS"), "category"]).revenue.sum().reset_index()
    this_month = pd.Timestamp.now().to_period("M").to_timestamp()
    monthly = monthly[monthly.day < this_month]
    st.plotly_chart(px.line(monthly, x="day", y="revenue", color="category", markers=True,
                            title="Monthly revenue by category"), width="stretch")

    c1, c2 = st.columns(2)
    by_branch = s.groupby("branch").revenue.sum().sort_values().reset_index()
    c1.plotly_chart(px.bar(by_branch, x="revenue", y="branch", orientation="h",
                           title="Revenue by branch"), width="stretch")
    branch_month = s.groupby([pd.Grouper(key="day", freq="MS"), "branch"]).revenue.sum().reset_index()
    c2.plotly_chart(px.line(branch_month, x="day", y="revenue", color="branch",
                            title="Monthly revenue by branch"), width="stretch")
    c1, c2 = st.columns(2)
    stores = s.groupby("store").revenue.sum().sort_values().reset_index()
    c1.plotly_chart(px.bar(stores, x="revenue", y="store", orientation="h",
                           title="Revenue by store"), width="stretch")

    pay = q("SELECT b.name AS branch, o.payment_method, COUNT(*) AS orders "
            "FROM orders o JOIN branches b USING(branch_id) GROUP BY 1, 2")
    pay = pay[pay.branch.isin(branches)].groupby("payment_method").orders.sum().reset_index()
    c2.plotly_chart(px.pie(pay, names="payment_method", values="orders", hole=0.5,
                           title="Payment method mix"), width="stretch")

    top = q("""
        SELECT b.name AS branch, p.name, p.category, SUM(oi.quantity) AS units,
               SUM(oi.quantity * oi.unit_price) AS revenue
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        JOIN orders o ON o.order_id = oi.order_id
        JOIN branches b ON b.branch_id = o.branch_id
        GROUP BY b.name, p.product_id""")

    top = (top[top.branch.isin(branches)].groupby(["name", "category"], as_index=False)[["units", "revenue"]]
              .sum().nlargest(10, "revenue").sort_values("revenue"))
    st.plotly_chart(px.bar(top, x="revenue", y="name", color="category", orientation="h",
                           hover_data=["units"], title="Top 10 products by revenue"), width="stretch")

# CUSTOMERS

elif page == "Customers":
    header("Customers", "customers.png", "group")
    rfm = q("SELECT * FROM dim_customer_rfm")
    seg = rfm.segment.value_counts().reset_index()
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.pie(seg, names="segment", values="count", color="segment",
                           color_discrete_map=SEG_COLORS, category_orders=SEG_ORDER,
                           title="Customer segments (RFM)"), width="stretch")
    c2.plotly_chart(px.scatter(rfm, x="recency_days", y="monetary", size="frequency", color="segment",
                               color_discrete_map=SEG_COLORS, category_orders=SEG_ORDER,
                               title="Recency vs spend"), width="stretch")

    rfm = rfm.merge(q("SELECT customer_id, full_name, gender FROM customers"), on="customer_id")
    by_gender = rfm.groupby("gender").agg(customers=("customer_id", "count"),
                                          avg_spend=("monetary", "mean")).reset_index()

    c1, c2 = st.columns(2)
    c1.plotly_chart(px.pie(by_gender, names="gender", values="customers", hole=0.5,
                           title="Customers by gender"), width="stretch")
    c2.plotly_chart(px.bar(by_gender, x="gender", y="avg_spend", color="gender",
                           title="Average lifetime spend by gender"), width="stretch")
    st.subheader("Top 10 customers")
    st.dataframe(rfm.nlargest(10, "monetary")[["customer_id", "full_name", "gender", "frequency",
                                               "monetary", "segment"]],
                 width="stretch", hide_index=True)

# LOGISTICS
elif page == "Logistics":
    header("Logistics", "logistics.png", "local_shipping")
    d = q("SELECT * FROM fact_delivery WHERE delivered_at IS NOT NULL")
    d = d[d.branch.isin(branches)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg delivery time", f"{d.delivery_mins.mean():.0f} min")
    c2.metric("On-time rate", f"{1 - d.is_late.mean():.1%}")
    c3.metric("Avg distance", f"{d.distance_km.mean():.1f} km")

    perf = (d.groupby("branch").agg(orders=("order_id", "count"), avg_mins=("delivery_mins", "mean"),
                                    avg_km=("distance_km", "mean"), late_rate=("is_late", "mean"))
            .reset_index())

    st.subheader("Branch performance")
    st.dataframe(perf.style.format({"avg_mins": "{:.0f}", "avg_km": "{:.1f}", "late_rate": "{:.1%}"}),
                 width="stretch", hide_index=True)
    zone = d.groupby("area").agg(late=("is_late", "mean"), orders=("order_id", "count")).reset_index()
    zone["lat"] = zone.area.map(lambda a: ZONES[a][0])
    zone["lon"] = zone.area.map(lambda a: ZONES[a][1])
    fig = px.scatter_map(zone, lat="lat", lon="lon", size="orders", color="late", hover_name="area",
                         color_continuous_scale="RdYlGn_r", zoom=11, center=CITY_CENTER,
                         map_style="open-street-map", title="Late rate by delivery zone (squares = branches)")
    shown = BRANCH_MAP[BRANCH_MAP.branch.isin(branches)]
    fig.add_scattermap(lat=shown.lat, lon=shown.lon, text=shown.branch, name="Branch",
                       mode="markers+text", textposition="top center",
                       marker=dict(size=16, color="#1E3A8A", symbol="square"))
    st.plotly_chart(fig, width="stretch")

    heat = (d.assign(day=d.order_dow.map(dict(enumerate(DAYS))))
            .pivot_table(index="day", columns="order_hour", values="order_id", aggfunc="count")
            .reindex(DAYS).fillna(0))
    st.plotly_chart(px.imshow(heat, aspect="auto", color_continuous_scale="Blues",
                              labels=dict(x="Hour of day", y="", color="Orders"),
                              title="Order volume: day of week * hour"), width="stretch")

    hour = d.groupby(["order_hour", "branch"]).is_late.mean().reset_index()
    st.plotly_chart(px.line(hour, x="order_hour", y="is_late", color="branch", markers=True,
                            title="Late rate by order hour"), width="stretch")
    riders = (d.groupby(["rider_id", "vehicle"]).agg(trips=("order_id", "count"), late=("is_late", "mean"),
                                                     avg_mins=("delivery_mins", "mean"))
              .reset_index().sort_values("late"))
    st.subheader("Rider leaderboard")
    st.dataframe(riders, width="stretch", hide_index=True)

# TRACKER

elif page == "Order Tracker":
    header("Order Tracker", "tracker.png", "package_2")
    key = (st.text_input("Search by customer name, phone, email, customer ID or Order ID",
                         placeholder="e.g. Chioma Eze, 0803..., CUS-00001, ORD-000001") or "").strip()

    if key and not key.upper().startswith("ORD-"):
        like = f"%{key}%"
        matches = query("""
            SELECT customer_id, full_name, phone, email FROM customers
            WHERE customer_id = ? OR full_name LIKE ? OR phone LIKE ? OR email LIKE ?
            ORDER BY full_name LIMIT 50""", (key.upper(), like, like, like))
        if matches.empty:
            st.error("Customer not found")
            cid = None
        elif len(matches) == 1:
            cid = matches.customer_id.iloc[0]
        else:
            st.info(f"{len(matches)} customers match. Pick one:")
            labels = {r.customer_id: f"{r.full_name} • {r.phone} • {r.customer_id}"
                      for r in matches.itertuples()}
            cid = st.selectbox("Customer", list(labels), format_func=lambda ci: labels[ci])

        if cid:
            c = query("SELECT * FROM customers WHERE customer_id = ?", (cid,)).iloc[0]
            st.subheader(f":material/person: {c.full_name}")
            st.write(f":material/call: {c.phone} • :material/mail: {c.email} • "
                     f":material/calendar_today: Joined {c.signup_date}")
            st.write("**Saved addresses**")
            st.dataframe(query("SELECT label, street, area, city FROM addresses WHERE customer_id = ?", (cid,)),
                         width="stretch", hide_index=True)
            orders = query("""
                SELECT o.order_id, o.order_date, b.name AS branch, o.status, o.total_amount,
                       GROUP_CONCAT(p.name || ' x' || oi.quantity, ', ') AS goods
                FROM orders o
                JOIN branches b ON b.branch_id = o.branch_id
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN products p ON p.product_id = oi.product_id
                WHERE o.customer_id = ?
                GROUP BY o.order_id ORDER BY o.order_date DESC""", (cid,))
            st.write(f"**Orders ({len(orders)})** - total spend ₦{orders.total_amount.sum():,.0f}")
            st.dataframe(orders, width="stretch", hide_index=True)

    elif key.upper().startswith("ORD-"):
        key = key.upper()
        head = query("""
            SELECT o.*, c.full_name, c.phone, a.label, a.street, a.area, a.latitude, a.longitude,
                   b.name AS branch, b.latitude AS b_lat, b.longitude AS b_lon,
                   d.rider_id, r.name AS rider_name, r.phone AS rider_phone, r.vehicle,
                   d.eta, d.delivered_at, d.distance_km, d.delivery_otp
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            JOIN addresses a ON a.address_id = o.address_id
            JOIN branches  b ON b.branch_id = o.branch_id
            JOIN deliveries d ON d.order_id = o.order_id
            JOIN riders r ON r.rider_id = d.rider_id
            WHERE o.order_id = ?""", (key,))

        if head.empty:
            st.error("Order not found")
        else:
            h = head.iloc[0]
            st.subheader(f":material/package_2: {h.order_id} - {h.status}")
            c1, c2 = st.columns(2)
            c1.write(f"**Customer:** {h.full_name} ({h.customer_id}) • {h.phone}")
            c1.write(f"**Deliver to ({h.label}):** {h.street}, {h.area}")
            c1.write(f"**Paid:** ₦{h.total_amount:,.0f} via {h.payment_method}")
            c2.write(f"**Ships from:** {h.branch}")
            c2.write(f"**Rider:** {h.rider_name} • {h.rider_phone} • {h.vehicle}")
            c2.write(f"**ETA:** {h.eta} • **Distance:** {h.distance_km} km")
            show_otp = c2.toggle("Show OTP (customer view)")
            otp_text = h.delivery_otp if show_otp else "...."
            c2.write(f"**Delivery OTP:** `{otp_text}`")

            st.write("**Goods**")
            st.dataframe(query("""
                SELECT p.name, p.category, p.store, oi.quantity, oi.unit_price,
                       oi.quantity * oi.unit_price AS line_total
                FROM order_items oi JOIN products p ON p.product_id = oi.product_id
                WHERE oi.order_id = ?""",(key,)), width="stretch", hide_index=True)

            st.write("**Tracking timeline**")
            for _, e in query("SELECT status, event_time, note FROM tracking_events WHERE order_id = ? "
                              "ORDER BY event_time DESC", (key,)).iterrows():
                st.write(f":green[:material/check_circle:] **{e.status}** - {e.event_time} • {e.note}")

            route = pd.DataFrame({"lat": [h.b_lat, h.latitude], "lon": [h.b_lon, h.longitude],
                                  "stop": [h.branch, f"Customer ({h.area})"]})
            fig = px.line_map(route, lat="lat", lon="lon", hover_name="stop", zoom=12,
                              map_style="open-street-map")
            fig.update_traces(mode="lines+markers", marker=dict(size=14), line=dict(width=3))
            st.plotly_chart(fig, width="stretch")

    elif key:
        st.warning("IDS start with CUS- or ORD-")

# --- Store Admin
elif page == "Store Admin":
    header("Store Admin", "admin.png", "edit_note")
    tab_cust, tab_order, tab_status = st.tabs(["Add customer", "New order", "Update order"])

    #--- add new customer
    with tab_cust:
        with st.form("add_customer", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full Name *", placeholder="Full Name")
            gender = c2.radio("Gender *", ["Female", "Male"], horizontal=True)
            phone = c1.text_input("Phone *", placeholder="Phone #")
            email = c2.text_input("Email (optional)")
            street = c1.text_input("Street address *", placeholder="Street address")
            area = c2.selectbox("Delivery area *", list(ZONES))
            label = c2.selectbox("Address label", ["Home", "Office", "Other"])
            if st.form_submit_button("Save customer", type="primary"):
                try:
                    cid = add_customer(name, gender, phone, email, street, area, label)
                    st.cache_data.clear()
                    st.success(f"Saved {name.strip()} as **{cid}**")
                except ValueError as err:
                    st.error(str(err))
    #--Place a new order
    with tab_order:
        who = (st.text_input("Find customer (name, phone, email or ID)", key="order_cust") or "").strip()
        cust = None
        if who:
            like = f"%{who}%"
            found = query("""SELECT customer_id, full_name, phone FROM customers
                             WHERE customer_id = ? OR full_name LIKE ? OR phone LIKE ? OR email LIKE ?
                             ORDER BY full_name LIMIT 50""", (who.upper(), like, like, like))
            if found.empty:
                st.warning("No customer found. Add them in the 'Add customer' tab first.")
            else:
                names = {r.customer_id: f"{r.full_name} • {r.phone} • {r.customer_id}" for r in found.itertuples()}
                cust = st.selectbox("Customer", list(names), format_func=lambda k: names[k])

            if cust:
                addrs = query("SELECT address_id, label, street, area FROM addresses WHERE customer_id = ?", (cust, ))
                addr_labels = {int(r.address_id): f"{r.label}: {r.street}, {r.area}" for r in addrs.itertuples()}
                address_id = st.selectbox("Deliver to", list(addr_labels), format_func=lambda k: addr_labels[k])

                products = q("SELECT product_id, name, store, price, stock FROM products WHERE stock > 0 "
                             "ORDER BY category, name")
                prod_labels = {r.product_id: f"{r.name} • {r.store} • ₦{r.price:,.0f} ({r.stock} left)"
                               for r in products.itertuples()}
                chosen = st.multiselect("Products", list(prod_labels), format_func=lambda k: prod_labels[k])
                stock = products.set_index("product_id").stock

                items = []
                for pid in chosen:
                    qty = st.number_input(f"Quantity: {prod_labels[pid].split(' • ')[0]}", min_value=1,
                                          max_value=int(stock[pid]), value=1, key=f"qty_{pid}")
                    items.append((pid, int(qty))) #type: ignore
                payment = st.selectbox("Payment method", ["Card", "Bank Transfer", "Pay on Delivery", "USSD"])

                if items:
                    try:
                        preview = quote(address_id, items)
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Ships from", preview["branch"].replace("EcommerceIQ ", ""))
                        m2.metric("Subtotal", f"₦{preview['subtotal']:,.0f}")
                        m3.metric("Delivery fee", f"₦{preview['fee']:,.0f}")
                        m4.metric("Total", f"₦{preview['total']:,.0f}")
                        if st.button("Place order", type="primary"):
                            oid, _ = create_order(cust, address_id, items, payment)
                            st.cache_data.clear()
                            st.success(f"Order **{oid}** placed. Track it in the Order Tracker.")
                    except ValueError as err:
                        st.error(str(err))

    #--- MOVE AN ORDER TO ITS NEXT STAGE--
    with tab_status:
        open_orders = query("""
            SELECT o.order_id, o.status, c.full_name FROM orders o
            JOIN customers c USING (customer_id)
            WHERE o.status NOT IN ('Delivered', 'Returned')
            ORDER BY o.order_date DESC""")
        if open_orders.empty:
            st.info("No open orders.")
        else:
            info = {r.order_id: f"{r.order_id} • {r.full_name} • {r.status}" for r in open_orders.itertuples()}
            oid = st.selectbox("Open order", list(info), format_func=lambda k: info[k])
            current = open_orders.set_index("order_id").status[oid]
            nxt = NEXT_STATUS[current]
            st.write(f"Current stage: **{current}** → next: **{nxt}**")
            otp = st.text_input("Customer's 4-digit OTP", max_chars=4) if nxt == "Delivered" else None
            if st.button(f"Mark as {nxt}", type="primary"):
                try:
                    advance_order(oid, otp)
                    st.cache_data.clear()
                    st.success(f"{oid} is now **{nxt}**")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))

# PREDICTOR
else:
    header("Late-Delivery Predictor", "predictor.png", "insights")
    if not MODEL_PATH.exists():
        st.error("Run `python run_all.py` first")
    else:
        bundle = load_model()
        riders = q("SELECT rider_id, vehicle FROM riders")
        c1, c2 = st.columns(2)
        branch = c1.selectbox("Ships from", BRANCH_NAMES)
        area = c1.selectbox("Delivery area", list(ZONES))
        rider = c1.selectbox("Rider", riders.rider_id)
        distance = c1.slider("Distance (km)", 1.0, 15.0, 5.0)
        n_items = c2.slider("Items in order", 1, 15, 3)
        hour = c2.slider("Order hour", 8, 21, 12)
        month = c2.slider("Month", 1, 12, 7)
        dow = c2.selectbox("Day of week", list(range(7)), format_func=lambda i: DAYS[i]) #type: ignore
        vehicle = riders.set_index("rider_id").vehicle[rider]
        po = predict(dict(distance_km=distance, n_items=n_items, order_hour=hour, order_month=month,
                         order_dow=dow, promised_mins=(10 + 4.2 * distance) * 2.1,
                         branch=branch, area=area, vehicle=vehicle, rider_id=rider))

        st.metric("Probability of late delivery", f"{po:.0%}")
        st.progress(po)

        # FEATURE IMPORTANCE
        pipe: Pipeline = bundle["model"]
        names = pipe.named_steps["pre"].get_feature_names_out()
        clf = pipe.named_steps["clf"]
        weights = clf.feature_importances_ if hasattr(clf, "feature_importances_") else abs(clf.coef_[0])

        def base(col):
            col = col.split("__", 1)[1]
            return next((ci for ci in CAT if col.startswith(ci + "_")), col)
        imp = (pd.DataFrame({"feature": [base(n) for n in names], "importance": weights})
               .groupby("feature").importance.sum().sort_values().reset_index())
        st.caption(f"Model: {bundle['name']} • ROC-AUC {bundle['auc']:.3f}")
        st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h",
                               title="What drives late deliveries (feature importance)"), width="stretch")

