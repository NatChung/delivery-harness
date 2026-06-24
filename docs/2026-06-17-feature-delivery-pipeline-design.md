# Feature Delivery Pipeline — Design

> 把「客戶功能需求」從進場到上 stg 的整條流程,做成**可重複、狀態耐久、人在迴圈**的 pipeline。沿用 superpowers skills,補上 prototype-first + AC/BDD + TestID 幾個自訂階段。
>
> 日期:2026-06-17 ｜ rev 2(已納 design review:加失敗/rework 邊、branch model、mock-data 閘、spike track、並行/id、定 AC+TestID 慣例)｜ 狀態:design(待 review → writing-plans)

## 目標 / 非目標

**目標**
- 一條可重複的 feature pipeline:需求 → 讀 code 確認 → UI prototype(真 app/web)→ 客戶定案 → spec(AC/BDD+TestID)→ plan(TDD)→ 開發 → 測試 pass → stg UAT。
- 同一引擎再開一條 **bug track**:`/systematic-debugging` 找 root cause → 寫失敗重現測試 → TDD 修綠 → verify(詳「Bug track」段)。
- 狀態跨 session/多天耐久(人在迴圈、等客戶)。
- 最大化重用既有 superpowers skills,只新增必要黏合與自訂階段。

**非目標**
- 不在此 spec 實作具體功能需求(功能 A / 功能 B / 功能 C)—— 它們是 pipeline 首批貨,各自走流程。
- 不建 sqlite 儀表板(md 為主存,sqlite 之後當衍生 index 再議)。

## 命名

- pipeline 名 = **feature**;入口 `/feature`;ticket 目錄 `docs/features/<NNN>-<slug>/`(ticket.md + spec.md + plan.md 同住)。
- 刻意不用 "CR / 變更 / 需求" —— 避免交付後變客戶口中「改功能」代名詞。
- **skill 命名**:自訂 skill 不加客戶專屬前綴(`/feature`、`/bug`,未來 sub-skill 如 `feature-intake` 比照)—— 避免跟內建/通用 skill 撞名。引擎目錄 `scripts/feature/` 不加前綴(非指令)。

## Track(四條:feature 三條 + bug 一條,進場時於 ticket 標定,可改)

| track | 適用 | 路徑 |
|---|---|---|
| **full** | 有新 UI 面、視覺重 | 走完整 Phase 0–6(含 prototype)|
| **lite** | 無新 UI / 純後端 / 純修則 | 跳 Phase 2,brainstorming → spec → plan → TDD → UAT |
| **spike** | AI / data-heavy / 外部整合(成敗在準確率/延遲/成本,非 UI)| 先做**薄真實 spike** 量測可行性 → 產 feasibility note 餵 spec,再決定走 full/lite |
| **bug** | 既有功能壞掉 / 客戶報修 | 不走 feature 前半(無 prototype/客戶定案/AC 作者):`/systematic-debugging` 找 root cause → 寫**會 fail 的重現測試** → TDD 修綠 → verify。詳「Bug track」段 |

> **spike 存在理由**:某些功能接 AI/外部服務,價值在辨識準確率/延遲/成本。UI-only mock 假造 AI 結果 → 給客戶**假定案信心**、驗不到真東西。這類 feature 先 spike 真 API 量測,不先做 UI mock。

**Spike 流程 / 狀態**:track:spike 進場後 phase = `1b-spike`(在 Phase 1 之後、Phase 2 之前)。產出 **feasibility note**(準確率/延遲/成本 + 真實整合注意事項),gate **`feasibility-approved`**(內部技術 signoff)。過 gate 後依結論轉 track:有新 UI → `full`(進 Phase 2);無 UI/純整合 → `lite`(進 Phase 3)。`1b-spike` 已列入 phase enum。

## Bug track(共用引擎、獨立 flow)

Bug 與 feature 前半根本不同:**不需要** UI prototype / 客戶批次定案 / 在新 UI 上寫 Gherkin AC。它要的是「重現 → root cause → 失敗測試 → 修 → 綠」。但**共用同一引擎**(state machine + ticket + INDEX + CLI)—— bug 多一條 track sequence + 一個 `/bug` skill,**外加 bug 專屬的 rework/reject 特例邊(見下「引擎改動」,非純資料增量)**。入口 skill `/bug`(feature 那條是 `/feature`),ticket 一樣放 `docs/features/<NNN>-<slug>/`(同 registry、同配號)。

