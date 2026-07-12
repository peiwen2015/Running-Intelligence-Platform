# Canonical Data Model Release Notes

## Purpose

This file tracks version history for Canonical Data Model artifacts.

Each Final LDM should have an explicit version and a short list of changes.

## Current Artifact Versions

| Artifact | Version | Status |
|---|---|---|
| Running Analytics Metadata Repository | v1.1 | Active |
| Metadata Design Standard | v1.0 | Active |
| Activity LDM | v1.1 | Final |
| Kilometer Split LDM | v1.1 | Final |
| Shoe LDM | v1.1 | Final |
| Workout Type LDM | v1.1 | Final |
| Training Purpose LDM | v1.1 | Final |
| Activity Training Purpose LDM | v1.1 | Final |
| Excel Schema | v1.1 | Active |
| SQLite Importer / Parser | Internal milestone E2E-002 | SQLite Schema v1.0 real-data verified |
| SQLite Mapping Specification | v1.0 | Core mapping complete |
| SQLite Schema | v1.0 | Core schema real-data verified |
| Semantic Layer | v1.0 | Journey story and turning-point semantics active |
| Query Layer | v1.0 | Reads Semantic Layer views |
| Dashboard App | v0.4.12-alpha | Weekly Polish reframed the week page as a coaching review meeting with verdict, focus, why, and next |

## Engineering Milestones

### Semantic Layer v1.0

Scope:

- `activity_review_view`
- `platform_summary_view`
- `monthly_summary_view`
- `current_month_summary_view`
- `current_month_intelligence_view`
- `current_month_training_distribution_view`
- `weekly_summary_view`
- `current_week_summary_view`
- `current_week_intelligence_view`
- `training_distribution_view`
- `training_balance_view`
- `training_assignment_quality_view`
- `recent_training_intent_view`
- `shoe_comparison_view`
- `shoe_intelligence_view`
- `shoe_workout_comparison_view`
- `recent_activity_view`
- `journey_month_story_view`
- `journey_turning_point_view`

Changes:

- Established Semantic Layer as the product-facing SQL layer above SQLite Schema v1.0.
- Moved reusable dashboard review logic out of Python and into semantic SQL views.
- Promoted weekly review, training distribution, shoe comparison, and recent activity retrieval into governed semantic artifacts.
- Added monthly review semantics so product surfaces can compare the latest month with a governed rolling baseline instead of rebuilding month logic in Python.
- Added tagged shoe intelligence semantics for product surfaces that need equipment-level insight without guessing missing labels.
- Added training balance, assignment quality, and recent intent semantics for product surfaces that need training-context visibility without embedding raw SQL in Python.
- Added journey story semantics so product surfaces can describe each month as a training chapter instead of a plain calendar bucket.
- Added turning-point semantics so the product can surface milestone months such as first 200 km, first stable quality block, and first fully tagged month.
- Exposed semantic activity context:
  - workout display name
  - shoe display name
  - training purpose context
  - weather / feel context
- Updated Query Layer and Dashboard App to read semantic views instead of rebuilding the same SQL logic repeatedly.

### Internal Milestone E2E-002 - SQLite Schema v1.0 Real-Data Verified

Scope:

- SQLite Importer / Parser
- SQLite Schema v1.0
- `shoe`
- `workout_type`
- `training_purpose`
- `activity`
- `activity_training_purpose`
- `kilometer_split`
- `activity_view`
- `kilometer_split_view`
- `activity_training_purpose_view`
- `shoe_statistics_view`

Verification:

- Imported `210 / 210` FIT files successfully into a clean SQLite v1.0 database.
- Created `210` `activity` records.
- Created `2453` `kilometer_split` records.
- Seeded/upserted `5` `shoe` records.
- Seeded/upserted `12` `workout_type` records.
- Seeded/upserted `12` `training_purpose` records.
- Verified repeated import remains idempotent.
- Verified `activity_view` and `kilometer_split_view` calculate derived pace fields.
- Verified `activity_training_purpose_view` and `shoe_statistics_view` query successfully.
- Verified `PRAGMA foreign_key_check` returns clean.
- Verified real FIT plus supplied metadata can populate `shoe_id`, `workout_type_id`, and `activity_training_purpose` with `PRIMARY` / `SECONDARY` roles.

Notes:

- Raw FIT files do not contain manual shoe, workout intent, or training purpose data. The importer therefore does not fabricate these values during raw FIT-only imports.

### SQLite Mapping Specification v1.0

Scope:

