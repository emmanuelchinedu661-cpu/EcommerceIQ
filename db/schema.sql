PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  full_name    TEXT NOT NULL,
  gender       TEXT CHECK (gender IN ('Male', 'Female')),
  phone        TEXT,
  email        TEXT,
  signup_date  DATE
);

CREATE TABLE IF NOT EXISTS addresses (
  address_id   INTEGER PRIMARY KEY,
  customer_id  TEXT REFERENCES customers(customer_id),
  label        TEXT,
  street       TEXT,
  area         TEXT,
  city         TEXT,
  state        TEXT,
  latitude     REAL,
  longitude    REAL,
  is_default   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
  product_id  TEXT PRIMARY KEY,
  name        TEXT,
  category    TEXT,
  store       TEXT,
  price       REAL,
  stock       INTEGER
);

CREATE TABLE IF NOT EXISTS branches (
  branch_id   TEXT PRIMARY KEY,
  name        TEXT,
  area        TEXT,
  latitude    REAL,
  longitude   REAL
);

CREATE TABLE IF NOT EXISTS riders (
  rider_id   TEXT PRIMARY KEY,
  name       TEXT,
  phone      TEXT,
  vehicle    TEXT
);

CREATE TABLE IF NOT EXISTS orders (
  order_id       TEXT PRIMARY KEY,
  customer_id    TEXT REFERENCES customers(customer_id),
  address_id     INTEGER REFERENCES addresses(address_id),
  branch_id      TEXT REFERENCES branches(branch_id),
  order_date     DATETIME,
  payment_method TEXT,
  total_amount   REAL,
  delivery_fee   REAL,
  status         TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
  order_id     TEXT REFERENCES orders(order_id),
  product_id   TEXT REFERENCES products(product_id),
  quantity     INTEGER,
  unit_price   REAL
);

CREATE TABLE IF NOT EXISTS deliveries (
  order_id      TEXT PRIMARY KEY REFERENCES orders(order_id),
  rider_id      TEXT REFERENCES riders(rider_id),
  dispatched_at DATETIME,
  eta           DATETIME,
  delivered_at  DATETIME,
  distance_km   REAL,
  delivery_otp  TEXT
);

CREATE TABLE IF NOT EXISTS tracking_events (
  event_id     INTEGER PRIMARY KEY,
  order_id     TEXT REFERENCES orders(order_id),
  status       TEXT,
  event_time   DATETIME,
  note         TEXT
);

CREATE INDEX IF NOT EXISTS ix_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS ix_orders_branch   ON orders(branch_id);
CREATE INDEX IF NOT EXISTS ix_items_order     ON order_items(order_id);
CREATE INDEX IF NOT EXISTS ix_events_order    ON tracking_events(order_id);