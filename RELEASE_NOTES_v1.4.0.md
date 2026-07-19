# CoachOS v1.4.0

CoachOS v1.4.0 introduces the first product version of `Workout Sequence Intelligence`.

## What This Release Means

This release moves CoachOS beyond single-activity interpretation.

Activity, Weekly, and Monthly now share a common coaching language for understanding where a run sits inside the surrounding training sequence:

- Activity answers: `today, where does this workout sit?`
- Weekly answers: `this week, what did the training actually leave behind?`
- Monthly answers: `this month, what did the training become?`

In other words:

`v1.4.0 turns Workout Sequence Intelligence from research into product language.`

## 中文

CoachOS v1.4.0 是 `Workout Sequence Intelligence` 第一次正式進入產品介面的版本。

這一版的重點不是新增更多統計，而是讓 CoachOS 開始把每一堂課放回前後訓練裡理解。Activity 會回答「今天這堂課在整段訓練中的位置」，Weekly 會回答「這週真正留下來的是什麼」，Monthly 則會回答「這個月最後建立了什麼」。

這代表 WSI 不再只是研究文件裡的推理模型，而是成為 Activity、Weekly、Monthly 與 AI 交棒共同使用的產品語言。使用者不需要理解 Mission Category、Mission Status 或 Continuity State；產品會把這些推理翻譯成更接近教練會說的話，例如「準備下一堂」、「已準備好下一堂」、「以銜接為主的建構月」。

這一版也加入資料匯入工具的序列理解重算入口，讓既有 SQLite 活動可以用目前規則重新產生 WSI。Excel 仍維持單純，不匯出 WSI；WSI 是 CoachOS 產品層與 SQLite 語意層的能力。

## English

CoachOS v1.4.0 is the first release where `Workout Sequence Intelligence` becomes a product-facing layer.

Instead of treating each activity as an isolated session, CoachOS now reads the surrounding sequence and translates that reasoning into human coaching language. Activity explains the position of today’s workout, Weekly summarizes how the week was organized, and Monthly turns mission distribution into a month-level coaching position.

This means WSI is no longer just a research model. It now shapes product copy, UI hierarchy, and AI handoff across the core coaching surfaces.

## Highlights

- Activity page now includes a productized `訓練序列理解` card
- Activity explains the workout’s sequence role, readiness outcome, coaching interpretation, and supporting evidence
- Weekly now summarizes mission distribution as `本週訓練重點`
- Monthly now includes a month-level hero such as `以銜接為主的建構月` or `以吸收為主的調整月`
- Weekly and Monthly rollups filter out low-confidence WSI so uncertain data does not drive the main product narrative
- AI handoff now receives WSI context before coach reasoning
- Import tool can batch recompute WSI into SQLite without changing Excel exports
- User-facing WSI labels are localized into Traditional Chinese across the import tool and product surfaces
- Rule engine v1.1 clarifies Long Run / LSD as `Build` and keeps low-confidence rows out of period-level hero summaries

## Notes

- `v1.4.0` is the first `Workout Sequence Intelligence Product Layer` release
- Workbook schema remains `v1.1`
- Excel remains intentionally simple; WSI is not exported to Excel
- WSI rules are still rule-based and versioned separately as `rule-v1.1`
- Research documents remain supporting artifacts; the release value is the productized coaching language

## Release Readiness

This release is ready when:

- Activity shows `訓練序列理解` before AI extended analysis
- Weekly and Monthly summarize WSI in coach-facing language rather than raw mission codes
- AI handoff includes WSI context
- Import tool can recompute WSI for existing SQLite activities
- No user-facing import-tool WSI labels remain in raw English
