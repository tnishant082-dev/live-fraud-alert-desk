"""Generate deterministic payment fraud / dispute datasets (Jul–Aug 2025)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEANED = ROOT / "data" / "cleaned"
MARTS = ROOT / "data" / "marts"
LIVE = ROOT / "live"

SEED = 20250901
rng = np.random.default_rng(SEED)

CHANNELS = ["UPI", "Card", "Wallet"]
CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    "Chandigarh", "Kochi", "Indore", "Nagpur", "Surat",
]
MCC = [
    "Grocery", "Fuel", "Electronics", "Fashion", "Travel",
    "Food Delivery", "Utilities", "Healthcare", "Gaming", "Education",
]
RULES = ["velocity", "device", "amount_spike", "geo_mismatch", "new_payee", "night_burst"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["Open", "Investigating", "Blocked", "Cleared", "Escalated"]
DISPUTE_TYPES = ["Unauthorized", "Goods not received", "Duplicate charge", "Amount mismatch", "Account takeover"]

DATES = pd.date_range("2025-07-15", "2025-08-13", freq="D")


def _choice(a, n, p=None):
    return rng.choice(a, size=n, p=p)


def generate_transactions(n: int = 48000) -> pd.DataFrame:
    ts = pd.to_datetime("2025-07-15") + pd.to_timedelta(
        rng.integers(0, 30 * 24 * 3600, size=n), unit="s"
    )
    channel = _choice(CHANNELS, n, p=[0.58, 0.28, 0.14])
    city = _choice(CITIES, n)
    mcc = _choice(MCC, n, p=[0.18, 0.12, 0.10, 0.11, 0.08, 0.14, 0.09, 0.06, 0.07, 0.05])
    # INR amounts — UPI mid, Card higher, Wallet lower
    base = rng.lognormal(mean=7.8, sigma=1.05, size=n)  # median ~₹2.4k
    mult = np.where(channel == "Card", 2.2, np.where(channel == "Wallet", 0.65, 1.0))
    amount = np.round(base * mult, 2)
    amount = np.clip(amount, 50, 350000)

    merchant_id = rng.integers(1000, 1899, size=n)
    customer_id = rng.integers(10000, 89999, size=n)
    device_id = rng.integers(50000, 99999, size=n)
    is_night = ((ts.hour < 5) | (ts.hour >= 23)).astype(int)
    is_new_device = (rng.random(n) < 0.09).astype(int)
    is_geo_shift = (rng.random(n) < 0.06).astype(int)
    txn_count_1h = rng.integers(1, 14, size=n)

    score = (
        0.18 * (amount > 25000).astype(float)
        + 0.18 * is_night.astype(float)
        + 0.22 * is_new_device.astype(float)
        + 0.20 * is_geo_shift.astype(float)
        + 0.16 * (txn_count_1h >= 6).astype(float)
        + rng.random(n) * 0.28
    )
    score = np.clip(np.round(score, 3), 0, 1)
    is_fraud_label = (
        ((score >= 0.72) & (rng.random(n) < 0.82))
        | ((score >= 0.55) & (rng.random(n) < 0.14))
    ).astype(int)

    df = pd.DataFrame({
        "txn_id": [f"TXN{i:08d}" for i in range(1, n + 1)],
        "txn_ts": ts,
        "channel": channel,
        "city": city,
        "merchant_category": mcc,
        "merchant_id": [f"M{m}" for m in merchant_id],
        "customer_id": [f"C{c}" for c in customer_id],
        "device_id": [f"D{d}" for d in device_id],
        "amount_inr": amount,
        "is_night": is_night,
        "is_new_device": is_new_device,
        "is_geo_shift": is_geo_shift,
        "txn_count_1h": txn_count_1h,
        "fraud_score": score,
        "is_fraud_label": is_fraud_label,
    })
    return df.sort_values("txn_ts").reset_index(drop=True)


def assign_rule(row) -> str:
    candidates = []
    weights = []
    if row["txn_count_1h"] >= 5:
        candidates.append("velocity"); weights.append(3.0)
    if row["is_new_device"]:
        candidates.append("device"); weights.append(2.5)
    if row["amount_inr"] > 15000:
        candidates.append("amount_spike"); weights.append(2.2)
    if row["is_geo_shift"]:
        candidates.append("geo_mismatch"); weights.append(2.0)
    if row["is_night"]:
        candidates.append("night_burst"); weights.append(1.5)
    # always allow new_payee as soft option
    candidates.append("new_payee"); weights.append(1.0)
    if not candidates:
        return "velocity"
    w = np.array(weights, dtype=float)
    w = w / w.sum()
    return str(rng.choice(candidates, p=w))


def generate_alerts(txn: pd.DataFrame) -> pd.DataFrame:
    cand = txn[txn["fraud_score"] >= 0.48].copy()
    if len(cand) > 4200:
        cand = cand.sample(4200, random_state=SEED)
    # Enrich alert amounts: boost a share to look like real fraud spikes
    boost = rng.random(len(cand)) < 0.35
    cand = cand.copy()
    cand.loc[boost, "amount_inr"] = np.round(
        cand.loc[boost, "amount_inr"] * rng.uniform(2.5, 8.0, size=boost.sum()), 2
    )
    cand["amount_inr"] = np.clip(cand["amount_inr"], 50, 350000)
    cand = cand.sort_values("txn_ts")

    rule_hit = cand.apply(assign_rule, axis=1)
    severity = pd.cut(
        cand["fraud_score"],
        bins=[-0.01, 0.55, 0.68, 0.82, 1.01],
        labels=["Low", "Medium", "High", "Critical"],
    )
    status_p = {
        "Critical": [0.05, 0.15, 0.55, 0.05, 0.20],
        "High": [0.10, 0.25, 0.40, 0.15, 0.10],
        "Medium": [0.15, 0.30, 0.20, 0.30, 0.05],
        "Low": [0.20, 0.20, 0.10, 0.48, 0.02],
    }
    statuses = []
    for s in severity.astype(str):
        statuses.append(_choice(STATUSES, 1, p=status_p.get(s, status_p["Medium"]))[0])
    statuses = np.array(statuses)

    is_fp = (
        ((statuses == "Cleared") & (cand["fraud_score"].values < 0.70))
        | ((statuses == "Blocked") & (cand["is_fraud_label"].values == 0) & (rng.random(len(cand)) < 0.55))
    ).astype(int)

    alerts = pd.DataFrame({
        "alert_id": [f"ALT{i:07d}" for i in range(1, len(cand) + 1)],
        "txn_id": cand["txn_id"].values,
        "alert_ts": cand["txn_ts"].values,
        "channel": cand["channel"].values,
        "city": cand["city"].values,
        "merchant_category": cand["merchant_category"].values,
        "merchant_id": cand["merchant_id"].values,
        "customer_id": cand["customer_id"].values,
        "amount_inr": cand["amount_inr"].values,
        "fraud_score": cand["fraud_score"].values,
        "rule_hit": rule_hit.values,
        "severity": severity.astype(str).values,
        "status": statuses,
        "is_false_positive": is_fp,
        "is_blocked": (statuses == "Blocked").astype(int),
        "analyst_queue": np.where(np.isin(statuses, ["Open", "Investigating", "Escalated"]), "Queue", "Done"),
    })
    return alerts.reset_index(drop=True)


def generate_disputes(txn: pd.DataFrame, n: int = 680) -> pd.DataFrame:
    sample = txn.sample(n, random_state=SEED + 7).sort_values("txn_ts")
    opened = sample["txn_ts"] + pd.to_timedelta(rng.integers(1, 72, size=n), unit="h")
    return pd.DataFrame({
        "dispute_id": [f"DSP{i:06d}" for i in range(1, n + 1)],
        "txn_id": sample["txn_id"].values,
        "opened_ts": opened.values,
        "channel": sample["channel"].values,
        "city": sample["city"].values,
        "amount_inr": sample["amount_inr"].values,
        "dispute_type": _choice(DISPUTE_TYPES, n, p=[0.35, 0.18, 0.15, 0.12, 0.20]),
        "status": _choice(["Open", "Under Review", "Won", "Lost", "Withdrawn"], n, p=[0.22, 0.28, 0.25, 0.18, 0.07]),
    }).reset_index(drop=True)


def build_marts(txn: pd.DataFrame, alerts: pd.DataFrame, disputes: pd.DataFrame):
    daily = alerts.assign(date=pd.to_datetime(alerts["alert_ts"]).dt.date).groupby("date").agg(
        alerts=("alert_id", "count"),
        high_risk=("severity", lambda s: int(s.isin(["High", "Critical"]).sum())),
        blocked=("is_blocked", "sum"),
        false_positives=("is_false_positive", "sum"),
        amount_at_risk=("amount_inr", "sum"),
        avg_score=("fraud_score", "mean"),
    ).reset_index()
    daily["block_rate"] = (daily["blocked"] / daily["alerts"]).round(4)
    daily["fp_rate"] = (daily["false_positives"] / daily["alerts"]).round(4)

    by_channel = alerts.groupby("channel").agg(
        alerts=("alert_id", "count"),
        amount_at_risk=("amount_inr", "sum"),
        blocked=("is_blocked", "sum"),
        avg_score=("fraud_score", "mean"),
        high_risk=("severity", lambda s: int(s.isin(["High", "Critical"]).sum())),
    ).reset_index()

    by_city = (
        alerts.groupby("city")
        .agg(
            alerts=("alert_id", "count"),
            amount_at_risk=("amount_inr", "sum"),
            high_risk=("severity", lambda s: int(s.isin(["High", "Critical"]).sum())),
            blocked=("is_blocked", "sum"),
        )
        .reset_index()
        .sort_values("alerts", ascending=False)
    )

    by_mcc = (
        alerts.groupby("merchant_category")
        .agg(
            alerts=("alert_id", "count"),
            amount_at_risk=("amount_inr", "sum"),
            avg_score=("fraud_score", "mean"),
            blocked=("is_blocked", "sum"),
        )
        .reset_index()
        .sort_values("alerts", ascending=False)
    )

    by_rule = alerts.groupby("rule_hit").agg(
        alerts=("alert_id", "count"),
        amount_at_risk=("amount_inr", "sum"),
        blocked=("is_blocked", "sum"),
        fp=("is_false_positive", "sum"),
    ).reset_index()

    merchant_hot = (
        alerts.groupby(["merchant_id", "merchant_category", "city"])
        .agg(
            alerts=("alert_id", "count"),
            amount_at_risk=("amount_inr", "sum"),
            high_risk=("severity", lambda s: int(s.isin(["High", "Critical"]).sum())),
            avg_score=("fraud_score", "mean"),
        )
        .reset_index()
        .sort_values("alerts", ascending=False)
        .head(50)
    )

    queue = alerts[alerts["analyst_queue"] == "Queue"].copy()
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    queue["_o"] = queue["severity"].map(sev_order)
    queue = queue.sort_values(["_o", "alert_ts"]).drop(columns="_o").head(200)

    dim_date = pd.DataFrame({"date": DATES})
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["day"] = dim_date["date"].dt.day
    dim_date["weekday"] = dim_date["date"].dt.day_name()
    dim_date["week"] = dim_date["date"].dt.isocalendar().week.astype(int)

    return {
        "mart_daily_alerts": daily,
        "mart_channel": by_channel,
        "mart_city": by_city,
        "mart_mcc": by_mcc,
        "mart_rule": by_rule,
        "mart_merchant_hotspots": merchant_hot,
        "mart_analyst_queue": queue,
        "dim_date": dim_date,
        "dim_channel": pd.DataFrame({"channel": CHANNELS}),
        "dim_city": pd.DataFrame({"city": CITIES}),
        "dim_mcc": pd.DataFrame({"merchant_category": MCC}),
        "dim_rule": pd.DataFrame({"rule_hit": RULES}),
    }


def live_events(alerts: pd.DataFrame, n: int = 200) -> pd.DataFrame:
    recent = alerts.tail(900).sample(n, random_state=SEED + 3).sort_values("alert_ts")
    base = pd.Timestamp("2025-08-13 18:00:00")
    recent = recent.copy()
    recent["stream_ts"] = [base + pd.Timedelta(seconds=int(i * 2.5)) for i in range(len(recent))]
    cols = [
        "alert_id", "stream_ts", "txn_id", "channel", "city", "merchant_category",
        "merchant_id", "amount_inr", "fraud_score", "rule_hit", "severity", "status",
    ]
    return recent[cols].reset_index(drop=True)


def kpi_summary(txn, alerts, disputes) -> dict:
    total_alerts = len(alerts)
    high_risk = int(alerts["severity"].isin(["High", "Critical"]).sum())
    blocked = int(alerts["is_blocked"].sum())
    fp = int(alerts["is_false_positive"].sum())
    amount = float(alerts["amount_inr"].sum())
    days = (pd.to_datetime(alerts["alert_ts"]).max() - pd.to_datetime(alerts["alert_ts"]).min()).days + 1
    return {
        "window_start": "2025-07-15",
        "window_end": "2025-08-13",
        "transactions": int(len(txn)),
        "alerts": total_alerts,
        "disputes": int(len(disputes)),
        "high_risk_alerts": high_risk,
        "blocked_alerts": blocked,
        "block_rate_pct": round(100 * blocked / total_alerts, 2),
        "false_positive_proxy": fp,
        "fp_rate_pct": round(100 * fp / total_alerts, 2),
        "amount_at_risk_inr": round(amount, 2),
        "amount_at_risk_cr": round(amount / 1e7, 2),
        "amount_at_risk_lakh": round(amount / 1e5, 2),
        "avg_fraud_score": round(float(alerts["fraud_score"].mean()), 3),
        "alerts_per_day": round(total_alerts / max(days, 1), 1),
        "upi_share_pct": round(100 * (alerts["channel"] == "UPI").mean(), 1),
        "top_city": str(alerts.groupby("city").size().idxmax()),
        "top_rule": str(alerts.groupby("rule_hit").size().idxmax()),
        "top_mcc": str(alerts.groupby("merchant_category").size().idxmax()),
        "queue_open": int((alerts["analyst_queue"] == "Queue").sum()),
    }


def main():
    for p in (RAW, CLEANED, MARTS, LIVE):
        p.mkdir(parents=True, exist_ok=True)

    print("Generating transactions…")
    txn = generate_transactions(48000)
    print("Generating alerts…")
    alerts = generate_alerts(txn)
    print("Generating disputes…")
    disputes = generate_disputes(txn)

    txn.to_csv(RAW / "transactions.csv", index=False)
    alerts.to_csv(RAW / "alerts.csv", index=False)
    disputes.to_csv(RAW / "disputes.csv", index=False)

    txn.to_csv(CLEANED / "transactions.csv", index=False)
    alerts.to_csv(CLEANED / "alerts.csv", index=False)
    disputes.to_csv(CLEANED / "disputes.csv", index=False)
    fact = alerts.copy()
    fact["alert_date"] = pd.to_datetime(fact["alert_ts"]).dt.strftime("%Y-%m-%d")
    fact.to_csv(CLEANED / "fact_alerts.csv", index=False)

    marts = build_marts(txn, alerts, disputes)
    for name, df in marts.items():
        df.to_csv(MARTS / f"{name}.csv", index=False)
        print(f"  wrote {name}.csv ({len(df)} rows)")

    events = live_events(alerts, 200)
    events.to_csv(LIVE / "events_stream.csv", index=False)
    events_js = events.to_dict(orient="records")
    for r in events_js:
        r["stream_ts"] = str(r["stream_ts"])
        r["amount_inr"] = float(r["amount_inr"])
        r["fraud_score"] = float(r["fraud_score"])
    (LIVE / "events_seed.json").write_text(json.dumps(events_js), encoding="utf-8")

    kpis = kpi_summary(txn, alerts, disputes)
    (ROOT / "python" / "outputs").mkdir(exist_ok=True)
    (ROOT / "python" / "outputs" / "kpi_summary.json").write_text(json.dumps(kpis, indent=2), encoding="utf-8")
    print(json.dumps(kpis, indent=2))
    print("rules:", alerts["rule_hit"].value_counts().to_dict())
    print("Done.")


if __name__ == "__main__":
    main()
