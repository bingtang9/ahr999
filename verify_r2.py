"""Verify the article's claim: re-fit log10(price) = slope*log10(age) + b
over the full BTC daily history, report slope, intercept, R².

Data source: Coin Metrics Community API (btc PriceUSD, daily)
Fit formula in article form:  Fit = 10^(slope * log10(age_days) - c)
  -> c = -b   (b is the regression intercept of y = log10(price) on x = log10(age))
"""
import json
from datetime import date, datetime, timezone
import numpy as np

GENESIS = date(2009, 1, 3)

rows = json.load(open("/tmp/cm.json"))["data"]
dates, prices = [], []
for r in rows:
    d = datetime.strptime(r["time"][:10], "%Y-%m-%d").date()
    p = float(r["PriceUSD"])
    if p > 0:
        dates.append(d)
        prices.append(p)
dates = np.array(dates); prices = np.array(prices)
ages  = np.array([(d - GENESIS).days for d in dates], dtype=float)

print(f"rows: {len(prices):,}   range: {dates[0]} → {dates[-1]}")
print(f"first price: ${prices[0]:.4f}    last price: ${prices[-1]:,.2f}\n")

def fit(x, y):
    """OLS linear fit y = slope*x + b, return slope, b, R²."""
    n = len(x)
    xm, ym = x.mean(), y.mean()
    sxy = ((x - xm) * (y - ym)).sum()
    sxx = ((x - xm) ** 2).sum()
    slope = sxy / sxx
    b = ym - slope * xm
    y_hat = slope * x + b
    ss_res = ((y - y_hat) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2 = 1 - ss_res / ss_tot
    # standard error of slope, 95% CI
    resid_var = ss_res / (n - 2)
    se_slope = np.sqrt(resid_var / sxx)
    return slope, b, r2, se_slope

x = np.log10(ages)
y = np.log10(prices)

# --- 1. Full history (2010-07 to today)  ≈ "17 年全部数据" ---
s, b, r2, se = fit(x, y)
c = -b
print("=== 拟合 1: 全部历史 (2010-07-18 → 今天) ===")
print(f"  样本数        : {len(x):,}")
print(f"  斜率 slope    : {s:.4f}   (95% CI ± {1.96*se:.4f})")
print(f"  截距 b        : {b:.4f}")
print(f"  文章形式 c    : {c:.4f}   (Fit = 10^(slope·log10(age) − c))")
print(f"  R²            : {r2:.4f}")
print(f"  文章值对比    : slope 5.64  /  c 16.33  /  R² 0.96")
print()

# --- 2. Pre-2018 subset (what the ORIGINAL author had in 2018) ---
mask_2018 = dates < date(2018, 1, 1)
s0, b0, r20, _ = fit(x[mask_2018], y[mask_2018])
print("=== 拟合 2: 2018 年之前 (还原旧作者当年拟合) ===")
print(f"  样本数        : {mask_2018.sum():,}")
print(f"  斜率 slope    : {s0:.4f}")
print(f"  c             : {-b0:.4f}")
print(f"  R²            : {r20:.4f}")
print(f"  原版 ahr999   : slope 5.84  /  c 17.01")
print()

# --- 3. The 2026 article's claimed parameters → what R² do THEY actually give?
article_slope, article_c = 5.64, 16.33
y_hat = article_slope * x - article_c
ss_res = ((y - y_hat) ** 2).sum()
ss_tot = ((y - y.mean()) ** 2).sum()
r2_article = 1 - ss_res / ss_tot
print("=== 校验: 把文章参数 (5.64 / 16.33) 直接套到全部数据算 R² ===")
print(f"  R²(文章参数)  : {r2_article:.4f}")

# --- 4. BTC today per fitted curve ---
today_age = (date(2026, 4, 23) - GENESIS).days
fit_today = 10 ** (s * np.log10(today_age) - c)
print()
print(f"=== 今日拟合公允值 (我重拟) : ${fit_today:,.0f}   BTC收盘 ${prices[-1]:,.0f} ===")
