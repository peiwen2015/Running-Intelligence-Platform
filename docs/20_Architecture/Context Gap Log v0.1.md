# Context Gap Log v0.1

## Purpose

This log records where Narrative Engine v0.1 shadow outputs diverge from current coach-facing interpretations because of missing context.

It is not a rule-tuning document.

It is a context-discovery document for Narrative Engine v0.2.

## Why This Exists

Narrative Engine v0.1 has already proven two things:

1. It can produce stable, structured coach understanding from existing signals.
2. Its main disagreements are usually not data errors, but missing context about why a pattern is reasonable for this runner at this moment.

The goal of this log is to prevent us from hiding context problems behind more `if/else` rules.

## Context Categories

| Category | Meaning |
|---|---|
| Existing | Context already exists somewhere in the platform and is not yet injected into the engine |
| Derivable | Context can likely be derived from governed facts or Semantic Layer outputs |
| Manual / future | Context should come from human annotation, training plan, or future health/training models |

## Priority Guide

| Priority | Meaning |
|---|---|
| P0 | Repeatedly affects high-visibility monthly or journey interpretation |
| P1 | Repeatedly affects weekly interpretation or surface tone |
| P2 | Useful, but can wait until after the first context-injection pass |

## Gap Entries

| Gap ID | Surface | Period | Current Interpretation | Engine Interpretation | Matched Rule | Input Signals | Observed Conflict | Missing Context | Expected Effect | Context Source | Availability | Priority | Resolution Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CG-001 | Monthly | 2026-06 | 吸收月 | 這個月值得留意 | NE-MON-RISK-002 | `load_vs_3m_reference_pct=-15.4`; `distance_vs_3m_reference_pct=-17.1` | Engine reads decline as risk, but current coaching read treats it as deliberate absorption | `previous_month_theme=load_build`; planned absorption phase; long-run continuity maintained | Reclassify from decline risk to intentional recovery | Previous narrative object; semantic long-run continuity; future plan phase | Existing + manual / future | P0 | Open | Canonical mismatch example for context injection |
| CG-002 | Journey | 2026-07 | 平衡建構中 | 吸收調整 | NE-JNY-REC-001 | `monthly_load_trend=-74.8`; `long_run_continuity=True` | Partial month is being compared like a full month, pulling the chapter toward recovery | `month_completeness`; previous chapter; quality sessions already returning | Reclassify from recovery chapter to quality reintroduction or stable build | Month completeness; previous narrative object; semantic quality continuity | Existing + derivable | P0 | Open | Strong evidence that period completeness is core engine context |
| CG-003 | Weekly | 2026-07-04 → 2026-07-10 | 節奏穩住了 | 刺激慢慢回來了 | NE-WK-QLT-001 | `previous_week_load=303.0`; `key_session_present=True` | Engine overweights quality return; current weekly read keeps stable rhythm as the main takeaway | Stable load band; quality share of weekly load; week structure remained controlled | Make quality reintroduction secondary while keeping stable build as primary verdict | Weekly load band; quality-share metric; semantic week structure | Derivable | P1 | Open | Suggests future support for primary vs secondary understanding |
| CG-004 | Weekly | 2026-06-27 → 2026-07-03 | 吸收週 | 節奏穩住了 | NE-WK-STB-001 | `load_vs_4w_avg_pct=-72.5`; `distance_vs_4w_avg_pct=-74.7` | Engine interprets the week as stable because both signals move together, but coaching read sees a down week | Period completeness; intentional down-week marker; recent block position | Reclassify toward recovery / absorption instead of stable rhythm | Week completeness; training block position; future manual plan | Existing + manual / future | P1 | Open | Another case where raw deltas alone are not enough |
| CG-005 | Weekly | 2026-06-20 → 2026-06-26 | 節奏穩住了 | 吸收週 | NE-WK-REC-001 | `load_vs_4w_avg_pct=-11.4`; `long_run_present=True` | Engine reads softer load as absorption; current page emphasizes rhythm continuity | Load remained inside acceptable stable band; absorption did not dominate whole week | Rebalance toward stable build as primary, with recovery as secondary nuance | Weekly stable-band logic; week structure; quality / long-run share | Derivable | P1 | Open | Same family as CG-003 |
| CG-006 | Weekly | 2026-06-13 → 2026-06-19 | 刺激偏高 | 刺激慢慢回來了 | NE-WK-QLT-001 | `previous_week_load=1037.0`; `key_session_present=True` | Engine treats the week as reintroduction, but current read sees elevated stimulus | Absolute load level; concentration of hard sessions; intensity share | Reclassify toward high-stimulus / controlled build instead of simple return | Semantic load concentration; quality-share metric | Derivable | P1 | Open | Points to missing overload-vs-return distinction |
| CG-007 | Weekly | 2026-06-06 → 2026-06-12 | 先穩住節奏 | 節奏穩住了 | NE-WK-STB-001 | `load_vs_4w_avg_pct=-16.1`; `distance_vs_4w_avg_pct=-1.5` | Same family, but current coaching tone is more cautionary than engine output | Recent instability before this week; recommendation continuity | Preserve stable verdict but carry over cautious pacing from prior week | Previous recommendation; recent weekly sequence | Existing + derivable | P2 | Open | Likely a tone / adapter issue more than a core rule issue |
| CG-008 | Monthly | 2026-07 | 正常 | 這個月在把刺激帶回來 | NE-MON-QLT-001 | `previous_month_theme=absorb`; `key_session_count=2` | Engine is directionally plausible, but current page stays broader because the month is still partial | `month_completeness`; current month is partial; total monthly rhythm still controlled | Downgrade verdict strength or combine stable + reintroduction | Month completeness; stable monthly load band | Existing + derivable | P0 | Open | Partial-period context again |
| CG-009 | Monthly | 2026-05 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | `load_vs_3m_reference_pct=42.3`; `key_session_count=0` | Engine confuses deliberate build with risk | Training phase = build; continuity remained intact; no overload symptoms | Reclassify from risk to controlled build | Training phase; multi-period direction; future health signals | Derivable + manual / future | P0 | Open | Build vs overload boundary is still too mechanical |
| CG-010 | Monthly | 2026-04 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | `load_vs_3m_reference_pct=36.1`; `key_session_count=0` | Same conflict as 2026-05 | Training phase = build; previous month / next month sequence | Reclassify to controlled build | Multi-period sequence; planned phase | Derivable + manual / future | P0 | Open | Repeated mismatch, so high leverage |
| CG-011 | Monthly | 2026-03 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | `load_vs_3m_reference_pct=80.3`; `key_session_count=0` | Engine sees high delta and jumps to risk, but current read sees intentional load build | Baseline immaturity; early build context; lack of overload evidence | Reclassify toward load build with medium confidence | Baseline maturity; training phase; health data in future | Derivable + manual / future | P0 | Open | Suggests confidence should drop when early baseline is thin |
| CG-012 | Monthly | 2026-02 | 平衡建構 | 方向是對的 | NE-MON-STB-001 | `load_vs_3m_reference_pct=-1.2`; `distance_vs_3m_reference_pct=-13.7` | Verdict is close, but chapter naming / coaching meaning differs | Current chapter identity; foundation-to-build narrative context | Shift from generic stable to balanced build | Previous / current chapter narrative context | Existing | P2 | Open | Mostly a semantic naming refinement |
| CG-013 | Journey | 2026-06 | 吸收調整 | 需要重新找回節奏 | NE-JNY-RISK-001 | `monthly_load_trend=-15.4`; `monthly_distance_trend=-17.1` | Engine interprets a softer month as lost rhythm, not planned absorption | Previous build chapter; long-run continuity; recommendation continuity | Reclassify from rhythm risk to absorption chapter | Previous chapter; semantic long-run continuity; previous recommendation | Existing + derivable | P0 | Open | Same root cause as CG-001, but on journey surface |
| CG-014 | Journey | 2026-05 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | `current_chapter=load_build`; `turning_points=0` | Engine under-describes build chapters because chapter identity is flattened into “stable” | Build intensity relative to prior chapters; chapter acceleration | Reclassify from stable accumulation to load build | Multi-period direction; chapter trend slope | Derivable | P1 | Open | Suggests chapter adapter needs richer chapter-context input |
| CG-015 | Journey | 2026-04 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | `current_chapter=load_build`; `turning_points=0` | Same conflict as 2026-05 | Build sequence continuity | Preserve build chapter identity | Multi-period direction | Derivable | P1 | Open | Repeated chapter compression |
| CG-016 | Journey | 2026-03 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | `current_chapter=load_build`; `turning_points=2` | Turning points exist, but engine still collapses story into “stable accumulation” | Early build milestone significance; chapter transition from foundation | Reclassify to load build with milestone-aware chapter language | Turning-point weighting; chapter transition context | Derivable | P1 | Open | Turning points need to affect interpretation, not just evidence |
| CG-017 | Journey | 2026-02 | 基礎建立 | 穩定累積 | NE-JNY-STB-001 | `current_chapter=foundation`; `turning_points=0` | Engine loses the distinction between foundation and generic stability | Early-stage chapter identity; runner phase | Reclassify to foundation chapter | Current training phase; chapter ontology | Existing + derivable | P1 | Open | Chapter ontology likely belongs in context injection, not voice |

