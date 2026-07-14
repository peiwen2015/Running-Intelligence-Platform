# Activity Coach Knowledge Implementation Note v0.1

## Purpose

This note records the current Activity-page implementation of `Coach Knowledge`.

It is a bridge document between:

- the original `CoachOS v1.1 - Coach Knowledge` product theme
- the current Activity UI implementation
- the governance lineage that later absorbed the idea

It is intentionally scoped to the current initial implementation.

## Current State

The Activity page now contains a visible `Coach Knowledge` panel that sits between:

- `Coach Review`
- `Evidence`

The panel supports a three-step learning loop:

```text
Shoe
  ↓
Workout Type
  ↓
Training Purpose
```

Each step can:

- suggest a likely value
- explain why the suggestion appeared
- confirm immediately
- choose another option
- skip for later

After confirmation, the panel transforms into a learned state.

## What Is Implemented

### 1. Suggest Before Ask

The panel does not start as a blank form.

It starts with a suggested coach interpretation.

Implementation:

- current shoe, workout, and purpose are inferred from activity data and recent metadata
- the UI shows a single active learning step at a time
- suggestions are hints only; they must not overwrite an already confirmed value

The metadata editing page follows the same rule: it may prefill the most likely shoe, workout type, and training purpose, but the runner still confirms before anything is written back.

### 2. Explanation Before Trust

Every suggestion is paired with a short `Because...` explanation.

Examples of explanation sources:

- recent shoe reuse
- workout structure signals
- training-purpose compatibility

This matches the original rule that no suggestion should appear without explanation.

### 3. One Learning at a Time

The panel presents one learning step at a time rather than a metadata form.

This keeps the interaction aligned with coach language rather than admin language.

### 4. Immediate Confirmation

Confirming a suggestion writes back to SQLite immediately.

The implementation updates:

- `activity.shoe_id`
- `activity.workout_type_id`
- `activity_training_purpose`

This makes the interaction a real learning loop instead of a visual hint.

The learning layer should never auto-commit inferred shoe values into activities that already have a runner-selected shoe.
Confirmed values remain the source of truth.
Every saved metadata change should also write provenance so the app can later tell whether a value came from manual tagging, Coach Knowledge, or a legacy inference.

### 5. Learned State

After confirmation, the UI switches into a completion state that says CoachOS learned.

The completion state is meant to feel like understanding improved, not like a successful form submission.

## Implementation Map

- Panel rendering: [`analysis_platform/dashboard_app.py`](file:///Users/perryliu/Documents/Running%20Analytics/analysis_platform/dashboard_app.py#L6526)
- State inference: [`analysis_platform/dashboard_app.py`](file:///Users/perryliu/Documents/Running%20Analytics/analysis_platform/dashboard_app.py#L6461)
- Activity page placement: [`analysis_platform/dashboard_app.py`](file:///Users/perryliu/Documents/Running%20Analytics/analysis_platform/dashboard_app.py#L6945)
- Submission route: [`analysis_platform/dashboard_app.py`](file:///Users/perryliu/Documents/Running%20Analytics/analysis_platform/dashboard_app.py#L11919)
- Metadata write-back: [`analysis_platform/dashboard_app.py`](file:///Users/perryliu/Documents/Running%20Analytics/analysis_platform/dashboard_app.py#L1773)

## Match Against Original Theme

The current implementation already reflects several requirements from the original theme:

- Coach language instead of form language
- Suggest likely values before asking
- Show why each suggestion appeared
- Allow quick confirmation
- Allow choosing another option
- Transform confirmation into a learning message

That means the original `Coach Knowledge` idea is no longer only conceptual.

It is visible in the product.

## What Is Still Missing

The current implementation is still an early version.

It does not yet fully implement:

- explicit confidence display
- stronger provenance / evidence breakdown
- a governed learning event record
- broader coach-knowledge domains beyond Activity tagging

So the current result should be read as:

`metadata tagging learning loop`

not yet:

`full coach knowledge system`

## Why This Matters

This is important because it shows where the product actually moved from idea to behavior.

The early `Coach Knowledge` thread helped the product cross a key boundary:

- from asking for metadata
- to teaching through metadata

That shift is part of why the later governance documents could be more metadata-first and more coach-like.

## Status

`Activity Coach Knowledge Implementation Note v0.1`

- Status: Active
- Scope: Current Activity-page learning loop
- Classification: Architecture / Product Implementation Note