| Phase | 做什麼 | 通過 gate | 失敗 / 退回 | 由誰 |
|---|---|---|---|---|
| 0 intake | 報修源 → 建 ticket + 配 id + 入 registry(track=bug)| ticket 建立 | — | `feature-intake`(重用)|
| bug-debug | 找 root cause(Phase 1 蒐證 → 不猜)| root cause 確認入 ticket | 查無法重現 → `on-hold` 等更多資料 | `superpowers:systematic-debugging` |
| bug-repro | 寫一支**會 fail 的重現測試**(red)| 測試紅、且紅在「對的原因」 | 寫不出穩定重現 → 回 bug-debug | TDD(`superpowers:test-driven-development`)|
| bug-fix | 改 root cause 修到測試綠(green)| 重現測試綠 + 既有測試沒壞 | 修 3 次仍紅 → 質疑架構(systematic-debugging Phase 4.5)| `test-driven-development` + `executing-plans` |
| bug-verify | 上 stg、原報修情境驗收;重現測試留作 regression | 報修者/QA 確認修好 → `done` | 沒修好 → `rework` 回 bug-debug,`rework_round`+1 | `verification-before-completion` + `finishing-a-development-branch` + `docs/bugs/` 反思 |

**重現測試在哪一層(per-bug 於 bug-repro 決定)**:bug 在哪層就測哪層 ——
- 邏輯 / 計算 → **function/unit 測試**(Flutter widget+bloc_test / go test / jest)
- 後端行為 / 合約 → **API 測試**(go test / jest e2e / curl 腳本)
- UI 行為 / 互動 → **Auto UI script**(Flutter integration_test / Playwright;重用 feature pipeline 的 TestID 慣例)

重用 feature pipeline 建立的測試基建(尤其 cms 那塊 bootstrap)。

**phase enum(bug 專屬,加入封閉集)**:`bug-debug, bug-repro, bug-fix, bug-verify`(用 `bug-` 前綴避免跟 feature 的 1/2/3… 號碼混)。共用 `0-intake, done, rejected, on-hold`。bug track sequence = `0-intake → bug-debug → bug-repro → bug-fix → bug-verify → done`;`bug-verify` 失敗 rework 回 `bug-debug`。

> 跟 `docs/bugs/`(每修一個 bug 寫的輕量反思 ledger)的關係:**互補不重疊**。bug track = 「修 bug 的工作流程 + 狀態」;`docs/bugs/` = 修完後的 pattern 反思(bug-verify→done 時順手寫,見現有 routine)。

### Bug track 細節(review 補強)

**引擎改動(C1 — 非純加資料)**:現有 `valid_next` 的 rework/特例邊 hardcode 在 feature phase 名上(`6-uat→REWORK_TARGETS`、`2-ui-prototype→rejected` 等)。bug 的 rework/reject 邊(`bug-repro→bug-debug`、`bug-verify→bug-debug`、`bug-debug→rejected`)**engine 預設不會有** → 加 bug track **必須改 `valid_next` 邏輯**、不是只加 sequence。建議重構成 **per-track rework/reject map**(`REWORK = {"full": {"6-uat": {...}}, "bug": {"bug-repro": {"bug-debug"}, "bug-verify": {"bug-debug"}}}`)讓未來 track 純資料化。bug track plan 要明列此改動 + 改既有 skeleton 測試(`test_enums_are_exact` 的 `TRACKS`、`cmd_new` 錯誤訊息)。

**bug ticket 欄位 / gates(track-conditional)**:bug **不用** feature 的 `rounds.prototype` / `prototype-signoff` / `mock-data-cleared`。bug 專屬:
- `severity`:`P0-prod-down` / `P1-prod-partial` / `P2-user-facing` / `P3-internal`(決定走不走 hotfix lane)
- gates:`repro-red`、`tests-green`、`bug-verified`
- **`repro-red` 操作化(M2)**:測試 assert 在「客戶回報的症狀」上;失敗訊息對得上回報的錯誤行為;只有在 root-cause 修好後才轉綠(預期行為下會 pass)。否則此 gate 不可證偽。

