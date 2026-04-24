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
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(__file__)
START_MS = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
OUT = os.path.join(HERE, "..", "data", "btc_daily.json")
HIST = os.path.join(HERE, "..", "data", "btc_historical.json")
UA = {"User-Agent": "ahr999-updater/1.0"}
GENESIS = date(2009, 1, 3)
WINDOW = 200

# Power-law parameters are expensive to re-interpret (every change shifts ALL
# historical ahr999 values slightly). Adding one more daily bar to ~5,700+
# samples moves slope by ~0.0001, so daily re-fitting is essentially noise.
# Recompute only every REFIT_INTERVAL_DAYS days. Override by deleting params
# from data/btc_daily.json and re-running the script.
REFIT_INTERVAL_DAYS = 90

# Reference values from 定投大饼 2026 refit article — kept ONLY for comparison.
# The slope/intercept we actually use are self-computed from full history.
REF_SLOPE, REF_INTERCEPT = 5.64, 16.33

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


def compute_regression(pairs):
    """OLS fit of log10(price) on log10(coin_age_days).

    Returns (slope, intercept, r2, n) where the long-term fitted price is
        fit(age) = 10 ** (slope * log10(age) - intercept)
    (i.e. 'intercept' here is the article's `c`, equal to the negation of the
    regression's y-intercept `b`.)
    """
    xs = []
    ys = []
    for t_ms, close in pairs:
        if close <= 0:
            continue
        day = datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc).date()
        age = (day - GENESIS).days
        if age <= 0:
            continue
        xs.append(math.log10(age))
        ys.append(math.log10(close))
    n = len(xs)
    if n < 200:
        raise RuntimeError(f"not enough points for regression (got {n})")
    xm = sum(xs) / n
    ym = sum(ys) / n
    sxy = sum((xs[i] - xm) * (ys[i] - ym) for i in range(n))
    sxx = sum((xs[i] - xm) ** 2 for i in range(n))
    slope = sxy / sxx
    b = ym - slope * xm
    ss_res = sum((ys[i] - (slope * xs[i] + b)) ** 2 for i in range(n))
    ss_tot = sum((ys[i] - ym) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, -b, r2, n  # article-form c = -b


def compute_indicators(pairs, slope, intercept):
    """Given sorted [(tms, close), ...] and the fit params, return list of dicts
    with precomputed ahr999 / gm / fit (null for bars inside the first 200-day window).
    """
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
            fit = 10 ** (slope * math.log10(age) - intercept)
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

    # Reuse existing fit params if they're still fresh (< REFIT_INTERVAL_DAYS old).
    today = datetime.now(timezone.utc).date()
    cached_params = None
    fit_date_str = None
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT)).get("params") or {}
            fit_date_str = prev.get("fit_date")
            if fit_date_str:
                fit_age = (today - date.fromisoformat(fit_date_str)).days
                if fit_age < REFIT_INTERVAL_DAYS \
                   and all(k in prev for k in ("slope", "intercept", "r2", "sample_size")):
                    cached_params = prev
        except Exception as e:
            print(f"warn: cannot read prior params ({e})", file=sys.stderr)

    if cached_params:
        slope     = cached_params["slope"]
        intercept = cached_params["intercept"]
        r2        = cached_params["r2"]
        n_fit     = cached_params["sample_size"]
        next_refit = date.fromisoformat(cached_params["fit_date"]) + \
                     timedelta(days=REFIT_INTERVAL_DAYS)
        print(f"fit: reusing (fitted {cached_params['fit_date']}, "
              f"next refit {next_refit.isoformat()})  "
              f"slope={slope}  c={intercept}  R²={r2}")
    else:
        slope, intercept, r2, n_fit = compute_regression(ordered)
        fit_date_str = today.isoformat()
        print(f"fit: REFIT  slope={slope:.4f}  c={intercept:.4f}  R²={r2:.4f}  (n={n_fit:,})")
        print(f"           ref (定投大饼 2026): slope={REF_SLOPE}  c={REF_INTERCEPT}  "
              f"Δslope={slope-REF_SLOPE:+.4f}  Δc={intercept-REF_INTERCEPT:+.4f}")

    rows = compute_indicators(ordered, slope, intercept)

    first_d = datetime.fromtimestamp(ordered[0][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last_d  = datetime.fromtimestamp(ordered[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last = rows[-1]

    params = {
        "slope":           round(slope, 4) if not cached_params else slope,
        "intercept":       round(intercept, 4) if not cached_params else intercept,
        "r2":              round(r2, 4) if not cached_params else r2,
        "sample_size":     n_fit,
        "fit_date":        fit_date_str,
        "refit_every_days": REFIT_INTERVAL_DAYS,
        "window":          WINDOW,
        "genesis":         GENESIS.isoformat(),
        "ref_slope":       REF_SLOPE,
        "ref_intercept":   REF_INTERCEPT,
        "ref_note":        "reference values from 定投大饼 2026 refit — not used for calculation",
    }

    # Short-circuit: same bars + same params on disk? skip write to avoid noise commits.
    if os.path.exists(OUT):
        try:
            existing = json.load(open(OUT))
            if existing.get("bars") == rows and existing.get("params") == params:
                print(f"no change (bars + params identical)  rows={len(rows):,}  last={last_d}  "
                      f"lastClose=${last['c']:,.2f}  ahr999={last.get('ahr','n/a')}")
                return 0
        except Exception as e:
            print(f"warn: could not diff existing output ({e}); rewriting", file=sys.stderr)

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": (f"Binance BTCUSDT daily klines ({host_used})" if host_used
                   else "Coin Metrics historical (Binance unavailable)"),
        "params": params,
        "bars": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    print(f"OK  rows={len(rows):,}  first={first_d}  last={last_d}  "
          f"lastClose=${last['c']:,.2f}  ahr999={last.get('ahr','n/a')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
