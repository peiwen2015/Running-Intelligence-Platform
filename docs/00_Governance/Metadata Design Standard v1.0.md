# Metadata Design Standard v1.0

## Purpose

This standard defines the design rules that govern the Running Analytics Metadata Repository, Canonical Data Model, SQLite schema, parser, dashboard, and AI Coach.

The Metadata Repository is the single source of truth. LDM and physical schema should be validated against it.

## Rule 01: Metadata First

All new data items must be added to the Metadata Repository before they are added to Excel, LDM, SQLite, parser output, dashboard, or AI Coach prompts.

## Rule 02: Source of Truth Must Be Explicit

Every data item must have exactly one `Source of Truth`.

When multiple sources provide similar values, the platform must use `Source of Truth` to decide precedence.

Examples:

| Data Item | Source of Truth |
|---|---|
| Distance | FIT |
| Shoe | Manual |
| Weather | Weather API |
| Training Purpose | Manual |

## Rule 03: Granularity Drives Table Placement

Data should be stored at its natural grain.

| Granularity | Target |
|---|---|
| Activity | activity |
| Split | kilometer_split |
| Daily | health_daily |
| Shoe | shoe |
| Workout Type | workout_type |
| Training Purpose | training_purpose |
| Activity Training Purpose | activity_training_purpose |
| Analysis | view / analysis / ai_analysis |

## Rule 04: Fact Tables Store What Happened

Fact tables describe events or observations.

Examples:

| Table | Grain |
|---|---|
| activity | One activity = one record |
| kilometer_split | One split = one record |

## Rule 05: Dimension Tables Store What It Is

Dimension/reference tables describe stable entities, categories, or controlled vocabularies.

Examples:

| Table | Meaning |
|---|---|
| shoe | Shoe static attributes and lifecycle |
| workout_type | Workout structure |
| training_purpose | Training intent |

## Rule 06: Derived Data Is Not Core Fact Data

Data with `Lifecycle = Derived` should not be stored in core fact tables by default.

Use view, query, or analysis layer unless there is a clear materialization reason.

Examples:

| Data Item | Reason |
|---|---|
| Average Pace | Derived from distance and duration |
| HR Drift | Derived from split HR and pace |
| Efficiency Index | Derived analytical metric |

## Rule 07: Analysis Output Stays Out of Core Facts

Data with `Lifecycle = Analysis` must not be written back to core fact tables.

It belongs in views, analysis tables, or AI output tables.

## Rule 08: Training Purpose Is Intent, Not Outcome

`training_purpose` describes coaching intent.

It must not be overwritten by actual physiological outcome.

Example:

If a threshold workout becomes VO2max-like because of heat or fatigue, the original `training_purpose = threshold` remains unchanged. The outcome belongs to the analysis layer.

## Rule 09: Bridge Tables Represent Relationships

Many-to-many relationships should use bridge tables.

Example:

`activity_training_purpose` connects one activity to one or more training purposes.

Use role-based classification such as `PRIMARY` / `SECONDARY` before adding subjective percentage weights.

## Rule 10: Reference Tables Avoid Coaching Defaults

Reference/dimension tables should avoid context-dependent defaults.

Do not store:

- default_training_purpose
- default_shoe
- default_intensity

These belong to coaching strategy, not canonical data.

## Rule 11: Nullable Must Reflect Real Availability

If a data item is device-dependent, API-dependent, manual, or research-only, it should usually be nullable.

Examples:

| Data Item | Nullable |
|---|---|
| Stamina | YES |
| Weather | YES |
| HRV | YES |
| Training Readiness | YES |

## Rule 12: Validation Rules Should Be Enforceable

Validation rules in the Metadata Repository should be usable by importer, application, tests, or SQLite constraints where practical.

Examples:

| Data Item | Validation |
|---|---|
| Distance | > 0 |
| HR | 30-240 bpm |
| Humidity | 0-100 |
| Training Effect | 0-5 |

## Rule 13: Naming Conventions

Codes and database fields should use lowercase `snake_case`.

Examples:

| Good | Avoid |
|---|---|
| easy_run | EasyRun |
| race_specific | RaceSpecific |
| heat_adaptation | HeatAdaptation |

## Rule 14: LDM Validation Is Required

Every LDM table should be validated against the Metadata Repository:

- Every field exists in the Metadata Repository.
- Lifecycle is compatible with storage.
- Granularity matches table placement.
- Data Type matches the LDM.
- Required / Nullable is consistent.
- Source of Truth is respected.
- Derived and Analysis items are justified if stored.
