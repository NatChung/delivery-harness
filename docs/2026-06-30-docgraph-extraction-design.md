# doc-graph module 抽取 — design.md

**日期**:2026-06-30
**狀態**:design(brainstorming 產物,待 fresh-subagent doc-review)
**作者**:Nat + Claude

## 1. 目標與框架(why)

把 `pohai-hub` 裡驗證過的「文件知識圖譜層」抽成 `delivery-harness` 的**第四個可安裝 module**(`doc-graph`),讓任何 repo 都能照 AI-bootstrap 流程裝上。

主要消費者 = **AI agent 直接讀 repo 原始檔**(不是渲染網站)。要解的痛點:repo 文件多、且**分不清新舊**(archive / WIP / 「留作參考」滿地),agent 找不到正確且當下有效的文件。

**性質**:抽取既有設計(pohai-hub 的 `pohai-query` + `doc-rot` 圖譜驗證)+ **補一塊新的**(`graph-init` —— pohai 當初手動建圖,沒有這支)。

## 2. 範圍

**做(本設計)**
- 新增 harness module `doc-graph`,含兩支 skill:`graph-init`(建圖)+ `query`(查圖)。
- 獨立圖譜驗證器 `scripts/docgraph/check.py`(從 pohai `doc-rot/check.py` 切 `check_map_graph` 出來)+ 測試。
- MAP 種子模板 + 節點 schema 參考檔。
- `INSTALL.md` 加「doc-graph module(可獨立裝)」段。

**不做(各自後續)**
- 把 pohai-hub 反向改裝成「裝回泛化版」(pohai 現況可留著,本次不動 pohai repo)。
- mkdocs / 渲染網站。
- 賣前消毒執行(只沿用 `sensitive` 旗標慣例,不做移除)。
- 把整支 doc-rot scanner(stale-term / dead-link)搬進來(已決:只帶圖譜驗證器)。

## 3. 架構

### 3.1 模組邊界與耦合

- `doc-graph` 是**獨立可裝 module**,**不綁** feature/bug pipeline。一個 repo 可只裝 doc-graph、不裝 CR pipeline。
- 因此 `query` skill 對 ticket 的查詢是**條件式**:repo 有裝 feature pipeline(偵測 `scripts/feature/cli.py` 存在)才查 ticket,否則跳過該活源。
- `graph-init` 完全不依賴 cli.py / ticket。
- 前提:repo 有 Python3(驗證器抽取後純 stdlib,見 §3.5)、有 `docs/` 目錄(沒有則 init 時建)。
- **`codegraph` 是外部 optional 相依、harness 不安裝也裝不了**:它是 user 機器層級工具(`~/.local/bin` + per-repo `codegraph init` MCP),不在本 module 安裝範圍。query skill 的「純 code 快捷路徑」依賴它;**未裝時退化成 `grep`**,query 的文件圖譜半邊不受影響照常運作。INSTALL 段要標註「不代裝、建議 user 自行 `codegraph init`,否則純 code 問題走 grep」。(對比 superpowers:INSTALL 對 superpowers 是「必裝、代裝」;codegraph 是「optional、不代裝」。)

### 3.2 兩支 skill 的分工

**`skills/graph-init`(生成式、互動 pilot、每 repo 跑一次)**
1. 掃 `docs/`:列文件清單,標出「疑似 outdated」訊號(路徑含 archive、檔名/內文含 WIP、舊日期、「留作參考」等字樣)。
2. 提議**封閉清單 domain**(pilot 挑 2 個高價值 domain)+ 每個 domain 的代表節點(含 1-2 個熱點 procedure 或 ADR)。
3. **給人逐項確認**(核可 / 刪 / 標 `status`)後才動工 —— 不盲掃全 repo 自動產。
4. 寫 front-matter 到檔案級節點、給熱點 procedure 加 `{#anchor}` 標題、產 `docs/MAP.md`。
5. 跑 `scripts/docgraph/check.py` 綠 → 告知 user 之後用 `<prefix>-query` skill 查。

> graph-init 是**互動式 pilot**,不是一次自動掃全 repo。outdated repo 盲掃會產垃圾節點 + status 全靠猜;互動 pilot 產「小而準」的種子圖,之後可增量擴。

