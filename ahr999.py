"""Compute and plot the ahr999 index — with 2026 refit per 定投大饼 article.

Formula (general form):
  ahr999(t) = (P(t) / GM200(t)) * (P(t) / Fit(t))

  P(t)     = BTC close on day t (USD)
  GM200(t) = geometric mean of P over the last 200 days ending at t
  Fit(t)   = 10 ** (slope * log10(age_days) - intercept)
  age_days = (date(t) - 2009-01-03).days        (Bitcoin genesis)

Two parameter sets compared:
  OLD  (ahr999, 2018 fit, 10 years of data):   slope=5.84,  intercept=17.01
  NEW  (2026 refit, 17 years of data, R²=0.96): slope=5.64,  intercept=16.33

Intercept for the new fit is calibrated to the article's anchor:
  Fit_old / Fit_new = 1.21 at age 6318 (2026-04-23).
  -> intercept_new = 5.64*log10(6318) - log10(Fit_old_today / 1.21) ≈ 16.33

Thresholds (unchanged):
  ahr999 < 0.45        -> 抄底 (bottom-buy)
  0.45 <= a < 1.2      -> 定投 (DCA)
  ahr999 >= 1.2        -> 停止定投 (stop DCA)
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

OLD_SLOPE, OLD_INT = 5.84, 17.01
NEW_SLOPE, NEW_INT = 5.64, 16.33

# Pick a Chinese-capable font if available (macOS ships several).
for fname in ["PingFang SC", "Heiti SC", "STHeiti", "Hiragino Sans GB",
              "Songti SC", "Arial Unicode MS"]:
    try:
        font_manager.findfont(fname, fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [fname]
        matplotlib.rcParams["axes.unicode_minus"] = False
        print(f"Using font: {fname}")
        break
    except Exception:
        continue

with open("/Users/longxia/codeSpace/ahr999/btc_daily.json") as f:
    rows = json.load(f)

dates = np.array([datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows])
prices = np.array([r["close"] for r in rows], dtype=float)

# Rolling 200-day geometric mean via cumulative log sum.
log_p = np.log(prices)
csum = np.concatenate([[0.0], np.cumsum(log_p)])
gm200 = np.full_like(prices, np.nan)
for i in range(WINDOW - 1, len(prices)):
    gm200[i] = np.exp((csum[i + 1] - csum[i + 1 - WINDOW]) / WINDOW)

age_days = np.array([(d - GENESIS).days for d in dates], dtype=float)

def fit_curve(slope, intercept):
    return 10 ** (slope * np.log10(age_days) - intercept)

fit_old = fit_curve(OLD_SLOPE, OLD_INT)
fit_new = fit_curve(NEW_SLOPE, NEW_INT)

ahr_old = (prices / gm200) * (prices / fit_old)
ahr_new = (prices / gm200) * (prices / fit_new)

valid = ~np.isnan(gm200)
d = dates[valid]
a_old = ahr_old[valid]
a_new = ahr_new[valid]
p = prices[valid]
f_old = fit_old[valid]
f_new = fit_new[valid]

# --- latest values ---
i = -1
last_date, last_price = d[i], float(p[i])
last_old, last_new = float(a_old[i]), float(a_new[i])
last_fit_old, last_fit_new = float(f_old[i]), float(f_new[i])

def zone(v):
    if v < 0.45: return "抄底"
    if v < 1.2:  return "定投"
    return "停止定投"

age_today = (last_date - GENESIS).days
print(f"Date            : {last_date}  (age {age_today} days)")
print(f"BTC close       : ${last_price:,.2f}")
print(f"Fit OLD (5.84)  : ${last_fit_old:,.0f}  -> ahr999 = {last_old:.3f}  [{zone(last_old)}]")
print(f"Fit NEW (5.64)  : ${last_fit_new:,.0f}  -> ahr999 = {last_new:.3f}  [{zone(last_new)}]")
print(f"Ratio old/new   : {last_fit_old/last_fit_new:.3f}")

# --- plot ---
fig, ax1 = plt.subplots(figsize=(14, 7.5))
ax1.set_title(
    f"ahr999 曲线  (截至 {last_date})   "
    f"新参数 = {last_new:.3f} [{zone(last_new)}]   |   "
    f"旧参数 = {last_old:.3f} [{zone(last_old)}]",
    fontsize=13, pad=14)

ax1.axhspan(0, 0.45, color="#2ecc71", alpha=0.10)
ax1.axhspan(0.45, 1.2, color="#f1c40f", alpha=0.10)
ax1.axhspan(1.2, 10, color="#e74c3c", alpha=0.10)
ax1.axhline(0.45, color="#27ae60", lw=1, ls="--", alpha=0.8)
ax1.axhline(1.2, color="#c0392b", lw=1, ls="--", alpha=0.8)

# shade the gap between old and new so the bias is obvious
ax1.fill_between(d, a_old, a_new, where=(a_new > a_old),
                 color="#ec7063", alpha=0.15, label="新-旧 差值 (旧偏低)")

ax1.plot(d, a_old, color="#c0392b", lw=1.2, alpha=0.85,
         label=f"旧参数 ahr999  (slope={OLD_SLOPE}, c={OLD_INT})")
ax1.plot(d, a_new, color="#2c3e50", lw=1.5,
         label=f"新参数 ahr999  (slope={NEW_SLOPE}, c={NEW_INT})")

ax1.scatter([last_date], [last_new], color="#2c3e50", s=44, zorder=5)
ax1.annotate(f"{last_new:.3f}", (last_date, last_new),
             textcoords="offset points", xytext=(8, 10),
             fontsize=11, color="#2c3e50", weight="bold")
ax1.scatter([last_date], [last_old], color="#c0392b", s=30, zorder=5, alpha=0.8)
ax1.annotate(f"{last_old:.3f}", (last_date, last_old),
             textcoords="offset points", xytext=(8, -14),
             fontsize=10, color="#c0392b")

# zone labels on the right
ax1.text(d[-1], 0.30, "  抄底 <0.45", color="#1e8449", fontsize=9, va="center")
ax1.text(d[-1], 0.75, "  定投 0.45–1.2", color="#b7950b", fontsize=9, va="center")
ax1.text(d[-1], 2.5, "  停止定投 ≥1.2", color="#922b21", fontsize=9, va="center")

ax1.set_ylabel("ahr999", fontsize=12)
ax1.set_yscale("log")
ax1.set_ylim(0.15, 6)
ax1.grid(True, which="both", ls=":", alpha=0.4)
ax1.legend(loc="upper left", fontsize=9)

# secondary axis: BTC price + both fit curves
ax2 = ax1.twinx()
ax2.plot(d, p, color="#e67e22", lw=0.9, alpha=0.55, label="BTC 价格")
ax2.plot(d, f_old, color="#c0392b", lw=0.8, ls=":", alpha=0.6,
         label=f"旧拟合估值")
ax2.plot(d, f_new, color="#2c3e50", lw=0.8, ls=":", alpha=0.6,
         label=f"新拟合估值")
ax2.set_yscale("log")
ax2.set_ylabel("BTC / 拟合值 (USD, log)", color="#e67e22", fontsize=11)
ax2.tick_params(axis="y", labelcolor="#e67e22")
ax2.legend(loc="upper right", fontsize=9)

ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.autofmt_xdate()

footer = ("公式: ahr999 = (价格 / 200日几何均值) × (价格 / 拟合值)    "
          "新参数来源: 公众号『定投大饼』2026 重拟 (5.64 / 16.33, R²=0.96)")
fig.text(0.5, 0.01, footer, ha="center", fontsize=8.5, color="#555")

plt.tight_layout(rect=[0, 0.02, 1, 1])
out = "/Users/longxia/codeSpace/ahr999/ahr999_curve.png"
plt.savefig(out, dpi=140)
print(f"Saved: {out}")

# --- dump last-30-day table ---
csv_path = "/Users/longxia/codeSpace/ahr999/ahr999_recent.csv"
with open(csv_path, "w") as f:
    f.write("date,close_usd,fit_old,fit_new,ahr999_old,ahr999_new,zone_new\n")
    for j in range(max(0, len(d) - 30), len(d)):
        f.write(f"{d[j]},{p[j]:.2f},{f_old[j]:.0f},{f_new[j]:.0f},"
                f"{a_old[j]:.4f},{a_new[j]:.4f},{zone(float(a_new[j]))}\n")
print(f"Saved: {csv_path}")
