"""EDA for Live Fraud Alert Desk — summaries written to python/outputs/."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "python" / "outputs"
OUT.mkdir(exist_ok=True)

alerts = pd.read_csv(ROOT / "data" / "cleaned" / "alerts.csv", parse_dates=["alert_ts"])
txn = pd.read_csv(ROOT / "data" / "cleaned" / "transactions.csv", parse_dates=["txn_ts"])
disputes = pd.read_csv(ROOT / "data" / "cleaned" / "disputes.csv", parse_dates=["opened_ts"])

summary = {
    "rows": {"transactions": len(txn), "alerts": len(alerts), "disputes": len(disputes)},
    "date_range": {
        "txn_min": str(txn["txn_ts"].min()),
        "txn_max": str(txn["txn_ts"].max()),
        "alert_min": str(alerts["alert_ts"].min()),
        "alert_max": str(alerts["alert_ts"].max()),
    },
    "channel_mix_alerts": alerts["channel"].value_counts(normalize=True).round(3).to_dict(),
    "severity_mix": alerts["severity"].value_counts().to_dict(),
    "rule_mix": alerts["rule_hit"].value_counts().to_dict(),
    "status_mix": alerts["status"].value_counts().to_dict(),
    "top_cities": alerts["city"].value_counts().head(5).to_dict(),
    "top_mcc": alerts["merchant_category"].value_counts().head(5).to_dict(),
    "amount_stats": alerts["amount_inr"].describe().round(2).to_dict(),
    "score_stats": alerts["fraud_score"].describe().round(3).to_dict(),
    "night_share": round(float((pd.to_datetime(alerts["alert_ts"]).dt.hour.isin(list(range(0, 5)) + [23])).mean()), 3),
}

# hourly profile
hourly = (
    alerts.assign(hour=alerts["alert_ts"].dt.hour)
    .groupby("hour")
    .size()
    .rename("alerts")
    .reset_index()
)
hourly.to_csv(OUT / "eda_hourly.csv", index=False)

corr_cols = ["amount_inr", "fraud_score", "is_blocked", "is_false_positive"]
# numeric only from txn merge sample
sample = txn.sample(min(8000, len(txn)), random_state=42)
corr = sample[["amount_inr", "fraud_score", "is_night", "is_new_device", "is_geo_shift", "txn_count_1h", "is_fraud_label"]].corr().round(3)
corr.to_csv(OUT / "eda_corr.csv")

(OUT / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
print("EDA written to python/outputs/")
