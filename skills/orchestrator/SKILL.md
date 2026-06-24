---
name: orchestrator
description: Use when 同時並行多個 feature/bug、需要 orchestrator 調度多條 CR、並行跑 feature/bug pipeline、parallel features across multiple in-flight CRs simultaneously. NOT for single feature — use /feature directly.
---

# Parallel Feature/Bug Orchestrator

Spec: `docs/2026-06-23-parallel-feature-orchestrator-design.md`

## Cheat-Sheet

```
主迴圈零延遲(§2 鐵則):主迴圈只做 6 件秒級事 = 收feature/問你澄清/決策/cli.py advance/派subagent/收report
任何「讀·抓·搜·草擬·生產」要超過幾秒 → run_in_background:true 丟背景 subagent，主迴圈不自己做(含 codegraph、讀外部文件、spec/plan/impl)
派完背景就回頂:當輪去做下一件秒級事(問下一條 feature / 問已回報的澄清題)再交回控制權，不 inline 等
進場先 batch 收齊 fleet(§1b:A/B/C 連文件一次給) → 各派 intake-research 背景 → 邊回邊問澄清
決策 = reversible provisional → 往下不擋；load-bearing(需求等) → 擋下游；不可逆/等客戶/動prod → 真問
worktree = scripts/orch/wt.sh add/remove；build 可並行但隔離；merge 序列化
狀態 = ticket(真相) + INDEX.md(艦隊) + .superpowers/orch/confirmations.md(在飛+BLOCKING)
file-handoff = subagent 寫 scratchpad report；orchestrator 只收 STATUS + 一行摘要
```

---

## 1. 何時用

開 orchestrator 的條件：手上 **≥2 條** feature/bug **且有重疊的 agent 等待**（某條在跑 spec/plan/implement，另一條也在排等）。

**只有 1 條 → 直接 `/feature`**（state 在 ticket，本來就免費切換，不需這套）。

---

## 1b. 入口：叫一次 + 進場先 batch 收齊 fleet

`/orchestrator` 是**模式，不是 per-feature 指令** —— **叫一次**進模式，之後 fleet **用對話餵大**，不用每條重叫 skill。

**進場第一個動作 = batch 收齊 fleet,不要一拿到第一條就鑽進去。** 進模式後先反問 user:
> 「**把這輪要並行的都給我** —— 每條:slug + 需求/文件連結 + track(full/lite/spike/bug)。一次列齊我再開跑。」

- ⚠️ **為何先收齊**:orchestrator 的並行只在 **≥2 條同時在飛**時才有效益。拿到第一條就一頭栽進它的研究(讀文件、codegraph),主迴圈會被單條佔滿、根本開不了第二條 —— **這是本 skill 實測爆過的頭號錯誤**(主迴圈 8 分鐘自己讀 Google Doc、0 次回頭收第二條,見 §2 零延遲鐵則)。
- user 真的只有 1 條 → 提醒「**1 條用 `/feature` 就好**」(§1),orchestrator 沒並行效益。
- **加一條**:`python3 scripts/feature/cli.py new <slug> --track <full|lite|spike|bug>` 建 ticket,文件/原文寫進 ticket「來源/需求摘要」段。
- **分段輸入 OK**:一條的資料可跨多則訊息(先 Notion、再 Figma、再 API 合約)→ **累積進同一 ticket**(後到的補進去,**別重建**)。`cli.py new` 只在該 slug 第一次出現時跑。
- **收齊後**:對每條派一個 **intake-research 背景 subagent**(`run_in_background:true`;codegraph 摸既有 code + 讀附的文件 + **草擬澄清題** → 寫進 report)。主迴圈**派完就回頂**,邊收 report 邊問 user 澄清題(§2)。
- **晚到的 feature 隨時可加**:加新條時**別停既有的**背景 subagent;新條一樣派 intake-research 背景。
- orchestrator 有決策需求 → **反過來問 user**(§4 即時中斷 + queue,標 feature id)。

