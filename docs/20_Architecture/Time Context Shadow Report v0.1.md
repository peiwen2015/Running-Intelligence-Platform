# Narrative Engine Shadow Report v0.1

Shadow mode comparison only. Current dashboard-visible narratives remain unchanged.

## Weekly | Latest 8 Weeks

| Period | Current Verdict | Engine Verdict | Rule | Confidence | Evidence | Match | Human Review |
|---|---|---|---|---|---|---|---|
| 2026-07-05 → 2026-07-11 | 吸收週 | 節奏開始鬆了 | NE-WK-RISK-002 | MEDIUM (0.77) | load_vs_4w_avg_pct=-18.9 (Load is below baseline for more than one week.); distance_vs_4w_avg_pct=-6.7 (Distance is also below recent rhythm.) | NO | TODO |
| 2026-06-28 → 2026-07-04 | 吸收週 | 節奏開始鬆了 | NE-WK-RISK-002 | MEDIUM (0.77) | load_vs_4w_avg_pct=-45.2 (Load is below baseline for more than one week.); distance_vs_4w_avg_pct=-40.3 (Distance is also below recent rhythm.) | NO | TODO |
| 2026-06-21 → 2026-06-27 | 吸收週 | 吸收週 | NE-WK-REC-001 | HIGH (0.92) | load_vs_4w_avg_pct=-44.9 (Load is below recent baseline.); long_run_present=False (Long-run or continuity signal stayed alive.) | YES | TODO |
| 2026-06-14 → 2026-06-20 | 刺激偏高 | 刺激慢慢回來了 | NE-WK-QLT-001 | MEDIUM (0.77) | previous_week_load=993.0 (The previous week was lighter.); key_session_present=True (Quality stimulus returned this week.) | NO | TODO |
| 2026-06-07 → 2026-06-13 | 先穩住節奏 | 節奏穩住了 | NE-WK-STB-001 | HIGH (0.92) | load_vs_4w_avg_pct=-19.7 (Load is close to recent baseline.); distance_vs_4w_avg_pct=-4.8 (Distance is also staying near baseline.) | NO | TODO |
| 2026-05-31 → 2026-06-06 | 節奏穩住了 | 節奏穩住了 | NE-WK-STB-001 | HIGH (0.92) | load_vs_4w_avg_pct=-3.3 (Load is close to recent baseline.); distance_vs_4w_avg_pct=7.3 (Distance is also staying near baseline.) | YES | TODO |
| 2026-05-24 → 2026-05-30 | 節奏穩住了 | 節奏穩住了 | NE-WK-STB-001 | HIGH (0.92) | load_vs_4w_avg_pct=6.5 (Load is close to recent baseline.); distance_vs_4w_avg_pct=-3.0 (Distance is also staying near baseline.) | YES | TODO |
| 2026-05-17 → 2026-05-23 | 節奏穩住了 | 節奏穩住了 | NE-WK-STB-001 | HIGH (0.92) | load_vs_4w_avg_pct=13.1 (Load is close to recent baseline.); distance_vs_4w_avg_pct=0.8 (Distance is also staying near baseline.) | YES | TODO |

## Monthly | Latest 6 Months

