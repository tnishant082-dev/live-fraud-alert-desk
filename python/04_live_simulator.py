"""Optional live simulator — appends rotating rows to live/events_stream.csv.

The HTML desk self-simulates from an embedded seed, so cloning works without
running this script. Use it when you want a fresher CSV on disk.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live"
SEED_CSV = LIVE / "events_stream.csv"


def main(cycles: int = 40, sleep_s: float = 2.5):
    if not SEED_CSV.exists():
        raise SystemExit("Run python/01_generate_data.py first.")
    base = pd.read_csv(SEED_CSV)
    print(f"Simulator started — writing rotating window to {SEED_CSV} ({cycles} ticks)")
    for i in range(cycles):
        # rotate: move first row to end with bumped stream_ts
        row = base.iloc[0].copy()
        last_ts = pd.to_datetime(base["stream_ts"].iloc[-1])
        row["stream_ts"] = str(last_ts + pd.Timedelta(seconds=3))
        base = pd.concat([base.iloc[1:], pd.DataFrame([row])], ignore_index=True)
        base.to_csv(SEED_CSV, index=False)
        print(f"  tick {i+1}/{cycles}: {row['alert_id']} {row['severity']} ₹{row['amount_inr']} {row['rule_hit']}")
        time.sleep(sleep_s)
    print("Done.")


if __name__ == "__main__":
    main()