---

## 2. 核心迴圈（每輪）—— 主迴圈零延遲

### 🔑 鐵則:主迴圈只做秒級事,任何延遲一律背景化

主迴圈(你)是唯一能調度 + 問 user + 決策的那條 thread。**它一旦自己去做有延遲的事(讀文件、codegraph 探查、草擬、寫 spec/plan/code),那條 thread 就被佔住 —— 收不了下一條 feature、也調度不了別條,並行直接歸零。**

> 實測 RED:首跑時主迴圈自己 4× WebFetch 讀 Google Doc + codegraph,**8 分鐘沒回頭收第二條**。這就是「block 了 event loop」—— 主迴圈做了 blocking I/O,而非丟 worker。

**主迴圈只准做這 6 件事(都秒級),其餘一律 `Agent(run_in_background:true)` 丟背景:**
1. 收 user 餵的新 feature(`cli.py new` 建 ticket、把連結貼進 ticket)
2. 問 user 澄清題 / 收 user 答案
3. 決策(provisional / advance gate / 真阻塞路由,§4)
4. `cli.py advance` / 更新 confirmations.md
5. `Agent(run_in_background:true)` 派 subagent(含 reviewer)
6. 收 subagent 的 report callback(讀 STATUS 一行;要細節才 Read report file)

**判準(observable)**:一個動作若是「**讀 / 抓 / 搜 / 草擬 / 生產**」且要超過幾秒 → 它是延遲工作 → **派背景 subagent,主迴圈不自己做**。涵蓋 intake 的 codegraph、requirements 讀外部文件/草擬澄清題、3-spec/4-plan/5-implement 全部。

**派完背景就回頂**:做完上面任一件秒級事後,**當輪立刻去做下一件能做的秒級事**(問下一條 feature、問某條已回報的澄清題、處理剛回的 report),然後把控制權交回 user;**絕不在原地 inline 等 subagent**(背景 subagent 完成時 harness 會自動再叫你)。

### 每輪流程（compaction 後也走這個復原）

1. 讀 `docs/features/INDEX.md`(艦隊) + `.superpowers/orch/confirmations.md`(在飛 subagent + BLOCKING)
2. `cli.py status <id>` for each in-flight feature(不靠記憶)
3. 每條看當前 phase 缺什麼,**把延遲部分派背景 subagent**:
   - **1-requirements** → 派 **intake-research subagent**(codegraph + 讀文件 + 草擬澄清題 → report)。**research 回來後**,主迴圈才做那一片秒級事:把草擬的澄清題問 user(§4:requirements provisional 是 BLOCKING,等 user/客戶答才 advance)。
   - **3-spec / 4-plan**(hub docs) → 派背景 subagent,**只寫檔不 commit**(hub 同 repo,並行 commit 撞 index)→ 主迴圈收回後**串行 commit**,`git add docs/features/<id>-<slug>/` **scope 到該 feature 路徑**(別 `git add .`/`git add docs/`)。不需 worktree。
   - **5-implement**(submodule code) → 先 `wt.sh add` 開 worktree → subagent 在 worktree branch **commit**(隔離、不撞 hub index)。
   - **2-ui-prototype / 6-uat**:只有「**人眼看版面 / 客戶簽核**」那一薄片是真同步、留主迴圈;其**研究/build 部分**(codegraph 摸 UI 樹、跑 build)照樣背景化。
4. **subagent 回** → 主迴圈執行 `superpowers:requesting-code-review`(派 reviewer 兄弟 subagent,**也是背景**)→ 收 review → provisional-decide 或 `cli.py advance` → 派下一步
5. 更新 confirmations.md(記新的 BLOCKING / 在飛 subagent / worktree)

### 並行流程示例（零延遲版）

