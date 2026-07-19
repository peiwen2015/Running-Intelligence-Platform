# Workout Sequence Gold Cases v0.1

## Purpose

This document is the calibration set for Workout Sequence Reference Intelligence.

It should be used before the first broader twenty-case batch.

These are not coverage cases.

They are gold cases.

Their purpose is to test whether the current WSI workflow, contract, and worldview are stable enough to survive repeated real use.

## Working Rule

These five cases should be run before broader sequence batching.

Any meaningful refinement to WSI should first be checked against this calibration set.

After Sprint 0, these five cases should also be treated as the regression suite for Workout Sequence Intelligence.

No scoring without reasoning.

Every score must include a short explanation of why.

Every five new Batch 20 cases should trigger a rerun of G01–G05.

## Gold Cases

### G01 — Tempo -> Rest -> Easy

**Validation Focus**

Activate vs Absorb boundary.

**Case Record**

- Date / Sequence Window: 2026-07-15 -> 2026-07-16 -> 2026-07-17
- Previous Workout: 2026-07-15 Tempo Run / Threshold / 10.009 km / Training Load 242 / RPE 4 - 有點難
- Current Workout: 2026-07-17 Easy Run / Aerobic Base / 8.01 km / Training Load 135 / RPE 2 - 輕鬆
- Next Workout: Not yet observed
- Activity-only Reading: 這是一堂輕鬆跑。它把前一堂節奏課之後的強度拉回來，留下的是溫和的有氧刺激，而不是新的品質負荷。
- WSI Reading:
  - Mission Category: Activate
  - Mission Phrase: Reconnect aerobic rhythm
  - Mission Status: Completed
  - Continuity State: Maintained
  - Sequence Reasoning: 這堂課的任務不是延續前一堂 Threshold 的刺激，也不是單純吸收前一堂課而已。Tempo 後先休一天，再用一堂真正輕鬆的 Easy Run 把有氧節奏接回來，代表今天更像是重新啟動訓練節奏。由於下一堂課尚未觀測到，這裡不宜過度宣告 `Ready`，目前較保守也較可信的判讀是：這堂課已完成 Activate 任務，並把 continuity 維持在穩定狀態。
- Correctness Score: 2
  - Why: 前一堂是明確的 Threshold / Tempo，當中有完整休息日，當前課又是單一步驟的 8K Easy Run，負荷明顯回落，最符合 `Activate` 而不是 `Absorb`。`Absorb` 更像 Tempo 之後的 Rest 本身；7/17 這堂則是在吸收之後把跑步節奏重新接回來。
- Helpfulness Score: 2
  - Why: Activity-only 只能說「這是一堂輕鬆跑，刺激不高」。WSI 則多回答了「它為什麼排在這裡」與「它在前一堂節奏課之後完成了什麼任務」，這比單看 Activity 更像教練，也更能幫助 Runner 理解今天的存在目的。
- Reviewer Confidence: Medium
  - Why: `Mission Category = Activate` 的把握很高，但 `Continuity State` 仍受限於 next workout 尚未發生。沒有後續課，就不適合把結論拉到 `Ready`；因此整體信心應是 Medium，而不是 High。
- Learning Notes: 這個案例顯示 `Activate` 與 `Absorb` 的邊界目前是可用的，真正的限制不在 ontology，而在 forward context。當 next workout 尚未觀測到時，WSI 需要一條更保守的 continuity 判讀規則，避免把 `Maintained` 說成 `Ready`。
- Refinement Decision: refine reasoning rule

### G02 — Easy -> LSD

**Validation Focus**

Whether Prepare actually increases understanding.

**Case Record**

