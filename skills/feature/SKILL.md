---
name: feature
description: Drive a customer feature through the delivery pipeline (intake → requirements → prototype → spec → plan → TDD → stg UAT). Use when starting, advancing, or checking a feature/CR. State lives in docs/features/<NNN>-<slug>/ticket.md; transitions are enforced by scripts/feature/cli.py.
---

# Feature Delivery Pipeline orchestrator

Spec: `docs/2026-06-17-feature-delivery-pipeline-design.md`.

**State lives in markdown tickets, not in this session.** Always read the ticket first, then act.

## CLI (the state machine — use it, don't hand-edit phase/track/id)

Run from repo root:
- New feature: `python3 scripts/feature/cli.py new <slug> --track <full|lite|spike>`
- Where am I / what's next: `python3 scripts/feature/cli.py status <id>`
- Move to next phase: `python3 scripts/feature/cli.py advance <id> --to <phase>`
- Validate a ticket: `python3 scripts/feature/cli.py lint <id>`

`advance` refuses illegal transitions and prints the allowed set. On `1b-spike → 2-ui-prototype` it converts track to `full`; on `1b-spike → 3-spec` it converts to `lite`.

## Tracks

- **full** — new UI: 0-intake → 1-requirements → 2-ui-prototype → 3-spec → 4-plan → 5-implement → 6-uat → done
- **lite** — no new UI / backend-only: skips 2-ui-prototype (3-spec writes AC over the API contract, no TestID)
- **spike** — AI/data/external-integration: 1b-spike measures feasibility first, then convert to full or lite

**選 track 別只看「我方有沒有新 UI」**:`track = max(技術上有新 UI 面, 客戶要不要先在 STG 看畫面)`。後者(客戶要先看 → full + prototype)很容易漏問,漏了就會 lite→full reopen 來回。**好消息**:`reopen` edge(`3-spec → 2-ui-prototype` 自動轉 full)讓猜錯成本很低 → **別為了一次猜對而過度糾結,猜錯 reopen 就好**。

## 讀 code 一律先用 codegraph(重要)

凡是要追既有 code 的階段(**phase 1 需求** 讀相關 code、**phase 3 spec** 讀 UI 樹 / 列受影響面),**先用 codegraph,不要無腦 grep**(全域 CLAUDE.md 規則,這裡列為必做):
- `mcp__codegraph__codegraph_explore` — 「X 怎麼運作 / 在哪 / 這塊架構」一次拿到相關 symbol 的源碼
- `codegraph_callers` / `codegraph_callees` / `codegraph_impact` — 誰 call、call 誰、**改這會炸到誰**(決定 prototype 動到哪、AC 要涵蓋哪些路徑)
- 跨多子 repo 都吃。新 session 重啟後有 MCP 工具。

## How to drive a feature

1. Read `status <id>` → note the current phase + valid next phases.
2. Open `docs/features/<id>-<slug>/ticket.md`. Do the work for the current phase (see the per-phase responsibilities + gates in the spec). Record gates / feedback / branch / source in the ticket body yourself — the CLI does not manage those.
3. When the phase's gate is met, `advance <id> --to <next>`.
4. On UAT failure, advance back to `2-ui-prototype` / `3-spec` / `5-implement` (rework). On giving up, advance to `on-hold` then `rejected`.

## 並行多條(orchestrator)
手上 **≥2 條** feature/bug 想在**同一 session 並行**推進(填滿各步驟數分鐘的 agent 等待) → 用 **`orchestrator`** skill(主迴圈當純調度、subagent 只做生產、worktree 隔離)。只有 1 條就照本 skill 序列跑即可(state 在 ticket、切換免費)。

## Phase → which skill does the work (from the spec)

- 1-requirements ← `superpowers:brainstorming` (code-aware — **先用 codegraph 摸清相關 code 再問澄清題**)
- 1b-spike ← brainstorming + a thin real spike; record a feasibility note; gate `feasibility-approved`
  - ⚠️ **spike 是抓「外部依賴不可靠」最便宜的點 —— 別只測 happy path 一兩次就過**。接外部 AI/外部系統/API 時,`feasibility-approved` 要含:**用真實典型輸入多打 N 次(≥5)測失敗/空回/非確定率 + 延遲分佈**,直打外部端點(curl,別經過自己的壓圖/封裝層)。教訓:曾因「用刁鑽大雜燴樣本 + 太少 trial」過了 gate,結果漏掉某外部服務約 1/3 空回,拖到 UAT 才爆、還一度誤判成自己的 bug。**薄證據跨系統邊界歸咎前,先做受控重複。**
