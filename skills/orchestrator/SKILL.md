---
name: orchestrator
description: Use when 同時並行多個 feature/bug、需要 orchestrator 調度多條 CR、並行跑 feature/bug pipeline、parallel features across multiple in-flight CRs simultaneously. NOT for single feature — use /feature directly.
---

# Parallel Feature/Bug Orchestrator

Spec: `docs/2026-06-23-parallel-feature-orchestrator-design.md`

## Cheat-Sheet

```
主迴圈零延遲(§2 鐵則):主迴圈只做 6 件秒級事 = 收feature/問你澄清/決策/cli.py advance/派subagent/收report
任何「讀·抓·搜·草擬·生產」要超過幾秒 → run_in_background:true 丟背景 subagent，主迴圈不自己做(含 codegraph、讀外部文件、design.md/spec/plan/impl 寫稿)
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
   - **1-requirements** → 派 **intake-research subagent**(codegraph + 讀文件 + 草擬澄清題 → report)。**research 回來後**,主迴圈才做那一片秒級事:把草擬的澄清題問 user(§4:requirements provisional 是 BLOCKING,等 user/客戶答才動)。**澄清答定後** → 把結論寫成 `design.md` 是 production 步驟 → 派**寫 design.md** 背景 subagent(hub doc,**只寫不 commit**,規則同下行)→ 主迴圈串行 commit + review `design.md` → 才 advance 到 2-ui-prototype。(主迴圈別自己寫稿,違反零延遲)
   - **design.md / 3-spec / 4-plan**(hub docs) → 派背景 subagent,**只寫檔不 commit**(hub 同 repo,並行 commit 撞 index)→ 主迴圈收回後**串行 commit**,`git add docs/features/<id>-<slug>/` **scope 到該 feature 路徑**(別 `git add .`/`git add docs/`)。不需 worktree。
   - **5-implement**(submodule code) → 先 `wt.sh add` 開 worktree → subagent 在 worktree branch **commit**(隔離、不撞 hub index)。
   - **2-ui-prototype / 6-uat**:只有「**人眼看版面 / 客戶簽核**」那一薄片是真同步、留主迴圈;其**研究/build 部分**(codegraph 摸 UI 樹、跑 build)照樣背景化。
4. **subagent 回** → 主迴圈執行 `superpowers:requesting-code-review`(派 reviewer 兄弟 subagent,**也是背景**)→ 收 review → provisional-decide 或 `cli.py advance` → 派下一步
5. 更新 confirmations.md(記新的 BLOCKING / 在飛 subagent / worktree)

### 並行流程示例（零延遲版）

```
進場:batch 收齊 A/B/C → 各派 intake-research 背景(run_in_background) → 主迴圈回頂,不等
A research 回(帶草擬澄清題) → 主迴圈問 user A 的澄清題   ← 此刻 B/C research 仍在背景跑
user 答 A → 派 A 的「寫 design.md」背景 → 回頂(收回後串行 commit + review design.md → advance 到 2-ui-prototype → 再派下一階段背景)
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
- design.md(1-requirements 寫稿)/ 3-spec / 4-plan → **無 worktree**，直接編輯 hub `docs/features/<NNN>-<slug>/`（你只寫檔）

任務：<具體生產步驟，例：依 spec.md 寫出 implementation plan 到 docs/features/NNN-slug/plan.md>

context：<必要的 spec 路徑、ticket 路徑、相關 API 等>

⚠️ OVERRIDE — 覆蓋 skill 指令，強制執行：
- 不要叫 superpowers:requesting-code-review 或任何 review step
- 不要叫 cli.py advance
- 不要向 user 提問（AskUserQuestion）
- **commit 規則**：5-implement → 在 worktree branch commit 你的生產(+test)；design.md / 3-spec / 4-plan → **只寫檔、不要 commit**（hub docs 由 orchestrator 串行 commit，避免並行撞 hub index）
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

⚠️ **brainstorming（1-requirements）的 provisional 產出天生是 BLOCKING**：agent solo 跑需求只能給假設，不是驗證過的需求（unknown-unknowns 需要對話才浮出）。requirements provisional 必標 BLOCKING，等你或客戶確認後才 advance 到下一 phase（full → 2-ui-prototype、lite → 3-spec）。

---

## 5. Worktree（一律用 wt.sh）

**只有 `5-implement`(動 submodule code)需要 worktree**;`1-requirements` 的 design.md / `3-spec` / `4-plan` 都是 hub docs、**不開 worktree**。`wt.sh add` 前 **feature branch 要先存在**(pipeline 在 prototype/implement 階段才開 branch)。`wt.sh add` 印出的路徑是 `<repo>-<branch-slug>`(slug 過,非 `repo-NNN`),**用它印的路徑**,別自己拼。

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

## 5b. Branch / Worktree 生命週期（implement→交付）

四個分支角色,別混:

| 角色 | 是什麼 | 何時生 | 何時收 |
|------|--------|--------|--------|
| **working-branch** | 該 repo 主力開發分支(per `pipeline.config` 的 `CODEBASE_BRANCH`)| 既存 | 永存;feature land 進這 |
| **feature/\<NNN\>-\<slug\>** | 單一 feature 真相分支,可獨立 land | pipeline prototype/implement 階段開 | land 進 working-branch 後**可留**(各 feature 成熟度不同、分開 land) |
| **worktree** | feature branch 的隔離 checkout 目錄(`wt.sh add`)| 5-implement 派 subagent 前 | implement 完 / 放棄 → `wt.sh remove`。**worktree ≠ branch:收 worktree 不刪 branch** |
| **integration-bundle（\<bundle-slug\>）** | 多 feature 合併上 staging 的衍生分支,可重生 | 要一起上 staging 時 | 暫時的,測完即棄;bug 修在所屬 feature branch 再**重生** bundle,別直接改 bundle |

**關鍵分辨**(實測反覆被問的):
- 「切了 feature branch 還要 worktree 嗎」→ **要**。branch 是命名;worktree 是隔離的工作目錄,讓多 feature 並行 implement 不互踩同一 checkout。
- 「收 worktree = 刪 branch 嗎」→ **否**。`wt.sh remove` 只收工作目錄,feature branch 還在。
- 「bug 修哪條」→ 見 §6 的「bug 修分支歸屬」。
- 「為何從 working-branch 不是 main」→ working-branch 由 `pipeline.config` 的 `CODEBASE_BRANCH` 定,可能 = main + 未釋出功能,**未必等於 repo 的 GitHub 預設分支**。land / PR base 對準 `CODEBASE_BRANCH`,別假設 main。

---

## 6. Build / Merge / 排程

**Build（可並行，但要隔離）**：
- 語言層級的依賴安裝先序列化（共用 cache race），build 本身可並行
- UI/integration test 各給不同 runner/emulator
- **並行上限 = 機器資源**（spec/plan/review 純思考類可全並行）

**Merge（序列化）**：一條先 merge → **該 codebase 的主 branch**（各 codebase 主 branch 見 `.claude/pipeline.config` 的 `CODEBASE_BRANCH`）；其餘 **rebase** 到新主 branch 再進。多條一起上 staging → 走 `integration-bundle-convention`（`integration-bundle-<bundle-slug>` 整合分支）。

**排程**：ticket 的 `conflicts:` 標記的 feature（動到同檔/同 branch）→ **不同時 implement**，錯開排程避免 merge 衝突。

**bug 修分支歸屬**:
- staging / 整合 UAT 抓到的「**未上線 feature 的 bug**」→ 修在該 **feature/\<NNN\>** branch(它還沒 land),再**重生** integration-bundle。**別直接在 bundle 改**,否則該 feature 日後單獨 land 會漏掉這個 fix。
- 「**獨立缺陷 / 已上線 code 的 bug**」→ 走 bug track(`cli.py new \<slug\> --track bug`),開 fix 分支照 bug 流程。
- ⚠️ **bug track 的 phase 紀律(走 bug skill phase、repro-red gate、reproduce-confirm、review 上提)見 §6d** —— 並行跑多條 bug 時每條都要走,別自建流程繞過。

---

## 6b. Implement 之後（6-uat → 交付）

⚠️ **並行段在此結束、進序列段（P4）。** intake→implement 是多 feature 並行(subagent fan-out);**6-uat 之後是單線程** —— 部署、人眼/模擬器/瀏覽器 UAT、客戶簽核都不可並行。orchestrator 的「並行」價值此段歸零,別再期待 fan-out,改成一條一條序列推。

流程:
1. **6-uat → 部署**:多 feature 一起上 staging → 走 integration-bundle(§5b)合併 → 照**該 repo 的部署 runbook 部署**。runbook 是 **fork 本地文件**(upstream 不含,因含 cluster 名/CLI 指令/憑證);fork 在 `pipeline.config` 旁放一份 deploy doc,skill 指過去。
2. **staging UAT**:單線程,主迴圈驅動測試 MCP(browser/mobile)跑 happy + edge。
3. **staging 抓到 bug → 接回 pipeline**:依 §6「bug 修分支歸屬」判斷修哪條 → 修 → **重生** integration-bundle → 重測(branch 操作後務必複測,別假設 binary 沒重編就沒事)。
4. 全綠 → 客戶簽核 → `cli.py advance` 到 done → feature land 進 working-branch。

---

## 6c. Env 前置 + infra 除錯紀律

**UAT 前先驗環境健康**(隔夜 / 換機最常斷):
- port-forward / 本地服務起著?
- creds / 登入態還有效?
- 外部依賴(後端 HIS、auth、物件儲存)連得到?

fork 把**實際 checklist**(host/port/服務名)放本地 `docs/ENV_PRECHECK.md`(upstream 不含實值)。UAT 前先跑一遍。

**infra 症狀一律走 `superpowers:systematic-debugging`,別臆測。** 連線失敗 / auth 失敗 / 上傳 500 / 404 這類根因常在環境(配錯 SA、漏 API 白名單、URL 雙前綴、port-forward 斷),不在 code。先收集跨層證據定位哪層斷,再修;別猜一個就改。

---

