# delivery-harness

[English](README.md) | **繁體中文**

一套 **agent-native 的功能/錯誤交付 pipeline harness** —— 給 Claude Code 用的 skills + 狀態機引擎。

> **與 [Harness.io](https://harness.io)(CI/CD 平台)無關。**
> 這是一套 Claude Code 的 skill harness:它把 Claude 接進一條結構化的交付工作流,
> 而不是一個 CI/CD runner。

---

## 這是什麼

`delivery-harness` 是 **Agent Harness** 模式的一份參考實作:
由一層輕薄的 markdown skills、一個 Python 狀態機,以及 bash 編排腳本組成的鷹架,
讓 Claude Code 擁有一條可重複、可稽核的工作流來交付功能與修復錯誤。

agent 不會自由發揮地硬幹。取而代之的是:

1. **一張 ticket**(`docs/features/<NNN>-<slug>/ticket.md`)持有所有狀態 —— phase、track、驗收條件、連結。
2. **`scripts/feature/cli.py`** 強制執行合法的 phase 轉移,並拒絕不合法的轉移。
3. **三個 skills**(`/feature`、`/bug`、`/orchestrator`)給 Claude 進入點,讓它讀 ticket 並推動它前進 —— 從不臆測,永遠驗證。

成果是一條你能稽核的交付流程:每次 phase 變更都記錄在 ticket 裡,每條 AC 都在實作前寫好,而一週後再對同一張 ticket 跑 Claude,它會剛好從上次停下的地方接續。

---

## Tracks(交付軌道)

| Track | 流程 |
|-------|------|
| `full` | intake → requirements → UI prototype → spec → plan → implement → UAT → done |
| `lite` | intake → requirements → spec → plan → implement → UAT → done(無 UI prototype) |
| `bug` | debug → reproduction test → spec → plan → TDD fix → verify → done |
| `spike` | intake → spike → 升級為 `full` 或 `lite` |

---

## 快速開始

請見 **[INSTALL.md](INSTALL.md)** 的三步驟 fork 指南。

```bash
# 安裝後:
python3 scripts/feature/cli.py new my-feature --track full
# 然後在 Claude Code 裡:
# /feature
```

---

## 平行編排(Parallel orchestration)

對於同時跑多張 in-flight CR 的團隊,`/orchestrator` 會為每個功能派出
背景 subagent 並協調它們的回報 —— 讓主迴圈保持在人類的時間尺度上
(提問、決策、委派),而背景 agent 去做緩慢的工作。

---

## 既有相關工作(Prior art)

[`heliohq/ship`](https://github.com/heliohq/ship) 是一個概念核心相同
(結構化的 agent 交付 pipeline)的既有專案。`delivery-harness` 走的是
不同角度 —— 更緊密的 Claude Code skill 整合、明確的狀態機強制執行,以及
平行編排的基礎元件 —— 但概念上的血緣是重疊的。詳細的差異說明 TBD。

---

## 與 Agent Harness 課程 / Harness Notes 的關係

本 repo 是 **Agent Harness** 課程與
[Harness Notes](https://natchung.beehiiv.com) 電子報的
**參考實作**。
課程從第一原理教這套 harness 模式;
本 repo 則是這套模式在 production 裡的樣子。

---

## 結構

```
skills/
  feature/      # /feature skill —— 帶一張 CR 走過 full/lite/spike 軌道
  bug/          # /bug skill —— 帶一個 defect 走過 bug 軌道
  orchestrator/ # /orchestrator skill —— 平行多 CR 協調
scripts/
  feature/      # cli.py + state_machine.py + 測試
  orch/         # wt.sh —— 平行執行用的 worktree 管理
config/
  pipeline.config.example   # codebase 對照表模板(複製 → .claude/pipeline.config)
hooks/
  settings.snippet.json     # 併入 .claude/settings.json
mcp/
  .mcp.json.example         # 選用:Playwright / mobile 測試 MCP
docs/
  2026-06-17-feature-delivery-pipeline-design.md   # 完整 spec
  2026-06-23-parallel-feature-orchestrator-design.md
  2026-06-23-integration-bundle-convention.md
```

---

## 授權

MIT —— 見 [LICENSE](LICENSE)。
