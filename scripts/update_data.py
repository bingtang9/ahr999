"""Fetch BTC daily closes from Binance (with mirror fallback), merge with static
historical data, precompute ahr999 / gm200 / fit per bar, write data/btc_daily.json.

Binance main API is geo-blocked (HTTP 451) in some US datacenters including GitHub
Actions' Azure runners. We try a list of Binance mirror hosts in order.

Output: data/btc_daily.json
  {
    "updated":  "...",
    "source":   "...",
    "bars":     [ {"t": ms, "c": close, "gm": gm200, "fit": fit, "ahr": ahr999 }, ... ]
  }
Bars before the 200-day window have no indicators (gm/fit/ahr = null).
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

HERE = os.path.dirname(__file__)
START_MS = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
OUT = os.path.join(HERE, "..", "data", "btc_daily.json")
HIST = os.path.join(HERE, "..", "data", "btc_historical.json")
UA = {"User-Agent": "ahr999-updater/1.0"}
GENESIS = date(2009, 1, 3)
WINDOW = 200
SLOPE, INTERCEPT = 5.64, 16.33

# Binance API hosts tried in order. All serve the same /api/v3/klines endpoint.
BINANCE_HOSTS = [
    "api.binance.com",
    "api-gcp.binance.com",        # Google Cloud mirror
    "data-api.binance.vision",    # Public market-data mirror
    "api1.binance.com",
    "api2.binance.com",
    "api3.binance.com",
    "api4.binance.com",
]


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_binance_via(host: str) -> dict[int, float]:
    bars: dict[int, float] = {}
    cursor = START_MS
    end_ms = int(time.time() * 1000)
    pages = 0
    while cursor < end_ms and pages < 30:
        url = (
            f"https://{host}/api/v3/klines"
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


def compute_indicators(pairs):
    """Given sorted [(tms, close), ...], return list of dicts with precomputed
    ahr999 / gm / fit (or null for bars inside the first 200-day window)."""
    n = len(pairs)
    logs = [math.log(c) for _, c in pairs]
    csum = [0.0]
    for lv in logs:
        csum.append(csum[-1] + lv)
    out = []
    for i, (t, c) in enumerate(pairs):
        row = {"t": t, "c": round(c, 4)}
        if i >= WINDOW - 1:
            gm = math.exp((csum[i + 1] - csum[i + 1 - WINDOW]) / WINDOW)
            day = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
            age = (day - GENESIS).days
            fit = 10 ** (SLOPE * math.log10(age) - INTERCEPT)
            ahr = (c / gm) * (c / fit)
            row["gm"]  = round(gm, 2)
            row["fit"] = round(fit, 2)
            row["ahr"] = round(ahr, 6)
        out.append(row)
    return out


def main() -> int:
    bars: dict[int, float] = {}

    # 1. Historical static file (pre-Binance, 2010-07 → 2017-08). Read only.
    if os.path.exists(HIST):
        try:
            hist = json.load(open(HIST))
            for b in hist.get("bars", []):
                bars[int(b["t"])] = float(b["c"])
            print(f"historical loaded: {len(bars):,} rows from data/btc_historical.json")
        except Exception as e:
            print(f"warn: cannot read historical: {e}", file=sys.stderr)

    # 2. Binance (fresh, Binance wins on any overlap with historical).
    host_used = None
    errors: list[str] = []
    for host in BINANCE_HOSTS:
        try:
            b = fetch_binance_via(host)
            if b:
                bars.update(b)
                host_used = host
                print(f"binance: {host}  rows fetched: {len(b):,}")
                break
        except urllib.error.HTTPError as e:
            errors.append(f"{host}: HTTP {e.code}")
            print(f"skip {host}: HTTP {e.code}", file=sys.stderr)
        except Exception as e:
            errors.append(f"{host}: {e}")
            print(f"skip {host}: {e}", file=sys.stderr)

    if not bars:
        print("ERROR: no data. Binance errors: " + " | ".join(errors), file=sys.stderr)
        return 1
    if not host_used:
        print("WARN: no fresh Binance data; using historical only.", file=sys.stderr)

    ordered = sorted(bars.items())
    rows = compute_indicators(ordered)
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": (f"Binance BTCUSDT daily klines ({host_used})" if host_used
                   else "Coin Metrics historical (Binance unavailable)"),
        "bars": rows,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    first_d = datetime.fromtimestamp(ordered[0][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last_d  = datetime.fromtimestamp(ordered[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last = rows[-1]
    print(f"OK  rows={len(rows):,}  first={first_d}  last={last_d}  "
          f"lastClose=${last['c']:,.2f}  ahr999={last.get('ahr','n/a')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
