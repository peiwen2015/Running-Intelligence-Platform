# CoachOS Intelligence Map v0.1

## Purpose

This document is the navigation map for CoachOS Intelligence.

It does not define architecture rules.

It does not define layer design standards.

It does not define one specific intelligence implementation.

Its purpose is to show where each intelligence layer sits inside the larger CoachOS intelligence space.

In other words:

- Architecture defines the constitution
- Design Standard defines the building code
- Intelligence Map defines the navigation space

## Why This Document Exists

CoachOS should not be explained only as:

- a running data product
- a review dashboard
- a set of weekly and monthly summaries

CoachOS should be explained as an intelligence system.

That system needs a map.

The map should answer:

1. What level of training abstraction is CoachOS trying to understand?
2. What level of cognitive abstraction is CoachOS trying to produce?
3. How do the intelligence layers work together to support better training decisions?

## Core Definition

CoachOS Intelligence Map locates each intelligence layer inside a shared space of:

- training abstraction
- cognitive abstraction
- reasoning responsibility
- knowledge flow

It is not a process chart.

It is not a UI sitemap.

It is an intelligence-space map.

## The Four Dimensions

### 1. Training Abstraction

This dimension answers:

`What scale of training is this layer trying to understand?`

```text
Workout
  ↓
Sequence
  ↓
Week
  ↓
Block
  ↓
Cycle
```

### 2. Cognitive Abstraction

This dimension answers:

`What kind of cognitive output is this layer trying to produce?`

```text
Evidence
  ↓
Reasoning
  ↓
Knowledge
  ↓
Judgment
  ↓
Decision
```

### 3. Reasoning Responsibility

This dimension answers:

`What distinct coaching responsibility does this layer own?`

Current CoachOS responsibilities are:

- Execution — understand execution
- Continuity — preserve continuity
- Progression — evaluate progression
- Adaptation — understand adaptation
- Readiness — evaluate readiness

### 4. Knowledge Flow

This dimension answers:

`What knowledge is flowing upward from one layer to the next?`

CoachOS should not be modeled as a raw data flow.

It should be modeled as a knowledge flow.

```text
Observation
  ↓
Execution Knowledge
  ↓
Continuity Knowledge
  ↓
Progression Knowledge
  ↓
Adaptation Knowledge
  ↓
Readiness Knowledge
```

## The Intelligence Space

The CoachOS intelligence layers can be located on two primary axes.

### Axis A — Training Abstraction

```text
Workout → Sequence → Week → Block → Cycle
```

### Axis B — Cognitive Abstraction

```text
Evidence → Reasoning → Knowledge → Judgment → Decision
```

Together, these axes define the CoachOS intelligence space.

## Current Layer Positions

The current map can be described like this:

| Layer | Training Abstraction | Cognitive Abstraction | Reasoning Responsibility |
|---|---|---|---|
| Observation | Workout | Evidence | Observe what happened |
| Execution Intelligence | Workout | Reasoning | Understand execution |
| Continuity Intelligence / WSI | Sequence | Knowledge | Preserve continuity |
| Weekly Intelligence | Week | Judgment | Evaluate progression |
| Monthly Intelligence | Block | Judgment | Understand adaptation |
| Readiness Intelligence | Cycle | Decision | Evaluate readiness |

## Visual Reading

The map can be read as a coordinate system:

```text
                    Cognitive Abstraction

Decision    ───────────────────────────────────────── Readiness
Judgment                  Weekly            Monthly
Knowledge                          WSI
Reasoning        Execution
Evidence   Observation

             Workout   Sequence   Week   Block   Cycle
                    Training Abstraction
```

This means:

- Execution sits at Workout × Reasoning
- WSI sits at Sequence × Knowledge
- Weekly sits at Week × Judgment
- Monthly sits at Block × Judgment
- Readiness sits at Cycle × Decision

## Why This Matters

This map clarifies that CoachOS layers are not only separated by training scale.

They are also separated by cognitive output.

That means:

- Execution does not just analyze today's workout
- WSI does not just read three nearby activities
- Weekly does not just summarize seven days
- Monthly does not just summarize thirty days
- Readiness does not just label a cycle phase

Each layer creates a different kind of understanding.

## Decision Horizon

A future extension of the map should include a fifth dimension:

`Decision Horizon`

This dimension would answer:

`How far forward does this layer influence training decisions?`

For example:

- Execution influences today's adjustment
- WSI influences the next workout or near sequence
- Weekly influences next-week direction
- Monthly influences the next block
- Readiness influences target-race decisions

This dimension is not yet formalized in v0.1, but the map should leave room for it.

## Relationship to Architecture

This map should be read under:

- [`CoachOS Intelligence Architecture v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Intelligence%20Architecture%20v0.1.md)

The architecture document defines what CoachOS intelligence is.

The map defines where each layer sits inside the CoachOS intelligence world.

## Relationship to Design Standard

This map should also be read together with:

- [`Intelligence Layer Design Standard v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/Intelligence%20Layer%20Design%20Standard%20v1.0.md)

The design standard defines how to build a valid intelligence layer.

The map defines how to locate that layer in the larger system.

## Relationship to Future Reference Implementations

Future reference implementations such as Workout Sequence Intelligence should use this map to explain:

- where the layer sits in training abstraction
- where the layer sits in cognitive abstraction
- what knowledge it receives
- what knowledge it creates
- what decision horizon it supports

That way, individual layer documents inherit both:

- architectural legitimacy
- spatial clarity inside the CoachOS intelligence system

## The Four Pillars

Taken together, CoachOS Intelligence governance should now be understood as four distinct but connected artifacts:

1. `CoachOS Intelligence Architecture`
   Constitution
2. `CoachOS Intelligence Map`
   Navigation map
3. `Intelligence Layer Design Standard`
   Building code
4. `Reference Intelligence Implementation`
   Golden reference

These four artifacts should remain distinct.

They solve different problems.

## Status

`CoachOS Intelligence Map v0.1`

- Status: Draft
- Scope: Intelligence-space navigation
- Classification: Governance / Intelligence Map
