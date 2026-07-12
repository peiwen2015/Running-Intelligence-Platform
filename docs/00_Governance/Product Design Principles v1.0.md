# Product Design Principles

## Purpose

These principles define the product experience philosophy of the Personal Running Intelligence Platform.

They sit above individual pages and features.

They guide how governed data should be turned into useful review, explanation, and coaching experiences.

## Principle 1: Decision Before Data

Every product surface should answer a decision question before showing detailed information.

Examples:

- `Overview`: What should I do today?
- `Weekly Review`: Did this week go according to plan?
- `Monthly Coaching Review`: Is this month moving toward the goal?
- `Shoes`: Which shoe is best suited to which kind of work?
- `Training`: Is my training structure balanced?
- `Metadata`: What is still missing before the system can judge more confidently?

## Principle 2: State, Reason, Recommendation

Every core page should answer three questions in order:

1. What is my current state?
2. Why is that the current state?
3. What should I do next?

This creates a stable product pattern:

`State -> Reason -> Recommendation`

## Principle 3: Coach Before Dashboard

The platform should behave like a helpful coach, not just a reporting surface.

The goal is not to maximize visible metrics.

The goal is to reduce uncertainty and help the runner make better training decisions.

## Principle 4: Verdict Before Evidence

Pages should lead with an interpreted verdict, then show supporting evidence.

Recommended page order:

`Verdict -> Evidence -> Exploration`

For example:

- first: `Balanced Build`
- then: progress, load, distribution, key sessions
- then: archive and drill-down tables

## Principle 5: Human Language Before Metrics

Use human-readable coaching language before technical metric language.

Prefer:

- `Training Load Status: Normal`
- `Month Progress: On track`
- `Confidence: Medium because only 32% of the month is complete`

Over:

- `Load Delta`
- `Volume Delta`
- `Confidence: Medium` with no explanation

Metrics still matter, but they should support the explanation rather than replace it.

## Principle 6: Recommendation Before Exploration

Product surfaces should provide a next-step recommendation before inviting deeper exploration.

Users should be able to leave each page with a clearer action than when they arrived.

Examples:

- keep current mileage
- add one more recovery session
- increase threshold focus next block
- continue heat adaptation
- review unassigned activities before comparing shoes

## Principle 7: Context Creates Meaning

A metric without context is only a number.

Context may include:

- time completeness (`month-to-date`, `complete month`)
- comparison baseline (`previous 3-month average`, `same day of month`)
- workout structure
- training purpose
- shoe
- weather
- subjective feeling

The platform should avoid strong judgments when the necessary context is missing.

## Principle 8: Be Honest About Uncertainty

The platform must not pretend to know more than the governed data supports.

When labels are missing or a period is incomplete, the product should say so clearly.

Examples:

- `Month-to-date`
- `Baseline still building`
- `Not enough tagged data`
- `Confidence: Medium`

This honesty is part of the coaching experience, not a product weakness.

## Principle 9: Intelligence Over Information Density

More information is not automatically more useful.

If a page feels visually dense but does not improve a decision, it should be simplified.

The platform should optimize for:

- faster orientation
- clearer judgment
- lower cognitive load
- stronger next-step clarity

## Principle 10: Semantic Layer Is the Product Backbone

If a product judgment or evidence pattern will be reused, it should be expressed in the Semantic Layer rather than duplicated in application code.

This keeps product meaning stable across:

- Dashboard
- future AI Coach
- chat interfaces
- weekly and monthly review surfaces

## Product Pattern

The default experience pattern for a product surface is:

```text
Verdict
  ↓
Reason
  ↓
Recommendation
  ↓
Evidence
  ↓
Exploration
```

Not:

```text
Raw data
  ↓
More raw data
  ↓
User tries to infer meaning alone
```

## Product Position

Running Intelligence is not just data access.

It is the ability to:

```text
Observe
  ↓
Understand
  ↓
Decide
  ↓
Improve
```

## Status

`Product Design Principles v1.0`

- Status: Active
- Scope: Dashboard App, future AI Coach, and all product-facing review surfaces
