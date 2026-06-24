# Parallel feature/bug orchestrator — design

> 2026-06-23 ｜ 在**單一 session、單一 repo** 內並行推進多個 feature/bug,疊在既有 `/feature` + `/bug` pipeline 之上。
> 過一輪 architecture review(opus subagent)後重寫 —— review 打掉了第一版的重 orchestrator;本版採其技術約束 + 用 user 的「provisional 決策」放寬解掉「客戶瓶頸」反對。

## 問題 / 目標

pipeline 每一步(spec-review、plan-review、各 implement task、build…)的 subagent **都要跑數分鐘**,單條 feature 序列跑時,人在那幾分鐘**乾等**。目標:讓 **N 條 feature/bug 的這些等待互相填滿**,在**同一 session/repo** 內穿梭推進 → 大幅加速。

**關鍵放寬(這版成立的前提)**:除了**真的非等客戶不可**的事,其餘決策 **agent 先 provisional 幫客戶決定、記下假設、往下走,之後再改**。→ 人類閘從「**阻塞每一步**」變成「**事後非阻塞確認**」。這正是讓 overlap 真正不卡的解。

**何時用(別過度)**:手上**≥2 條** feature/bug 且有**重疊的自動等待**時才開 orchestrator。只有 1 條、或只是想切換 → 直接序列跑 `/feature`(state 在 ticket、本來就免費切換),不需這套。

## 核心原則

**orchestrator = 主迴圈,純調度 + 決策。subagent 只做有界的「生產」葉子任務。**

- 主迴圈是**唯一**能 `AskUserQuestion`(問你)+ 唯一能 dispatch subagent 的層。
- subagent 是 leaf:不能問人、不能再開 subagent。所以一切「要問你 / 要派下一個」都回到 orchestrator。

## 並行機制(harness 真做得到)

`run_in_background: true`:派一個 subagent **馬上返回、主迴圈繼續**,完成時 harness 通知。

```
派 001 spec-production(背景) → 不等,馬上 →
派 002 plan-production(背景) → 不等 → 派 003 implement-task(背景) →
誰先回 → 通知 orchestrator → 它處理(review / provisional 決策 / advance) → 再派那條下一步
```

同一 session 多個背景 subagent 並行;orchestrator 穿梭調度。**並行度上限**取 harness 並發上限與下方 build 約束的較小者(實務 2–5 條)。

## 下放粒度規則(解「skill 寫要開 subagent、自己又是 subagent」的巢狀)

**orchestrator 才是「跑 feature/bug 流程」的人;只下放 skill 裡的單一生產步驟。**

- dispatch prompt **把 subagent 框死在生產、停在 review 步驟前**:例「寫出 `spec.md`,做到 review 前停、回傳,**不要自己叫 review**」。→ subagent 走不到那行 → **不巢狀**。
- subagent 回來後,**orchestrator 自己**執行 skill 的「`superpowers:requesting-code-review`(派 reviewer subagent)」那步 —— reviewer 是 orchestrator 派的**兄弟**,結果回到**你看得到**的層。
- review/決策/advance/問你 **永遠在 orchestrator**。
- **skill 完全不改** —— 邊界靠 dispatch prompt 的任務範圍 enforce。這就是 `subagent-driven-development` 本來的切法(implementer 只 implement+test+commit+self-review 回傳,review 由 orchestrator 派)。

## 決策路由(provisional + 非阻塞確認)

⚠️ **provisional 分兩種,別混**:
- **可逆內部 provisional**(檔名、測哪層、版面細節)→ decide-and-proceed,**不擋下游**。記 confirmation log,你有空再掃。
- **load-bearing provisional**(尤其 **requirements / 需求假設**,以及任何「下游 4 個 phase 都建在它上面」的決策)→ **擋下游**:可以 provisional 決定 + 繼續到**本 phase 結束**,但**不准在它被你確認前往下推 prototype/spec/plan/implement**(否則需求猜錯 → 4 個 phase 全 rework,cascade)。confirmation log 標 `BLOCKING`,這種你**優先確認**。
- 規則:**任何未確認的 load-bearing provisional,下游 advance 必須等它確認**(寧可這條卡著,讓 orchestrator 去推別條 feature 填等待,也別 cascade)。

流程:
- orchestrator provisional-decide → **ticket 記假設** + confirmation log(標 feature + `BLOCKING`/`reversible`)。
- 你掃 log 確認;**不同意 → 該 feature rework** 回對應 phase。
- **真阻塞才即時問**:非等客戶不可 / 不可逆 / 花錢 / 動 prod → `AskUserQuestion`(標 feature);同時到的排隊逐個問。