- Date / Sequence Window: 2026-04-30 -> 2026-05-01 -> 2026-05-02 -> 2026-05-03
- Previous Workout: 2026-04-30 Recovery Run / Recovery / 5.007 km / Training Load 61 / RPE 2 - 輕鬆
- Current Workout: 2026-05-01 Easy Run / Aerobic Base / 8.01 km / Training Load 187 / RPE 3 - 中等
- Next Workout: 2026-05-02 LSD / Endurance / 16.008 km / Training Load 299 / RPE 4 - 有點難
- Activity-only Reading: 這是一堂中等負荷的有氧跑。它本身完成了穩定的有氧刺激，但如果只看 Activity，會比較像一堂獨立的 Z2 跑，而不會明確說出它和隔天 LSD 的關係。
- WSI Reading:
  - Mission Category: Prepare
  - Mission Phrase: Prepare for long run
  - Mission Status: Completed
  - Continuity State: Ready
  - Sequence Reasoning: 這堂課不是單純再做一次有氧刺激，而是在前一堂 Recovery 之後，把身體帶回穩定的有氧節奏，並且沒有把負荷推到會干擾隔天 LSD 的程度。因為隔天的 16K LSD 已經實際完成，這讓今天這堂 Easy Run 的 sequence mission 可以被讀成一堂真正的 preparation day，而不是泛泛的 easy mileage。
- Correctness Score: 2
  - Why: 這個序列有完整 forward context。5/01 是單一步驟 8K Easy，隔天是明確的 16K LSD，之後 5/03 又回到 Recovery。這使得 `Prepare for long run` 比單純的 `Maintain aerobic continuity` 更準，也比 `Activate` 更有明確指向。
- Helpfulness Score: 2
  - Why: Activity-only 只能說這堂 8K Easy 跑本身穩定、負荷中等；WSI 則能把它重新解釋為「隔天 LSD 的準備日」。這讓 Runner 更容易理解今天的功能不是再練一次，而是為下一堂關鍵課鋪路，因此明顯更有幫助。
- Reviewer Confidence: High
  - Why: 這個案例的前後脈絡完整，而且 next workout 已經發生並成功完成。WSI 不需要做超出證據的推測，`Prepare -> Ready` 的判讀有足夠 sequence evidence 支撐。
- Learning Notes: 這個案例支持 `Prepare` 作為獨立 mission 類別存在，而且它帶來的理解增量是真實的，不只是重新命名 easy run。相較 G01，這個案例也顯示當 forward context 完整時，WSI 可以合理地從 `Maintained` 提升到 `Ready`，而不會構成過度宣告。
- Refinement Decision: keep as is

### G03 — LSD -> Recovery

**Validation Focus**

Whether Recover is more valuable than activity-only analysis.

**Case Record**

- Date / Sequence Window: 2026-04-11 -> 2026-04-12 -> 2026-04-13
- Previous Workout: 2026-04-11 LSD / Endurance / 16.009 km / Training Load 235 / RPE 3 - 中等
- Current Workout: 2026-04-12 Recovery Run / Recovery / 6.007 km / Training Load 107 / RPE 3 - 中等
- Next Workout: 2026-04-13 Recovery Run / Recovery / 5.01 km / Training Load 114 / RPE 3 - 中等
- Activity-only Reading: 這是一堂恢復跑。它把前一天長距離之後的強度降下來，負荷不高，目的是讓身體回到比較輕鬆的狀態。
- WSI Reading:
  - Mission Category: Recover
  - Mission Phrase: Recover from accumulated fatigue
  - Mission Status: Completed
  - Continuity State: Maintained
  - Sequence Reasoning: 這堂課的任務不是建立能力，也不是替下一堂關鍵課做準備，而是先把 LSD 帶來的疲勞壓力往下拉，保住整個 sequence 的可持續性。由於隔天仍然安排了另一堂 Recovery Run，這代表 4/12 雖然完成了 recovery mission，但還不足以讓 sequence 直接進入 `Ready`；更可信的判讀是：今天成功完成了 `Recover`，並把 continuity 維持在可繼續吸收的狀態。
- Correctness Score: 2
  - Why: 這個序列非常乾淨。前一天是明確的 LSD，當前與隔天都標成 Recovery Run，負荷也維持在低到中低區間。`Recover` 比 `Maintain` 或 `Prepare` 更符合當前課的 sequence function，而且 `Maintained` 比 `Ready` 更符合後續證據。
