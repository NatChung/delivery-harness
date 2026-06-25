---
name: bug
description: Drive a bug / customer-reported defect through the fix pipeline (debug → reproduction test → TDD fix → verify). Use when triaging or fixing a bug. Shares the feature-pipeline engine; state lives in docs/features/<NNN>-<slug>/ticket.md (track=bug); transitions enforced by scripts/feature/cli.py.
---

# Bug fix pipeline orchestrator

Spec: `docs/2026-06-17-feature-delivery-pipeline-design.md` (Bug track section). Same engine as `/feature`, different track.

**State lives in markdown tickets, not in this session.** Read the ticket first, then act.

## CLI (run from repo root)

- New bug: `python3 scripts/feature/cli.py new <slug> --track bug --severity <P0-prod-down|P1-prod-partial|P2-user-facing|P3-internal>`
- Where am I / what's next: `python3 scripts/feature/cli.py status <id>`
- Advance phase: `python3 scripts/feature/cli.py advance <id> --to <phase>`
- Validate ticket: `python3 scripts/feature/cli.py lint <id>`

Phases: `0-intake → bug-debug → bug-repro → bug-fix → bug-verify → done`.
Rework: `advance <id> --to bug-debug` from bug-repro or bug-verify. Triage-reject: `advance <id> --to rejected` from bug-debug (not-a-bug / dup / wontfix; record the reason in the ticket).

## How to drive a bug

1. `new <slug> --track bug --severity <…>` — set severity honestly (it gates the hotfix lane).
**開工前先判斷分支歸屬**(細節見 orchestrator skill 的「bug 修分支歸屬」):
這個 bug 是「**未上線 feature 的缺陷**」還是「**獨立 / 已上線缺陷**」?
- 未上線 feature → **不走本 bug track**,回該 feature branch 修、重生 integration-bundle。
- 獨立 / 已上線 → 本 bug track 繼續,開 fix 分支。

2. **bug-debug** — use `superpowers:systematic-debugging`. **先用 codegraph 追 root cause**(`mcp__codegraph__codegraph_explore` 理解出問題的區塊;`codegraph_callers`/`codegraph_callees`/`codegraph_impact` 追呼叫/資料流、找壞值從哪來 + 改這會炸到誰)—— 不要無腦 grep。Find the root cause (Phase 1 evidence-gathering — do NOT guess). Record it in the ticket "Root cause" section. If it can't be reproduced, `advance --to on-hold` and gather more data. If it's not-a-bug/dup/wontfix, `advance --to rejected`.
3. **bug-repro** — write ONE failing test that reproduces the bug (`superpowers:test-driven-development`). Pick the layer **by where the customer sees the symptom**（見下方 🚨;不是按「bug 屬哪類」—— 下表只是起點,最終一律以「症狀被看到的那層」為準）:
   - logic/calc **whose output IS what the customer sees**（e.g. a library / compute API where that value is the contract）→ unit test (`<unit: 你的單元測試框架>`)
   - backend behavior/contract → API test (`<API: 你的 API 測試>`)
   - UI behavior → Auto-UI script (`<UI: 你的 E2E/integration 框架>`; reuse the feature pipeline's TestID convention)
   🚨 **複現一定要在客戶實際看到症狀的那層 (the customer-facing surface — UI or API).** 選層級看「症狀在哪被人看到」不是「root cause 在哪」:UI 回報(畫面/欄位/狀態) → UI 層 assert 那一格的值;API/contract 回錯 → API 層 assert 那個回應。**就算根因在後端,只要客戶在 UI 看到症狀,repro 就寫 UI 層** —— 後端綠不證明畫面好。
   ❌ **internal-value / unit assertion ≠ 複現.** 斷言內部回傳值、DTO 欄位、單一函式輸出這種「機制」斷言,**若不是客戶實際看到的那個症狀,不算 `repro-red`** —— 它繞過了客戶到症狀之間整條路徑,綠了使用者仍可能壞。(unit test 只在「客戶症狀本身就在 unit 層」時才算數;否則它是 fix 的附帶單測,不是 repro。)
   Gate `repro-red`: the test asserts **the customer-reported symptom at the surface the customer actually sees it (UI/API)** — not an internal return value / DTO field / single-function output; the failure message matches the reported wrong behavior; it would PASS only once the root cause is fixed. Branch: `fix/<id>-<slug>` (cut from the repo's real branch).
   ⚠️ **reproduce-confirm gate (進 bug-fix 前):** bug-debug 追到的 root cause 是**假設**,不是結論。「code-trace 到某行」≠「已複現」—— **未在 API/UI 層實際把症狀複現出來(看到它紅在客戶報的那一格/那個回應)之前,不准進 bug-fix**。intake 順暢、trace 到行都不算驗證。
   Rationale: 繞過症狀層複現(用 internal-value/unit 斷言充數、或 trace 到行就開修)會產生幻影測試 / 假陽性 / regression 漏抓 —— 這是跨 fork 實測反覆爆過的教訓。
4. **bug-fix** — fix the root cause until the repro test is green (`test-driven-development` + `executing-plans`). Gate `tests-green`: repro test green AND existing tests not broken. If 3 fixes fail, question the architecture (systematic-debugging Phase 4.5).
5. **bug-verify** — verify against the original report. Gate `bug-verified`: reporter/QA confirms. The repro test stays as a regression test. Then `advance --to done`. On failure, `advance --to bug-debug` (rework). Finish with `superpowers:finishing-a-development-branch` + a `docs/bugs/` reflection entry.

## 並行多條(orchestrator)
手上 **≥2 條** feature/bug 想在**同一 session 並行**推進(填滿各步驟數分鐘的 agent 等待) → 用 **`orchestrator`** skill(主迴圈當純調度、subagent 只做生產、worktree 隔離)。只有 1 條就照本 skill 序列跑即可(state 在 ticket、切換免費)。

## Review(改完一律用 subagent,**不要**用 `/review` 或 `/code-review`)

bug-fix `tests-green` 後、進 bug-verify **前**,**一律用 `superpowers:requesting-code-review`** 跑一輪 —— 它 **dispatch 一個 subagent(fresh context)** review 修正 diff + repro test,比主執行緒自審更能抓 regression / scope drift。

⚠️ **不要用 `/review` 或 `/code-review`**(主執行緒 inline / cloud,不開 fresh subagent)。收到回饋走 `superpowers:receiving-code-review`(不盲改)。P0/P1 hotfix lane 趕也要跑(可只 review 核心 diff)。

## Severity & hotfix lane (convention — not code-enforced)

- `P0-prod-down` / `P1-prod-partial` (prod broken — live App Store / Play / prod gateway): **hotfix lane** — debug → repro → fix → fix prod directly + land the regression test, do stg UAT after the fact. Note `hotfix: true` in the ticket.
- `P2-user-facing` / `P3-internal`: normal lane — through stg, then verify.

## Branch

`fix/<NNN>-<slug>` (NOT `feature/`). `bug-repro` + `bug-fix` share one branch. Merge only after the `tests-green` gate.

## docs/bugs/ relationship

The bug track = workflow + state. `docs/bugs/` = the post-fix lightweight pattern reflection (write it at bug-verify→done, see `docs/bugs/README.md`). Complementary, not duplicate.
