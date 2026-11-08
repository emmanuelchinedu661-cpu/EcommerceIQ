from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "ecommerceiq.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
MODEL_PATH = ROOT / "models" / "late_delivery.joblib"

CITY_CENTER = {"lat": 4.8300, "lon": 7.0100}

BRANCHES = {
    "BR-GRA": ("EcommerceIQ GRA",       "GRA Phase 2", 4.8215, 7.0080),
    "BR-RMK": ("EcommerceIQ Rumuokoro",  "Rumuokoro",  4.8680, 6.9980),
    "BR-TAM": ("EcommerceIQ Trans-Amadi", "Trans-Amadi", 4.8120, 7.0450),
}

ZONES = {
    "GRA Phase 2":  (4.8240, 7.0050, 1.3),
    "Rumuola":   (4.8420, 7.0150, 1.4),
    "Trans-Amadi": (4.8100, 7.0400, 1.2),
    "D-Line":   (4.7950, 7.0150, 1.5),
    "Rumuokoro": (4.8700, 6.9950, 1.6),
    "Woji":     (4.8300, 7.0600, 1.1),
    "Choba":   (4.8950, 6.9200, 1.4),
    "Elelenwo":  (4.8350, 7.0850, 1.2),
    "Ada George": (4.8600, 6.9800, 1.5),
    "Old GRA":  (4.7800, 7.0100, 1.3),
}

STATUSES = ["Placed", "Packed", "Dispatched","Out for Delivery", "Delivered"]