**`skills/query`(唯讀導航、反覆跑)**
- **快捷(純 code 定位)**:問題是「X 在哪定義 / 誰 call Y / 這函式呼叫誰」→ **跳過 MAP,直接 `codegraph`**(search/callers/callees/explore)。純 code 不在 MAP(MAP 只收文件節點),先讀 MAP 是空轉。
- **文件/系統問題**:
  1. 讀 `docs/MAP.md` → 依 hook/id/domain 鎖節點。
  2. 讀節點 `path#anchor`;沿 front-matter `related`(裸 id)與內文 `[[id]]`、經 MAP 解析遍歷鄰居。
  3. 視需要查**活源**:ticket、`git log`/`git blame`、`codegraph`(code 層)。
     > ⚠️ ticket 是條件式:skill body 要明文寫「**先確認 `scripts/feature/cli.py` 存在**(`test -f`),否則**跳過** ticket 活源、不要嘗試跑不存在的 cli.py」。這是 doc-graph 與 feature pipeline 解耦的落地細節 —— 母版 `pohai-query` 無條件跑 cli.py(因 pohai 一定裝了),泛化版必須條件化。
  4. 答案 + **引用來源節點 id**;可執行任務(部署)直接吐該 procedure 步驟。
  5. **新舊提醒**:判新舊看**內容區塊**(`git blame` 內文行,或 `git log` 略過純 front-matter / anchor commit),**別用整檔 `git log -1`**(加 front-matter / `{#anchor}` 那次 commit 會把整檔日期重置成當天、讓節點看似「很新」其實沒動 —— 已知坑)。命中 `status: dated-snapshot/archived` 或內容很久沒動 → **主動提醒「可能過時、請查活源」**。
- **不做**:不改檔、不跑部署、不 ingest、不合成。MAP 沒有的 id = 圖譜外,改用 grep/codegraph 找並回報「未納管」。

### 3.3 節點 schema(沿用 pohai 定案,放 `skills/graph-init/schema.md`)

**id 全域規則**:`id` 限 `[a-z0-9-]+`,且 **id == 標題 anchor 字面 == 檔案級節點 front-matter id**。→ anchor 檢查 = 對目標檔 grep `{#<id>}`,CJK slug 歧義消失。

**檔案級節點(預設,每份納管 doc)** front-matter:
```yaml
---
id: <kebab-id>
title: <人讀標題>
type: runbook        # runbook | spec | adr | reference | bug
status: current      # current | dated-snapshot | archived
domain: <封閉清單之一>
sensitive: false
related:             # YAML block list of 裸 id(不是 [[ ]])
  - <other-id>
---
```
- `related` 必須是 YAML block list 裸 id;內文連結才用 `[[id]]`。兩者 id 都必須在 MAP 有列。
- `updated` **不手填**,查詢時由 git 推導(避免 drift)。
- `type` 不含 `ticket`(活狀態由 ticket 系統管,圖譜只指不鏡像)。

**熱點節點(兩類,表示法不同)**
- **procedure = 檔內 anchor**:`## 標題 {#id}` + 在 MAP 註冊,**不自帶 front-matter**(一檔一塊 front-matter),身分靠 MAP 那列。type=`procedure`(MAP-only)。
- **ADR = 獨立小檔**:一決策一檔,**自帶 front-matter**(`type: adr`),跟其他檔案級節點一樣。
- 只有「同檔多節點(procedure)」需靠 MAP 補身分。

### 3.4 MAP.md(註冊表 + `[[id]]` 解析器 + 消毒閘)

`docs/MAP.md` = agent 第一個讀的檔,`[[id]]` 唯一解析來源。per-domain markdown 表:
```markdown
## <domain>
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| <id> | <path>#<anchor> | <type> | <status> | false | <一句話用途> |
```
- 解析:`[[id]]` → MAP 找列 → 得 `path#anchor` → 讀。
- 消毒閘:`sensitive: true` 列標記,未來交付前可一鍵過濾。
- domain = 封閉清單(init 時與 user 議定)。
- `type` 詞彙 = 檔案級 enum(`runbook|spec|adr|reference|bug`)∪ `{procedure}`(procedure 只存在 MAP)。
- parser 健壯性:跳 `|---|` 列;`## <domain>` 當分組;`path#anchor` 以**第一個 `#`** 切;`hook` 內 `|` 要 `\|` escape。
- 種子模板 `docs/docgraph/MAP.template.md`:含 header + 兩張空 domain 表骨架(無 data row),init 時複製改寫。

### 3.5 圖譜驗證器(`scripts/docgraph/check.py`,獨立、抽取後純 stdlib)

從 pohai `scripts/doc-rot/check.py` 抽出**只做圖譜完整性**的半邊(不帶 stale-term / dead-link)。

