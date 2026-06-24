#!/usr/bin/env bash
# Smoke test: wt.sh 正確 source pipeline.config 並解析 codebase key。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 假 hub:.claude/pipeline.config + 兩個假 codebase 路徑
mkdir -p "$TMP/.claude" "$TMP/codebases/a" "$TMP/codebases/b"
cat > "$TMP/.claude/pipeline.config" <<EOF
declare -A CODEBASE_DIR=( [a]="codebases/a" [b]="codebases/b" )
declare -A CODEBASE_BRANCH=( [a]="main" [b]="dev" )
WT_CACHE_ROOT="$TMP/.cache"
EOF

# 1) 未知 key → usage(exit 64)
if DELIVERY_WT_HUB_ROOT="$TMP" "$HERE/wt.sh" list zzz 2>/dev/null; then
  echo "FAIL: 未知 key 應該 exit 非 0"; exit 1
fi

# 2) 缺 config → exit 78
if DELIVERY_WT_HUB_ROOT="$TMP" DELIVERY_PIPELINE_CONFIG="$TMP/nope" "$HERE/wt.sh" list a 2>/dev/null; then
  echo "FAIL: 缺 config 應該 exit 非 0"; exit 1
fi

# 3) 已知 key 的 list 在真 git repo 解析到正確路徑(用假 codebase 當 repo)
git -C "$TMP/codebases/a" init -q
out="$(DELIVERY_WT_HUB_ROOT="$TMP" "$HERE/wt.sh" list a 2>&1 || true)"
echo "$out" | grep -qi "usage:" && { echo "FAIL: 已知 key 不該印 usage"; exit 1; }
# 正向斷言(M1):worktree list 應印出該 codebase 路徑(no-commit repo 會印 "<path> 0000000 [...]")
echo "$out" | grep -q "$TMP/codebases/a" || { echo "FAIL: list 應印出 codebase a 的路徑,實得: $out"; exit 1; }

echo "PASS: wt.sh config 解析 smoke test"
