# CoachOS Interaction Principles v1.0

## Purpose

These principles define how CoachOS should help the runner understand training data, make decisions, and improve over time.

They are broader than any single page or workflow.

They apply to `Overview`, `Weekly`, `Monthly`, `Activity`, `Shoes`, `AI Conversation Loop`, `Reasoning Navigation`, `Journey`, and metadata workflows.

The product should feel like it is helping the runner understand.

Not requiring them to fill forms for the system's sake.

## Principle 1: Verdict Before Evidence

Every product surface should lead with interpretation before detail.

The runner should first see:

- what the product thinks
- why it thinks that
- what to do next

Only then should the product show supporting evidence.

## Principle 2: Fast Before Perfect

The first interaction should make the common case easy.

If the product can reduce friction, it should.

Examples:

- recent choices appear first
- the last similar item can be reused
- batch editing remains available
- common actions are one click away

## Principle 3: Suggest Before Ask

The product should offer a likely suggestion before asking the runner to decide from scratch.

Suggestions are guidance, not facts.

They may come from:

- recent history
- structured activity patterns
- training load and pace
- shoe usage
- completion context

## Principle 4: Confidence Must Be Visible

If the product suggests something, it should also show how confident it is.

The user should be able to tell whether the suggestion is:

- strong
- likely
- uncertain

The product should never hide uncertainty behind polished language.

## Principle 5: Every Action Should Improve Understanding

Every action should move CoachOS toward a clearer model of the runner.

Examples:

- saving a shoe tag improves shoe intelligence
- saving a workout type improves weekly grouping
- saving a training purpose improves reasoning quality
- saving an AI reply improves context for the next conversation

If an action does not improve understanding, the product should question why it exists.

## Principle 6: Missing Information Should Become the Next Best Action

Missing information is not just a gap.

It is a prompt for the next helpful action.

The product should help the runner see:

- what is missing
- what matters most
- what should be done first

Examples:

- no shoe tag -> next best action: tag the shoe
- no AI reply -> next best action: hand off to AI
- no tempo classification -> next best action: confirm workout intent

## Principle 7: History Should Teach

The product should learn from repeated choices.

If the runner keeps choosing the same shoe, workout type, or review pattern, CoachOS should start to remember.

Examples:

- the last similar item becomes easier to reuse
- common patterns surface earlier
- confidence rises as history accumulates
- the product becomes more useful because the runner kept using it

## Principle 8: The Product Should Learn With Me

CoachOS should adapt alongside the runner.

The product should not behave like a fixed form.

It should behave like a system that gradually understands:

- the runner's tagging habits
- the runner's training patterns
- the runner's preferred review style
- the recurring signals that matter most

## Principle 9: Be Honest About Uncertainty

The product must not pretend to know more than the governed data supports.

When labels are missing or the period is incomplete, the product should say so clearly.

Examples:

- `Month-to-date`
- `Baseline still building`
- `Not enough tagged data`
- `Confidence: Medium`

This honesty is part of the coaching experience.

## Principle 10: Understanding Over Information Density

More information is not automatically more useful.

The product should optimize for:

- faster orientation
- clearer judgment
- lower cognitive load
- stronger next-step clarity

If a page feels dense but does not improve a decision, it should be simplified.

## Product Pattern

The default experience pattern for CoachOS is:

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
User guesses alone
```

## Relationship to Other Documents

- `Product Design Principles v1.0` defines the product philosophy.
- `Product UX Polish Sprint v1.0` defines the review standard for the user experience.
- `Metadata Tagging Experience v1.0` applies these principles to tagging and knowledge workflows.

## Status

`CoachOS Interaction Principles v1.0`

- Status: Draft
- Scope: All product-facing surfaces, AI conversation flows, metadata workflows, review pages, and future Journey surfaces
- Classification: Governance / Interaction Standard
