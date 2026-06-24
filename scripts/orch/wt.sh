#!/usr/bin/env bash
# Orchestrator git-worktree helper for parallel feature/bug work.
# Worktrees 落在 hub 工作樹之外(避免 sync-all / git add -A 掃到)。
# codebase→path / →branch / cache root 由 <repo-root>/.claude/pipeline.config 提供。
set -euo pipefail

HUB_ROOT="${DELIVERY_WT_HUB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CONFIG="${DELIVERY_PIPELINE_CONFIG:-$HUB_ROOT/.claude/pipeline.config}"
[ -f "$CONFIG" ] || { echo "pipeline.config not found: $CONFIG (copy from config/pipeline.config.example)" >&2; exit 78; }
# shellcheck source=/dev/null
source "$CONFIG"
WT_ROOT="${WT_CACHE_ROOT:-$HOME/.cache/delivery-wt}"

keys() { printf '%s\n' "${!CODEBASE_DIR[@]}" | sort | paste -sd'|' -; }   # sort → usage 訊息 key 順序穩定(M2)
usage() { echo "usage: wt.sh <add|remove|list> <$(keys)> [branch|path] [--force]" >&2; exit 64; }

repo_dir() {
  local d="${CODEBASE_DIR[$1]:-}"
  [ -n "$d" ] || usage
  echo "$HUB_ROOT/$d"
}

slug() { echo "$1" | tr '/' '-'; }

cmd="${1:-}"; repo="${2:-}"; arg="${3:-}"
[ -n "$cmd" ] && [ -n "$repo" ] || usage
RD="$(repo_dir "$repo")"

case "$cmd" in
  add)
    [ -n "$arg" ] || usage
    git -C "$RD" rev-parse --verify "$arg" >/dev/null 2>&1 || { echo "branch not found in $repo: $arg" >&2; exit 1; }
    wt="$WT_ROOT/${repo}-$(slug "$arg")"
    mkdir -p "$WT_ROOT"
    git -C "$RD" worktree add "$wt" "$arg" >&2
    echo "$wt"
    ;;
  remove)
    [ -n "$arg" ] || usage
    force=""; [ "${4:-}" = "--force" ] && force="--force"   # 放棄含未 commit 改動的 worktree 才用
    if [ -d "$arg" ]; then wt="$arg"; else wt="$WT_ROOT/${repo}-$(slug "$arg")"; fi
    git -C "$RD" worktree remove $force "$wt"
    ;;
  list) git -C "$RD" worktree list ;;
  *) usage ;;
esac
