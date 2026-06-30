# doc-graph Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 pohai-hub 驗證過的文件知識圖譜層抽成 `delivery-harness` 的第四個可獨立安裝 module `doc-graph`(兩支 skill + 獨立驗證器 + MAP 模板)。

**Architecture:** 純文字慣例 + 兩支 skill(`graph-init` 互動建圖 / `query` 圖譜優先導航)+ 一支獨立 stdlib 驗證器 `scripts/docgraph/check.py`(從 pohai `doc-rot/check.py` 抽 map-graph 半邊、刪 yaml 依賴)。靠 `INSTALL.md` 的 AI-bootstrap 套 prefix 安裝,不綁 feature/bug pipeline。

**Tech Stack:** Python 3 stdlib(驗證器 + 測試,`unittest`)、Markdown(skill / schema / MAP)、Claude Code skill 慣例。

**Spec:** `docs/2026-06-30-docgraph-extraction-design.md`(本計畫的設計來源,已過 fresh-subagent review)。

## Global Constraints

- 驗證器 **抽取後純 stdlib**:**不可** `import yaml`、不可帶 stale-term / dead-link 邏輯。照字面 copy 母檔會在沒裝 PyYAML 的 repo `exit 2`。
- 驗證器測試走 **`python3 -m unittest`**(對齊 harness 既有引擎測試 + 純 stdlib);**不可**用 pytest(`tmp_path` fixture / bare `assert` 在 unittest 下不會被收集)。
- 驗證器 **只做四種 finding**:`dead-map-entry` / `duplicate-id` / `id-path-mismatch` / `dangling-link`。**不做** orphan 偵測。
- 無發現 exit 0、有發現 exit 1;**MAP 不存在** 與 **MAP 存在但空** 兩種都 exit 0。
- harness 內 skill 資料夾 **不帶 prefix**(`graph-init` / `query`);prefix 在安裝時套(`<prefix>-graph-init` / `<prefix>-query`)。
- `codegraph` 是 **外部 optional 相依、不代裝**;query 純 code 快捷路徑未裝 codegraph 時退化成 grep。
- skill body 內 slash-command 一律寫 backtick 形式(`` `/<prefix>-query` ``),方便安裝驗收 grep 錨定。
- pohai 母體來源(供 Task 1 verbatim copy):`/Users/natchung/projects/pohai-hub/scripts/doc-rot/check.py`、`/Users/natchung/projects/pohai-hub/scripts/doc-rot/test_map_graph.py`、`/Users/natchung/projects/pohai-hub/.claude/skills/pohai-query/SKILL.md`。
- 所有工作在 harness repo `/Users/natchung/projects/public-delivery-harness`、分支 `feat/doc-graph-module`。

---

### Task 1: 獨立圖譜驗證器(`scripts/docgraph/check.py` + `test_check.py`)

**Files:**
- Create: `scripts/docgraph/check.py`
- Create: `scripts/docgraph/test_check.py`

**Interfaces:**
- Produces:
  - `check_map_graph(files: list[str], root: str) -> list[Finding]` — `files`=repo-relative `.md` 路徑清單,`root`=repo 絕對路徑。回 Finding 清單。
  - `parse_map(map_full: str) -> list[MapEntry]`、`format_report(findings: list) -> str`、`collect_md_files(root: str) -> list[str]`、`repo_root() -> str`、`main(argv=None) -> int`。
  - `Finding(path, line, category, message)`(frozen dataclass)、`MapEntry(id, path, anchor, type, status, sensitive, domain, line)`(frozen dataclass)。

- [ ] **Step 1: 寫 unittest 測試(從 pohai `test_map_graph.py` port,RED)**

建 `scripts/docgraph/test_check.py`。這是把 pohai pytest 風格的 13 個案例改寫成 `unittest.TestCase`、`tmp_path` → `tempfile.TemporaryDirectory`、bare `assert` → `self.assert*`,並 **新增** `test_empty_map_is_clean`。完整內容:

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import check  # noqa: E402

MAP_SAMPLE = """\
# MAP

## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| stg-deploy-runbook | docs/STG_DEPLOY_RUNBOOK.md | runbook | current | false | 全平台 STG 部署 |
| deploy-cms-stg | docs/STG_DEPLOY_RUNBOOK.md#deploy-cms-stg | procedure | current | false | 部署 cms 到 STG |

## architecture
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| adr-gcs-public-url | docs/architecture/adr-gcs-public-url.md | adr | current | false | 圖用公開 URL 的決策 |
"""

