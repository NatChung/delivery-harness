# Install into your repo（AI-bootstrap）

你(target repo 的 AI)拿到本檔 URL + 指定 prefix(例 `dek-`),照以下 9 步把 pipeline 裝進當前 repo。全程在 target repo 根目錄操作。

1. fetch 本 repo 的 `skills/*`、`scripts/*`、`docs/features/*`、`config/*`(GitHub raw)。
2. copy `skills/{feature,bug,orchestrator}` → `<repo>/.claude/skills/<prefix>-{feature,bug,orchestrator}/`;copy `scripts/feature` `scripts/orch` → `<repo>/scripts/`。
3. **copy 引擎 runtime 依賴**:`docs/features/{INDEX.md,_template.md,_template_bug.md}` → `<repo>/docs/features/`(`cli.py new` 執行時要讀;缺了第一次 `cli.py new` 就炸。`INDEX.md` 保持空 registry:header + 分隔線,無 data row)。
4. **套 prefix**:把三個 skill 目錄改名加 `<prefix>-`;改 body 內彼此 cross-ref(feature/bug 指向 orchestrator;orchestrator 指向 feature/bug)與 slash 引用(`/feature`→`/<prefix>-feature` 等);標題列的 skill 名也改。
5. 從 `config/pipeline.config.example` 生 `<repo>/.claude/pipeline.config`,**問 user** 填:每個 codebase 的 `CODEBASE_DIR`(相對路徑)、`CODEBASE_BRANCH`(主分支)、`WT_CACHE_ROOT`(worktree 快取根)。
6. **hooks**:檢查本 repo `hooks/settings.snippet.json`。若非空且與 pipeline 相關 → merge 進 `<repo>/.claude/settings.json`;若空殼 → 跳過並告知 user 無 hook 需裝。
7. (選用)依 `mcp/README.md` 接測試 MCP(Playwright / mobile)。**post-implement UAT 重度靠 MCP** → 建議裝;不裝則 UAT 階段要另接測試工具。
8. 生 `<repo>/.claude/skills/.harness-version`,照 `config/harness-version.example` 三行,`commit` 填 install 當下本 upstream 的 `git rev-parse HEAD`、`installed` 填今日。
9. **驗收三條**,全綠才算裝成:
   - `cd <repo>/scripts/feature && python3 -m unittest -v` → 引擎測試綠。
   - `<repo>/scripts/orch/wt.sh list <任一 codebase-key>` → 正常列(驗 worktree 半邊 + pipeline.config 讀得到)。
   - `grep -rnE "(^|[^A-Za-z0-9_/-])/(feature|bug|orchestrator)([^A-Za-z0-9_/-]|\$)" <repo>/.claude/skills/<prefix>-*` → **零 hit**(驗 step 4 改名乾淨)。**注意**:邊界條件刻意排除路徑語境 —— `scripts/feature/`(前有字母)、`docs/features`(後接 `s`)、純文字 `feature/bug`(前有字母)都不算 hit;只抓 `` `/feature` `` 這種真 slash-command 調用,改名後該歸零。**別用裸 `grep "/feature"`**(會撞 script/doc 路徑、數學上不可能零)。

裝完該 repo 有 `<prefix>-{feature,bug,orchestrator}` 三個 skill + `scripts/{feature,orch}` + `docs/features/` 模板 + `.harness-version`。

前提:repo 有 Python3(engine 純 stdlib 零依賴)。
