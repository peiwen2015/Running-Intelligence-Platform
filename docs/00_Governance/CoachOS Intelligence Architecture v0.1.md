# CoachOS Intelligence Architecture v0.1

## Purpose

This document defines the top-level intelligence architecture for CoachOS.

It does not define one page, one prompt, or one feature.

It defines how CoachOS should create, transform, and pass training knowledge upward through multiple reasoning layers.

The goal is to make later product work depend on a stable intelligence hierarchy instead of ad hoc analysis logic.

## Why This Document Exists

CoachOS should not be understood as:

- one activity analyzer
- one weekly summary
- one monthly summary
- several time-scaled review screens

CoachOS should be understood as a knowledge system.

Each intelligence layer exists to create a higher-level form of training knowledge from the layer below.

That means the key architectural question is not:

`What does this page show?`

The key architectural question is:

`What knowledge does this layer create?`

## Core Definition

CoachOS is not a stack of summaries.

It is a hierarchy of knowledge creation.

## Core Principles

### 1. Intelligence Layers Are Separated by Reasoning Responsibility

CoachOS layers should be separated by reasoning responsibility, not by time scale.

For example:

- Activity Intelligence is responsible for execution understanding
- Workout Sequence Intelligence is responsible for continuity understanding
- Weekly Intelligence is responsible for progression understanding
- Monthly Intelligence is responsible for adaptation understanding
- Training Cycle Intelligence is responsible for readiness understanding

The point of each layer is not "how many days it covers."

The point of each layer is "what kind of training knowledge it is responsible for creating."

### 2. Every Intelligence Layer Must Deepen Understanding

Every intelligence layer exists to deepen understanding, and where appropriate, stabilize reusable understanding into knowledge.

This is the most important architecture rule in CoachOS.

If a layer only repeats what the lower layer already did, it is not deepening understanding.

It is only a display surface.

### 3. Reasoning Moves Upward; Evidence Stays Downward

Reasoning should move upward.

Evidence should stay downward.

This means:

- raw observations remain at the lower layers
- higher layers should inherit already-reasoned knowledge
- higher layers may explain themselves by referencing lower evidence
- higher layers should not re-run the full lower-layer analysis unless absolutely necessary

### 4. Higher Layers Should Consume Knowledge, Not Raw Evidence

Weekly should not directly re-read raw split logic.

Monthly should not directly re-read single-activity execution details.

Training Cycle should not directly reason from daily raw metrics.

Each upper layer should consume the best available knowledge output from the layer below.

### 5. Product Surfaces Should Follow the Knowledge Hierarchy

Pages are not the architecture.

Pages are only one way to expose the architecture.

The architecture should therefore be defined independently from:

- UI layout
- prompt formatting
- database schema
- release-specific implementation details

## CoachOS Knowledge Hierarchy

### Layer 0 — Observation

Question:

`What happened?`

This layer contains observation only.

It includes:

- FIT records
- GPS
- HR
- power
- cadence
- elevation
- weather
- splits

This layer contains no coaching reasoning.

It is the evidence base.

### Layer 1 — Execution Intelligence

Question:

`How was today's workout executed?`

This is the current Activity Intelligence layer.

It creates knowledge such as:

- execution summary
- workout assessment
- key evidence
- pace / HR / power interpretation
- coach-level reading of today as a workout

This layer is responsible for understanding today's execution quality.

It is not responsible for sequence continuity, weekly progression, or monthly adaptation.

### Layer 2 — Continuity Intelligence

Question:

`How does today's workout affect the continuity of training?`

This is where Workout Sequence Intelligence (WSI) lives.

This layer should not primarily ask whether today's workout was fast or slow.

It should ask:

- why today's workout exists
- what mission it serves between surrounding workouts
- whether that mission was fulfilled
- how continuity is preserved, advanced, delayed, or interrupted afterward

This layer creates knowledge such as:

- transition understanding
- mission understanding
- continuity state
- sequence reasoning

This is the first Sequence Reasoning Engine inside CoachOS.

### Layer 3 — Progression Intelligence

Question:

`Is training progressing as intended?`

This is the Weekly Intelligence layer.

Weekly should not be treated as a seven-day summary.

It should be treated as a progression layer.

This layer creates knowledge such as:

- weekly direction
- progression confidence
- build / recovery / stability / absorption reading
- whether the week stayed on plan or drifted away

Weekly should consume:

- execution knowledge from Activity
- continuity knowledge from WSI

Weekly should not need to re-analyze raw split evidence for every activity in order to know what the week is doing.

### Layer 4 — Adaptation Intelligence

Question:

`What adaptations are emerging?`

This is the Monthly Intelligence layer.

Monthly should not be treated as a thirty-day summary.

