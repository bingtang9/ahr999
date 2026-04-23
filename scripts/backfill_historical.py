"""One-time backfill of pre-Binance BTC history (2010-07-18 → 2017-08-16).

Binance BTCUSDT was listed 2017-08-17 and has no earlier data. To match chart
references that go back to 2012+, we supplement with Coin Metrics Community
API (free, no auth) for the pre-Binance era only.

Output: data/btc_historical.json  (static; commit once, never regenerated)
  {
    "updated": "2026-04-23T...",
    "source":  "Coin Metrics Community API (btc PriceUSD)",
    "bars":    [ {"t": <openTimeMs UTC 00:00>, "c": <closeUSD>}, ... ]
  }

Run: python3 scripts/backfill_historical.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

URL = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
       "?assets=btc&metrics=PriceUSD&frequency=1d&start_time=2010-07-18"
       "&end_time=2017-08-16&page_size=10000")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "btc_historical.json")


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "ahr999-backfill/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.loads(r.read())

    data = body.get("data", [])
    if not data:
        print("ERROR: no data returned from Coin Metrics", file=sys.stderr)
        return 1

    bars = []
    for row in data:
        t = datetime.strptime(row["time"][:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        c = float(row["PriceUSD"])
        if c > 0:
            bars.append({"t": int(t.timestamp() * 1000), "c": c})
    bars.sort(key=lambda b: b["t"])

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Coin Metrics Community API (btc PriceUSD)",
        "bars": bars,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    first = datetime.fromtimestamp(bars[0]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last  = datetime.fromtimestamp(bars[-1]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"OK  rows={len(bars):,}  first={first}  last={last}  firstPrice=${bars[0]['c']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
