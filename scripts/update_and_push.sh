#!/usr/bin/env bash
# Daily BTC data updater. Called from launchd (or cron). Pulls the latest bar(s)
# from Binance, precomputes indicators, commits + pushes if changed.
#
# On failure, sends a macOS notification so problems don't go unnoticed.
set -o pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
mkdir -p logs

LOG="$REPO/logs/update.log"

# Keep log file from growing unbounded — keep last 100KB only.
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 102400 ]; then
  tail -c 100000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

notify() {
  # osascript is macOS-only; fail silently on other platforms.
  if [ -x /usr/bin/osascript ]; then
    /usr/bin/osascript -e "display notification \"$1\" with title \"ahr999 更新\" subtitle \"$2\"" 2>/dev/null || true
  fi
}

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ==="

  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH ($PATH)"
    notify "python3 不可用" "跳过本次更新"
    exit 1
  fi

  # Sync first so local doesn't conflict with GitHub Actions.
  if git remote get-url origin >/dev/null 2>&1; then
    git pull --rebase --autostash 2>&1 || echo "WARN: pull failed, continuing"
  fi

  # Fetch with 1 retry after 60s on failure (handles transient network hiccups
  # like WiFi handoff or a bad Binance mirror response).
  attempt=1
  while : ; do
    if python3 scripts/update_data.py; then
      break
    fi
    if [ "$attempt" -ge 2 ]; then
      echo "ERROR: update_data.py failed after $attempt attempts"
      notify "数据拉取失败" "所有镜像重试都失败了"
      exit 2
    fi
    echo "attempt $attempt failed; retrying in 60s…"
    attempt=$((attempt + 1))
    sleep 60
  done

  # Nothing changed? Done.
  if [ -z "$(git status --porcelain data/btc_daily.json)" ]; then
    echo "no changes"
    exit 0
  fi

  git add data/btc_daily.json
  if ! git commit -m "data: daily BTC update ($(date -u +%Y-%m-%d))"; then
    notify "commit 失败" "检查 git 状态"
    exit 3
  fi

  if git remote get-url origin >/dev/null 2>&1; then
    if git push 2>&1; then
      echo "pushed OK"
      # Quiet success by default — uncomment the next line to get a daily ping.
      # notify "每日数据已推送" "$(date '+%H:%M')"
    else
      notify "push 失败" "检查凭据或网络"
      echo "WARN: push failed"
    fi
  else
    echo "WARN: no 'origin' remote configured, skipping push"
  fi
} >> "$LOG" 2>&1
