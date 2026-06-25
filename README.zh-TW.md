# delivery-harness

[English](README.md) | **繁體中文**

一套 **agent-native 的功能/錯誤交付 pipeline harness** —— 給 Claude Code 用的 skills + 狀態機引擎。

---

## 這是什麼

`delivery-harness` 給 Claude Code 一條**可重複、可稽核的工作流**來交付功能與修復錯誤,而不是讓 agent 自由發揮地硬幹。

它解決的問題:一個即興發揮的 agent,狀態只活在對話裡、不留下「為什麼這樣做」的紀錄、也沒有任何東西攔著它跳過步驟。這套 harness 把工作流的狀態**從模型裡搬到磁碟上**,靠三塊承重結構:

- **ticket 是唯一真相來源。** 每張 CR 或 bug 是一個 markdown 檔 `docs/features/<NNN>-<slug>/ticket.md`,frontmatter 持有 phase、track、驗收條件,body 累積 gates、連結,以及 phase 變更歷史。agent 先讀 ticket 再動作 —— 所以一週後再跑的 session,會在任何一台機器上剛好從上次停下的地方接續。
- **CLI 是被強制執行的狀態機。** `scripts/feature/cli.py`(`new` / `status` / `advance` / `lint`)是**唯一**被認可、能改 ticket phase/track 的途徑。`advance` 拒絕不合法的轉移並印出合法集合,所以 agent 沒辦法偷偷跳過 spec、plan 或 UAT —— 規則活在 code 裡,不是一段模型能說服自己繞過的 prompt。
- **skills 是懂 phase 的進入點。** `/feature` 與 `/bug` 帶一張 ticket 走完它的 track;`/orchestrator` 並行跑好幾張。除了路由,skills 還編進了 pipeline 賴以為生的操作紀律:動作前先讀 ticket、改 code 前先用 code graph 摸清既有結構、每個產出物(spec、plan、diff)都過一個 fresh-context 的 review subagent 把關、可逆的選擇就 decide-and-proceed 而不是卡住問。

成果是一條你能稽核的交付流程:每次 phase 變更都記在 ticket 裡,每條 AC 都在實作前寫好,而同一張 ticket 可跨 session、跨機器接續。

---

## Tracks(交付軌道)

| Track | 流程 |
|-------|------|
| `full` | intake → requirements → UI prototype → spec → plan → implement → UAT → done |
| `lite` | intake → requirements → spec → plan → implement → UAT → done(無 UI prototype) |
| `bug` | debug → reproduction test → spec → plan → TDD fix → verify → done |
| `spike` | intake → spike → 升級為 `full` 或 `lite` |

表上是順向的「happy path」。狀態機也描述了更亂的現實:**rework 回圈**(UAT 失敗會繞回 spec 或 implement)、**reopen edge**(一張 `lite` CR 後來發現需要 prototype 就轉成 `full`)、**spike 收斂**(`spike` 在 feasibility 確定後升級成 `full` 或 `lite`),外加 **`on-hold`** 暫停與 **`done` / `rejected`** 終止狀態。不合法的跳轉一律拒絕。

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
(提問、決策、委派),而背景 agent 去做緩慢的工作,
並由 `scripts/orch/wt.sh` 給每個並行的 implement 一個隔離的 worktree。

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
