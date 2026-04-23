"""Fetch BTC daily klines from Binance, paginated, write JSON to btc_daily.json."""
import json
import time
import urllib.request
from datetime import datetime, timezone

URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1d"
LIMIT = 1000

# BTCUSDT trading started 2017-08-17. Fetch from 2017-08-01 to be safe.
start_ms = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
end_ms = int(time.time() * 1000)

all_rows = []
cursor = start_ms
while cursor < end_ms:
    q = f"?symbol={SYMBOL}&interval={INTERVAL}&startTime={cursor}&limit={LIMIT}"
    with urllib.request.urlopen(URL + q, timeout=30) as r:
        batch = json.loads(r.read())
    if not batch:
        break
    all_rows.extend(batch)
    last_open = batch[-1][0]
    # advance cursor past last candle
    next_cursor = last_open + 24 * 3600 * 1000
    if next_cursor <= cursor:
        break
    cursor = next_cursor
    if len(batch) < LIMIT:
        break
    time.sleep(0.2)

# dedupe by open_time
seen = {}
for row in all_rows:
    seen[row[0]] = row
rows = [seen[k] for k in sorted(seen)]

out = [
    {
        "date": datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
        "open_time_ms": r[0],
        "close": float(r[4]),
    }
    for r in rows
]

with open("/Users/longxia/codeSpace/ahr999/btc_daily.json", "w") as f:
    json.dump(out, f)

print(f"rows: {len(out)}  first: {out[0]['date']}  last: {out[-1]['date']}  last close: {out[-1]['close']}")