- Helpfulness Score: 2
  - Why: Activity-only 已經能說出「這是一堂恢復跑」，但 WSI 多提供了一個更重要的理解：今天的價值不只是在降低負荷，而是在回答「為什麼一堂 Recovery 之後，隔天還是 Recovery」。這使 Runner 比較能理解 recovery 並不是單日事件，而是 sequence 中的吸收過程。
- Reviewer Confidence: High
  - Why: 這個案例的前後證據完整，而且後續課已經發生。WSI 不需要做超出證據的推測；相反地，後續仍是 Recovery 反而強化了 `Continuity State = Maintained` 的判讀。
- Learning Notes: Case learning: 這個案例顯示 `Recover` 不只是對 workout label 的重述，而是能把單日恢復重新解釋成 sequence-level absorption process。 Rule learning: 這個案例支持目前已浮現的第二條規則，亦即 forward context 不決定 mission，但會校準 continuity 可以宣告到什麼程度。即使當前 workout label 與 mission category 一致，WSI 仍然需要依靠後續證據決定 `Maintained` 而不是 `Ready`。 Epistemic learning: 這個案例再次支持目前世界觀的克制性，因為 WSI 沒有因為「Recovery 完成」就過度宣告 sequence 已完全恢復。
- Refinement Decision: keep as is

### G04 — Rest -> Easy + Strides -> Threshold

**Validation Focus**

Whether Activate and Prepare can coexist coherently.

**Case Record**

- Date / Sequence Window: 2026-07-13 -> 2026-07-14 -> 2026-07-15
- Previous Workout: 2026-07-13 Recovery Run / Recovery / 7.009 km / Training Load 96 / RPE 3 - 中等
- Current Workout: 2026-07-14 Easy Run + Strides / Aerobic Base / 9.033 km / Training Load 206 / RPE 3 - 中等
- Next Workout: 2026-07-15 Tempo Run / Threshold / 10.009 km / Training Load 242 / RPE 4 - 有點難
- Activity-only Reading: 這是一堂帶 strides 的輕鬆跑。它本身既保留了有氧主體，也加入短促加速來喚醒節奏，因此可以被讀成一堂把身體重新打開的課。
- WSI Reading:
  - Mission Category: Prepare
  - Mission Phrase: Prepare for threshold by reopening leg turnover
  - Mission Status: Completed
  - Continuity State: Ready
  - Sequence Reasoning: 這堂課同時帶有 `Activate` 的味道，但它在這個 sequence 裡的主要功能不是單純把節奏接回來，而是為隔天的 Threshold 做準備。前一天已經是 Recovery Run，代表重新進入訓練節奏這件事早已開始；7/14 這堂 `Easy + Strides` 更像是在不過度消耗的前提下，把神經與步頻感喚醒，讓隔天 Tempo 能夠順利成立。因此最穩定的單一 mission 不是把它拆成雙 mission，而是以 `Prepare` 為主，並在 mission phrase 裡保留 activation mechanism。
- Correctness Score: 2
  - Why: 這個案例確實存在 `Activate` 與 `Prepare` 的邊界壓力，但前後脈絡讓 `Prepare` 更像主要 mission。若只有前一堂 Rest，`Activate` 會更有競爭力；但這裡前一天已是 Recovery，隔天又是明確的 Threshold，表示 7/14 的 sequence function 更偏向「替下一堂關鍵課鋪路」。
- Helpfulness Score: 2
  - Why: Activity-only 能說這是一堂 Easy + Strides，會喚醒節奏；WSI 則進一步回答「它為什麼喚醒節奏」以及「它是為哪一堂課服務」。這個回答比單純描述 strides 的存在更有教練感，也更能讓 Runner 理解今天不是主角，而是為明天的 Threshold 做準備。
- Reviewer Confidence: Medium
  - Why: 這是一個邊界案例。`Prepare` 是目前更強的解釋，但 `Activate` 並非錯誤讀法，因此信心不應拉到 High。這裡的 Medium 並不是因為證據不足，而是因為存在另一個仍可理解的相鄰 mission。
