"""Feature engineering for fraud scores — exports scored features + simple model metrics."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "python" / "outputs"
OUT.mkdir(exist_ok=True)
SEED = 20250901
rng = np.random.default_rng(SEED)

txn = pd.read_csv(ROOT / "data" / "cleaned" / "transactions.csv", parse_dates=["txn_ts"])

# Engineer features at transaction grain
feat = txn.copy()
feat["log_amount"] = np.log1p(feat["amount_inr"])
feat["hour"] = feat["txn_ts"].dt.hour
feat["dow"] = feat["txn_ts"].dt.dayofweek
feat["is_weekend"] = (feat["dow"] >= 5).astype(int)
feat["channel_upi"] = (feat["channel"] == "UPI").astype(int)
feat["channel_card"] = (feat["channel"] == "Card").astype(int)
feat["channel_wallet"] = (feat["channel"] == "Wallet").astype(int)

# Customer velocity proxies (deterministic group stats)
cust = feat.groupby("customer_id")["amount_inr"].agg(["count", "mean", "std"]).fillna(0)
cust.columns = ["cust_txn_n", "cust_amt_mean", "cust_amt_std"]
feat = feat.merge(cust, left_on="customer_id", right_index=True, how="left")

# Merchant risk prior from fraud labels
merch = feat.groupby("merchant_id")["is_fraud_label"].mean().rename("merchant_fraud_rate")
feat = feat.merge(merch, left_on="merchant_id", right_index=True, how="left")

# Composite engineered score (transparent, not a black-box claim)
z_amount = (feat["log_amount"] - feat["log_amount"].mean()) / feat["log_amount"].std()
eng_score = (
    0.22 * feat["is_night"]
    + 0.20 * feat["is_new_device"]
    + 0.18 * feat["is_geo_shift"]
    + 0.15 * (feat["txn_count_1h"] >= 6).astype(float)
    + 0.12 * np.clip(z_amount / 3, 0, 1)
    + 0.13 * np.clip(feat["merchant_fraud_rate"] * 3, 0, 1)
)
feat["eng_fraud_score"] = np.clip(np.round(eng_score, 3), 0, 1)

# Simple threshold eval vs label
y = feat["is_fraud_label"].values
pred = (feat["eng_fraud_score"] >= 0.55).astype(int)
tp = int(((pred == 1) & (y == 1)).sum())
fp = int(((pred == 1) & (y == 0)).sum())
fn = int(((pred == 0) & (y == 1)).sum())
tn = int(((pred == 0) & (y == 0)).sum())
precision = tp / (tp + fp) if (tp + fp) else 0
recall = tp / (tp + fn) if (tp + fn) else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

metrics = {
    "threshold": 0.55,
    "precision": round(precision, 3),
    "recall": round(recall, 3),
    "f1": round(f1, 3),
    "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    "note": "Transparent linear feature blend — baseline for rule tuning, not a production model.",
}

cols_out = [
    "txn_id", "txn_ts", "channel", "city", "merchant_category", "merchant_id",
    "customer_id", "amount_inr", "log_amount", "hour", "is_weekend",
    "is_night", "is_new_device", "is_geo_shift", "txn_count_1h",
    "cust_txn_n", "merchant_fraud_rate", "fraud_score", "eng_fraud_score", "is_fraud_label",
]
feat[cols_out].to_csv(ROOT / "data" / "marts" / "mart_txn_features.csv", index=False)
(OUT / "feature_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print(json.dumps(metrics, indent=2))
print("Features → data/marts/mart_txn_features.csv")