**prod hotfix lane(I2)**:`severity` P0/P1(prod 壞,影響 App Store/Play/prod gateway)→ 走**快線**:bug-debug→bug-repro→bug-fix→**直接修 prod + 補 regression**,stg UAT 事後補(ticket 標 `hotfix: true`)。P2/P3 走正常 → stg → 驗收。

**bug branch(I3)**:`fix/<NNN>-<slug>`(非 `feature/`),從該 repo 真 branch 切;`bug-repro` + `bug-fix` 同一條 branch;過 `tests-green` gate 才 merge。

**direct reject(M3)**:`bug-debug` 可直接 → `rejected`(not-a-bug / 重複 / wontfix),history 記原因,不必繞 on-hold(此邊納入上面 reject map)。

**bug 增量階段不依賴 intake skill(I4)**:bug track(分解 step 2)時 `feature-intake` 尚未建 → 直接 `cli.py new --track bug <slug>` 建 ticket。且該階段只有**後端/邏輯 bug** 可全自動(test 基建已在);**UI bug 的 Auto-UI 重現測試** 要等分解 step 4 的 cms/Flutter integration bootstrap。

## Pipeline 階段(feature track,含失敗/rework 邊)

狀態活在 `docs/features/<NNN>-<slug>/ticket.md`。`/feature` 讀 ticket → 報「現在哪階段 / 下一步 / 產物」→ 呼叫對應 phase skill → 回寫 ticket。

| Phase | 做什麼 | 通過 gate | 失敗 / 退回 | 由誰 |
|---|---|---|---|---|
| 0 intake | 需求源(Notion/Figma/docx)→ 建 ticket + 配 id + 入 registry | ticket 建立 | — | `feature-intake`(新)|
| 1 requirements | 讀相關 code、問澄清題、確認需求 | 需求確認入 ticket | 需求不清 → 停 `on-hold` 等人 | `brainstorming`(重用)|
| 1b spike *(僅 spike track)* | 薄真實 spike 量測準確率/延遲/成本 → feasibility note | `feasibility-approved`(內部技術 signoff)| 不可行 → `on-hold` / `rejected` | `brainstorming` + 手作 spike |
| 2 ui-prototype | branch 做 UI-only+mock;**出一版 → 客戶一次收齊回饋 → 改一次**(round 上限 **3**)| 客戶 `prototype` signoff | 超過 3 輪未定案 → `on-hold`,人決定:回 Phase 1 重scope / 終止 → `rejected` | `feature-ui-prototype`(新)|
| 3 spec | 讀 branch diff 當**起始集** + 讀懂 UI 樹 → UI 面 inventory → 注 TestID → 寫 AC/BDD → 產 `spec.md` | spec.md 完成 | — | `feature-spec`(新)|
| 4 plan | `spec.md` 餵 writing-plans → `plan.md`(TDD 排序)| plan.md | — | `writing-plans`(重用)|
| 5 implement | red-green;UI 骨架下補真邏輯(UI 保留不重做)| unit/TDD+AC/BDD 全 pass **且 mock-data 清零 gate 過** | 測試紅 → 留在 Phase 5 | `test-driven-development`+`executing-plans`(重用)|
| 6 uat | merge → 上 stg、客戶照 AC 驗收 | 客戶 `uat` signoff → `done` | UAT 不過 → `rework`:依原因 loop 回 Phase 2(UI 錯)/3(AC 錯)/5(實作 bug),`rework_round`+1、記原因 | `verification-before-completion`+`finishing-a-development-branch`(重用)|

**phase enum(封閉集,orchestrator 路由依此)**:feature = `0-intake, 1-requirements, 1b-spike, 2-ui-prototype, 3-spec, 4-plan, 5-implement, 6-uat`;bug = `bug-debug, bug-repro, bug-fix, bug-verify`;共用終止/暫停 = `done, rejected, on-hold`。`rework` 是轉移(重入較早 phase + round 計數),非獨立 phase。`1b-spike` 僅 track:spike 經過,`bug-*` 僅 track:bug 經過。`rejected` = 終止態(Phase 2 超輪放棄、或 on-hold 後人決定不做)。

