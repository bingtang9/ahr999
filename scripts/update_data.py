"""Fetch BTC daily closes from Binance and write data/btc_daily.json.

Runs in GitHub Actions daily. Paginates BTCUSDT daily klines from
2017-08 (BTCUSDT listing) to now, dedupes by open time, writes a
compact JSON the frontend can load directly.

Output: data/btc_daily.json
  {
    "updated": "2026-04-23T12:00:00Z",
    "source":  "Binance BTCUSDT daily klines",
    "bars": [ {"t": <openTimeMs>, "c": <closeUSD>}, ... ]
  }
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1d"
LIMIT = 1000
# BTCUSDT started 2017-08-17; start slightly earlier to be safe.
START_MS = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "btc_daily.json")


def fetch_page(start_ms: int):
    q = f"?symbol={SYMBOL}&interval={INTERVAL}&startTime={start_ms}&limit={LIMIT}"
    req = urllib.request.Request(
        URL + q,
        headers={"User-Agent": "ahr999-updater/1.0 (+github-actions)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    bars: dict[int, float] = {}
    cursor = START_MS
    end_ms = int(time.time() * 1000)
    pages = 0
    while cursor < end_ms and pages < 30:
        batch = fetch_page(cursor)
        if not batch:
            break
        for k in batch:
            bars[int(k[0])] = float(k[4])  # openTime -> close
        last_open = int(batch[-1][0])
        next_cursor = last_open + 86_400_000
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        pages += 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    if not bars:
        print("ERROR: no data returned", file=sys.stderr)
        return 1

    ordered = sorted(bars.items())
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Binance BTCUSDT daily klines",
        "bars": [{"t": t, "c": c} for t, c in ordered],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    first_d = datetime.fromtimestamp(ordered[0][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last_d = datetime.fromtimestamp(ordered[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"OK  rows={len(ordered):,}  first={first_d}  last={last_d}  lastClose=${ordered[-1][1]:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
