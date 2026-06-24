# STG-review bundle branch convention

> 2026-06-23 ｜ 適用 hub + submodules(app/api/cms/chat)
> 配合 `/feature` pipeline(`docs/2026-06-17-feature-delivery-pipeline-design.md`)。
> **本文是約定(convention),不是工具** —— 先靠 git 紀律 + checklist 跑;痛點摸清了再考慮做進 CLI。
> 已過 subagent doc-review(2026-06-23),C/I 級問題已修進本文。

## 問題

客戶同時提多個功能需求(功能 A、功能 B…),各自成熟速度不同(有的還在 mock prototype、有的快做完),**常跨 app+api+cms**。但要給客戶的是**一包多功能**的 STG build 一起試。需要一套 branch 規則:
- 多個功能打包成一個 STG build 給客戶 review,
- 每個功能仍能**獨立依 review 回饋修改**,
- 在客戶全部 OK + 真功能(非 mock)都完成前,**不污染正式 dev branch**(`<CODEBASE_BRANCH>`)。

## Branch 分類

| Branch | 範圍 | 說明 |
|---|---|---|
| `<CODEBASE_BRANCH>` | per repo | 正式 dev branch(由 `pipeline.config CODEBASE_BRANCH` 設定)。功能最終落地處。 |
| `feature/<NNN>-<slug>` | per repo | 單一功能工作分支(現有 pipeline)。**一律從 dev branch 開,絕不從 stg-review 開。** |
| `stg-review-<bundle-slug>` | per affected repo | **一個 bundle 一條**的整合分支,跨 app/api/cms/chat **同名**。打包進 STG 給客戶 review 的就是它。 |
| hub `stg-review-<bundle-slug>` | hub | submodule pointer 快照 —— 精確記錄這個 bundle 由各 sub-repo 哪個 commit 組成(可重現「客戶當時試的版本」,也是 rollback 的回復點)。 |

### 命名:`stg-review-<bundle-slug>`
- `<bundle-slug>` **基於功能**、人看得懂,描述這包裝了什麼。例:`stg-review-feature-a-b`、`stg-review-sprint1`。
- **跨 repo 同名**(含 chat,若該 bundle 動到 chat)。
- hub 的 bundle 分支同名,commit message 列出包含的 ticket id(`001`,`002`…)。
- **一個 bundle 週期一條**;落地後刪掉(本地 + 遠端),下一包用**新 slug** 重開。

## 五條合併規則(核心,務必遵守)

1. **修正一律源自 feature branch** —— 絕不直接在 `stg-review-*` 上 commit 功能 code(deploy 自動產生的 version bump commit 除外,見下)。
2. **`feature → stg-review-*` 單向** —— 只把 feature merge **進** 整合分支;**絕不把 `stg-review-*` merge 回 feature branch**(會把別的功能 code 污染進這個 feature)。
3. **base 往上流、且用 merge 不用 rebase** —— 視需要 `<CODEBASE_BRANCH> → stg-review-*`(讓 STG build base 跟上 dev,含 mid-bundle hotfix),衝突在整合分支解;review 期間不反向。整合分支一律 merge(別 rebase),跟 pipeline 對 feature 的 rebase 區隔開,避免 base 分歧放大衝突。
4. **`stg-review-* → <CODEBASE_BRANCH>` 只在 landing** —— 當這包**所有要落地的功能都 uat-signoff** 且 **無 mock 殘留** 才合。
5. **Mock gate** —— prototype 的 mock(標記 `PROTOTYPE-MOCK`)可待在 `stg-review-*` 給客戶看,但**只要 mock gate grep 還有命中,該分支就不准 merge 進 `<CODEBASE_BRANCH>`**:
   ```bash
   # 標記慣例 = PROTOTYPE-MOCK;防禦性連舊例 FEATURE-MOCK 一起 grep
   grep -rnE "PROTOTYPE-MOCK|FEATURE-MOCK" \
     codebases/app/lib codebases/cms/src \
     codebases/api codebases/chat/src
   # 必須無輸出才可 landing。mock 資產(assets/json fixture)也要人工確認。
   ```

## 流程

### A. 建立 / 刷新 bundle(每個受影響 sub-repo)
```bash
git checkout <CODEBASE_BRANCH> && git pull          # 從最新 dev branch
git checkout -b stg-review-<bundle-slug>             # 第一次建
git merge feature/001-feature-a feature/002-feature-b
#   解衝突(pubspec version 見下)→ commit
```
部署 STG —— **注意 `deploy-stg.sh` 的 git 副作用**:它會 bump pubspec、`git commit`、建 `stg-X.Y.Z+B` tag、**並 push 當前分支 + tag**。所以:
```bash
# app:在 stg-review-* 上跑;每輪 build number +1(否則 tag/commit 被跳過 = 無聲 no-op)
./deploy-stg.sh <ver> <build+1> staging
# ⚠️ 絕不在 stg-review-* 上用 production arg(會 build/tag/push prod、繞過 mock gate)
# api/cms:各自 deploy script;若它們也 commit/tag,清理負擔同 app(landing 後一併清)
```
hub 記錄快照(**先 push 各 sub-repo 的 stg-review 分支,再快照**,否則 hub 指到別人 fetch 不到的 SHA):
```bash
# 各 sub-repo:git push origin stg-review-<bundle-slug>   ← 先 push
# 在 hub:
git checkout -b stg-review-<bundle-slug>
#   逐一進 submodule、fetch + checkout 到該 repo stg-review 分支的新 HEAD
git add codebases/app codebases/api codebases/cms codebases/chat
git commit -m "bundle(stg-review-<bundle-slug>): 001 feature-a + 002 feature-b → STG build <stg tag>"
```

