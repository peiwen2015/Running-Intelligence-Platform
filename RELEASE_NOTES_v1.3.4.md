# CoachOS v1.3.4

CoachOS v1.3.4 is a refinement release for `Connected Coach Knowledge`.

## What This Release Means

This release does not rename the product or change the milestone theme.

Instead, it makes the existing v1.3 direction feel more real in daily use:

- confirmed knowledge flows more cleanly into later coaching
- Activity reasoning reads workout structure more directly
- AI handoff and training card prompts are more usable
- local import and backfill flows are more reliable

In other words:

`Connected Coach Knowledge now feels more operational, not just conceptual.`

## 中文

CoachOS v1.3.4 不是一個全新主題的版本，而是 `Connected Coach Knowledge` 的收斂版。這一波的重點，不是再新增一個大功能，而是把已經存在的產品方向做得更完整、更可信、更適合每天使用。現在，Activity 不只會顯示 Coach Knowledge，還會更直接讀課表結構來理解 WU / Main / Recovery / CD；每公里 raw split 不再單獨扮演整堂課的唯一真相。Weekly / Monthly 與 AI handoff 仍然建立在已確認知識之上，但整體資料脈絡更穩，讓跑者更容易感受到「我剛剛教了 CoachOS，它後面真的有變懂」。

同時，v1.3.4 也把幾個日常使用上真的會卡住的地方補齊了。現在平台可以回補 GPS 與課表結構到 Excel 與 SQLite，Activity 的每日圖卡 prompt 不只可以直接交給圖像 AI，也會帶著更完整的課表片段與判讀脈絡；週圖卡與月圖卡 prompt 也一起成立。Metadata / Settings 的流程則持續穩定下來，包含建議值、provenance、鞋款狀態與補標註體驗。這代表 v1.3.4 的價值，不是在宣布一個新的產品方向，而是在讓 `Connected Coach Knowledge` 從「已經打通」走向「真的能每天使用」。

## English

CoachOS v1.3.4 is not a new milestone theme. It is a refinement release for `Connected Coach Knowledge`. The point of this version is not to introduce one more large feature, but to make the existing product direction more complete, more trustworthy, and more usable in everyday workflow. Activity now does more than display Coach Knowledge; it reads workout structure more directly so WU / Main / Recovery / CD can shape the interpretation, instead of letting raw kilometer splits act as the only truth of the session. Weekly / Monthly reasoning and AI handoff still build on confirmed knowledge, but the overall data flow is steadier, making it easier for the runner to feel that “I just taught CoachOS something, and it really understood more afterward.”

At the same time, v1.3.4 closes several practical gaps that mattered in daily use. The platform can now backfill GPS and workout structure into both Excel and SQLite. The daily training card prompt from Activity is more complete and better suited for image AI, carrying stronger structure and reasoning context, and weekly and monthly training card prompts now exist as well. Metadata / Settings also became more stable, including suggested values, provenance, shoe status management, and tagging flow improvements. In that sense, the value of v1.3.4 is not declaring a new product direction, but helping `Connected Coach Knowledge` move from “connected in principle” to “usable every day.”

## Highlights

- Activity reasoning now reads workout structure more directly
- Daily training card prompt is more complete and safer to hand off to image AI
- Weekly and Monthly training card prompts are now available
- GPS backfill is available for SQLite and Excel
- Workout-structure backfill is available for SQLite and Excel
- Activity metadata flow is more stable, including provenance and suggestion behavior
- Dashboard interaction is more resilient during reloads, attachment actions, and interrupted local requests

## Notes

- `v1.3.4` remains part of the `Connected Coach Knowledge` line
- This release improves the daily-use quality of v1.3 rather than redefining the roadmap
- `Memory` / `Belief` is still intentionally outside the scope of this release

## Release Readiness

This release is ready when the runner can use Activity, Weekly, Monthly, AI handoff, and backfill flows as one coherent local workflow without feeling that the product direction is still only half-connected.