GOOD_MAP = """\
## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| runbook | docs/run.md | runbook | current | false | 部署 |
| deploy-cms | docs/run.md#deploy-cms | procedure | current | false | 部署 cms |
"""

EMPTY_MAP = """\
# MAP

## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|

## architecture
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
"""

RUN_MD = """\
---
id: runbook
title: Run
type: runbook
status: current
domain: cicd
sensitive: false
related:
  - deploy-cms
---
# Run
## 部署 cms {#deploy-cms}
步驟……內文連到 [[deploy-cms]]。
"""


class DocGraphCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def _run(self):
        files = []
        for dirpath, _, names in os.walk(self.root):
            for n in names:
                if n.endswith(".md"):
                    full = os.path.join(dirpath, n)
                    files.append(os.path.relpath(full, self.root))
        return check.check_map_graph(files, self.root)

    def _cats(self):
        return {f.category for f in self._run()}

    def test_parse_map_basic(self):
        self._write("docs/MAP.md", MAP_SAMPLE)
        entries = check.parse_map(os.path.join(self.root, "docs/MAP.md"))
        by_id = {e.id: e for e in entries}
        self.assertEqual(
            set(by_id),
            {"stg-deploy-runbook", "deploy-cms-stg", "adr-gcs-public-url"},
        )
        self.assertEqual(by_id["deploy-cms-stg"].path, "docs/STG_DEPLOY_RUNBOOK.md")
        self.assertEqual(by_id["deploy-cms-stg"].anchor, "deploy-cms-stg")
        self.assertEqual(by_id["deploy-cms-stg"].type, "procedure")
        self.assertEqual(by_id["deploy-cms-stg"].domain, "cicd")
        self.assertEqual(by_id["stg-deploy-runbook"].anchor, "")
        self.assertEqual(by_id["adr-gcs-public-url"].domain, "architecture")
        self.assertIs(by_id["adr-gcs-public-url"].sensitive, False)

    def test_clean_graph_no_findings(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self.assertEqual(self._run(), [])

    def test_dead_map_entry_missing_anchor(self):
        self._write("docs/MAP.md", GOOD_MAP.replace("docs/run.md#deploy-cms", "docs/run.md#nope"))
        self._write("docs/run.md", RUN_MD)
        self.assertIn("dead-map-entry", self._cats())

    def test_dead_map_entry_missing_file(self):
        self._write("docs/MAP.md", GOOD_MAP.replace("docs/run.md", "docs/gone.md"))
        self.assertIn("dead-map-entry", self._cats())

    def test_missing_map_is_clean(self):
        self.assertEqual(check.check_map_graph([], self.root), [])

    def test_empty_map_is_clean(self):
        self._write("docs/MAP.md", EMPTY_MAP)
        self.assertEqual(self._run(), [])

    def test_dangling_link(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD.replace("[[deploy-cms]]", "[[ghost]]"))
        self.assertIn("dangling-link", self._cats())

    def test_duplicate_id(self):
        self._write("docs/MAP.md", GOOD_MAP + "| runbook | docs/run.md | runbook | current | false | dup |\n")
        self._write("docs/run.md", RUN_MD)
        self.assertIn("duplicate-id", self._cats())

    def test_id_path_mismatch(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/other.md", RUN_MD)
        self._write("docs/run.md", "# Run\n## 部署 cms {#deploy-cms}\n")
        self.assertIn("id-path-mismatch", self._cats())

    def test_bug_ticket_not_a_node(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/bugs/x.md", "---\nid: bug-x\ntrack: bug\nsystem: app\n---\n# Bug x\n")
        self.assertEqual(self._run(), [])

    def test_inline_code_wikilink_ignored(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/meta.md", "# Meta\n說明:連結寫成 `[[id]]`,例如 `[[ghost]]`。\n")
        self.assertEqual(self._run(), [])

    def test_non_node_related_not_dangling(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/bugs/y.md", "---\nid: bug-y\ntrack: bug\nsystem: app\nrelated:\n  - bug-zzz\n---\n# Bug y\n")
        self.assertEqual(self._run(), [])

    def test_managed_node_related_dangling(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD.replace("  - deploy-cms\n", "  - deploy-cms\n  - ghostnode\n"))
        self.assertIn("dangling-link", self._cats())

    def test_duplicate_id_no_spurious_mismatch(self):
        self._write("docs/MAP.md", GOOD_MAP + "| runbook | docs/other.md | runbook | current | false | dup |\n")
        self._write("docs/run.md", RUN_MD)
        cats = self._cats()
        self.assertIn("duplicate-id", cats)
        self.assertNotIn("id-path-mismatch", cats)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗(RED)**

Run: `cd /Users/natchung/projects/public-delivery-harness/scripts/docgraph && python3 -m unittest -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'check'`(check.py 還沒建)。

- [ ] **Step 3: 建 `scripts/docgraph/check.py`(抽取 + 刪 yaml + 自帶 collection/main)**

`check.py` 的中段函式 **逐字 copy** 自 pohai `/Users/natchung/projects/pohai-hub/scripts/doc-rot/check.py` 的下列行段(**不要改邏輯**):
`Finding`(L40-45)、`MapEntry`(L258-267)、4 個常數 `MAP_REL`/`_PIPE_SPLIT`/`DOMAIN_HDR_RE`/`WIKILINK_RE`(L270-273)、`parse_map`(L276-300)、`_read_lines`(L303-305)、`_frontmatter_id`(L308-323)、`_related_ids`(L326-343)、`_inline_ids`(L346-359)、`check_map_graph`(L362-421)、`format_report`(L424-433)。

檔頭(**無 yaml**)、file-collection、main 為 **新寫**,完整如下。組裝順序:檔頭 → `Finding` → file-collection(`repo_root`/`collect_md_files`)→ `MapEntry` + 4 常數 → `parse_map` → 4 個 `_*` helper → `check_map_graph` → `format_report` → `main` → `__main__` guard。

檔頭:
```python
#!/usr/bin/env python3
"""docgraph: 驗證 docs/MAP.md 文件圖譜完整性(獨立、純 stdlib)。
無發現 exit 0,有發現 exit 1。從 pohai doc-rot check.py 抽 map-graph 半邊。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
```

file-collection(新寫,取代母版 `collect_files`/`repo_root` 的 git-only 行為):
```python
def repo_root() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def collect_md_files(root: str) -> list:
    """收 root 下所有 .md 的 repo-relative 路徑。優先 git ls-files,失敗 fallback os.walk。"""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "*.md"], cwd=root, stderr=subprocess.DEVNULL
        )
        files = [ln for ln in out.decode().splitlines() if ln]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    files = []
    for dirpath, dirnames, names in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.relpath(os.path.join(dirpath, n), root))
    return files
```

main(新寫,只跑 map-graph、無母版的 `--only`/`--rules`):
```python
def main(argv=None) -> int:
    root = repo_root()
    files = collect_md_files(root)
    findings = check_map_graph(files, root)
    print(format_report(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑測試確認通過(GREEN)**

Run: `cd /Users/natchung/projects/public-delivery-harness/scripts/docgraph && python3 -m unittest -v`
Expected: PASS —— 14 個 test 全綠(13 ported + `test_empty_map_is_clean`)。

- [ ] **Step 5: 驗 CLI entry 可跑**

Run: `cd /Users/natchung/projects/public-delivery-harness && python3 scripts/docgraph/check.py; echo "exit=$?"`
Expected: 印 `—— 乾淨,0 筆。` 且 `exit=0`(harness repo 此時還沒 MAP.md → `check_map_graph` 走 MAP-不存在分支回 [])。

- [ ] **Step 6: Commit**

```bash
cd /Users/natchung/projects/public-delivery-harness
git add scripts/docgraph/check.py scripts/docgraph/test_check.py
git commit -m "feat(doc-graph): standalone stdlib map-graph validator + unittest

Extracted map-graph half from pohai doc-rot/check.py, dropped yaml import
and stale-term/dead-link code, added git-ls-files/os.walk collection and
slim main. 14 unittest cases (ported from pytest + empty-map clean).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: MAP 種子模板 + 節點 schema 參考(`docs/docgraph/MAP.template.md` + `skills/graph-init/schema.md`)

**Files:**
- Create: `docs/docgraph/MAP.template.md`
- Create: `skills/graph-init/schema.md`

**Interfaces:**
- Produces: 安裝時 copy 進 target repo 的兩份靜態檔。MAP.template 落地成 `docs/MAP.md` 後驗證器須回乾淨;schema.md 是 graph-init builder 的 heavy reference。

- [ ] **Step 1: 建 `docs/docgraph/MAP.template.md`**

```markdown
# MAP — 文件圖譜註冊表

> `<prefix>-query` 與 `scripts/docgraph/check.py` 的入口。每列 = 一個節點:`id → path#anchor`。
> `[[id]]` 一律經此表解析。`sensitive: true` 的節點交付前需過濾。
> 由 `<prefix>-graph-init` 互動建立;新增節點請照 `skills/<prefix>-graph-init/schema.md`。

## <domain-a>
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|

## <domain-b>
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
```

- [ ] **Step 2: 驗空模板跑驗證器乾淨**

Run:
```bash
cd /Users/natchung/projects/public-delivery-harness && \
  TMP=$(mktemp -d) && git -C "$TMP" init -q && mkdir -p "$TMP/docs" && \
  cp docs/docgraph/MAP.template.md "$TMP/docs/MAP.md" && \
  cp scripts/docgraph/check.py "$TMP/" && \
  ( cd "$TMP" && python3 check.py; echo "exit=$?" ) && rm -rf "$TMP"
```
Expected: 印 `—— 乾淨,0 筆。` 且 `exit=0`(空 domain 表 → `parse_map` 無 data row → 無 finding)。

- [ ] **Step 3: 建 `skills/graph-init/schema.md`(heavy reference)**

```markdown
# 節點 schema 與 MAP 格式(graph-init builder 參考)

## id 全域規則
`id` 限 `[a-z0-9-]+`;且 **id == 標題 anchor 字面 == 檔案級節點 front-matter id**。
→ anchor 檢查 = 對目標檔 grep `{#<id>}`,CJK slug 歧義消失。

## 檔案級節點(預設,每份納管 doc)
doc 開頭加 front-matter:
\`\`\`yaml
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
\`\`\`
- `related` 必須是 YAML block list 裸 id;**內文連結才用 `[[id]]`**。兩者 id 都必須在 MAP 有列。
- `updated` **不手填**,查詢時由 git 推導。
- `type` 不含 `ticket`(活狀態由 ticket 系統管,圖譜只指不鏡像)。
- `status` 是分新舊的核心:`current` 有效 / `dated-snapshot` 某時點快照 / `archived` 已封存。

## 熱點節點(兩類,表示法不同)
- **procedure = 檔內 anchor**:大檔內一段。`## 標題 {#id}` + 在 MAP 註冊,**不自帶 front-matter**(一檔一塊 front-matter),身分靠 MAP 那列。type=`procedure`(只存在 MAP)。
- **ADR = 獨立小檔**:一決策一檔(context/decision/consequence),**自帶 front-matter**(`type: adr`),跟其他檔案級節點一樣。
- 只有「同檔多節點(procedure)」需靠 MAP 補身分。

## MAP.md 格式
per-domain markdown 表,每列一節點:
\`\`\`markdown
## <domain>
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| <id> | <path>#<anchor> | <type> | <status> | false | <一句話用途> |
\`\`\`
- `path#anchor` 以**第一個 `#`** 切;檔案級節點無 anchor(留 `path`)。
- `hook` 內若有 `|` 要 `\|` escape。
- domain = 封閉清單(init 時與 user 議定,不開放自由值)。
- `type` 詞彙 = 檔案級 enum(`runbook|spec|adr|reference|bug`)∪ `{procedure}`。
```

> 註:上面 yaml/markdown fence 在實際檔案用三個反引號(此處為避免巢狀 fence 顯示而轉義),寫檔時還原成正常 ```。

- [ ] **Step 4: Commit**

```bash
cd /Users/natchung/projects/public-delivery-harness
git add docs/docgraph/MAP.template.md skills/graph-init/schema.md
git commit -m "feat(doc-graph): MAP seed template + node schema reference

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `graph-init` skill(互動建圖,RED→GREEN per writing-skills)

**Files:**
- Create: `skills/graph-init/SKILL.md`
- (uses) `skills/graph-init/schema.md`(Task 2)、`scripts/docgraph/check.py`(Task 1)

**Interfaces:**
- Consumes: schema.md(節點/MAP 格式)、check.py(建完跑驗證)。
- Produces: 一支互動式 technique skill,觸發 `<prefix>-graph-init`。

> **writing-skills 鐵則:NO SKILL WITHOUT A FAILING TEST FIRST。** 先跑 RED baseline(無 skill 看 agent 怎麼失敗)再寫。

- [ ] **Step 1: 建 RED baseline 測試夾具**

建臨時假 repo(scratchpad 下),含一個「文件多又 outdated」的 `docs/`:
```bash
FIX=/private/tmp/claude-501/-Users-natchung-projects-pohai-hub/e673ea5e-263c-401d-ab38-8b811ac4b1c0/scratchpad/graphinit-red
rm -rf "$FIX" && mkdir -p "$FIX/docs/archive"
printf '# 部署 SOP\n舊版部署步驟……\n' > "$FIX/docs/DEPLOY.md"
printf '# 架構\n服務拆解……\n' > "$FIX/docs/architecture.md"
printf '# 2025 遷移 WIP(留作參考)\n已過時內容……\n' > "$FIX/docs/archive/2025-migration-WIP.md"
printf '# 隨手筆記\n雜記……\n' > "$FIX/docs/notes.md"
echo "fixture ready: $FIX"
```

- [ ] **Step 2: 跑 RED baseline(無 skill,dispatch 一個 general-purpose subagent)**

Dispatch 一個 subagent,prompt:「這個 repo 在 `<FIX>`,docs/ 文件多且有些 outdated。請幫它建一套『文件知識圖譜』讓 AI 能找到正確且分得清新舊的文件。」**不給任何 skill。** 記錄 baseline 行為(逐字):
- 是否盲掃全 docs/ 自動產節點、不跟人確認?
- 是否完全沒處理「新舊」(`status` 概念)?
- 是否把 archive/WIP 跟 current 混為一談?
- 用了哪些 rationalization?
把觀察寫進 `skills/graph-init/SKILL.md` 之前先存到 commit message / 暫存筆記,作為 RED 證據。

- [ ] **Step 3: 寫 `skills/graph-init/SKILL.md`(GREEN,針對 baseline 失敗)**

```markdown
---
name: graph-init
description: 在本 repo 互動式建立文件知識圖譜(docs/MAP.md + 節點 front-matter),讓 AI 能找到正確且分得清新舊的文件。Trigger:「建文件圖譜 / init 圖譜 / 把 docs 納管」這類請求,每個 repo 跑一次。
---

# graph-init — 互動式建文件圖譜(pilot)

把 repo 文件做成「機器可解析的節點圖」。**互動式 pilot**,不是一次掃全 repo 自動產 —— outdated repo 盲掃會產垃圾節點 + status 全靠猜。產「小而準」的種子圖,之後可增量擴。

> Schema 與 MAP 格式 = `schema.md`(同目錄)。建完用 `scripts/docgraph/check.py` 驗。

## 步驟(每步給人看,別一口氣全自動)

1. **掃 `docs/` + 標 outdated 訊號**:列文件清單;標出疑似過時的(路徑含 `archive`、檔名/內文含 `WIP`、舊日期、「留作參考」「已過時」等字樣)。**把清單給 user 看。**
2. **提議封閉清單 domain(pilot 挑 2 個高價值 domain)** + 每 domain 的代表節點(含 1-2 個熱點 procedure 或 ADR)。**給 user 逐項確認:核可 / 刪 / 改 domain。**
3. **逐節點議定 `status`**:current / dated-snapshot / archived。outdated 的別丟掉 —— 標 `dated-snapshot`/`archived`,讓查詢時能提醒。**status 由 user 拍板,不要自己猜。**
4. **動工(經 user 同意後)**:照 `schema.md` 給檔案級節點加 front-matter、給熱點 procedure 加 `## 標題 {#id}`、產 `docs/MAP.md`(由 `MAP.template.md` 起手、填節點列)。
5. **驗證**:跑 `python3 scripts/docgraph/check.py` → 必須乾淨(exit 0)。有 finding 就修到綠。
6. **收尾**:告訴 user 之後用 `` `/<prefix>-query` `` 查圖;圖可日後增量擴(再跑本 skill 加 domain/節點)。

## 鐵則(對抗盲建)
- **不跟人確認就不寫檔。** domain、納管哪些節點、每個節點的 `status`,全部要 user 拍板。
- **不丟棄 outdated 文件** —— 標 `status` 納管,不是排除。分新舊是本圖譜的核心價值。
- **pilot = 2 domain 起步**,不要一次納管整個 repo。

## 不做
- 不一次自動掃全 repo 產整份 MAP(那是反模式)。
- 不改文件「內容語意」,只加 front-matter / anchor / MAP 列。
- 不執行部署、不刪檔。
```

- [ ] **Step 4: 跑 GREEN(同 Step 1 夾具 + 這支 skill,dispatch subagent 帶 skill)**

重置夾具(同 Step 1),dispatch 一個 subagent **帶 `skills/graph-init/SKILL.md` 內容**跑同一任務。驗證它現在:① 先把文件清單 + outdated 標記給人看;② 提議 2 domain 並等確認;③ 每節點問 status;④ 經同意才寫檔;⑤ 跑 check.py 驗。記錄是否 compliant。

Expected: subagent 走互動 pilot、不盲建、處理 status。若仍有 rationalization(如「user 沒回我就先建」)→ Step 5。

- [ ] **Step 5: REFACTOR(補漏洞)+ Commit**

把 GREEN 階段冒出的新 rationalization 加進「鐵則」表,re-test 到 compliant。然後:
```bash
cd /Users/natchung/projects/public-delivery-harness
git add skills/graph-init/SKILL.md
git commit -m "feat(doc-graph): graph-init interactive builder skill (RED->GREEN)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `query` skill(圖譜優先導航,RED→GREEN)

**Files:**
- Create: `skills/query/SKILL.md`

**Interfaces:**
- Consumes: `docs/MAP.md`(graph-init 產)、`scripts/docgraph/`(同 repo)、外部 `codegraph`(optional)。
- Produces: 一支唯讀導航 technique skill,觸發 `<prefix>-query`。母版 = pohai `pohai-query/SKILL.md`,泛化(拔 stg/MEMORY pohai-specific、ticket 改條件式)。

- [ ] **Step 1: 跑 RED baseline(無 skill)**

用 Task 3 建好圖的夾具(或 harness 自身的 docs),dispatch 一個 subagent 問一個跨節點系統問題(例:「這個 repo 怎麼部署 X / 為什麼這樣設計」)**不給 skill**。記錄 baseline:是否亂 grep、不查 MAP、不沿 related 遍歷、不對 outdated 節點警告、純 code 問題卻不直接走 codegraph?

- [ ] **Step 2: 寫 `skills/query/SKILL.md`(GREEN)**

```markdown
---
name: query
description: 查詢本 repo 的系統知識(文件圖譜 + git + codegraph)。回答「怎麼部署 X / 為什麼這樣設計 / Y 的現狀」並能吐可執行步驟。Trigger:「/query …」或「怎麼…/為什麼…/現狀…」這類問系統的問題。唯讀導航,不改檔、不執行部署。
---

# query — 查系統知識(唯讀導航)

回答關於本 repo 系統的問題。**唯讀**:只查、只答、只吐步驟;真要執行交給對應 runbook/skill。

## 步驟
> **快捷(純 code 定位)**:問題是「X 在哪定義 / 誰 call Y / 這函式呼叫誰」→ **跳過 MAP,直接 `codegraph`**(search/callers/callees/explore)。純 code 不在 MAP(MAP 只收文件節點),先讀 MAP 是空轉。**未裝 codegraph 則退化用 `grep`。** 只有牽涉「為什麼這樣設計 / 現狀」時才回到下面從 MAP 起手。

1. **讀 `docs/MAP.md`**:依 hook / id / domain 鎖定相關節點。MAP 每列 `id → path#anchor` 是唯一解析來源。
2. **讀節點**:打開該 `path`(有 `#anchor` 讀該段);沿 front-matter `related`(裸 id)與內文 `[[id]]`、經 MAP 解析遍歷必要鄰居。
3. **查活源**(視需要):
   - 變更歷史/為何:`git log` / `git blame <file>`
   - code 層:`codegraph`(未裝則 grep)
   - ticket 現狀:**先確認 `scripts/feature/cli.py` 存在**(`test -f`),有才跑 `python3 scripts/feature/cli.py status <id>`;**沒有就跳過 ticket 活源,別嘗試跑不存在的 cli.py。**
4. **回答** + **引用來源節點 id**;可執行任務(部署)直接吐該 procedure 步驟。
5. **新舊提醒**:判新舊看**內容區塊**(`git blame` 內文行,或 `git log` 略過純 front-matter / anchor commit),**別用整檔 `git log -1`** —— 加 front-matter / `{#anchor}` 那次 commit 會把整檔日期重置成當天、讓節點看似「很新」其實沒動(已知坑)。節點 `status: dated-snapshot|archived`,或內容很久沒動 → **主動提醒「可能過時、請查活源」**。

## 不做
- 不改檔、不跑部署、不 ingest、不合成。
- MAP 沒有的 id = 圖譜外,改用 grep/codegraph 直接找,並回報「此項未納管」。
```

- [ ] **Step 3: 跑 GREEN(帶 skill,dispatch subagent)**

同 Step 1 問題、帶 `skills/query/SKILL.md`。驗證:① 純 code 問題走 codegraph 快捷、② 系統問題先讀 MAP→沿 related 遍歷、③ 引用節點 id、④ 命中 dated-snapshot/archived 主動警告、⑤ 沒裝 cli.py 時不嘗試跑。

- [ ] **Step 4: REFACTOR + Commit**

補 GREEN 冒出的漏洞到步驟/不做。然後:
```bash
cd /Users/natchung/projects/public-delivery-harness
git add skills/query/SKILL.md
git commit -m "feat(doc-graph): query graph-first navigator skill (RED->GREEN)

Generalized from pohai-query: codegraph optional w/ grep fallback,
conditional ticket lookup (detect cli.py), no pohai-specific examples.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `INSTALL.md` doc-graph 安裝段 + 乾淨 repo 端到端驗收

**Files:**
- Modify: `INSTALL.md`(append 一段「doc-graph module(可獨立裝)」)

**Interfaces:**
- Consumes: Task 1-4 全部產物。
- Produces: target repo 的 AI 照此段把 doc-graph 裝進任一 repo 的步驟 + 驗收。

- [ ] **Step 1: append doc-graph 安裝段到 `INSTALL.md`**

在現有 9 步流程後新增一節(完整內容):

```markdown
---

## doc-graph module(可獨立裝,不綁 feature/bug pipeline)

把文件知識圖譜層裝進 target repo。可單獨裝(不需先裝 feature pipeline)。指定 `<prefix>`(例 `dek-`)。

1. fetch 本 repo `skills/{graph-init,query}`、`scripts/docgraph/`、`docs/docgraph/MAP.template.md`(GitHub raw,從 main)。
2. copy:
   - `skills/graph-init` → `<repo>/.claude/skills/<prefix>-graph-init/`(含 `schema.md`)
   - `skills/query` → `<repo>/.claude/skills/<prefix>-query/`
   - `scripts/docgraph` → `<repo>/scripts/docgraph/`(含 `check.py`、`test_check.py`)
   - `docs/docgraph/MAP.template.md` → `<repo>/docs/docgraph/MAP.template.md`
   (目標目錄不存在先 `mkdir -p`)
3. **套 prefix**:
   - 兩支 skill 的 `name:`(`graph-init`→`<prefix>-graph-init`、`query`→`<prefix>-query`)與 body 內 backtick slash-command(`` `/graph-init` ``、`` `/query` ``→ 加 prefix)
   - 兩支 skill 內互指(graph-init 收尾指向 `<prefix>-query`;query 指 schema.md 時用 `<prefix>-graph-init`)
   - `MAP.template.md` 內的 `<prefix>-query`/`<prefix>-graph-init` 佔位
   - **不動**:`scripts/docgraph/` 路徑、`check.py`/`test_check.py` code、`docs/MAP.md` 路徑(都不套 prefix)
4. **codegraph(外部 optional、不代裝)**:告知 user —— query 的純 code 快捷路徑靠 `codegraph`(user 機器層級 MCP)。建議 user 自行 `codegraph init`;未裝則純 code 問題退化走 grep,文件圖譜半邊不受影響。
5. **驗收三條**,全綠才算裝成:
   - `cd <repo>/scripts/docgraph && python3 -m unittest -v` → 驗證器測試綠(14 test)。
   - `cd <repo> && python3 scripts/docgraph/check.py; echo $?` → 印「乾淨」且 `0`(repo 尚無 `docs/MAP.md`,走 MAP-不存在分支)。
   - 改名零殘留(排除路徑語境,**別用裸 grep**):
     ```
     grep -rnE "(^|[^A-Za-z0-9_/-])/(graph-init|query)([^A-Za-z0-9_/-]|$)" <repo>/.claude/skills/<prefix>-graph-init <repo>/.claude/skills/<prefix>-query
     ```
     `/query` 高碰撞 → skill 內 slash-command 都寫 backtick 形式,確認剩下的命中都已是 `<prefix>-` 開頭、無裸 `/graph-init`、`/query`。

裝完該 repo 有 `<prefix>-{graph-init,query}` 兩個 skill + `scripts/docgraph/` + `docs/docgraph/MAP.template.md`。下一步:跑 `` `/<prefix>-graph-init` `` 互動建第一版圖。

前提:repo 有 Python3(驗證器純 stdlib)。codegraph 為 optional(見 step 4)。
```

- [ ] **Step 2: 端到端驗收(在乾淨臨時 repo 模擬安裝)**

```bash
cd /Users/natchung/projects/public-delivery-harness
DEST=$(mktemp -d) && git -C "$DEST" init -q
mkdir -p "$DEST/.claude/skills/dek-graph-init" "$DEST/.claude/skills/dek-query" "$DEST/scripts" "$DEST/docs/docgraph"
cp skills/graph-init/SKILL.md skills/graph-init/schema.md "$DEST/.claude/skills/dek-graph-init/"
cp skills/query/SKILL.md "$DEST/.claude/skills/dek-query/"
cp -r scripts/docgraph "$DEST/scripts/"
cp docs/docgraph/MAP.template.md "$DEST/docs/docgraph/"
# 套 prefix(name + backtick slash-command)
sed -i '' 's/^name: graph-init/name: dek-graph-init/' "$DEST/.claude/skills/dek-graph-init/SKILL.md"
sed -i '' 's/^name: query/name: dek-query/' "$DEST/.claude/skills/dek-query/SKILL.md"
sed -i '' 's#`/<prefix>-query`#`/dek-query`#g; s#`/<prefix>-graph-init`#`/dek-graph-init`#g' "$DEST/.claude/skills/dek-graph-init/SKILL.md" "$DEST/.claude/skills/dek-query/SKILL.md"
echo "=== 驗收① unittest ===" && ( cd "$DEST/scripts/docgraph" && python3 -m unittest 2>&1 | tail -3 )
echo "=== 驗收② check.py 乾淨 ===" && ( cd "$DEST" && python3 scripts/docgraph/check.py; echo "exit=$?" )
echo "=== 驗收③ 改名零殘留 ===" && grep -rnE "(^|[^A-Za-z0-9_/-])/(graph-init|query)([^A-Za-z0-9_/-]|$)" "$DEST/.claude/skills/dek-graph-init" "$DEST/.claude/skills/dek-query" || echo "零殘留 OK"
rm -rf "$DEST"
```
Expected: ① `OK`(14 test);② 印「乾淨」+`exit=0`;③ `零殘留 OK`(無裸 `/graph-init`、`/query`)。

- [ ] **Step 3: Commit**

```bash
cd /Users/natchung/projects/public-delivery-harness
git add INSTALL.md
git commit -m "docs(doc-graph): INSTALL section for standalone doc-graph module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage**(對 design 各節):
- §3.1 模組邊界/codegraph 外部相依 → Task 4 skill(grep fallback)+ Task 5 INSTALL step 4 ✓
- §3.2 兩 skill 分工(query 快捷 + 條件式 ticket)→ Task 4 ✓
- §3.3 節點 schema → Task 2 schema.md ✓
- §3.4 MAP 格式 + 種子模板 → Task 2 MAP.template.md ✓
- §3.5 驗證器(刪 yaml、真實相依、自帶 collection/main、四種 finding、不做 orphan)→ Task 1 ✓
- §3.6 資產(copy vs harness-only)+ test pytest→unittest → Task 1 Step 1 + Task 5 ✓
- §3.7 命名/prefix/驗收三條 → Task 5 ✓
- §5 測試策略(skill RED→GREEN、驗證器 unittest 四 finding)→ Task 1 / 3 / 4 ✓
- §7 成功標準 → Task 5 端到端驗收涵蓋 1-3;標準 4(RED→GREEN 紀錄)→ Task 3/4 ✓

**Placeholder scan:** 驗證器/測試/skill/INSTALL 皆給完整內容;copy-verbatim 段標明確切來源行段。schema.md 內巢狀 fence 已加「寫檔時還原」註記。無 TBD/TODO。

**Type consistency:** `check_map_graph(files, root)`、`Finding(path,line,category,message)`、`MapEntry(...)`、`collect_md_files`、`repo_root`、`main` 在 Task 1 定義並在 Task 2/5 一致引用;skill `name:`/slash-command 命名在 Task 3/4/5 一致(`graph-init`/`query` → 安裝套 `<prefix>-`)。
