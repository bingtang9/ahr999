#!/usr/bin/env bash
# Fetch the latest Binance daily klines, commit if changed, push to origin.
# Called from cron; logs to logs/update.log.
set -o pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

mkdir -p logs
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ==="

  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH ($PATH)"
    exit 1
  fi

  # Sync with remote first so local cron doesn't conflict with GitHub Actions.
  if git remote get-url origin >/dev/null 2>&1; then
    git pull --rebase --autostash 2>&1 || echo "WARN: pull failed, continuing"
  fi

  python3 scripts/update_data.py || { echo "ERROR: update_data.py failed"; exit 2; }

  if [ -z "$(git status --porcelain data/btc_daily.json)" ]; then
    echo "no changes"
    exit 0
  fi

  git add data/btc_daily.json
  git commit -m "data: daily BTC update ($(date -u +%Y-%m-%d))" || exit 3

  if git remote get-url origin >/dev/null 2>&1; then
    git push 2>&1 || echo "WARN: push failed (check remote / credentials)"
  else
    echo "WARN: no 'origin' remote configured, skipping push"
  fi
} >> logs/update.log 2>&1