**關鍵設計決定(brainstorm 確認):**
- UI prototype 做在**真 app/web**;mock UI **保留 = 真 UI 骨架**,Phase 5 在其下補邏輯不重做。
- prototype 回饋**批次**(一版收齊),非每輪出 build。
- `spec.md` 取代 superpowers 慣例的 `design.md` 槽位。

## Branch model(review Critical 2)

- feature branch `feature/<NNN>-<slug>`,從該 submodule 的**真 branch** 切(per `pipeline.config`:見 `CODEBASE_BRANCH` 各 codebase 設定)。跨多 repo 的 feature → 各 repo 各一條同名 branch。
- Phase 2 prototype 與 Phase 5 實作**同一條 branch**(UI 留著、補邏輯)。
- **防 drift**:客戶等待可能跨多天 → 規則 **Phase 5 開工前 + Phase 6 merge 前各 rebase 一次**真 branch。
- **只在 Phase 5 gate 過(測試 pass + mock-data 清零)才 merge 回真 branch** → 再上 stg。
- ticket `branch:` 記實際 branch;跨 repo 記多條。

## Mock-data 清零 gate(Phase 5→6,review Critical 3)

UI 刻意保留 → 最大風險是假 data survive 到 prod。Phase 5→6 強制 gate:
- 該 feature code path 內**無 mock/stub data provider**(grep 約定標記 `// PROTOTYPE-MOCK`,須全清;與 STG-review bundle convention 的 mock gate 同一標記)。
- 所有資料走真實整合(API/DB/service),無寫死假回應。
- reviewer 確認後才可 merge。

## 狀態模型

- **主存 = `ticket.md`(markdown,git 版本化)**:agent 直接 Read 零工具、人可讀、git diff/歷史/review、跟 branch 同行。
- **不**用 sqlite 當主存(binary 無 diff、merge 衝突難解、每次要查詢層)。衍生 index(跨多 feature 儀表板)日後從 md 自動產,如 codegraph 之於 code,先不做。

### `ticket.md` schema
```yaml
id: "001"
slug: feature-b
track: full             # full | lite | spike | bug
phase: 2-ui-prototype   # 見 phase enum 封閉集(spike 進行中則 phase: 1b-spike)
source:
  notion: <url>
  figma: <url>
  docx: <path>
branch:                 # 跨 repo 可多條
  - {repo: app, name: feature/001-feature-b, base: <CODEBASE_BRANCH>}
rounds:                 # 計數
  prototype: 1          # 上限 3
  rework: 0
gates:                  # 單一真相:所有 signoff/gate 只記這裡
  # (track:spike 另加) - {name: feasibility-approved, status: pending, at: null}
  - {name: prototype-signoff, status: pending, at: null, by: null}
  - {name: mock-data-cleared, status: pending, at: null}
  - {name: tests-green, status: pending, at: null}
  - {name: uat-signoff, status: pending, at: null, by: null}
artifacts: {spec: null, plan: null}
feedback:               # prototype/uat 回饋紀錄
  - {phase: 2, round: 1, from: <client-name>, at: ..., notes: ...}
history:                # 重大轉移(含 rework loop-back + 原因)
  - {at: ..., event: created}
```
> **signoff 單一真相**:只存 `gates:`。Phase 表「通過 gate」欄是描述、指向 gate name;不另立 `signoffs:`(消除 review Important 8 的三處重複)。

### `spec.md` 內容契約(Phase 3 產,餵 write-plan)
確認後需求 + 新 UI 面 inventory(diff 起始集 + 讀樹補全)+ **AC/BDD(Gherkin)** + **TestID map**(元件 TestID → 對應 AC scenario)+ branch ref + (spike 時)feasibility note。

## 已定慣例(原列待決,review Important 4 → 現拍)

- **AC/BDD 格式 = Gherkin**(Given/When/Then),寫在 spec.md;每 scenario 給 id。**不**強制 Cucumber engine —— Gherkin 當規格語言,實測由各平台原生框架實作並 ref scenario id。
- **TestID 命名**:Flutter `Key('feat-<NNN>-<area>-<element>')`;Vue/web `data-testid="feat-<NNN>-<area>-<element>"`。feature-scoped、穩定。
- **測試框架(per 平台)**:Flutter widget + `integration_test`;cms Vue(vue-cli/webpack)→ **jest + @vue/test-utils + Playwright e2e**(注意:**非 vitest**,vitest 綁 Vite,cms 是 webpack);api `go test`;chat jest(+e2e)。
- **lite / 純後端型 feature 的 Phase 3**:AC/BDD 寫在 **API / 服務契約**上(Given request → When → Then response/DB),**無 UI inventory / TestID**(或最小)。Phase 3 的「diff→UI inventory→注 TestID」只適用有新 UI 面的 full track。

