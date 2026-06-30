---
name: graph-init
description: Use when 要為本 repo 建立文件知識圖譜、init 圖譜、或把 docs 納管管理 —— 讓 AI 能找到正確且分得清新舊的文件。每個 repo 跑一次,互動式 pilot。
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