- 2-ui-prototype ← `feature-ui-prototype` (later plan) — UI-only+mock on a branch
- 3-spec ← `feature-spec` (later plan) — diff branch → AC/BDD + TestID → spec.md(**用 codegraph 讀懂 UI 樹 + `codegraph_impact` 列 AC 要涵蓋的路徑**)
- 4-plan ← `superpowers:writing-plans` (input = spec.md)
- 5-implement ← `superpowers:test-driven-development` + `superpowers:executing-plans`; gate: tests-green + mock-data-cleared
- 6-uat ← `superpowers:verification-before-completion` + `superpowers:finishing-a-development-branch`

## Review(產出物把關 — 一律用 subagent,**不要**用 `/review` 或 `/code-review`)

每個重要產出物在 advance 到下一階段**前**跑一輪 review,**一律用 `superpowers:requesting-code-review`** —— 它會 **dispatch 一個 subagent(fresh context)**,比主執行緒自審更能抓矛盾 / 漏洞 / scope drift。

⚠️ **不要用 `/review` 或 `/code-review`**(那是主執行緒 inline 或 cloud,不開 fresh subagent)。要的就是獨立 subagent context。

- **3-spec 後** → review `spec.md`(doc review 角度:spec coverage / 內部一致 / placeholder 掃描 / scope / 歧義 / 完整性 / 技術可行,**非** code review)。spec/plan 是 markdown,要把 prompt template 從「code change」改寫成文件 review,並把 doc + 相關 spec/code 都餵 reviewer subagent(全域 CLAUDE.md 已定此規則)。
- **4-plan 後** → review plan 文件(同 doc review 角度)。
- **5-implement(tests-green 後、進 6-uat 前)** → review 實作 diff(標準 code review)。
- 收到 review 回饋後 → 走 `superpowers:receiving-code-review`(技術嚴謹驗證,不盲改、不表演式同意)。

## 多功能一起上 staging 給客戶 review(bundle)

多個 CR 要**打包成一個 staging build** 給客戶下載試(常跨 app+api+cms)時,branch 怎麼開/合/落地 → 照 **`docs/2026-06-23-integration-bundle-convention.md`**(`integration-bundle-<bundle-slug>` 整合分支 + 五鐵則 + mock gate)。各 feature ticket 仍獨立跑 pipeline,`6-uat` = 已在 `integration-bundle-*` 上、客戶 review 中。

## 效率紀律(每個 CR 重複的 tax,刻意壓)

- **可逆的內部決策 → default-and-proceed,別問**。`AskUserQuestion` 只留給:**客戶面 / 不可逆 / 花錢 / 動 prod** 的決策。track 選哪個、測哪層、檔名、要不要先 commit 這種**可逆內部選擇**,自己挑合理 default、講一句「我選 X,不對再說」往下走 —— 把決策權塞回 user 等於 agent 不肯 commit default。(實測:一個功能跑下來 AskUserQuestion 很容易超過 20 個,一半可省。)
- **review 深度依 task 風險縮放,別每縫都全套**。spec/plan/實作 diff 的 gate review 有價值(實測每關都有抓到東西:spec 遺漏/矛盾、plan 陷阱、uat flaky bug)—— **但小而機械的 task**(改一條 route、4 行 wiring)吃 per-task review **又**進 final whole-branch review = 重複。trivial task 信 final review 就好,把 per-task review 留給有邏輯/有風險的 task。
- **本機驗證優先寫成可重跑的 test,別手點**。要驗真整合 → **<UI: 你的 E2E/integration 框架> / API test 對真 backend**(可重跑 = regression 資產 + 多 trial 自動暴 flake),別用大量手動點(丟棄式、下個 CR 全部重來)。手動 driving 留給「真的要人眼看版面」那一下。

## Not yet built

`feature-intake`, `feature-ui-prototype`, `feature-spec`, CMS test bootstrap — separate plans. Until then, do those phases manually and keep the ticket updated.
