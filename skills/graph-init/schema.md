# 節點 schema 與 MAP 格式(graph-init builder 參考)

## id 全域規則
`id` 限 `[a-z0-9-]+`;且 **id == 標題 anchor 字面 == 檔案級節點 front-matter id**。
→ anchor 檢查 = 對目標檔 grep `{#<id>}`,CJK slug 歧義消失。

## 檔案級節點(預設,每份納管 doc)
doc 開頭加 front-matter:
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
```markdown
## <domain>
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| <id> | <path>#<anchor> | <type> | <status> | false | <一句話用途> |
```
- `path#anchor` 以**第一個 `#`** 切;檔案級節點無 anchor(留 `path`)。
- `hook` 內若有 `|` 要 `\|` escape。
- domain = 封閉清單(init 時與 user 議定,不開放自由值)。
- `type` 詞彙 = 檔案級 enum(`runbook|spec|adr|reference|bug`)∪ `{procedure}`。