## Consolidated Context Backlog

### Highest-value context types

| Context Type | Why It Matters | Affected Gaps | Source | Availability | Suggested v0.2 Priority |
|---|---|---|---|---|---|
| `period_completeness` | Partial weeks and months should not be interpreted like closed periods | CG-002, CG-004, CG-008 | Semantic / period metadata | Existing | 1 |
| `previous_theme` | Lets the engine read build → absorb → reintroduce as a sequence instead of isolated facts | CG-001, CG-002, CG-008, CG-013 | Previous narrative object | Existing | 2 |
| `previous_recommendation` | Preserves coaching continuity and explains cautionary reads that the raw signals miss | CG-007, CG-013 | Previous narrative object | Existing | 3 |
| `long_run_continuity` | Distinguishes “load down but endurance alive” from true decline | CG-001, CG-013 | Semantic Layer | Existing / derivable | 4 |
| `quality_session_return` | Helps separate stable build from controlled reintroduction of intensity | CG-002, CG-003, CG-006, CG-008 | Semantic Layer | Existing / derivable | 5 |
| `multi_period_direction` | Needed to tell build from overload and decline from absorption | CG-009, CG-010, CG-011, CG-014, CG-015 | Derived chapter / monthly sequence | Derivable | 6 |
| `current_training_phase` | Needed when build, absorption, or race-specific intent is not inferable from raw deltas alone | CG-001, CG-009, CG-010, CG-011, CG-017 | Manual plan / future model | Manual / future | 7 |
| `week_structure` / `quality_share` | Needed to tell whether a quality session dominated the week or just returned inside a stable rhythm | CG-003, CG-005, CG-006 | Derived weekly structure metrics | Derivable | 8 |
| `turning_point_weight` | Needed so Journey chapters remember growth, not just stable load | CG-016 | Journey semantic metrics | Derivable | 9 |
| `baseline_maturity` | Needed when early periods should carry lower confidence instead of strong risk labels | CG-011 | Derived from period count / reference depth | Derivable | 10 |

## Recommended v0.2 Injection Scope

The first context-injection pass should stay small.

Recommended first batch:

1. `period_completeness`
2. `previous_theme`
3. `previous_recommendation`
4. `long_run_continuity`
5. `quality_session_return`
6. `multi_period_direction`

These six context types should resolve most of the highest-visibility mismatches without expanding the frozen Narrative Object schema.

## What Not To Do Yet

- Do not tune thresholds first.
- Do not add more surface-specific copy rules first.
- Do not expand the Narrative Object schema before proving repeated need.
- Do not pretend FIT-only data can supply planned absorption, race phase, injury, or travel context.

## Next Step

Narrative Engine v0.2 should start with **context injection**, not rule proliferation.

The immediate workflow should be:

1. Keep logging shadow mismatches here.
2. Group them by missing context family.
3. Inject the smallest high-value context set.
4. Re-run shadow mode.
5. Tune thresholds only after context gaps shrink.
