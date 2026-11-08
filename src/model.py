"""Train a late-delivery classifier on Fact_delivery."""
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import MODEL_PATH
from  db import query

NUM = ["distance_km", "n_items", "order_hour", "order_month", "order_dow", "promised_mins"]
CAT = ["branch", "area", "vehicle", "rider_id"]
TARGET = "is_late"

def load_data():
    df = query("SELECT * FROM fact_delivery WHERE is_late IS NOT NULL")
    df[TARGET] = df[TARGET].astype(int)
    return df

def build(model):
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT),
    ])
    return Pipeline([("pre", pre), ("clf", model)])

def train():
    df = load_data()
    print(f"Rows: {len(df):,} | late rate: {df[TARGET].mean():.1%}")
    x, y = df[NUM + CAT], df[TARGET]
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=0.2, stratify=y, random_state=42)

    candidates = {
        "logreg": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "gboost": GradientBoostingClassifier(random_state=42),
    }
    best, best_auc, best_name = None, 0, ""
    for name, m in candidates.items():
        pipe = build(m).fit(x_tr, y_tr)
        auc = roc_auc_score(y_te, pipe.predict_proba(x_te)[:, 1])#type: ignore
        print(f" {name}: ROC-AUC = {auc:.3f}")
        if auc > best_auc:
            best, best_auc, best_name = pipe, auc, name

    print(f"\nBest: {best_name}\n")
    print(classification_report(y_te, best.predict(x_te), digits=3))#type: ignore
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": best, "features": NUM + CAT, "auc": best_auc, "name": best_name}, MODEL_PATH)
    print(f"Saved → {MODEL_PATH}")

def predict(row: dict) -> float:
    bundle = joblib.load(MODEL_PATH)
    return float(bundle["model"].predict_proba(pd.DataFrame([row])[bundle["features"]])[0, 1])

if __name__ == "__main__":
    train()