**⚠️ 抽取真實成本(別當「搬兩個函式」)** —— pohai 母檔有 `import yaml`(line 16,缺則 `sys.exit(2)` gate 整模組),但圖譜半邊**完全不用 yaml**(yaml 只服務 stale-term 的 `load_rules`)。所以抽取 = **刪掉 `import yaml` + `load_rules`/`Rules`/`StaleTerm`/`check_stale_terms`/`check_dead_links` 整套**,只留圖譜件 —— 刪乾淨後才真的「純 stdlib」;**照字面 copy 母檔會在沒裝 PyYAML 的 target repo 一跑就 exit 2**。

抽取需帶齊的件(母檔內 `check_map_graph` 的真實相依,非只兩個函式):
- dataclass:`MapEntry`、`Finding`
- module-level 常數/regex:`MAP_REL`、`_PIPE_SPLIT`、`DOMAIN_HDR_RE`、`WIKILINK_RE`
- helper:`parse_map`、`_read_lines`、`_frontmatter_id`、`_related_ids`、`_inline_ids`、`check_map_graph`、`format_report`
- **自帶 file-collection**:母版 `check_map_graph(files, root)` 的 `files` 由母檔 `collect_files`(走 `git ls-files`)餵入;獨立版要自帶精簡收集(`git ls-files` 失敗則 fallback `os.walk` 收 `*.md`)。
- **精簡版 `main`**:只跑 map-graph、印 `format_report`、無 finding 則 exit 0;砍掉母版 `--only`/`--rules`/`load_rules` 等 stale-term 旗標。`scripts/docgraph/` 路徑下 `python3 check.py` 要能直接跑(§3.7 驗收要)。

檢查項:
1. **解析 MAP**:每張表取 `(id, path, anchor, line)`;跳分隔列。
2. **MAP 完整性**:每列 `path` 存在;有 `anchor` 則對該檔 grep 字面 `{#<anchor>}` 必命中。死 → `dead-map-entry`。
3. **id 唯一 + 對映**:全域 id 唯一(否則 `duplicate-id`);檔案級節點 front-matter `id` 須在 MAP 有列且 `path` 相符(否則 `id-path-mismatch`)。
4. **連結解析性**:front-matter `related` 裸 id + 內文 `\[\[([a-z0-9-]+)\]\]`(跳 code-fence)每個 id 須在 MAP 有列,否則 `dangling-link`。

> v1 **只做上述四種 finding**。「孤兒偵測」(MAP 有列但無人指向)**不做**(YAGNI;留半吊子 warning 不如不做,測試面也維持四種)。
> ⚠️ **已知 gap(沿用 pohai pilot 接受)**:不偵測「應納管卻沒進 MAP」(沒定義納管全集)→ 只抓 MAP→缺檔,不抓 檔→缺 MAP。

### 3.6 帶進 harness 的資產

**(A) 安裝時 copy 進 target repo 的資產**(INSTALL 會搬):
```
skills/graph-init/SKILL.md
skills/graph-init/schema.md            # 節點 front-matter + MAP 表格式 + procedure↔ADR 區分(heavy ref)
skills/query/SKILL.md
scripts/docgraph/check.py              # 獨立圖譜驗證器(抽取後純 stdlib,見 §3.5)
scripts/docgraph/test_check.py         # 驗證器測試(unittest,見下)
docs/docgraph/MAP.template.md          # 空 MAP 種子
```

**(B) 只存在 harness repo、不 copy 進 target 的檔**:
```
docs/2026-06-30-docgraph-extraction-design.md   # 本設計(harness 自留,不進客戶 repo)
INSTALL.md                                       # 加 doc-graph module 段
```

**測試檔來源 + 改寫**:pohai 母體現成 `test_map_graph.py`(已覆蓋四種 finding + edge case),**是 pytest 風格**(`def test_x(tmp_path)` + bare `assert`)。harness 驗收走 `python3 -m unittest`(對齊既有引擎測試 + 純 stdlib),pytest 的 `tmp_path` fixture / bare assert 在 `unittest` 下不會被收集。故:**帶 `test_map_graph.py` → 改寫 pytest→unittest(`unittest.TestCase` + `tempfile.TemporaryDirectory` 取代 `tmp_path` + `self.assert*`)→ 改名 `test_check.py`**。`schema.md` 由 `graph-init` 持有;`query` 不複製 schema,只需「讀 MAP + 遍歷」最小知識(MAP header 自述格式),若需完整 schema 以 prefixed 路徑 cross-ref `graph-init/schema.md`。

### 3.7 命名與安裝