| Period | Current Verdict | Engine Verdict | Rule | Confidence | Evidence | Match | Why Changed | Human Review |
|---|---|---|---|---|---|---|---|---|
| 2026-07 | 正常 | 正常 | NE-MON-STB-CTX-001 | HIGH (0.92) | month_completeness_pct=35.5 (This month is still being written and should not be read like a closed month.); previous_month_theme=absorb (The previous month was recovery-oriented, so this month is best read as transition rather than conclusion.) | YES | previous_theme, period_completeness | TODO |
| 2026-06 | 吸收月 | 吸收月 | NE-MON-REC-001 | HIGH (0.92) | load_vs_3m_reference_pct=-15.4 (Load is lower than recent baseline.); long_run_count=3 (Endurance continuity stayed in place.) | YES | previous_theme | TODO |
| 2026-05 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | MEDIUM (0.77) | load_vs_3m_reference_pct=42.3 (Monthly load is well above recent baseline.); key_session_count=0 (Quality sessions increased around the same period.) | NO | — | TODO |
| 2026-04 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | MEDIUM (0.77) | load_vs_3m_reference_pct=36.1 (Monthly load is well above recent baseline.); key_session_count=0 (Quality sessions increased around the same period.) | NO | — | TODO |
| 2026-03 | 負荷建構 | 這個月壓力偏高 | NE-MON-RISK-001 | MEDIUM (0.77) | load_vs_3m_reference_pct=80.3 (Monthly load is well above recent baseline.); key_session_count=0 (Quality sessions increased around the same period.) | NO | — | TODO |
| 2026-02 | 平衡建構 | 正常 | NE-MON-STB-001 | HIGH (0.92) | load_vs_3m_reference_pct=-1.2 (Load is within a stable band.); distance_vs_3m_reference_pct=-13.7 (Distance stayed near recent baseline.) | NO | — | TODO |

## Monthly Time Context Trace

| Period | Without Time Context | + previous_theme | + period_completeness | Changed By |
|---|---|---|---|---|
| 2026-07 | 這個月值得留意 | 這個月在把刺激帶回來 | 正常 | previous_theme, period_completeness |
| 2026-06 | 這個月值得留意 | 吸收月 | 吸收月 | previous_theme |
| 2026-05 | 這個月壓力偏高 | 這個月壓力偏高 | 這個月壓力偏高 | — |
| 2026-04 | 這個月壓力偏高 | 這個月壓力偏高 | 這個月壓力偏高 | — |
| 2026-03 | 這個月壓力偏高 | 這個月壓力偏高 | 這個月壓力偏高 | — |
| 2026-02 | 正常 | 正常 | 正常 | — |

## Monthly Gap Closure

- Monthly matches after Time First injection: 2 / 6
- Monthly mismatches after Time First injection: 4

## Journey | Latest 6 Months

| Chapter | Current Theme | Engine Theme | Rule | Confidence | Evidence | Match | Human Review |
|---|---|---|---|---|---|---|---|
| 2026-07 | 平衡建構中 | 吸收調整 | NE-JNY-REC-001 | HIGH (0.92) | monthly_load_trend=-72.3 (Chapter load softened relative to recent history.); long_run_continuity=True (Endurance continuity still stayed alive.) | NO | TODO |
| 2026-06 | 吸收調整 | 需要重新找回節奏 | NE-JNY-RISK-001 | MEDIUM (0.77) | monthly_load_trend=-15.4 (Load trend is down across chapters.); monthly_distance_trend=-17.1 (Distance trend also moved down.) | NO | TODO |
| 2026-05 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | MEDIUM (0.77) | current_chapter=load_build (The chapter is holding its current direction.); turning_points=0 (Milestones are accumulating without breaking rhythm.) | NO | TODO |
| 2026-04 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | MEDIUM (0.77) | current_chapter=load_build (The chapter is holding its current direction.); turning_points=0 (Milestones are accumulating without breaking rhythm.) | NO | TODO |
| 2026-03 | 負荷建構 | 穩定累積 | NE-JNY-STB-001 | MEDIUM (0.77) | current_chapter=load_build (The chapter is holding its current direction.); turning_points=2 (Milestones are accumulating without breaking rhythm.) | NO | TODO |
| 2026-02 | 基礎建立 | 穩定累積 | NE-JNY-STB-001 | MEDIUM (0.77) | current_chapter=foundation (The chapter is holding its current direction.); turning_points=0 (Milestones are accumulating without breaking rhythm.) | NO | TODO |

## Notes

- Weekly and Monthly compare current page-facing verdicts against Narrative Engine v0.1 shadow outputs.
- Journey compares current story chapter naming against engine-derived chapter understanding.
- This report is for rule tuning only and does not change dashboard-visible copy.

