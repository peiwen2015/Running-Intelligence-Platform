# Monthly Coach Briefing v0.1

## Purpose

This is a product implementation draft for Monthly.

It does not introduce a new architecture layer.

It does not define a new methodology.

It only answers three practical product questions:

1. What should Monthly keep on screen?
2. Which charts are necessary evidence?
3. In what order should the user read the page?

## Product Role

Monthly is no longer a dashboard-first monthly summary.

Monthly should become a **Coach Briefing**:

- a short coach judgment
- a small set of visible evidence
- one clear next step

Its job is not to fully narrate the month.

Its job is to help the runner:

- understand the month quickly
- verify the judgment visually
- leave with one next action

## Reading Order

Monthly Coach Briefing should be read in this order:

```text
Coach Verdict
   ↓
Why
   ↓
Key Evidence
   ↓
Next Step
```

This is the working briefing order for the page.

## 1. Coach Verdict

This section should keep only:

- monthly status
- one short judgment
- whether the month is complete or still in progress
- confidence with a short reason

It should not lead with heavy metrics.

### Example

```text
本月：Controlled Build
負荷持續增加，但目前仍維持可吸收、可延續的節奏。

月份狀態：完整
信心：高（基準可用、資料完整、主要訊號一致）
```

### Keep

- top-line verdict
- one-sentence interpretation
- partial/full month state
- confidence and short cause

### Reduce

- decorative rating treatment
- repeated labels that restate the same judgment twice

## 2. Why

This section should answer only:

**Why is this the current coach judgment?**

Keep it to 2 to 4 concise points.

Typical inputs:

- load change
- distance change
- long-run continuity
- quality-session distribution
- whether prior recovery or adjustment was completed

This section does not need to become a long letter paragraph.

Short evidence sentences are enough.

### Example

```text
- 負荷較基準增加 15%，但增幅已較上月收斂
- 長跑連續性維持，沒有因增加刺激而中斷
- 品質課分布穩定，沒有過度集中
- 上一階段恢復已完成，因此本月增加仍可吸收
```

### Keep

- short cause statements
- selected evidence that directly explains the verdict

### Reduce

- abstract explanation that repeats the opening in different words

## 3. Key Evidence

This section should contain only the charts needed to verify the judgment.

Start with three charts only.

Do not begin with four or five.

Each chart must answer exactly one coaching question.

The goal is not to show data for its own sake.

The goal is to let the runner verify the judgment without needing the long explanation first.

### Required Evidence Questions

#### A. What does the recent load pattern mean?

This evidence view should answer:

**Is the current month part of build, recovery, or loss of continuity?**

The first visual should succeed only if the runner can look at it and understand:

- this is not random decline
- this is not loss of rhythm
- this is intentional absorption or controlled change

Each chart should include one short chart conclusion.

Example:

`負荷連續三個月上升，但本月增幅已開始收斂。`

The final visual form may be:

- line chart
- line chart with highlighted current month
- line chart with background phase bands

The deliverable is not "a line chart."

The deliverable is:

**the first evidence visual that can answer this question clearly.**

#### B. Is the load change mainly coming from mileage?

This evidence view should answer:

**Is the current load change mainly coming from mileage?**

Example:

`里程仍在增加，但幅度比負荷更平穩，代表刺激不只是來自多跑。`

#### C. What is this month made of?

This evidence view should answer:

**How was this month built from easy runs, long runs, quality work, and recovery?**

Example:

`本月仍以輕鬆跑為主體，品質刺激已回來，但尚未壓過整體節奏。`

### Optional Supporting Evidence

Do not make this a fourth major chart at first.

If needed, keep it small:

- current month vs baseline position
- confidence support
- one representative session or decision

### Keep

- evidence that helps the runner confirm or challenge the verdict
- one takeaway sentence per chart
- one coaching question per chart

### Reduce

- dense signal-card duplication
- large tables that repeat what a trend chart already shows

### Move Down

- detailed monthly trend tables
- secondary evidence that supports but does not drive understanding

## 4. Next Step

This section should keep only one primary coaching action.

If necessary, add one avoidance note.

Do not turn this into a checklist.

### Example

```text
下一步：先守住目前節奏，不急著再次提高刺激。
避免：不要因為本月感覺順，就提前把負荷再往上推。
```

### Keep

- one main next step
- one optional caution

### Reduce

- multiple simultaneous recommendations
- long future-planning paragraphs

## Current Section Triage

The current Monthly sections should be handled like this:

| Current Section | Recommendation |
|---|---|
| 本月月評 | Keep |
| 教練時間線 | Keep, but simplify |
| 為什麼我這樣看 | Keep |
| 下個月，我希望你 | Keep |
| 本月進度 | Reduce |
| 月份信號 | Reduce or fold into charts |
| 月度趨勢表 | Convert to trend chart or move down |
| 本月代表決策 | Keep only 1 to 3 items |
| 歷史累積 | Remove from Monthly |

## Validation Questions

Do not validate this draft by asking whether it looks polished.

Validate it with five product questions:

1. Without reading long text, can the runner know the monthly state within 30 seconds?
2. After seeing the charts, can the runner verify whether the judgment feels reasonable?
3. Does each chart answer one clear coaching question?
4. After closing the page, does the runner remember the verdict and the next step?
5. Without reading `Why`, would the runner reach the same broad judgment from the evidence alone?

## Coverage to Test Later

This structure should later be tested against different month types:

- build month
- recovery month
- partial month
- interrupted or abnormal month

The goal is not to fit only `2026-07`.

The goal is to confirm that the same briefing structure remains trustworthy across different monthly situations.

## Next Product Step

Do not start Context Pack yet.

First make Monthly stand on its own as a trustworthy coach briefing:

- short judgment
- visible evidence
- one next step

After that is stable, AI continuation can attach to a stronger product surface.

## Sprint Framing

The next sprint should not be framed as:

- build a line chart

It should be framed as:

- design the first evidence visual that answers one coaching question clearly

For the first pass, the most valuable question is:

**Why is this month being read as absorption rather than loss of continuity?**
