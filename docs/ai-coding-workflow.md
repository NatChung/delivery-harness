# AI Coding 工作流 cheat-sheet

給「用過 Claude Code、但還不熟這套流程」的開發者。一頁速查:開工前先記三個
「查哪裡」,然後照 0→3 走。

## 三個「查哪裡」

| 要查什麼 | 用什麼 | 一句話 |
|---|---|---|
| 查 CODE | **codegraph** | symbol 圖譜。問「X 在哪 / 誰呼叫 Y」用它,別 grep。 |
| 查規格 | **doc-graph(圖譜)** | 文件之間的關係圖。拿來找 spec / 設計。 |
| 工作狀態 | **ticket** | 狀態寫在磁碟的 markdown,不活在對話裡 → 換機器、隔週都能從上次停的地方接續。 |

## 0. 先別開 IDE、先別看 CODE

用 console 或 App,從「外部行為 / 規格」入手,別一上來就陷進實作細節。

## 1. 新功能(走 Superpowers)

```
brainstorming →（產出 design.md）→ requesting-code-review
  → writing-plans →（產出 plan.md）→ requesting-code-review
  → subagent-driven 實作
```

- 實作走 **TDD**:先寫測試再寫 code。
- 重點:`design.md` 和 `plan.md` 兩個產出物,**各過一次獨立 context 的 review
  subagent**(新的眼睛)才往下 —— 不是同一個 agent review 自己。

## 2. Debug

```
自己用 prompt 先複現問題 → 建 UI/API 測試（fail first，先讓它紅）
  → systematic-debugging → fix → 重跑測試轉綠
```

- **沒有穩定複現 = 還不能動手改。**

## 3. 收尾

```
Local PR → requesting-code-review
```

- 喊「好了」之前,先**實際跑過驗證**(拿 evidence,不是用嘴講)。

---

## 名稱對照(別叫錯就 invoke 不到)

`brainstorming`、`requesting-code-review`、`writing-plans`、
`subagent-driven-development`、`systematic-debugging`、
`verification-before-completion` —— 都是 Superpowers skill 名,照原樣才叫得出來。