## 互動 phase 在哪跑(明確)

`1-requirements`(brainstorming)、`2-ui-prototype`(客戶回饋)、`6-uat`(客戶簽核)**本質是對話,不下放給 subagent** —— 它們在 **orchestrator 主迴圈**跑(唯一能問你的層)。並行靠的是「**這條在 orchestrator 跑互動 phase 時,別條的 production subagent 在背景磨**」,不是把對話塞進 subagent。
- ⚠️ **brainstorming 不能 solo**:agent 獨自「provisional 決定整個需求對話」產出的是**假設(assumption)、不是驗證過的需求** —— 它漏的是對話才會浮出的 unknown-unknowns。所以 requirements 的 provisional 產出**天生標 provisional + BLOCKING**,等你(或客戶)確認。別假裝 solo 跑得出真需求。

## 狀態(撐過 context compaction)

- **per-feature `ticket.md`** = 單一真相(phase/track/gates/決策/branch/worktree),由 `cli.py` 管 phase。
- **`docs/features/INDEX.md`** = 艦隊索引(id/slug/track/phase),**已存在,直接用**,不另建 FLEET.md。
- **`.superpowers/orch/confirmations.md`**(git-ignored)= provisional 決策待確認 log + 在飛的背景 subagent → feature 對照(誰是誰、worktree 路徑、dispatch 時間)。orchestrator 每輪先讀它,compaction 後靠它 + `git log` + ticket 復原,別靠記憶。

## Git worktree(技術約束,務必照做)

⚠️ **不要用 Agent 的 `isolation:"worktree"`** —— 它 worktree 的是 **hub(superproject)**,不是 submodule;submodule 共用 `.git/modules/<name>`、auto-clean 語意對不上 working tree 的實際改動。

- **手動在 submodule 內開,worktree 放 hub 工作樹之外**:
  `cd codebases/app && git worktree add $WT_CACHE_ROOT/app-001 feature/001-<slug>`
  ⚠️ **別用 `../wt-001`** —— 那會落在 `codebases/` **裡**,hub 視為 untracked,`sync-submodules.sh` / hub 層 `git add -A` 會把它掃進去。一律放 repo 外(如 `$WT_CACHE_ROOT/<repo>-<id>`)。
- 同一 submodule、兩條 feature → 兩個 worktree、各 checkout 各 feature branch → 互不搶 working dir(admin 在 `.git/modules/app/worktrees/...`,hub 對 submodule 主樹的 gitlink 視圖不受影響)。
- **cleanup**:landing / 放棄時,**在 submodule 內** `git worktree remove <path>`(+ 必要時刪 branch);路徑記在 confirmation log。孤兒 → submodule 內 `git worktree prune`。
- ⚠️ **sync-submodules / `git submodule update` 與活著的 worktree**:這些動 submodule HEAD,跟有未 commit work 的 worktree 會撞。**orchestrator 在飛時別跑 sync-submodules**;要 sync 先確保 worktree 都 commit/clean。

## Build / 並發的誠實面(設對期待)

<mobile build> **可以**並行(不同 worktree 的 `build/`、`<build cache>`、`<emulator/simulator>` 各自獨立;`<mobile build>` 不佔 port;run/test 的 VM service port 自動挑空的)。**要處理的是共用可變狀態,不是「不能並行」**:
- **package cache**(共用):兩個**冷** package install 同時寫會 race → **暖 cache 或序列化 install 這一步**(build 本身可並行)。
- **build tool daemon**(如適用,shared home 共用):會 lock/contend → 每個 build 設隔離的 home 或接受變慢。
- **`<mobile build>` run/integration_test 上裝置**:**各給不同 `<emulator/simulator>`**(同一個 sim 一個 app 會撞);port 自動不撞。
- **真正的並發上限 = 機器資源(CPU/RAM/IO)**,不是 correctness;2 個同時 build 一般筆電會喘 → orchestrator 設一個**資源型並發上限**(可能就 1–2),而不是「禁止並行」。

**設對期待**:跨 submodule(app build 與 api 測試)幾乎無痛並行;同 submodule 多個 app build 並行**做得到但吃資源**,上限由機器決定。spec/plan/review 那些**純 subagent 思考**的等待最好 overlap(不吃 build 資源)。

## Merge / landing 序列化

多條 feature 最終 merge 進同一 submodule dev branch(`<CODEBASE_BRANCH>`)→ 重疊檔案會衝。