## 6d. Bug track —— 走 bug skill 的 phase,別自建流程繞過

> 實測 RED:orchestrator 並行跑多條 bug 時最常見的失敗是「**從沒 invoke bug skill、零次 `cli.py advance`、ticket 永停 `0-intake`**」,自建一套「reproduce→fix」流程,fix subagent 交回的全是斷言內部值的 unit test(非客戶症狀)→ 幻影測試 / 假陽性 / regression 漏抓。**因為從沒走 `bug-repro` phase,`repro-red` gate 整個被繞過。** 跨 fork 都會踩,所以並行調度 bug 一律照 bug skill 的 phase 走。

**`track=bug` 一律照 bug skill 的 phase 推,用 `cli.py advance` 真推進,別讓 ticket 停在 intake:**
`0-intake → bug-debug → bug-repro → bug-fix → bug-verify → done`

| phase | orchestrator 派什麼 | gate |
|---|---|---|
| **bug-debug** | subagent **先 invoke `superpowers:systematic-debugging`**,用 codegraph 追 root cause(`codegraph_explore/callers/callees/impact`)→ 寫進 ticket「Root cause」。🚨 **Phase 1 的「複現症狀」一律走 API/UI 客戶表面層**(手動或 repro 雛形;症狀本身就在 unit 層的少數情形除外,見 bug skill);internal-value/unit 斷言只能當往下追因的補充 trace、不算複現。 | — |
| **⚠️ reproduce-confirm**(進 bug-fix 前的 BLOCKING;不得跳過 bug-repro)| subagent 回的 root cause 是**假設**不是結論 —— **未在 API/UI 層實際複現症狀前不准開修**。intake 順暢 ≠ 已驗證;code-trace 到某行 ≠ 證實該行就是症狀因。 | API/UI 複現成立才 advance |
| **bug-repro** | 派 bug-repro subagent 寫 **ONE failing test 在客戶症狀層(UI/API)**。對「無 fix 的 base」跑 = 紅、斷言對症狀、非 skip 才算數。 | `repro-red`:base 紅、斷言客戶看到的症狀(非內部值)、非 skip |
| **bug-fix** | 派 bug-fix subagent 修到 **repro 測試綠**;dispatch prompt 必寫「先有症狀層 failing test、修到它綠」,不可只交 internal-value/unit 測試充數。 | `tests-green`:repro 綠 + 既有測試沒壞 |
| **bug-verify** | 對原始報修驗(UI/API);repro 測試留成 regression。 | `bug-verified` |

**review 上提主迴圈**(同 §2 步驟4):bug-fix subagent 回 `tests-green` 後,**orchestrator 主迴圈自己正式 invoke `superpowers:requesting-code-review`**(派 reviewer 兄弟 subagent、背景、讀 fix diff)→ 收 review(`receiving-code-review`)→ 才 advance 到 bug-verify。**絕不讓 fix subagent 自己叫 review**(會巢狀、結果回不到 orchestrator;§3 OVERRIDE)。

**鐵則**:
- **repro-red 先於 bug-fix**:沒有「斷言客戶症狀、會紅」的 UI/API 測試,不准進 bug-fix。**internal-value / unit 斷言(斷言內部回傳值、DTO 欄位、單一函式輸出)≠ repro-red** —— 那是 fix 的附帶單測,不是「無 fix 時會紅、斷言報修症狀」的測試。
- **沒走 bug-repro 不准進 bug-fix**;沒 `cli.py advance` 不算走 phase。
- 並行多條 bug 時這套 phase **每條都要走**(orchestrator 只是並行調度,不是省 phase 的藉口)。

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
8. **bug track 走 bug skill 的 phase**(§6d):`cli.py advance` 真推進 bug-debug→bug-repro→bug-fix→bug-verify,**別自建流程繞過**。`repro-red` 先有斷言客戶症狀、會紅的 UI/API 測試才准進 bug-fix;**internal-value / unit 斷言 ≠ repro-red**。review 上提主迴圈,別讓 fix subagent 自己叫(用 requesting-code-review subagent)。並行多 bug 每條都要走。
9. **假設 ≠ 結論**(reproduce-confirm,§6d):subagent 回的根因是「假設」,**未在 API/UI 層實際複現證實前不開修**。intake 順暢 / code-trace 到行 ≠ 已驗證。

---

## 11. Orchestrator Context 存活（File-Handoff）

N 條並行 → 各條 subagent 的細節堆進 context = 必爆。規則：

- dispatch prompt 給 subagent 一個 **scratchpad report path**（`/private/tmp/claude-501/.../scratchpad/feat-<id>-<phase>-report.md`）
- subagent **把所有細節寫進 report file**（diff、決策說明、遇到的問題、下一步建議）
- subagent **回傳只給** `STATUS: done|blocked — <一行摘要>`（進 orchestrator context 的只有這行）
- orchestrator 需要細節時 **Read report file**（不讓 subagent 重述）
- N 條 feature 的摘要 = N 行，orchestrator context 不爆

這是 2–5 條並行時 orchestrator 撐過整個 session 的機制，不做這個 N=3 就爆。