## Skill 盤點

**新增**:`/feature`(orchestrator:讀 ticket、報狀態/下一步、路由、回寫、管 registry/id)、`feature-intake`、`feature-ui-prototype`、`feature-spec`、**`/bug`(bug track orchestrator,共用引擎)**。
**重用 superpowers**:brainstorming(feature P1)、**systematic-debugging(bug-debug)**、writing-plans(feature P4)、test-driven-development+executing-plans+subagent-driven-development(feature P5 / bug-repro+bug-fix)、verification-before-completion+finishing-a-development-branch(feature P6 / bug-verify)。

## 並行 feature(review Important 7)

- **registry `docs/features/INDEX.md`**:每 feature 一列(id / slug / phase / track / branch / 起始日)。
- **id 配號**:取 INDEX 最大 +1(zero-pad 3 位)。手動 md 流程 → intake **先寫 INDEX 佔號**再繼續;同時兩筆需人工確認不撞號。
- **撞檔偵測**:intake 時列該 feature 預期動到的檔/區,與在途 feature 比對,重疊則於 ticket 標 `conflicts:` 提醒。

## 前置 / 風險

1. **測試基建**(AC/BDD+TDD gate 需要):
   - **cms (Vue):零測試** → **獨立 sub-spec** bootstrap(jest+@vue/test-utils+Playwright;webpack 非 Vite,別用 vitest)。**block 功能 C**。
   - app:有 unit/widget+bloc_test,**缺 integration_test** → 補,讓 TestID-based AC 跑得動。
   - api/chat:已有,OK。
2. **mock UI 技術債** → Phase 3 前結構/lint 閘 +(已加)Phase 5→6 mock-data 清零 gate。
3. **客戶慢**(MIS、歷史回得慢)→ 批次回饋 + branch rebase 規則降風險;Phase 2/6 仍受客戶響應牽制。
4. **spec/plan 版本化**:UAT 改 scope → 於 ticket history 記、重發 spec.md/plan.md(round bump)。
5. **intake 抓 Notion/Figma**:走 Playwright MCP,需登入態(私有 board);headless/cron 可能無 session。

## 分解(建置順序,各自 sub-spec)
1. **骨架**:`/feature` orchestrator + `ticket.md`/`INDEX.md` schema + phase 狀態機(含 rework/on-hold 轉移、track full/lite/spike 路由)。先做、最小、先能追狀態。〔plan 已出:`docs/plans/2026-06-22-feature-pipeline-skeleton.md`〕
2. **bug track 增量**:state machine 加 `bug` sequence(`0-intake→bug-debug→bug-repro→bug-fix→bug-verify→done`)**+ 改 `valid_next` 加 bug rework/reject 特例邊(C1,非純資料)**、bug ticket gates/severity(track-conditional)、`/bug` skill、`fix/` branch 慣例。**排在骨架之後、feature 肉之前**。⚠️ 範圍:此階段只有**後端/邏輯 bug 可全自動**(test 基建已在);**UI bug** 的 Auto-UI 重現測試要等 step 4 的 cms/Flutter integration bootstrap。bug 直接 `cli.py new --track bug` 建,不依賴尚未做的 intake skill。
3. `feature-intake` + `feature-ui-prototype`(含 branch model 操作)。
4. `feature-spec`(diff→AC/TestID)+ **cms 測試 bootstrap sub-spec**(獨立;bug track 的 Auto UI 重現測試也吃這塊)。
5. **試跑 pilot**:feature 走「功能 B」(有新 UI → 真正練到 Phase 2);bug 走任一筆客戶報修(走完 debug→repro→fix→verify 驗證 bug track)。

## 替代做法(已評估)
- Figma/原型工具先行:更便宜回饋,但已選真 app。
- AC-first:嚴謹但對客戶不夠視覺。
- 純 spec-driven(跳 prototype):快但 UI 誤解重工高 → 收進 lite track。