```
進場:batch 收齊 A/B/C → 各派 intake-research 背景(run_in_background) → 主迴圈回頂,不等
A research 回(帶草擬澄清題) → 主迴圈問 user A 的澄清題   ← 此刻 B/C research 仍在背景跑
user 答 A → cli.py advance A → 派 A 的 3-spec 背景 → 回頂
B research 回 → 問 user B 澄清題 …                       ← 「派完就回頂收下一個」永遠成立
```

**反例(RED,別這樣)**:`收到 A → 主迴圈自己 codegraph + 4×WebFetch 讀 A 的文件(8 分鐘)→ 才回頭` ❌。讀文件是延遲工作,該在 intake-research **背景** subagent 裡,主迴圈派完就該回頂收 B。

---

## 3. 下放粒度規則 + Dispatch Prompt 範本

⚠️ **最脆弱的鐵則**：subagent 讀到 feature skill 裡的「dispatch review」行 → 它會自己叫 review → 巢狀、review 結果回不到 orchestrator。dispatch prompt **必須 OVERRIDE 覆蓋**。

**規則**：只下放單一生產步驟（寫 spec.md、寫 plan.md、實作一個 task）。review / 決策 / advance 永遠留 orchestrator。

### Dispatch Prompt 範本（必須含 OVERRIDE 區塊）

```
你是 feature <NNN>（<slug>）的 production-only subagent，當前 phase: <phase-name>。
工作位置：
- 5-implement → worktree `<wt.sh add 印的路徑>`（已 checkout feature/<NNN>-<slug>）
- 3-spec / 4-plan → **無 worktree**，直接編輯 hub `docs/features/<NNN>-<slug>/`（你只寫檔）

任務：<具體生產步驟，例：依 spec.md 寫出 implementation plan 到 docs/features/NNN-slug/plan.md>

context：<必要的 spec 路徑、ticket 路徑、相關 API 等>

⚠️ OVERRIDE — 覆蓋 skill 指令，強制執行：
- 不要叫 superpowers:requesting-code-review 或任何 review step
- 不要叫 cli.py advance
- 不要向 user 提問（AskUserQuestion）
- **commit 規則**：5-implement → 在 worktree branch commit 你的生產(+test)；3-spec / 4-plan → **只寫檔、不要 commit**（hub docs 由 orchestrator 串行 commit，避免並行撞 hub index）
- 生產任務完成後：立即停止，回傳
- 把所有細節、diff summary、決策說明寫入 <scratchpad-report-path>
- 回傳格式：STATUS: done|blocked — <一行摘要>
```

### intake-research 變體（1-requirements 用,§2 步驟3）

requirements 的延遲部分(讀 code + 讀文件 + 草擬澄清題)就是靠這個背景 subagent,讓主迴圈不必自己讀。**read-only research,不寫 production、不 commit、不開 worktree。**

```
你是 feature <NNN>（<slug>）的 intake-research subagent(read-only)。
任務:摸清需求、把澄清題草擬好,讓 orchestrator 主迴圈直接拿去問 user。
1. 用 codegraph 摸既有可複用 code(query/callers/callees/impact),記下模板與改點。
2. 讀附的文件/連結(<doc URL / Notion / Figma / API 合約>),抽出規格(URL、欄位、流程、帶入資料等)。
3. 把以下寫進 report file <scratchpad-report-path>:
   - 現況/可複用(codegraph 發現)
   - 從文件抽到的規格(逐項)
   - **草擬的澄清題清單**(load-bearing 的標星;附你建議的 provisional 預設值)
   - 可逆 provisional 建議(track、欄位、入口位置…)

⚠️ OVERRIDE — 覆蓋 skill 指令,強制執行:
- 不要叫 superpowers:requesting-code-review 或任何 review step
- 不要叫 cli.py advance、不要改 ticket 的 phase
- 不要向 user 提問(AskUserQuestion)——「問 user」是 orchestrator 主迴圈的事;你只**草擬**題目寫進 report
- 不要寫 production code / spec / plan(這是 research,不是生產)
- 完成後立即停止,回傳格式:STATUS: done|blocked — <一行摘要>
```