- **序列化**:一條先 merge → `<CODEBASE_BRANCH>`;其餘 **rebase** 到新 `<CODEBASE_BRANCH>` 再進。orchestrator 不並行 merge。
- 多功能要一起上 staging → 走既有 `docs/2026-06-23-integration-bundle-convention.md`(本來就處理打包/落地)。
- intake 階段沿用 ticket 的 `conflicts:` 標記,orchestrator 對「會動到同檔/同 branch」的 feature 排程上避免同時 implement。

## 失敗模式 + 處理(review 抓出的,明列)

| 失敗 | 處理 |
|---|---|
| subagent crash / timeout 中途死 | orchestrator 偵測(通知含非零 exit / 無回傳)→ 該 feature ticket **未 advance**(本來就是)→ 檢查 worktree 有無半成品 → 重派或標 BLOCKED 問你 |
| worktree orphan(BLOCKED/放棄沒清) | confirmation log 記 worktree 路徑;orchestrator 收尾 / 你 status 時 `git worktree prune` |
| 同 submodule branch merge 衝突 | 上方序列化 + rebase |
| build 資源打架 | 上方並發上限 |
| orchestrator 自己 context 爆(N 條摘要堆積) | subagent 回傳走**檔案**(report file),orchestrator 只收 status + 一行摘要;細節在檔不在 context(沿用 sdd file-handoff) |

## 這是什麼 / 不是什麼

- **是**:一個新 skill `orchestrator`(prose 指引主迴圈當並行調度員),疊在 feature/bug 之上,**呼叫**它們的 phase 邏輯、不重寫。
- **不是**:不是新的 phase 狀態機(phase 規則仍在 `cli.py`);不是 Workflow 骨幹。
- **Workflow 的位置**:排除在互動骨幹外(它背景跑、不能中途問你)。保留給未來「**某 phase 內純自動、零 Nat 決策**的並行批次」(例:一次對 5 條跑 spike 量測或 spec-review),那才是它的場。

## 已知風險 / 取捨(誠實列)

- **prose-enforced 協定不如 code 可靠**:orchestrator 的鐵則(永遠讀 confirmation log、subagent 框死在生產、never 讓 subagent 叫 review)靠 model 守 markdown,不像 `cli.py` 的 `valid_next` 是硬 enforce。→ 鐵則**盡量少而硬**;能塞進 cli.py 的(如 phase 規則)就別放 prose。
- **provisional 決策的代價**:幫客戶決定錯 → rework。前提是「改的成本 < 等客戶的成本」,對**可逆**決策成立;**不可逆**的仍要真問。
- **真值得並行的場景有限**:客戶若回得慢,瓶頸仍在客戶;orchestrator 加速的是「agent 操作的數分鐘等待」那段。≥2 條有重疊自動等待才開(同 submodule 多 app build 可並行但吃資源、上限看機器,見上)。
- **「subagent 不准叫 review」是最脆弱那條 prose 鐵則**(它跟 skill 自己寫的「dispatch review」直接打架)→ dispatch prompt 必須**明寫覆蓋**:「忽略 skill 的 review/decision 步驟,做完生產**停、回傳**」,別只靠 model 自己權衡誰贏。
- **mock-data 洩漏被並行放大**:N 個 worktree + 半確認的 provisional + 序列化 merge → 帶 `PROTOTYPE-MOCK` 又沒確認的 feature 誤 landing 機率升。**parallel 模式 landing 前強制**:跑 mock gate(`grep -rnE "PROTOTYPE-MOCK|FEATURE-MOCK"`)+ confirmation log 有 `BLOCKING` 未確認 → 不准 landing。

## Cheat-sheet

```
orchestrator(主迴圈)= 唯一能問你 + 派 subagent;只調度+決策,不寫 code
並行 = run_in_background 多個 subagent,誰回處理誰
互動 phase(1需求/2prototype/6uat)在主迴圈跑、不下放;production phase(spec/plan/implement)才下放
下放 = 只下放單一生產步驟,prompt 明寫覆蓋 skill review 步驟、停在 review 前;review/決策/advance 留 orchestrator
決策 = reversible provisional → 往下不擋;load-bearing(需求等)provisional → 擋下游到你確認;不可逆/等客戶/動prod → 真問
worktree = 手動在 submodule 內 git worktree add 到 repo 外路徑(別用 isolation:worktree);build 可並行但隔離 pub-get/Gradle-home + run 各自 sim,並發上限看機器資源;merge 序列化
狀態 = ticket(真相+假設)+ INDEX.md(艦隊)+ confirmations.md(待確認 BLOCKING/reversible + 在飛對照)
skill 不改;Workflow 只留給未來純自動批次
```