- Learning Notes: Case learning: 單一 mission 目前仍可承載這類邊界案例，不需要立刻引入雙 mission。 Rule learning: 這個案例支持目前第一條規則，亦即 mission 由 sequence function 決定，而不是由 workout label 或課中元素決定；同時它也支持一個新細化：當一堂課同時帶有兩種感受時，主要 mission 可由 sequence role 決定，次要功能可留在 mission phrase。 Epistemic learning: 這個案例顯示 WSI 可以承認相鄰 mission 的張力，但仍維持單一主 mission，而不是用 ontology expansion 來逃避判斷。
- Refinement Decision: keep as is

### G05 — Easy Run Overcooked -> LSD

**Validation Focus**

Whether Continuity State has real judgment value.

**Case Record**

- Date / Sequence Window: 2026-05-21 -> 2026-05-22 -> 2026-05-23 -> 2026-05-24
- Previous Workout: 2026-05-21 Recovery Run / Recovery / 5.01 km / Training Load 98 / RPE 3 - 中等
- Current Workout: 2026-05-22 Easy Run / Aerobic Base / 10.01 km / Training Load 247 / RPE 4 - 有點難
- Next Workout: 2026-05-23 LSD / Endurance / 18.009 km / Training Load 289 / RPE 5 - 困難
- Activity-only Reading: 這是一堂有氧跑，但負荷偏重、主觀感受也不算輕鬆。如果只看 Activity，它比較像一堂做得有點多的 aerobic steady，而不是典型的前一天調整課。
- WSI Reading:
  - Mission Category: Prepare
  - Mission Phrase: Prepare for long run without consuming too much freshness
  - Mission Status: Partial
  - Continuity State: Overloaded
  - Sequence Reasoning: 這堂課在 sequence 裡原本仍然是為隔天 LSD 做準備，因此 primary mission 依然是 `Prepare`，而不是另立新的 mission 類別。但它的執行強度明顯偏重：10K、Training Load 247、RPE 4，都比一堂理想的 pre-LSD easy day 更接近一堂獨立訓練日。這表示它沒有完全達成「為長距離保留新鮮度」的 preparation effect。隔天 LSD 雖然仍然完成，但 sequence 已經不是單純 `Ready`，而是帶著過多前置消耗進入下一堂課，因此 continuity 更適合被判成 `Overloaded`。
- Correctness Score: 2
  - Why: 這個案例最合理的 reading 不是改 mission，而是保留 `Prepare`，同時承認 execution quality 沒有完整支持該 mission。這剛好測到 `Mission Category` 與 `Mission Status` 的分離，也測到 `Mission Completion != Sequence Completion`。把它讀成新的 mission 類別，反而會把執行問題誤當成 ontology 問題。
- Helpfulness Score: 2
  - Why: Activity-only 只能說「這堂 Easy 跑太重」。WSI 則能進一步說出「它原本應該完成什麼任務」、「它為什麼只完成一部分」，以及「這對隔天 LSD 的 sequence state 造成了什麼影響」。這對 Runner 的幫助明顯更大，因為它把過重這件事從單日表現轉成了 sequence judgment。
- Reviewer Confidence: Medium
  - Why: `Prepare` 作為 primary mission 幾乎沒有疑問，但 `Continuity State` 在 `Delayed` 與 `Overloaded` 之間存在相鄰選項。這裡選 `Overloaded` 是因為問題更像前置消耗過多，而不是下一堂被延後；但這仍然屬於邊界判斷，因此信心應維持 Medium。
- Learning Notes: Case learning: 這是第一個明確顯示「sequence role 沒變，但 execution 沒有達成該角色效果」的案例。 Rule learning: 這個案例支持一條新的推理規則，亦即當 sequence role 不變時，mission category 可以保持穩定，而 mission status 與 continuity state 則負責吸收 execution quality 的差異。 Epistemic learning: 這個案例顯示 WSI 不需要用新增 ontology 來處理失敗的準備日；它可以透過 `Partial` 與 `Overloaded` 來表達 sequence-level judgment。
- Refinement Decision: keep as is

## Status

`Workout Sequence Gold Cases v0.1`

- Status: Active
- Scope: Sprint 0 calibration set for Workout Sequence Intelligence Training
- Classification: Architecture / Training Calibration Document
