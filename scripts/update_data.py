"""Fetch BTC daily closes from Binance and write data/btc_daily.json.

Output: data/btc_daily.json
  {
    "updated": "2026-04-23T12:00:00Z",
    "source":  "Binance BTCUSDT daily klines",
    "bars":    [ {"t": <openTimeMs>, "c": <closeUSD>}, ... ]
  }
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

START_MS = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "btc_daily.json")
UA = {"User-Agent": "ahr999-updater/1.0"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_binance() -> dict[int, float]:
    bars: dict[int, float] = {}
    cursor = START_MS
    end_ms = int(time.time() * 1000)
    pages = 0
    while cursor < end_ms and pages < 30:
        url = (
            "https://api.binance.com/api/v3/klines"
            f"?symbol=BTCUSDT&interval=1d&startTime={cursor}&limit=1000"
        )
        batch = json.loads(_get(url))
        if not batch:
            break
        for k in batch:
            bars[int(k[0])] = float(k[4])
        last_open = int(batch[-1][0])
        next_cursor = last_open + 86_400_000
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        pages += 1
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    return bars


def main() -> int:
    bars = fetch_binance()
    if not bars:
        print("ERROR: Binance returned no data", file=sys.stderr)
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
    last_d  = datetime.fromtimestamp(ordered[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"OK  rows={len(ordered):,}  first={first_d}  last={last_d}  lastClose=${ordered[-1][1]:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
