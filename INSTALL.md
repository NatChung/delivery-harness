# Install into your repo

1. Copy `skills/*` → `<repo>/.claude/skills/`(可加專案前綴,如 `acme-feature`;
   若加前綴,記得同步改 skill body 內彼此的 cross-reference 與 `/feature` 等 slash 引用)。
   Copy `scripts/feature/` 與 `scripts/orch/` → `<repo>/scripts/`(路徑保持不變,
   skill body 內的 `scripts/feature/cli.py` / `scripts/orch/wt.sh` 才不會斷)。
2. Copy `config/pipeline.config.example` → `<repo>/.claude/pipeline.config`,
   填入你的 codebase map(key→相對路徑)與每個 codebase 的主 branch。
3. Merge `hooks/settings.snippet.json` 的 hooks 區塊進 `<repo>/.claude/settings.json`。
   (選用)依 `mcp/README.md` 接測試 MCP。

驗證:`cd <repo>/scripts/feature && python3 -m unittest -v` 應綠燈;
`scripts/orch/wt.sh list <codebase-key>` 應正常列出 worktree。
