---
id: "{{id}}"
slug: {{slug}}
track: bug
phase: 0-intake
severity: {{severity}}
created: {{created}}
---

# Bug {{id}} — {{slug}}

> track: bug ｜ severity: {{severity}} ｜ phase 由 `scripts/feature/cli.py` 管理。
> 修法:`/systematic-debugging` 找 root cause → 寫會 fail 的重現測試 → TDD 修綠 → verify。

## 報修源
- 報修者 / 管道:
- 重現步驟:
- 期望 vs 實際:

## Root cause(bug-debug 階段填)
-

## Branch
- `fix/{{id}}-{{slug}}`(從該 repo 的真 branch 切;bug-repro + bug-fix 同一條)

## Gates(agent 維護)
- [ ] repro-red(失敗重現測試:assert 在客戶回報的症狀上、且紅在對的原因)
- [ ] tests-green(重現測試綠 + 既有測試沒壞)
- [ ] bug-verified(報修者 / QA 確認修好)

## History
- {{created}} created (track=bug, severity={{severity}})