- `shoe`
- `workout_type`
- `training_purpose`
- `activity`
- `activity_training_purpose`
- `kilometer_split`

Changes:

- Expanded physical mapping from the v0.1 two-table scope to all six Core Canonical Data Layer tables.
- Promoted `activity.shoe_id` and `activity.workout_type_id` to explicit foreign keys.
- Added mapping for `activity_training_purpose` with `purpose_role` constrained to `PRIMARY` / `SECONDARY`.
- Added business-key strategy for dimension tables.
- Added core view guidance for `activity_training_purpose_view` and `shoe_statistics_view`.

### SQLite Schema v1.0

Scope:

- `shoe`
- `workout_type`
- `training_purpose`
- `activity`
- `activity_training_purpose`
- `kilometer_split`
- `activity_view`
- `kilometer_split_view`
- `activity_training_purpose_view`
- `shoe_statistics_view`

Verification:

- Generated from `SQLite Mapping Specification v1.0`.
- Syntax verified with SQLite.
- Verified table and view creation on a clean database.
- Verified minimal inserts across dimension, fact, bridge, and split tables.
- Verified derived pace from `activity_view` and `kilometer_split_view`.
- Verified readable training intent from `activity_training_purpose_view`.
- Verified shoe usage aggregation from `shoe_statistics_view`.
- Verified foreign key check is clean on the minimal test database.

### Internal Milestone E2E-001 - First End-to-End Pipeline Verified

Scope:

- FIT
- Parser / Excel Exporter
- Excel v1.1
- SQLite v0.1
- `activity_view`
- `kilometer_split_view`

Verification:

- Imported `126 / 126` FIT files successfully.
- Created `126` `activity` records.
- Created `1540` `kilometer_split` records.
- Verified `fit_sha256` idempotent upsert for repeated imports.
- Verified foreign key integrity with `PRAGMA foreign_key_check`.
- Verified `activity_view` and `kilometer_split_view` can calculate derived pace fields.

Notes:

- Fixed split-distance precision during SQLite import so very short FIT splits, such as `0.01m`, are not rounded to `0.0m` before constraint validation.

### Dashboard App v0.1.0-alpha

Scope:

- Summary cards: activities, total KM, total time, average pace, average HR.
- Week summary.
- Recent activities table with clickable rows.
- Activity detail summary with workout, shoe, training load and stamina.
- Activity detail split table.
- Pace / HR / Power trend using `kilometer_split_view`, with point tooltips and per-series ranges.
- Independent application in `analysis_platform/dashboard_app.py`; the Converter App remains focused on ingestion/import/transform.

Status:

- SQLite -> Query Layer -> Dashboard path verified locally.

### Dashboard App v0.1.0-beta

Scope:

- Added Weekly Intelligence section.
- Compares current 7-day distance, Training Load and Load / KM against the previous four-week average.
- Adds a simple AI Coach summary based on current weekly load.
- Product architecture now positions the Dashboard App as the user-facing data product and the Converter as the ingestion engine.

### Dashboard App v0.4.6-alpha

Scope:

- Refactored Monthly Coaching Review around the product pattern `Verdict -> Reason -> Recommendation -> Evidence`.
- Moved `Coach Summary` ahead of progress details to reduce cognitive load and support 5-second orientation.
- Replaced raw negative month-to-date deltas with more human coaching signals such as `On Track`, `Slightly Behind`, and `Month Completeness`.
- Added confidence explanation and progress reference language so month-to-date judgments are easier to trust.
- Added `current_month_assignment_quality_view` to make tagged-data confidence explicit in product-facing month review.

### Dashboard App v0.4.7-alpha

Scope:

- Added `旅程` as a new coaching surface above Overview / Weekly / Monthly / Shoes / Training.
- Introduced month-by-month journey chapter rendering based on governed semantic journey views.
- Added turning-point cards so major shifts in training progression can be recalled as milestones rather than raw calendar entries.
- Reused monthly coach continuity and key-session semantics so Journey starts with memory, context, and evidence instead of isolated metrics.

### Dashboard App v0.4.12-alpha

Scope:

- Reframed Weekly Review from a compact analytics summary into a more explicit weekly coaching review meeting.
- Added `本週週評`, `這週最重要的一件事`, `為什麼我這樣看`, and `下週，我希望你……`.
- Moved raw weekly metrics to a supporting role so the page leads with judgment and correction before evidence.
- Continued aligning the product with the rule that each page should leave one lasting memory rather than many competing metrics.

### Dashboard App v0.4.11-alpha