It should be treated as an adaptation layer.

This layer creates knowledge such as:

- adaptation direction
- emerging capability patterns
- training block character
- whether the month is building, absorbing, consolidating, or stagnating

Monthly should primarily read progression knowledge, continuity patterns, and confirmed knowledge summaries.

It should not need raw daily evidence unless it is explaining an exception.

### Layer 5 — Readiness Intelligence

Question:

`Is the athlete becoming ready for the target?`

This is the Training Cycle Intelligence layer.

It is not fundamentally about calendar phase labels.

It is about readiness.

This layer creates knowledge such as:

- event readiness
- cycle direction
- readiness gaps
- whether accumulated adaptation is moving toward the target

Examples:

- half marathon readiness
- marathon readiness
- ultra readiness

## Knowledge Cascade

CoachOS should be designed as a knowledge cascade.

```text
Observation
    ↓
Execution Intelligence
    ↓
Continuity Intelligence
    ↓
Progression Intelligence
    ↓
Adaptation Intelligence
    ↓
Readiness Intelligence
```

This is not just a reasoning cascade.

It is a knowledge cascade.

Each layer should create new knowledge that can be consumed by the next layer above.

## Layer Contract

Every intelligence layer in CoachOS should be defined by the same three questions:

1. What knowledge does this layer create?
2. What knowledge does it consume from the layer below?
3. What knowledge does it expose to the layer above?

For architecture safety, every layer should also answer a fourth question:

4. What should this layer never re-analyze directly?

This fourth question prevents architectural drift.

It keeps each layer from collapsing back into raw-data reasoning.

## Example Layer Contracts

### Execution Intelligence

Creates:

- execution understanding
- evidence-backed workout interpretation

Consumes:

- observation data

Exposes:

- execution summary
- evidence anchors
- workout assessment

Should not directly solve:

- continuity
- weekly progression
- monthly adaptation
- cycle readiness

### Continuity Intelligence

Creates:

- transition understanding
- mission understanding
- continuity state

Consumes:

- execution understanding
- nearby workout context

Exposes:

- continuity knowledge
- mission-level sequence interpretation

Should not directly re-analyze:

- raw split execution
- low-level pace evidence already resolved by Activity Intelligence

### Progression Intelligence

Creates:

- weekly progression knowledge

Consumes:

- execution knowledge
- continuity knowledge

Exposes:

- week direction
- progression confidence
- week story

Should not directly re-analyze:

- raw execution details from every activity

### Adaptation Intelligence

Creates:

- monthly adaptation knowledge

Consumes:

- progression knowledge
- continuity patterns

Exposes:

- adaptation narrative
- block-level capability reading

Should not directly re-analyze:

- daily evidence unless explaining an exception

### Readiness Intelligence

Creates:

- target readiness knowledge

Consumes:

- adaptation knowledge
- longer-cycle continuity and progression signals

Exposes:

- readiness judgment
- stage-change confidence

Should not directly re-analyze:

- monthly or activity-level evidence as if no higher-layer knowledge existed

## Why WSI Matters

Workout Sequence Intelligence matters because it reveals the missing layer between execution and progression.

Without WSI:

- Activity understands a workout
- Weekly tries to infer a week story directly from multiple workouts

That gap causes CoachOS to miss a crucial coaching layer:

`How does today's workout preserve, advance, or interrupt training continuity?`

WSI is therefore not just another feature.

It is the first concrete implementation of Continuity Intelligence.

It shows how CoachOS should reason above execution but below progression.

## What This Architecture Forbids

This architecture forbids several design mistakes:

- treating Weekly as only a seven-day report
- treating Monthly as only a longer report
- asking upper layers to repeatedly inspect raw lower-layer evidence
- building new intelligence layers that only restate lower-layer conclusions
- confusing UI sections with knowledge layers

## Near-Term Implications

This document implies that future intelligence work should be created in this order:

1. define the layer responsibility
2. define the knowledge created by that layer
3. define what lower-layer knowledge it consumes
4. define what higher-layer knowledge it exposes
5. only then define ontology, prompt behavior, or UI

That means Workout Sequence Intelligence should not be finalized as an isolated feature specification first.

It should be defined as the first sub-layer document that inherits from this top-level architecture.

## Relationship to Future Documents

This document should become the parent architecture for later intelligence-specific definitions such as:

- Activity Intelligence
- Workout Sequence Intelligence
- Weekly Intelligence
- Monthly Intelligence
- Training Cycle Intelligence

Each child document should inherit the layer-contract pattern defined here.

## Status

`CoachOS Intelligence Architecture v0.1`

- Status: Draft
- Scope: Top-level intelligence architecture
- Classification: Governance / Intelligence Architecture
