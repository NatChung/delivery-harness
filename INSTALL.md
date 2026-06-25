# Install into your repo（AI-bootstrap）

你(target repo 的 AI)拿到本檔 URL + 指定 prefix(例 `dek-`),照以下 9 步把 pipeline 裝進當前 repo。全程在 target repo 根目錄操作。

1. fetch 本 repo 的 `skills/*`、`scripts/*`、`docs/features/*`、`config/*`、`hooks/*`(GitHub raw;raw base 例:`https://raw.githubusercontent.com/NatChung/delivery-harness/main/<path>`;從 main 取穩定版)。
2. copy `skills/{feature,bug,orchestrator}` → `<repo>/.claude/skills/<prefix>-{feature,bug,orchestrator}/`;copy `scripts/feature` `scripts/orch` → `<repo>/scripts/`。(目標目錄不存在先 `mkdir -p`,例 `.claude/skills`、`docs/features`;乾淨 repo 可能缺這些)
3. **copy 引擎 runtime 依賴**:`docs/features/{INDEX.md,_template.md,_template_bug.md}` → `<repo>/docs/features/`(`cli.py new` 執行時要讀;缺了第一次 `cli.py new` 就炸。`INDEX.md` 保持空 registry:header + 分隔線,無 data row)。
4. **套 prefix**:把三個 skill 目錄改名加 `<prefix>-`;改 body 內彼此 cross-ref(feature/bug 指向 orchestrator;orchestrator 指向 feature/bug)與 slash 引用(`/feature`→`/<prefix>-feature` 等);標題列的 skill 名也改。**改名範圍完整清單**:
   - skill body 內的 skill 名(`name: feature` → `name: <prefix>-feature`)與 slash 指令(`/feature` → `/<prefix>-feature`)
   - `scripts/feature/README.md` 內的 skill 路徑引用(`.claude/skills/{feature,bug,orchestrator}/` → `.claude/skills/{<prefix>-feature,<prefix>-bug,<prefix>-orchestrator}/`)
   - skill body 內的**範例路徑**(如 `~/.cache/delivery-wt/` 下的路徑前綴),要與 `pipeline.config` 的 `WT_CACHE_ROOT` 配置命名一致(例:若 `WT_CACHE_ROOT="${WT_CACHE_ROOT:-$HOME/.cache/<prefix>-wt}"`,則範例改寫成 `~/.cache/<prefix>-wt/...`)
   - **不動**:state-machine 的 track 關鍵字(`full/lite/spike/bug`)與 `scripts/feature/cli.py` 引擎程式碼保持原樣;檔案路徑 `scripts/feature/`、`docs/features/` 保持原樣
5. 從 `config/pipeline.config.example` 生 `<repo>/.claude/pipeline.config`,**問 user** 填:每個 codebase 的 `CODEBASE_DIR`(相對路徑)、`CODEBASE_BRANCH`(主分支)、`WT_CACHE_ROOT`(worktree 快取根)。(若呼叫者已在指示中給齊 codebase map / branch,直接填、不必再問)
6. **hooks**:檢查本 repo `hooks/settings.snippet.json`。若非空且與 pipeline 相關 → merge 進 `<repo>/.claude/settings.json`;若空殼 → 跳過並告知 user 無 hook 需裝。
7. (選用)依 `mcp/README.md` 接測試 MCP(Playwright / mobile)。**post-implement UAT 重度靠 MCP** → 建議裝;不裝則 UAT 階段要另接測試工具。
8. 生 `<repo>/.claude/skills/.harness-version`,照 `config/harness-version.example` 三行,`commit` 填 install 當下本 upstream 的 `git rev-parse HEAD`、`installed` 填今日。
9. **驗收三條**,全綠才算裝成:
   - `cd <repo>/scripts/feature && python3 -m unittest -v` → 引擎測試綠。
   - `<repo>/scripts/orch/wt.sh list <任一 codebase-key>` → 正常列(驗 worktree 半邊 + pipeline.config 讀得到)。(前提:CODEBASE_DIR 指向的 git workdir 已存在;指到非 git 目錄會 exit 128)
   - `grep -rnE "(^|[^A-Za-z0-9_/-])/(feature|bug|orchestrator)([^A-Za-z0-9_/-]|\$)" <repo>/.claude/skills/<prefix>-*` → **零 hit**(驗 step 4 改名乾淨)。**注意**:邊界條件刻意排除路徑語境 —— `scripts/feature/`(前有字母)、`docs/features`(後接 `s`)、純文字 `feature/bug`(前有字母)都不算 hit;只抓 `` `/feature` `` 這種真 slash-command 調用,改名後該歸零。**別用裸 `grep "/feature"`**(會撞 script/doc 路徑、數學上不可能零)。

裝完該 repo 有 `<prefix>-{feature,bug,orchestrator}` 三個 skill + `scripts/{feature,orch}` + `docs/features/` 模板 + `.harness-version`。

前提:

- repo 有 Python3(engine 純 stdlib 零依賴)。
- **superpowers skills 已安裝**(本 pipeline 各 phase 的實作重度依賴 `superpowers:*`:brainstorming、writing-plans、test-driven-development、executing-plans、verification-before-completion、finishing-a-development-branch、requesting-code-review、systematic-debugging)。**先檢查**:Claude Code 裡 `superpowers:*` skills 是否可用(看 skill 列表,或試 `/superpowers:brainstorming`)。**沒裝 → 請 user 自行安裝**(`/plugin install superpowers@claude-plugins-official`,來源 <https://github.com/obra/superpowers>);**本安裝流程不代裝 superpowers**。缺它則 intake/spec/plan/implement/uat 各 phase 無 skill 可執行。