Scope:

- Reframed Monthly Coaching Review from a dashboard-like month summary into a more letter-like coach surface.
- Added `本月月評` as the opening paragraph so the page answers the monthly verdict before showing evidence.
- Reworked the middle of the page into `教練時間線`, `為什麼我這樣看`, and `下個月，我希望你……`.
- Renamed the supporting section to `本月代表決策` so evidence supports the coach's judgment instead of competing with it.
- Continued replacing system-heavy wording with calmer, more human coaching language.

### Dashboard App v0.4.10-alpha

Scope:

- Refined Monthly Coaching Review from a month summary into a more continuous coach surface.
- Added `教練時間線` so the month is framed as a carry-over from last month and a setup for next month.
- Replaced more system-like recommendation language with warmer coaching phrasing.
- Shifted month signals toward more human labels such as `穩定累積` and `可追回` instead of colder progress wording.
- Clarified that month progress is compared against a month-to-date reference rhythm, not a full-month target.

### Dashboard App v0.4.9-alpha

Scope:

- Refined Journey from narrative polish into a deeper, more memorable chapter experience.
- Added `這一章的感受` so each chapter carries emotional texture rather than only structural explanation.
- Added `留給未來的自己` so every month can leave behind one sentence worth remembering later.
- Reframed turning points toward growth meaning first and numeric evidence second.
- Renamed representative sessions toward `本章故事片段` so key workouts feel like memorable scenes instead of metrics-first highlights.

### Dashboard App v0.4.8-alpha

Scope:

- Refined Journey from a structural timeline into a more narrative monthly chapter experience.
- Renamed product language toward story structure, including `旅程章節` and `成長轉折`.
- Added `章節反思` so each month can leave behind a lesson, not only a recommendation.
- Added `這一章正在建立` to describe capability growth instead of only displaying metrics.
- Replaced the representative-session table with story-like cards so key sessions feel like meaningful moments in the chapter rather than rows in a report.

### Dashboard App v0.4.5-alpha

Scope:

- Refined the month surface from a simple monthly dashboard into a more coach-oriented monthly review.
- Added `Month Status`, `Coach Summary`, `Month Progress`, `Key Sessions`, and `Next Month` guidance.
- Shifted the month page toward strategy review rather than raw archive display.
- Reused governed semantic monthly views plus new progress and key-session semantic views instead of embedding month logic directly in Python.

### Dashboard App v0.4.4-alpha

Scope:

- Added a dedicated `Monthly Review` page as the newest product surface on top of Semantic Layer v1.0.
- Added month summary, month-to-date awareness, previous 3-month baseline comparison, and current-month workout/purpose distribution.
- Reused governed monthly semantic views instead of rebuilding month aggregation logic inside Python.

### Dashboard App v0.4.3-alpha

Scope:

- Added a dedicated `Training` page as the fourth product surface on top of Semantic Layer v1.0.
- Added `Training Balance`, `Workout / Purpose Distribution`, `Tagged vs Unassigned` quality signals, and `Recent Training Intent`.
- Exposed current metadata quality directly inside the product, so training semantics can improve before deeper AI features are added.
- Reused governed semantic views instead of rebuilding distribution, balance, and recent intent logic inside Python.

## Activity LDM

### v1.0

Initial logical model based on early Canonical Data Model discussion.

Included:

- Core activity summary
- Environment
- Performance
- Running Economy
- Subjective
- System fields

### v1.1

First production-ready Activity LDM after Metadata Repository validation.

Changes:

- Removed `avg_pace_sec_per_km` from core `activity` because `Lifecycle = Derived`.
- Removed `import_batch_id` from core `activity` because it belongs to ETL/System layer.
- Kept `avg_hr`, but required Metadata Repository update before SQLite generation.
- Kept `created_at` and `updated_at` as system fields, pending Metadata Repository update.
- Clarified `source_file_name` vs `data_source` naming.
- Established view/query replacement for average pace.

## Kilometer Split LDM

### v1.0

Initial logical model based on early split-level analytics discussion.

Included:

- Split distance and time
- Pace fields
- Heart rate
- Power
- Running dynamics
- Elevation
- Stamina

### v1.1

First production-ready Kilometer Split LDM after Metadata Repository validation.

Changes:

