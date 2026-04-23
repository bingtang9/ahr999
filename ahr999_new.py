"""Plot the new-parameter ahr999 curve on its own (clean version).

New parameters (2026 refit per 定投大饼):
  Fit(t) = 10 ** (5.64 * log10(age_days) - 16.33)
  age_days = (date(t) - 2009-01-03).days
  ahr999   = (P / GM200) * (P / Fit)
"""
import json
from datetime import date, datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager

GENESIS = date(2009, 1, 3)
WINDOW = 200
SLOPE, INTERCEPT = 5.64, 16.33

for fname in ["PingFang SC", "Heiti SC", "STHeiti", "Hiragino Sans GB",
              "Songti SC", "Arial Unicode MS"]:
    try:
        font_manager.findfont(fname, fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [fname]
        matplotlib.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue

with open("/Users/longxia/codeSpace/ahr999/btc_daily.json") as f:
    rows = json.load(f)

dates = np.array([datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows])
prices = np.array([r["close"] for r in rows], dtype=float)

log_p = np.log(prices)
csum = np.concatenate([[0.0], np.cumsum(log_p)])
gm200 = np.full_like(prices, np.nan)
for i in range(WINDOW - 1, len(prices)):
    gm200[i] = np.exp((csum[i + 1] - csum[i + 1 - WINDOW]) / WINDOW)

age_days = np.array([(d - GENESIS).days for d in dates], dtype=float)
fit = 10 ** (SLOPE * np.log10(age_days) - INTERCEPT)
ahr = (prices / gm200) * (prices / fit)

mask = ~np.isnan(gm200)
d = dates[mask]; a = ahr[mask]; p = prices[mask]; f = fit[mask]

last = -1
ld, lp, la, lf = d[last], float(p[last]), float(a[last]), float(f[last])

def zone(v):
    if v < 0.45: return "抄底"
    if v < 1.2:  return "定投"
    return "停止定投"

age_today = (ld - GENESIS).days
print(f"Date   : {ld}  (age {age_today} days)")
print(f"Price  : ${lp:,.2f}")
print(f"Fit    : ${lf:,.0f}")
print(f"ahr999 : {la:.3f}   [{zone(la)}]")

# --- plot ---
fig, ax1 = plt.subplots(figsize=(14, 7.5))
ax1.set_title(
    f"ahr999 指数 (2026 新参数)    截至 {ld}    ahr999 = {la:.3f}  [{zone(la)}]",
    fontsize=14, pad=12)

ax1.axhspan(0, 0.45, color="#2ecc71", alpha=0.12)
ax1.axhspan(0.45, 1.2, color="#f1c40f", alpha=0.12)
ax1.axhspan(1.2, 10, color="#e74c3c", alpha=0.12)
ax1.axhline(0.45, color="#27ae60", lw=1, ls="--")
ax1.axhline(1.2, color="#c0392b", lw=1, ls="--")
ax1.axhline(1.0, color="#7f8c8d", lw=0.6, ls=":", alpha=0.6)

ax1.plot(d, a, color="#1f3a5f", lw=1.5, label="ahr999 (新参数)")
ax1.scatter([ld], [la], color="#1f3a5f", s=48, zorder=5)
ax1.annotate(f"{la:.3f}", (ld, la),
             textcoords="offset points", xytext=(10, 10),
             fontsize=12, color="#1f3a5f", weight="bold")

ax1.text(d[-1], 0.28, "  抄底  <0.45", color="#1e8449", fontsize=9.5, va="center")
ax1.text(d[-1], 0.75, "  定投  0.45–1.2", color="#b7950b", fontsize=9.5, va="center")
ax1.text(d[-1], 2.3,  "  停止定投  ≥1.2", color="#922b21", fontsize=9.5, va="center")

ax1.set_ylabel("ahr999", fontsize=12)
ax1.set_yscale("log")
ax1.set_ylim(0.15, 6)
ax1.grid(True, which="both", ls=":", alpha=0.4)
ax1.legend(loc="upper left", fontsize=10)

ax2 = ax1.twinx()
ax2.plot(d, p, color="#e67e22", lw=0.9, alpha=0.55, label="BTC 价格")
ax2.plot(d, f, color="#1f3a5f", lw=0.8, ls=":", alpha=0.55, label="新拟合公允值")
ax2.set_yscale("log")
ax2.set_ylabel("BTC / 拟合值 (USD, log)", color="#e67e22", fontsize=11)
ax2.tick_params(axis="y", labelcolor="#e67e22")
ax2.legend(loc="upper right", fontsize=9)

ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.autofmt_xdate()

footer = (f"公式: ahr999 = (价格 / 200日几何均值) × (价格 / 拟合值)    "
          f"拟合: 10^({SLOPE}·log10(币龄天数) − {INTERCEPT})    "
          f"数据: Binance BTCUSDT 日线")
fig.text(0.5, 0.012, footer, ha="center", fontsize=8.5, color="#555")

plt.tight_layout(rect=[0, 0.025, 1, 1])
out = "/Users/longxia/codeSpace/ahr999/ahr999_new_curve.png"
plt.savefig(out, dpi=150)
print(f"Saved: {out}")
