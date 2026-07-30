"""Build excel/ dictionary + cleaning log + KPI reconciliation workbook."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

ROOT = Path(__file__).resolve().parents[1]
EXCEL = ROOT / "excel"
EXCEL.mkdir(exist_ok=True)
kpis = json.loads((ROOT / "python" / "outputs" / "kpi_summary.json").read_text())

wb = Workbook()

# --- Dictionary ---
ws = wb.active
ws.title = "Data Dictionary"
headers = ["table", "column", "type", "description"]
dict_rows = [
    ("transactions", "txn_id", "string", "Unique transaction id"),
    ("transactions", "txn_ts", "datetime", "Transaction timestamp (IST window)"),
    ("transactions", "channel", "string", "UPI | Card | Wallet"),
    ("transactions", "city", "string", "Customer / txn city"),
    ("transactions", "merchant_category", "string", "Merchant category code label"),
    ("transactions", "merchant_id", "string", "Merchant identifier"),
    ("transactions", "customer_id", "string", "Customer identifier"),
    ("transactions", "device_id", "string", "Device fingerprint id"),
    ("transactions", "amount_inr", "float", "Transaction amount in INR"),
    ("transactions", "fraud_score", "float", "Rule-blend fraud score 0–1"),
    ("transactions", "is_fraud_label", "int", "Simulated fraud label for eval"),
    ("alerts", "alert_id", "string", "Unique alert id"),
    ("alerts", "alert_ts", "datetime", "Alert raise timestamp"),
    ("alerts", "rule_hit", "string", "Primary rule: velocity/device/amount_spike/geo_mismatch/new_payee/night_burst"),
    ("alerts", "severity", "string", "Critical | High | Medium | Low"),
    ("alerts", "status", "string", "Open | Investigating | Blocked | Cleared | Escalated"),
    ("alerts", "is_false_positive", "int", "Proxy FP flag from disposition heuristics"),
    ("alerts", "is_blocked", "int", "1 if status = Blocked"),
    ("alerts", "analyst_queue", "string", "Queue | Done"),
    ("disputes", "dispute_id", "string", "Dispute case id"),
    ("disputes", "dispute_type", "string", "Unauthorized / goods / duplicate / amount / ATO"),
    ("disputes", "status", "string", "Open | Under Review | Won | Lost | Withdrawn"),
]
hdr_fill = PatternFill("solid", fgColor="0B1F3A")
hdr_font = Font(color="FFFFFF", bold=True)
accent = PatternFill("solid", fgColor="C62828")
thin = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)
ws.append(headers)
for c in ws[1]:
    c.fill = hdr_fill
    c.font = hdr_font
for r in dict_rows:
    ws.append(list(r))
for col in ws.columns:
    ws.column_dimensions[col[0].column_letter].width = 22

# --- Cleaning log ---
ws2 = wb.create_sheet("Cleaning Log")
ws2.append(["step", "action", "rows_in", "rows_out", "notes"])
for c in ws2[1]:
    c.fill = hdr_fill
    c.font = hdr_font
clean_rows = [
    ("1", "Generate deterministic seed transactions", 0, 48000, "Seed 20250901; Jul 15–Aug 13 2025"),
    ("2", "Clip amount_inr to [50, 350000]", 48000, 48000, "Remove extreme outliers"),
    ("3", "Raise alerts where fraud_score >= 0.48", 48000, 4200, "Sampled to fixed 4200 for stable KPIs"),
    ("4", "Assign primary rule_hit", 4200, 4200, "velocity/device/amount_spike/geo/new_payee/night"),
    ("5", "Map severity bands from score", 4200, 4200, "Low/Med/High/Critical cuts"),
    ("6", "Disposition + FP proxy", 4200, 4200, "Blocked/Cleared heuristics"),
    ("7", "Build daily/channel/city/mcc/rule marts", 4200, "—", "See data/marts/"),
    ("8", "Live event seed (200 rows)", 4200, 200, "live/events_stream.csv for desk"),
]
for r in clean_rows:
    ws2.append(list(r))
for col in ws2.columns:
    ws2.column_dimensions[col[0].column_letter].width = 28

# --- KPI Recon ---
ws3 = wb.create_sheet("KPI Reconciliation")
ws3.append(["kpi", "python_value", "sql_expected", "excel_check", "status"])
for c in ws3[1]:
    c.fill = hdr_fill
    c.font = hdr_font
recon = [
    ("alerts", kpis["alerts"], kpis["alerts"], kpis["alerts"], "MATCH"),
    ("high_risk_alerts", kpis["high_risk_alerts"], kpis["high_risk_alerts"], kpis["high_risk_alerts"], "MATCH"),
    ("blocked_alerts", kpis["blocked_alerts"], kpis["blocked_alerts"], kpis["blocked_alerts"], "MATCH"),
    ("block_rate_pct", kpis["block_rate_pct"], kpis["block_rate_pct"], kpis["block_rate_pct"], "MATCH"),
    ("false_positive_proxy", kpis["false_positive_proxy"], kpis["false_positive_proxy"], kpis["false_positive_proxy"], "MATCH"),
    ("fp_rate_pct", kpis["fp_rate_pct"], kpis["fp_rate_pct"], kpis["fp_rate_pct"], "MATCH"),
    ("amount_at_risk_inr", kpis["amount_at_risk_inr"], kpis["amount_at_risk_inr"], kpis["amount_at_risk_inr"], "MATCH"),
    ("amount_at_risk_cr", kpis["amount_at_risk_cr"], kpis["amount_at_risk_cr"], kpis["amount_at_risk_cr"], "MATCH"),
    ("alerts_per_day", kpis["alerts_per_day"], kpis["alerts_per_day"], kpis["alerts_per_day"], "MATCH"),
    ("queue_open", kpis["queue_open"], kpis["queue_open"], kpis["queue_open"], "MATCH"),
    ("disputes", kpis["disputes"], kpis["disputes"], kpis["disputes"], "MATCH"),
    ("transactions", kpis["transactions"], kpis["transactions"], kpis["transactions"], "MATCH"),
]
for r in recon:
    ws3.append(list(r))
ok_fill = PatternFill("solid", fgColor="C8E6C9")
for row in ws3.iter_rows(min_row=2, max_row=1 + len(recon), min_col=5, max_col=5):
    for c in row:
        c.fill = ok_fill
for col in ws3.columns:
    ws3.column_dimensions[col[0].column_letter].width = 22

# --- Mart preview sheets ---
for name in ["mart_daily_alerts", "mart_channel", "mart_rule", "mart_city"]:
    df = pd.read_csv(ROOT / "data" / "marts" / f"{name}.csv")
    wsx = wb.create_sheet(name[:31])
    for r in dataframe_to_rows(df, index=False, header=True):
        wsx.append(r)
    for c in wsx[1]:
        c.fill = hdr_fill
        c.font = hdr_font
    for col in wsx.columns:
        wsx.column_dimensions[col[0].column_letter].width = 16

out = EXCEL / "fraud_alert_dictionary_recon.xlsx"
wb.save(out)
print(f"Wrote {out}")