- Removed `elapsed_pace_sec_per_km` from core `kilometer_split` because `Lifecycle = Derived`.
- Excluded `moving_time_sec` because source is not confirmed and it is not currently parsed.
- Excluded `moving_pace_sec_per_km` because it depends on unverified moving time/source.
- Excluded `gap_pace_sec_per_km` until source is confirmed as FIT Native or Garmin algorithm output.
- Excluded `potential_stamina_pct` until split-level field mapping is confirmed.
- Kept raw heart rate, power, running dynamics, elevation, and nullable split Stamina observations.
- Added Metadata Repository entries for `activity_id`, `stamina_start_pct`, and `stamina_end_pct`.
- Established view/query replacement for split elapsed pace and speed.

## Shoe LDM

### v1.0

Initial logical model based on shoe dimension discussion.

Included:

- Shoe identity
- Basic shoe attributes
- Specification
- Lifecycle
- Status
- Notes
- System fields

### v1.1

First production-ready Shoe LDM after Metadata Repository validation.

Changes:

- Added Metadata Repository entries `SHOE-002` through `SHOE-017`.
- Kept `shoe_code` as the stable human-readable business key.
- Kept `category` as a controlled enum, not free text.
- Replaced open-ended `status` with required `is_active`.
- Kept nullable manual lifecycle fields such as `first_run_date` and `retire_actual_distance_km`.
- Excluded `rotation_order` and `default_workout` because they belong to coaching strategy.
- Excluded shoe performance metrics such as `avg_hr`, `avg_power`, `avg_gct`, and `efficiency_score`; these belong in views/query/analysis layer.

## Workout Type LDM

### v1.0

Initial logical model based on workout type dimension discussion.

Included:

- Workout type identity
- Display names
- Description
- Intensity classification
- Structural flags
- Display metadata
- System fields

### v1.1

First production-ready Workout Type LDM after Metadata Repository validation.

Changes:

- Added Metadata Repository entries `WKT-001` through `WKT-010`.
- Kept `workout_type_code` as the stable business key.
- Kept `intensity_category` as a controlled enum.
- Kept `is_quality_session`, `is_long_run`, and `is_recovery_focused` as structural flags.
- Excluded `default_training_purpose` and `training_purpose_id` because workout structure and training intent must stay separate.
- Excluded `default_shoe`, `default_intensity`, and target pace/HR/power fields because they belong to coaching strategy or future workout prescription models.
- Confirmed alignment with `ADR-003 Separate Workout Type and Training Purpose`.

## Training Purpose LDM

### v1.0

Initial logical model based on training purpose dimension discussion.

Included:

- Training purpose identity
- Display names
- Description
- Purpose classification
- Intent classification flags
- Display metadata
- System fields

### v1.1

First production-ready Training Purpose LDM after Metadata Repository validation.

Changes:

- Added Metadata Repository entries `TP-001` through `TP-010`.
- Kept `training_purpose_code` as the stable business key.
- Kept `purpose_category` as a controlled enum.
- Kept `is_primary_physiological`, `is_recovery_related`, and `is_performance_related` as intent classification flags.
- Clarified that `training_purpose` records coaching intent, not training outcome.
- Clarified `race_specific` vs `race`.
- Excluded `workout_type_id` and `default_workout_type` because workout structure and training intent must stay separate.
- Excluded target pace/HR/power fields because they belong to coaching strategy or future workout prescription models.
- Excluded actual outcome fields because they belong to analysis layer.
- Confirmed alignment with `ADR-003 Separate Workout Type and Training Purpose`.

## Activity Training Purpose LDM

### v1.0

Initial logical model based on activity-to-training-purpose bridge discussion.

Included:

- Activity relationship
- Training purpose relationship
- Purpose role
- System fields

### v1.1

First production-ready Activity Training Purpose LDM after Metadata Repository validation.

Changes:

- Added Metadata Repository entries `ATP-001` through `ATP-003`.
- Confirmed `activity_training_purpose` as the bridge between `activity` and `training_purpose`.
- Kept `purpose_role` as a required enum with `PRIMARY` / `SECONDARY`.
- Excluded `purpose_weight` because percentage-based intent attribution is subjective and not needed for v1.
- Excluded target pace/HR/power fields because they belong to coaching strategy or future workout prescription models.
- Excluded actual outcome and AI-detected purpose fields because they belong to analysis layer.
- Confirmed alignment with `ADR-003 Separate Workout Type and Training Purpose`.

## Canonical Data Layer

### v1.0 Core Layer

Core Canonical Data Layer v1.0 is complete for:

- `activity`
- `kilometer_split`
- `shoe`
- `workout_type`
- `training_purpose`
- `activity_training_purpose`

Status: Frozen for Core LDM v1.0.
