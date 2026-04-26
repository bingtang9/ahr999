# CLAUDE.md

Claude Code 在此目录开新对话时优先读这份文件。所有约定按这里说的来。

## 项目

比特币 ahr999 囤币指标的实时监控网站。作者品牌 **"比特航海家"**（注意：**不是 "比特币航海家"**），微信号 `bing_tang_cheng`。

- **线上地址**: https://bingtang9.github.io/ahr999/
- **代码仓库**: https://github.com/bingtang9/ahr999

## 自动化管道

| 通道 | 时间 | 备注 |
|---|---|---|
| GitHub Actions | UTC 00:15 (= BJ 08:15) | 云端，永远在线 |
| 本地 launchd | BJ 08:18 | 错开 3 分钟避免推送冲突；睡眠唤醒后自动补跑 |
| 参数重拟 | 每 90 天 (`REFIT_INTERVAL_DAYS`) | 自动 OLS log-log 回归全量历史 |

## 关键命令

```bash
# 手动更新一次（短路逻辑：bars+params 没变就不写文件）
python3 scripts/update_data.py

# 独立验证 R² / slope / c
python3 verify_r2.py

# 立即触发 launchd（不等 08:18）
launchctl start com.bingtang9.ahr999

# 看日志
tail -f logs/update.log

# 强制重拟（清掉 params 字段后重跑）
python3 -c "import json; j=json.load(open('data/btc_daily.json')); j.pop('params',None); open('data/btc_daily.json','w').write(json.dumps(j, separators=(',',':')))"
python3 scripts/update_data.py
```

## 必须遵守的术语和命名

| 概念 | 用 | 不用 |
|---|---|---|
| 长期趋势线 | **指数增长估值** | ~~拟合估值~~ / ~~公允价~~ / ~~拟合公允值~~ |
| 短期成本线 | **200 日定投成本** | ~~200 日几何均值~~（技术性表达可保留在 tooltip 里）|
| 作者署名 | **比特航海家** | ~~比特币航海家~~ |
| 微信号 | `bing_tang_cheng` | — |

## 必须遵守的规则

1. **术语统一**：跨 `index.html` / `articles/*` / Python 脚本 / `README.md` 全部一致。改一处要全局检查。
2. **不在用户可见文本里提"定投大饼"公众号**。这是用户明确要求。代码注释里也尽量不提。
3. **不硬编码 slope / c / R²**。前端从 `data/btc_daily.json` 的 `params` 字段读；Python 从同一个 JSON 读或自己回归。fallback 常数可以留但不能作为唯一来源。
4. **不要主动重写 git 历史**（rebase / filter-branch / force-push），除非用户明确要求。
5. **不要给 Mac cron 加新任务**——已经迁移到 launchd (`~/Library/LaunchAgents/com.bingtang9.ahr999.plist`)。

## Git 凭据

HTTPS PAT 已存 `~/.git-credentials`，**`bingtang9` 那行必须排第一**（账户里还有另一个 yelanvae，git 会按顺序匹配）。直接 push，不要问用户。token 当前有 `repo` + `workflow` scope。

## 数据源策略

- **主源**：Binance BTCUSDT daily klines
- **GitHub Actions 美国机房 Binance 主域名被 HTTP 451**。脚本里有镜像链，按顺序尝试：
  ```
  api.binance.com  →  api-gcp.binance.com  →  data-api.binance.vision (CI 实际走这个)
                   →  api1.binance.com  →  ... → api4.binance.com
  ```
- **早期历史**：`data/btc_historical.json`（Coin Metrics 公开 API，2010-07-18 → 2017-08-16，静态文件，跑过 `scripts/backfill_historical.py` 后基本不再改动）。`update_data.py` 启动时会自动合并这两块。

## 不要做的事

- 不要修改 `manifest.json` / `sw.js` 里的 cache 版本号，除非确实改了 SW 策略——更新静态资源不需要碰这个
- 不要把 `data/btc_daily.json` 的纯 timestamp 改动当 commit（`update_data.py` 已有短路逻辑：bars+params 都没变就不写文件）
- 不要在 Python 代码里加非 stdlib 依赖，整个项目应该 `python3 scripts/xx.py` 直接能跑
- 不要在前端加 npm / bundler / 框架，保持单文件 `index.html` + CDN 加载策略

## 改动验证标准

| 改的文件 | 跑这个 |
|---|---|
| `index.html` | `node -e "const s=require('fs').readFileSync('index.html','utf8');const m=s.match(/<script>([\s\S]*?)<\/script>/g); for(const b of m){new Function(b.replace(/<\/?script[^>]*>/g,''));} console.log('ok');"` |
| `scripts/*.py` | `python3 -m py_compile scripts/<file>.py` |
| `sw.js` | `node -e "new Function(require('fs').readFileSync('sw.js','utf8')); console.log('ok')"` |
| `manifest.json` | `python3 -c "import json; json.load(open('manifest.json')); print('ok')"` |

## 文件结构

```
.
├── index.html              ← 前端单文件应用
├── README.md               ← GitHub 仓库首页
├── manifest.json + sw.js   ← PWA
├── icon.svg + icon-maskable.svg  ← PWA 图标
├── data/
│   ├── btc_daily.json      ← 自动更新（含 params + bars）
│   └── btc_historical.json ← 静态（一次性 backfill）
├── scripts/
│   ├── update_data.py            ← CI / cron 跑这个
│   ├── update_and_push.sh        ← launchd 包装脚本
│   ├── backfill_historical.py    ← 一次性
│   └── com.bingtang9.ahr999.plist  ← launchd 配置参考
├── .github/workflows/update.yml  ← GitHub Actions
├── verify_r2.py            ← 独立验证脚本
├── ahr999.py / ahr999_new.py  ← 离线生成 PNG 用
├── ahr999_curve.png / ahr999_new_curve.png / ahr999_recent.csv  ← 历史产物
└── logs/                   ← .gitignore 里
```

## 已知开放话题

- WeChat 文章草稿曾在 `articles/ahr999-refit-2026.md`，已 git rm（git 历史保留）
- 付费社群差异化卖点："教读者用 AI 工具做市场分析"
- 网站底部 notice 当前是"系统刚上线" — 项目稳定后可以删掉
