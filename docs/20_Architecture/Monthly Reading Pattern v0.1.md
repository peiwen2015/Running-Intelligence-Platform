# Monthly Reading Pattern v0.1

## Purpose

This artifact does not define monthly writing yet.

It defines how Monthly should be read.

Its job is to turn coach understanding into a readable monthly experience before any rendering template or AI polish is introduced.

## Core Question

**How should a runner read a monthly coaching review?**

## Product Role

Monthly is not a dashboard.

Monthly is not a long Journey page.

Monthly is not a metrics report.

Monthly is a **coach letter**.

Its job is to help the runner answer:

- How did this month go?
- Why does the coach see it that way?
- What should happen next?

## Reading Rhythm

Monthly should be read in this order:

```text
Opening
   ↓
Why
   ↓
Forward
   ↓
Evidence
```

This is not a template order.

It is a reading rhythm.

## Section Roles

### 1. Opening

Opening answers:

**So, how did this month really go?**

It should do three things:

- give the runner a clear first judgment
- avoid evidence overload
- establish the emotional tone of the letter

Opening should feel like the first paragraph of a letter, not like a KPI summary.

### 2. Why

Why answers:

**Why does the coach see it this way?**

This is where monthly understanding begins to unfold.

It should draw primarily from:

- `Learning`
- selected `Evidence`
- selected `Confidence`

Why is not the full evidence dump.

It is the explanation layer that makes the opening believable.

### 3. Forward

Forward answers:

**What should happen next month?**

This is where monthly guidance becomes useful.

It should draw primarily from:

- `Recommendation`
- current month direction
- coaching continuity from the prior month when relevant

Forward should feel like a coach looking ahead, not a system issuing instructions.

### 4. Evidence

Evidence answers:

**If I want to inspect the basis of this judgment, what should I look at?**

This is where supporting detail belongs:

- selected signals
- confidence
- monthly progress
- trends
- key sessions
- training distribution

Evidence exists to support the letter, not to replace it.

## Narrative Object Mapping

Monthly does not consume the whole Narrative Object in the same way at every point.

| Monthly Section | Primary Narrative Object Inputs | Supporting Inputs |
|---|---|---|
| Opening | `Verdict` | selected `Theme`, month context |
| Why | `Learning` | selected `Evidence`, selected `Confidence` |
| Forward | `Recommendation` | previous-month continuity, current phase |
| Evidence | `Evidence`, `Confidence` | progress, trends, key sessions, distribution |

## What Monthly Should Avoid

Monthly should avoid:

- opening with raw metrics
- leading with evidence before judgment
- repeating the same idea across every section
- making the runner infer what matters from tables
- turning the whole page into a stretched dashboard

## Relationship to Rendering

Monthly Reading Pattern comes before rendering.

Composition decides:

- what comes first
- what each section is responsible for
- how the letter unfolds

Rendering decides:

- which words express each section
- how formal or warm the language is
- how the same meaning is phrased on the page

## Relationship to Existing Monthly Surface

The current monthly page already contains many of these elements:

- monthly verdict
- coach timeline
- explanation
- forward-looking recommendation
- progress and evidence sections

This artifact turns those pieces into an explicit reading pattern, so the page can evolve intentionally rather than section by section.

## What Comes Next

If this reading pattern remains useful after review, the next step is:

1. define a Monthly composition contract
2. map current monthly page sections to that contract
3. only then build rendering templates

Rendering should not start before the reading pattern is stable.
