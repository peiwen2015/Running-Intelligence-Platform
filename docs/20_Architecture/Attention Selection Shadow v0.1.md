# Attention Selection Shadow v0.1

This is a minimal executable shadow slice for deterministic Overview attention selection.

It does not define an Overview layout.

It only tests whether three domains can independently decide:

1. am I eligible to speak today?
2. if yes, how important am I?

## Purpose

We are not trying to prove an abstract attention engine.

We are only testing one practical question:

**can three domains look at the same day, speak independently, and produce an attention order a human would accept?**

## Domain Contract

| Field | Meaning |
| --- | --- |
| `domain` | Which knowledge domain is speaking |
| `eligible` | Whether the domain should enter today's attention competition |
| `priority` | `critical`, `high`, `medium`, or `null` when not eligible |
| `reason_codes` | Traceable machine-readable reasons |
| `attention_label` | The user-facing attention sentence |
| `target_surface` | Which page the runner should go to next |
| `evidence` | Human-readable evidence for quick verification |

## Selection Rule v0.1

- Only eligible domains enter ranking.
- Priority order: `critical` > `high` > `medium`.
- Tie-break order: `recovery` > `load_build` > `shoes`.
- When no domain is eligible, Overview should say there is no urgent focus today.

## What This Shadow Slice Must Prove

- Irrelevant domains can stay silent.
- Relevant domains can speak without needing help from a global if/elif chain.
- When multiple domains are active, the selection still feels coach-like.
- When nothing deserves attention, the system can say so without manufacturing anxiety.

## Scenario Results

## Scenario 1 | Live current recovery-oriented week

- Expected primary: `recovery`
- Ranked primary: `recovery`
- Shadow result: `pass`
- Human judgment: 會點頭：目前整體更像吸收與恢復，不需要硬找別的焦點。

| Domain | Eligible | Priority | Reason Codes | Attention Label | Target Surface | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `recovery` | `True` | `high` | WEEK_ABSORB<br>WEEK_LOAD_DROP<br>MONTH_LOAD_DROP | 今天最該關心的是恢復 | `weekly` | 本週已進入吸收節奏。<br>本週負荷較基準下降 19%。<br>本月負荷較基準下降 72%。 |
| `load_build` | `False` | `—` | — | — | `—` | — |
| `shoes` | `False` | `—` | — | — | `—` | — |

**Selected attention order**

1. `recovery` — high — 今天最該關心的是恢復

## Scenario 2 | Build progression should speak first

- Expected primary: `load_build`
- Ranked primary: `load_build`
- Shadow result: `pass`
- Human judgment: 會點頭：今天先談建構，比談鞋或恢復更自然。

| Domain | Eligible | Priority | Reason Codes | Attention Label | Target Surface | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `recovery` | `False` | `—` | — | — | `—` | — |
| `load_build` | `True` | `high` | WEEK_LOAD_RISING<br>MONTH_LOAD_RISING<br>WEEK_KM_RISING | 今天最該關心的是建構節奏 | `monthly` | 本週負荷較基準增加 18%。<br>本月負荷較基準增加 16%。<br>本週里程較基準增加 12%。 |
| `shoes` | `False` | `—` | — | — | `—` | — |

**Selected attention order**

1. `load_build` — high — 今天最該關心的是建構節奏

## Scenario 3 | Shoe maintenance should speak first

- Expected primary: `shoes`
- Ranked primary: `shoes`
- Shadow result: `pass`
- Human judgment: 會點頭：當訓練本身平穩時，鞋況成為今天最該先看的事。

| Domain | Eligible | Priority | Reason Codes | Attention Label | Target Surface | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `recovery` | `False` | `—` | — | — | `—` | — |
| `load_build` | `False` | `—` | — | — | `—` | — |
| `shoes` | `True` | `high` | SHOE_NEAR_RETIREMENT | 今天最該關心的是長跑鞋的更換 | `shoes` | 主力鞋已累積 910 km，接近更換區間。 |

**Selected attention order**

1. `shoes` — high — 今天最該關心的是長跑鞋的更換

## Scenario 4 | Multiple domains eligible on the same day

- Expected primary: `recovery`
- Ranked primary: `recovery`
- Shadow result: `pass`
- Human judgment: 可點頭：恢復應先於建構，建構再先於鞋況；第二名仍值得保留。

| Domain | Eligible | Priority | Reason Codes | Attention Label | Target Surface | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `recovery` | `True` | `high` | RECENT_QUALITY_STRESS<br>WEEK_ABSORB | 今天最該關心的是恢復 | `weekly` | 最近已有清楚刺激，恢復壓力正在累積。<br>本週已進入吸收節奏。 |
| `load_build` | `True` | `high` | WEEK_LOAD_RISING<br>MONTH_LOAD_RISING<br>WEEK_KM_RISING | 今天最該關心的是建構節奏 | `monthly` | 本週負荷較基準增加 19%。<br>本月負荷較基準增加 18%。<br>本週里程較基準增加 14%。 |
| `shoes` | `True` | `medium` | SHOE_WATCH_DISTANCE | 今天最該關心的是長跑鞋的更換 | `shoes` | 主力鞋已累積 780 km，值得開始留意。 |

**Selected attention order**

1. `recovery` — high — 今天最該關心的是恢復
2. `load_build` — high — 今天最該關心的是建構節奏
3. `shoes` — medium — 今天最該關心的是長跑鞋的更換

## Scenario 5 | No urgent focus day

- Expected primary: `None`
- Ranked primary: `None`
- Shadow result: `pass`
- Human judgment: 會點頭：今天不需要硬做提醒，照原本節奏走即可。

| Domain | Eligible | Priority | Reason Codes | Attention Label | Target Surface | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `recovery` | `False` | `—` | — | — | `—` | — |
| `load_build` | `False` | `—` | — | — | `—` | — |
| `shoes` | `False` | `—` | — | — | `—` | — |

**Selected attention order**

今天沒有需要特別處理的訊號，照原本節奏走就好。

## Shadow Outcome

- Irrelevant domains can stay silent.
- Recovery can outrank build when both are active.
- A no-urgent-focus day can be expressed without manufacturing anxiety.
- The hardest part is not ranking everything; it is deciding who has earned the right to speak today.

## Current Read

This is enough to say deterministic attention selection is viable in shadow form.

It is **not** enough to justify a full Overview implementation yet.

What it does prove is smaller and more useful:

1. each domain can decide whether it deserves attention today
2. only eligible domains need to enter competition
3. a simple deterministic selection rule can already produce human-readable focus ordering