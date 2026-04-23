"""Fetch BTC daily closes and write data/btc_daily.json.

Tries data sources in order:
  1. Binance BTCUSDT   — preferred (original source, deep history)
  2. Coinbase BTC-USD  — fallback for US-blocked environments (GitHub Actions)

Output: data/btc_daily.json
  {
    "updated": "2026-04-23T12:00:00Z",
    "source":  "<which source actually produced the data>",
    "bars":    [ {"t": <openTimeMs>, "c": <closeUSD>}, ... ]
  }
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

START_MS = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "btc_daily.json")
UA = {"User-Agent": "ahr999-updater/1.0"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------- source 1: Binance ----------
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


# ---------- source 2: Coinbase Exchange ----------
def fetch_coinbase() -> dict[int, float]:
    """Coinbase candles API — max 300 candles/request, paginate with start/end.
    Returns [[ts_seconds, low, high, open, close, volume], ...] sorted descending.
    """
    bars: dict[int, float] = {}
    GRAN = 86_400
    WINDOW = 300 * GRAN
    now = int(time.time())
    end = (now // GRAN) * GRAN
    start_floor = START_MS // 1000
    cur_end = end
    pages = 0
    while cur_end > start_floor and pages < 20:
        cur_start = max(cur_end - WINDOW + GRAN, start_floor)
        s_iso = datetime.fromtimestamp(cur_start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        e_iso = datetime.fromtimestamp(cur_end,   tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        url = (
            "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            f"?granularity={GRAN}&start={s_iso}&end={e_iso}"
        )
        batch = json.loads(_get(url))
        if not batch:
            break
        for row in batch:
            ts_s, _lo, _hi, _op, close, _vol = row
            bars[int(ts_s) * 1000] = float(close)
        cur_end = cur_start - GRAN
        pages += 1
        time.sleep(0.25)  # polite to Coinbase
    return bars


def main() -> int:
    sources = [
        ("Binance BTCUSDT daily klines", fetch_binance),
        ("Coinbase BTC-USD daily candles", fetch_coinbase),
    ]
    bars: dict[int, float] = {}
    used = None
    errors = []
    for name, fn in sources:
        try:
            bars = fn()
            if bars:
                used = name
                print(f"source: {name}  rows fetched: {len(bars):,}")
                break
        except urllib.error.HTTPError as e:
            errors.append(f"{name}: HTTP {e.code}")
            print(f"skip {name}: HTTP {e.code}", file=sys.stderr)
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"skip {name}: {e}", file=sys.stderr)

    if not bars:
        print("ERROR: all sources failed -> " + " | ".join(errors), file=sys.stderr)
        return 1

    ordered = sorted(bars.items())
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": used,
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
