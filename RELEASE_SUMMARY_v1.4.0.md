# CoachOS v1.4.0 Release Summary

## Short Summary

CoachOS v1.4.0 introduces the first product-facing `Workout Sequence Intelligence` layer.

This version brings sequence-aware coaching into Activity, Weekly, Monthly, and AI handoff. Instead of only asking what happened inside one run, CoachOS now explains where a workout sits in the training sequence, what the week was organized around, and what the month ultimately became.

## Highlights

- Activity 新增 `訓練序列理解`，回答今天這堂課在整段訓練中的位置
- Weekly 新增 `本週訓練重點`，用教練語言整理本週序列角色
- Monthly 新增月層級 Hero，回答這個月最後建立了什麼
- AI 交棒納入 WSI，讓外部 AI 先理解序列，再延伸分析
- 資料匯入工具可批次重算 SQLite 裡的 WSI
- Excel 維持單純，不匯出 WSI
- 低信心 WSI 不再主導 Weekly / Monthly 的主敘事
- Long Run / LSD 在 rule-v1.1 中回到 `建立能力`

## Suggested Git Commit Message

`release: prepare CoachOS v1.4.0 WSI product layer`

## Suggested Release Title

`CoachOS v1.4.0 — Workout Sequence Intelligence Product Layer`
