import sqlite3
import pandas as pd
from config import DB_PATH, SCHEMA_PATH

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(reset=False):
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())

def query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)