- harness 內 skill 資料夾**不帶 prefix**:`graph-init`、`query`(與既有 `feature`/`bug`/`orchestrator` 平行)。
- 安裝套 prefix:`graph-init` → `<prefix>-graph-init`、`query` → `<prefix>-query`(對齊 pohai 現況 `pohai-query`)。
- `docs/MAP.md`、`scripts/docgraph/` 是 repo 路徑,**不套 prefix**;`query` body 內對 `graph-init` 的 cross-ref 改 prefixed 名。
- INSTALL.md 新增「doc-graph module」段:copy `skills/{graph-init,query}` → `.claude/skills/<prefix>-{graph-init,query}/`;copy `scripts/docgraph` → `<repo>/scripts/`;copy `docs/docgraph/MAP.template.md`;套 prefix(cross-ref + slash 引用 + 標題列 skill 名);**不動** `scripts/docgraph/` 路徑與驗證器 code。
- 驗收三條:
  ① `cd <repo>/scripts/docgraph && python3 -m unittest -v` → 綠。
  ② MAP.template 落地後 `python3 scripts/docgraph/check.py` → **exit 0、零 finding**(空模板 = MAP 存在但無 data row → `parse_map` 回空 → 無 entry → 乾淨)。注意分清兩分支:**MAP 不存在** vs **MAP 存在但空**,獨立版兩者都該 exit 0,測試各覆蓋一例(`test_empty_map_is_clean`、`test_missing_map_is_clean`)。
  ③ 改名零殘留 —— **比照現有 INSTALL.md 的排除路徑語境 regex**,不可用裸 grep:
  ```
  grep -rnE "(^|[^A-Za-z0-9_/-])/(graph-init|query)([^A-Za-z0-9_/-]|$)" <repo>/.claude/skills/<prefix>-*
  ```
  ⚠️ `/query` 是高碰撞 token(會撞 `path#anchor`、URL query string、散文),光靠上式仍可能誤命中 → skill body 內 slash-command 一律寫成 backtick 形式 `` `/<prefix>-query` ``,驗收改 grep backtick-quoted 形式錨定,避免「數學上不可能零」。

## 4. 與既有 reuse 點

| 既有 | 角色 |
|------|------|
| `codegraph`(MCP) | code 層圖譜(query 第 3 步呼叫;純 code 走快捷直接用它) |
| pohai `doc-rot/check.py` | 切 `parse_map`+`check_map_graph` 出來成獨立驗證器 |
| pohai `pohai-query` SKILL | `query` skill 的母版(泛化:拔 stg/MEMORY pohai-specific 範例、ticket 改條件式) |
| harness module 慣例 | `graph-init`/`query` 照 `feature`/`bug` 同套 skill-dir + AI-bootstrap prefix 模式 |

## 5. 測試策略(writing-skills 鐵則)

兩支 skill 進 plan 後先跑 **RED baseline**:沒 skill 時丟 application/pressure scenario 看 agent 怎麼失敗,記錄 rationalization,再寫 skill 讓它 GREEN。

- `graph-init`(technique skill):給一個帶 outdated 文件的假 `docs/`,看 agent 沒 skill 時是否盲掃自動產 / 不分新舊 / 不跟人確認 → skill 要逼出「互動 pilot + status 標記 + 人工確認」。
- `query`(technique skill):給一個系統問題,看 agent 沒 skill 時是否亂 grep、不查 MAP、不警告 outdated → skill 要逼出「先 MAP / 純 code 走 codegraph / 命中 dated-snapshot 警告」。
- 驗證器 `check.py`:純 unittest(stdlib),覆蓋 dead-map-entry / duplicate-id / id-path-mismatch / dangling-link 各一例。

## 6. 風險 / 界線

- **graph-init 品質靠人**:互動 pilot 要求人逐項確認 domain/節點/status;若 user 草率全核可,圖譜品質會降 —— 但這是刻意把判斷留給人,優於盲掃自動產垃圾。
- **維護 drift**:`updated` 由 git 推、`status` enum 砍最小、`related` 容許爛(codegraph/grep 兜底);驗證器守連結不守「內容語意是否過時」—— 後者靠 `status` + query 第 5 步提醒。
- **納管邊界 gap**:沿用 pohai,不抓「該納管卻沒進 MAP」。rollout 到大 repo 時要另補納管邊界定義,別假設覆蓋率 100%。

## 7. 成功標準

1. harness 多出 `doc-graph` module(2 skill + 驗證器 + MAP 模板 + schema 參考),`INSTALL.md` 有可獨立裝的步驟。
2. 驗證器 `python3 -m unittest` 綠,覆蓋四種 finding。
3. 在一個乾淨測試 repo 上照 INSTALL 裝成:跑 `graph-init` 能互動建出小種子圖、`query` 能正確答跨節點問題並引用節點 id + 對 outdated 節點警告。
4. 兩支 skill 各有 RED→GREEN 測試紀錄(baseline 失敗 → 加 skill 後 compliant)。
