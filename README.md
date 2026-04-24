# ahr999 实时监控 · 2026 新参数

比特币 ahr999 囤币指标的实时查看页面，使用 **2026 年重拟参数** (slope = 5.64, intercept = 16.33, R² = 0.96)，数据每天自动更新。

> **比特币航海家 出品** · 微信号 `bing_tang_cheng`

🌐 在线访问：<https://bingtang9.github.io/ahr999/>

---

## ahr999 指标是什么

由微博用户 [@ahr999](https://weibo.com/ahr999) 2018 年提出的比特币定投辅助指标，帮判断"现在应该抄底、定投，还是停止定投"。

**公式**

```
ahr999 = (现价 / 200 日定投成本) × (现价 / 拟合估值)
拟合估值 = 10 ^ (slope · log10(币龄天数) − c)
```

币龄从比特币创世块（2009-01-03）起算。`slope` 和 `c` **不是写死的常数**——`scripts/update_data.py` 每次运行时检查：如果上次拟合已超过 90 天（`REFIT_INTERVAL_DAYS`），就在全量历史上重新做一次 OLS log-log 线性回归，把新的 `slope / c / R² / fit_date` 写进 `data/btc_daily.json` 的 `params` 字段；未超期则复用。

当前拟合（仓库最后一次自回归）：`slope ≈ 5.68, c ≈ 16.47, R² = 0.96, n = 5,760 天`。

**阈值分区**

| 区间 | ahr999 范围 | 含义 |
|---|---|---|
| 🟢 抄底 | `< 0.45` | 显著低估，直接买比定投划算 |
| 🟡 定投 | `0.45 – 1.2` | 常态区间，定投是好策略 |
| 🔴 停止定投 | `≥ 1.2` | 相对高估，停止买入 |

## 为什么用 2026 新参数

原版 `5.84 / 17.01` 是 2018 年用 10 年数据拟合的。到 2026 年（BTC 已 17 年），外推误差被幂律放大，拟合值系统性偏高，导致 ahr999 信号被压低，长期停在"抄底"区间。

本项目在 `scripts/update_data.py` 里对 2009 至今全部历史数据做 log-log 线性回归自动拟合新的 `slope / c`，每 90 天重拟一次。当前结果：`slope ≈ 5.68, c ≈ 16.47, R² = 0.96, n ≈ 5,760 天`。`verify_r2.py` 是独立的交叉验证脚本。

## 项目结构

```
├── index.html                     前端页面 (Chart.js, 纯静态)
├── data/btc_daily.json            BTC 日线数据（自动更新）
├── scripts/
│   ├── update_data.py             拉 Binance 日线 → 写 data/btc_daily.json
│   └── update_and_push.sh         本地 cron 包装脚本 (pull + 抓取 + commit + push)
├── .github/workflows/update.yml   每日 CI 更新 (UTC 00:15)
│
├── ahr999.py                      离线生成对比曲线 PNG (新旧参数)
├── ahr999_new.py                  离线生成新参数单图 PNG
├── verify_r2.py                   独立回归 + R² 校验
└── fetch_btc.py                   一次性抓取脚本（历史分析用）
```

## 数据自动更新

**双通道同步，每天 08:15 / 08:18 北京时间触发：**

| 通道 | 时间 (BJ) | 运行环境 | 触发方式 |
|---|---|---|---|
| GitHub Actions | 08:15 | ubuntu-latest (云) | `cron: "15 0 * * *"` (UTC) |
| 本地 cron | 08:18 | macOS | `crontab -l` |

Actions 先跑完 push，本地 cron 启动时 `git pull --rebase` 自动同步，零冲突。

**数据源 fallback 链**（Binance 主站在美国机房被 `HTTP 451`，mirror 总有一个通）：

1. `api.binance.com`
2. `api-gcp.binance.com`
3. `data-api.binance.vision` ← CI 通常走这个
4. `api1/2/3/4.binance.com`

## 本地运行

```bash
# 拉最新数据
python3 scripts/update_data.py

# 本地预览页面
python3 -m http.server 8000
# 打开 http://localhost:8000/
```

## 手动触发 CI

<https://github.com/bingtang9/ahr999/actions> → `update-btc-data` → **Run workflow**

---

## 参考

- 原版文章：[囤比特币：ahr999指数](https://ahr999.com/ahr999/ahr999_buy03.html)
- 拟合方法：本项目自动对全量历史做 log-log 线性回归，每 90 天重拟
- 数据源：Binance BTCUSDT 日线
- 估值起算：2009-01-03 比特币创世块

免责声明：本项目仅供信息参考，不构成投资建议。