### B. Review 一輪(客戶對功能 N 回饋)
```bash
git checkout feature/00N-<slug>     # 在功能自己的分支修
# ...fix, commit...
git checkout stg-review-<bundle-slug>
git merge feature/00N-<slug>        # 單向併回整合分支
./deploy-stg.sh <ver> <build+1> staging   # build number 再 +1
# push 各 sub-repo stg-review 分支 → 再更新 hub pointer(同 A 的快照步驟)→ 在 ticket feedback 記下這輪 build tag(可追蹤)
```

### C. Landing(全部 OK + 真功能都上了)
```bash
# 0) Mock gate:跑規則 5 的 grep,必須乾淨
# 1) 各 feature ticket 都到 uat-signoff(cli.py status)
# 2) 各 sub-repo 落地
git checkout <CODEBASE_BRANCH> && git merge stg-review-<bundle-slug>
#    pubspec 衝突:<CODEBASE_BRANCH> 可能已被別的 landing/hotfix 推進 → 取較高 build number
git push origin <CODEBASE_BRANCH>
#    bump prod tag + deploy(per 各 repo CLAUDE.md tag 規矩)
# 3) hub:更新 <CODEBASE_BRANCH> submodule pointer + sync-submodules
# 4) 重置(本地 + 遠端都要清,否則 orphan 分支/ tag 堆積):
git branch -D stg-review-<bundle-slug>
git push origin --delete stg-review-<bundle-slug>      # 各 sub-repo + hub
#    每輪 deploy 推的 stg-X.Y.Z tag:留作版本紀錄即可(刪分支後它們仍指著 commit)
```

### 部分 landing / 卡住的功能(escape hatch)
landing 是「整包一起」,但若某功能卡住(客戶一直退、或真功能 / 去 mock 還沒完成)不該凍住整包:
- **唯一認可的做法:不含它、從 `<CODEBASE_BRANCH>` 重建整合分支**(只 merge 仍 ready + mock-free + uat-signoff 的功能),把這批先 landing;卡住的功能留在自己的 `feature/` 分支,下一包再帶。
- ⚠️ **不要用 `git revert` 去掉某個 feature 的 merge**:revert 一個 merge commit 後,該 feature 的 commit 仍是 `<CODEBASE_BRANCH>` 的祖先,**下一包重新 merge 它時 git 會跳過原始改動 → 功能 code 無聲消失**。一律走「重建」,不走 revert。

### 新功能中途加入既有 bundle
直接把 `feature/00X` merge 進現有 `stg-review-*`、重做 hub 快照 + 重 deploy 即可;若 slug 已不足以描述內容,landing 後下一包換更貼切的 slug。

## 兩個摩擦點的規則

### App `pubspec.yaml` version 衝突(每輪都會發生)
app 每次 commit bump version,feature branch 各自 bump、又每輪重 merge,所以 **pubspec version 幾乎每次 merge 都衝**。
- **規則:bundle 版本由 `stg-review-*` 擁有。** 解衝突時直接在整合分支設**一個 bundle 版本**,build number 在整合分支單調遞增(每輪 +1)。
- 想免去每輪手解:可在整合分支設 `.gitattributes` 讓 `pubspec.yaml` 用 `merge=ours` driver(bundle 側永遠贏),但 landing 併回 `<CODEBASE_BRANCH>` 時記得改回正常、並**取較高 build number**。

### Rollback(STG build 出包)
STG 是 ephemeral —— 直接**重新 deploy 上一個 hub 快照**(前一輪的 hub `stg-review-*` commit 指的那組 submodule SHA)即可回復客戶手上的版本。

## 跟 pipeline 的銜接

- 每個 feature **ticket 仍獨立**(各自 phase)。bundle 是疊在 ticket 之上的 release 概念,**不進 ticket 狀態機**。
- **`6-uat` = 「已在 `stg-review-*` 上、客戶 review 中」**。多功能可同時在 6-uat、共用同一個 STG build;各自有自己的 uat-signoff。
- 某功能 uat 失敗 → 在它自己的 feature branch rework(`advance` 回 2-ui-prototype/3-spec/5-implement)→ 修完再 merge 回 `stg-review-*`。
- **prototype(mock)也能進 bundle 給客戶看** —— 但受 Mock gate(規則 5)擋著不會誤 landing。
- **mock 標記**:`PROTOTYPE-MOCK`(pipeline design doc 舊寫 `FEATURE-MOCK`,已統一為 `PROTOTYPE-MOCK`;gate 防禦性兩者都 grep)。

## Cheat-sheet

```
開 bundle:   feature/* ──merge──▶ stg-review-<slug>  ──deploy(build+1)──▶ STG（各 repo 同名分支）
hub 快照:    先 push sub-repo 分支 → hub stg-review-<slug> = 各 sub-repo HEAD 的 submodule pointer
review:      改 feature/* ──merge──▶ stg-review-<slug> ──redeploy(build+1)──▶ 重做 hub 快照、記 build tag
landing:     mock gate 乾淨 + 全 uat-signoff ──▶ <CODEBASE_BRANCH> ◀──merge── stg-review-<slug>（取較高 build）──▶ 刪分支(本地+遠端)、下包換新 slug
卡關功能:    不含它「重建」整合分支,別 revert merge
rollback:    重 deploy 上一個 hub 快照
鐵則:        ① 只在 feature 改 ② feature→stg-review 單向，絕不反向 ③ <CODEBASE_BRANCH>→stg-review 用 merge
             ④ stg-review→<CODEBASE_BRANCH> 只在 landing ⑤ 有 PROTOTYPE-MOCK 不准 landing
             ⑥ stg-review 絕不跑 production deploy
```
