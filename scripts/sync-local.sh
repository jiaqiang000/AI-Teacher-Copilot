#!/bin/zsh

# 自动把 jiaqiang000/deer-flow 的最新代码拉到本地。
# 只在工作区干净且能直接快进时更新，避免破坏未保存的改动。

set -uo pipefail

REPO="/Users/luojiaqiang/code/deer-flow"
LOG="$HOME/.deer-flow-sync.log"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
}

cd "$REPO" || { log "仓库路径不存在"; exit 0; }

if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code; then
  log "跳过：本地有未提交的改动"
  exit 0
fi

git fetch origin main >>"$LOG" 2>&1 || { log "跳过：拉取失败（网络或凭据问题）"; exit 0; }

local_head=$(git rev-parse HEAD)
remote_head=$(git rev-parse origin/main)

if [[ "$local_head" == "$remote_head" ]]; then
  log "已是最新"
  exit 0
fi

if git merge --ff-only origin/main >>"$LOG" 2>&1; then
  log "已更新到 $(git rev-parse --short HEAD)"
else
  log "跳过：本地分支有独立提交，无法自动快进，需要手动处理"
fi
