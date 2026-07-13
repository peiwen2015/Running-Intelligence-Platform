# CoachOS v1.1 - Coach Knowledge

## Purpose

CoachOS v1.1 focuses on the first real Learning Loop.

The user should feel that every confirmed decision helps CoachOS understand the runner better.

Not that the runner is filling in fields for the system.

## Theme

`Coach Knowledge`

The product should translate:

```text
Missing data
  ↓
Next best action
  ↓
Improved understanding
  ↓
Better coaching
```

## Objective

Make the first learning loop real:

```text
CoachOS doesn’t know
  ↓
CoachOS thinks
  ↓
Runner trusts
  ↓
Runner confirms
  ↓
CoachOS learns
  ↓
Weekly becomes better
```

## Sprint 1

### Goal

After finishing an activity, the runner should be able to help CoachOS learn the most important knowledge quickly.

### Scope

- Shoe
- Workout Type
- Training Purpose

### Experience Direction

- CoachOS should suggest likely values before asking the runner to choose
- CoachOS should show why each suggestion appeared
- The runner should be able to confirm quickly
- The runner should be able to choose another option when needed

### Trust Layer

`Trust` is not a separate step the runner must complete.

It is the condition that makes a suggestion worth presenting.

The UI should answer:

- Why does CoachOS think this?
- Can the runner understand the reason?
- Is the suggestion worth trusting enough to confirm?

The first Sprint should optimize for explanation before scoring.

Trust comes from clarity.

Not from a larger set of options.

### State Model

The first Learning Loop should support three states:

#### 1. CoachOS doesn’t know

Example:

- `Shoe`
- `Unknown`
- `Can you teach me?`

#### 2. CoachOS thinks

Example:

- `CoachOS thinks this is Boston 13`
- `Because the last 4 Tempo Runs used Boston 13`
- `Accept?`

#### 3. CoachOS learned

Example:

- `Thank you`
- `CoachOS now understands this session better`
- `Weekly reasoning improved`

### Intended Language

Use coach language, not form language.

Examples:

- `CoachOS thinks this is likely Boston 13`
- `This is the most likely workout type`
- `This confirmation will help Weekly understand this session better`

### Implementation Rule

No suggestion without explanation.

If CoachOS cannot explain why it thinks something is likely, it should not suggest it yet.

### UI Spec

The first UI should be a single `Activity Learning Panel`.

It should appear after `Coach Review` and before any other deep navigation.

It should not require a separate `Metadata` page.

It should not expose a knowledge center.

It should present one learning at a time.

#### Layout

```text
Coach Review
  ↓
Coach Knowledge
  ↓
CoachOS thinks
  ↓
Because...
  ↓
[Confirm]
[Choose Another]
[Skip]
```

#### Example Panel

```text
──────────────────────────────
Coach Review
今天真正留下的是：
接回節奏。
──────────────────────────────
Coach Knowledge
CoachOS thinks
────────────────
🏃 Shoe
Boston 13
Because
Last 4 Tempo Runs used Boston 13.
[ Confirm ]
[ Choose Another ]

🏃 Workout
Tempo Run
Because
10 km
Load 228
Threshold pattern
[ Confirm ]
[ Choose Another ]

🎯 Training Purpose
Threshold
Because
Recent workout structure matches Threshold sessions.
[ Confirm ]
[ Choose Another ]
──────────────────────────────
```

#### Interaction Rules

- One learning at a time.
- Do not show all suggestions as a form.
- Do not show dropdowns by default.
- `Choose Another` is the only path that opens a broader option list.
- `Skip` should be available for later decisions.
- `Confirm` should teach CoachOS immediately.

#### Confirmation State

After confirmation, the panel should transform into a learning message.

Example:

```text
CoachOS learned.
✓ Boston 13
Weekly reasoning became stronger.
```

The confirmation state should feel like learning.

Not like success messaging.

## Product Language Rules

- Do not lead with `Metadata` in user-facing labels when `Coach Knowledge` is clearer.
- Do not present confirmation as paperwork.
- Do present suggestions as coaching help.
- Do present confirmed decisions as learning moments.
- Do present missing information as the next best action.

## Success Criteria

This theme is working when:

- the first learning loop happens naturally
- users feel they are teaching CoachOS
- CoachOS can say what it thinks and why
- users understand why each suggestion appears
- confirmed decisions improve later reasoning
- weekly and monthly reasoning get better over time

## Status

`CoachOS v1.1 - Coach Knowledge`

- Status: Draft
- Scope: Sprint 1 only
- Classification: Product Theme / Release Direction