---

## 4. 決策路由

| 類型 | 定義 | 動作 |
|------|------|------|
| **reversible provisional** | 可逆內部決策（檔名、測哪層、版面細節、架構選擇）| decide-and-proceed；記 confirmations（kind=reversible）；不擋下游 |
| **load-bearing provisional** | 需求假設 / 下游 3+ phase 建在上面（尤其 requirements）| provisional 決定 + 繼續本 phase；**擋下游 advance** 直到你確認；記 confirmations（kind=BLOCKING） |
| **真阻塞** | 不可逆 / 等客戶 / 花錢 / 動 prod | 即時 `AskUserQuestion`（標 feature id）；同時到的排隊逐個問 |

⚠️ **brainstorming（1-requirements）的 provisional 產出天生是 BLOCKING**：agent solo 跑需求只能給假設，不是驗證過的需求（unknown-unknowns 需要對話才浮出）。requirements provisional 必標 BLOCKING，等你或客戶確認後才 advance 到 3-spec。

---

## 5. Worktree（一律用 wt.sh）

**只有 `5-implement`(動 submodule code)需要 worktree**;`3-spec`/`4-plan` 是 hub docs、**不開 worktree**。`wt.sh add` 前 **feature branch 要先存在**(pipeline 在 prototype/implement 階段才開 branch)。`wt.sh add` 印出的路徑是 `<repo>-<branch-slug>`(slug 過,非 `repo-NNN`),**用它印的路徑**,別自己拼。

```bash
# 開 worktree（5-implement 派 subagent 前）
scripts/orch/wt.sh add <repo> <feature-branch>
# → 回傳 worktree path → 填進 dispatch prompt + confirmations.md

# 收（landing 完成或 feature 放棄）
scripts/orch/wt.sh remove <repo> <feature-branch>

# 孤兒清理（BLOCKED/放棄沒清）
cd codebases/<repo> && git worktree prune
```

**禁止**：
- 手敲 `git worktree add`（用 wt.sh，它處理 hub 外路徑 + 避免 hub 誤掃）
- 用 `Agent(isolation:"worktree")`（它 worktree 的是 hub，不是 submodule）
- orchestrator 在飛時跑 `sync-all.sh`（會撞有 uncommitted work 的 worktree）

---

## 6. Build / Merge / 排程

**Build（可並行，但要隔離）**：
- 語言層級的依賴安裝先序列化（共用 cache race），build 本身可並行
- UI/integration test 各給不同 runner/emulator
- **並行上限 = 機器資源**（spec/plan/review 純思考類可全並行）

**Merge（序列化）**：一條先 merge → **該 codebase 的主 branch**（各 codebase 主 branch 見 `.claude/pipeline.config` 的 `CODEBASE_BRANCH`）；其餘 **rebase** 到新主 branch 再進。多條一起上 STG → 走 `stg-review-bundle-convention`（`stg-review-<bundle-slug>` 整合分支）。

**排程**：ticket 的 `conflicts:` 標記的 feature（動到同檔/同 branch）→ **不同時 implement**，錯開排程避免 merge 衝突。

---

## 7. Mock Gate（landing 前強制）

Landing 前必須全過，才可 advance 到 done：

```bash
# 1. grep 乾淨
grep -rnE "PROTOTYPE-MOCK|FEATURE-MOCK" codebases/
# → 必須零 hit

# 2. confirmations.md 無 BLOCKING 未確認
# → 掃所有 kind=BLOCKING 欄位，確認你都 ack'd
```

任一未過 → 不准 landing，orchestrator 暫停該條直到清乾淨。

---

## 8. confirmations.md 格式

路徑：`.superpowers/orch/confirmations.md`（已被 `.gitignore` 的 `.superpowers/` 覆蓋）

