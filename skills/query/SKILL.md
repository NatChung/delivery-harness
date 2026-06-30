---
name: query
description: Use when 問本 repo 的系統知識 —— 「怎麼部署 X / 為什麼這樣設計 / Y 的現狀」或任何「怎麼…/為什麼…/現狀…」這類問系統的問題,或 `/<prefix>-query`。唯讀導航,不改檔、不執行部署。
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