每輪開始先讀它；compaction 後靠它 + `git log` + ticket 復原 orchestrator 狀態。

**兩個正交軸別混在一欄**:`status`(subagent 生命週期:`in-flight`/`done`/`ack'd`)與 `kind`(決策性質:`reversible`/`BLOCKING`;純追蹤在飛、還沒產生決策的列 `kind=—`)。

```markdown
| feature-id | phase | status | kind | 假設/問題 | subagent-task-id | worktree-path | dispatch-時間 |
|---|---|---|---|---|---|---|---|
| 001 | 5-implement | in-flight | — | impl subagent 進行中 | task-abc123 | ~/.cache/delivery-wt/app-feature-001-sample-feature | 2026-01-01T14:00 |
| 003 | 4-plan | done | reversible | 採 layered repo 架構 | task-def456 | —（hub docs，不開 worktree） | 2026-06-23T14:05 |
| 002 | 1-requirements | done | BLOCKING | UX flow 假設：用戶從列表進詳情 | — | — | 2026-06-23T13:50 |
```

**`kind=BLOCKING` 且 `status≠ack'd` 的行** = 該 feature 下游 advance 被擋,等你確認。確認後 `status→ack'd` 或刪行。掃 gate 只看 `kind=BLOCKING`(與 status 正交,清楚)。

---

## 9. 失敗處理

| 失敗 | 處理 |
|------|------|
| subagent crash / timeout | ticket 未 advance（本來就是，不用回滾）→ 查 worktree 有無半成品 → 修完重派，或標 BLOCKING 問你 |
| 孤兒 worktree（BLOCKED/放棄沒清）| confirmations.md 有 worktree-path → `wt.sh remove` 或 `cd codebases/<repo> && git worktree prune` |
| 同 submodule merge 衝突 | 序列化 + rebase（第6節）|
| build 資源打架 | 降並發上限（第6節）|
| orchestrator context 爆 | file-handoff（第11節）；若已爆：讀 confirmations.md + `cli.py status` 全部 in-flight 復原 |

---

## 10. 鐵則（不可談判）

0. **主迴圈零延遲**(§2):主迴圈只做 6 件秒級事;任何「讀/抓/搜/草擬/生產」超過幾秒 → `run_in_background:true` 丟背景,主迴圈派完就回頂收下一條。**主迴圈自己 inline 讀文件/codegraph = 並行歸零(實測 RED)。**
1. **每輪必讀 confirmations.md**（別靠記憶，撐 compaction）
2. **進場先 batch 收齊 fleet**(§1b),別拿到第一條就鑽進它的研究
3. **subagent 框死在生產/research**（dispatch prompt 必含 OVERRIDE 區塊，明寫覆蓋 skill review 步驟）
4. **review / 決策 / advance 永遠在 orchestrator**（never 讓 subagent 叫 review）
5. **worktree 走 wt.sh**（不手敲 `git worktree`，不用 `isolation:"worktree"`）
6. **load-bearing provisional 擋下游**（BLOCKING 未確認 → 該條 feature 不 advance，讓別條繼續填等待）
7. **在飛時不跑 sync-all**

---

## 11. Orchestrator Context 存活（File-Handoff）

N 條並行 → 各條 subagent 的細節堆進 context = 必爆。規則：

- dispatch prompt 給 subagent 一個 **scratchpad report path**（`/private/tmp/claude-501/.../scratchpad/feat-<id>-<phase>-report.md`）
- subagent **把所有細節寫進 report file**（diff、決策說明、遇到的問題、下一步建議）
- subagent **回傳只給** `STATUS: done|blocked — <一行摘要>`（進 orchestrator context 的只有這行）
- orchestrator 需要細節時 **Read report file**（不讓 subagent 重述）
- N 條 feature 的摘要 = N 行，orchestrator context 不爆

這是 2–5 條並行時 orchestrator 撐過整個 session 的機制，不做這個 N=3 就爆。
