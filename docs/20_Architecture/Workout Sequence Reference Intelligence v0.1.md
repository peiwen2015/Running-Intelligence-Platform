# Workout Sequence Reference Intelligence v0.1

## Purpose

This document is the first CoachOS reference intelligence implementation.

It does not exist to introduce Workout Sequence Intelligence as a product feature.

It exists to prove that CoachOS Worldview v1 can produce a better coaching explanation than activity-only analysis.

This means the purpose of this document is not:

- UI design
- prompt styling
- release planning
- ontology expansion

Its purpose is to define the first real intelligence implementation that can be validated against repeated training cases.

## Position in CoachOS

This document should be read under:

- [`CoachOS Knowledge Philosophy v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Knowledge%20Philosophy%20v0.1.md)
- [`CoachOS Intelligence Architecture v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Intelligence%20Architecture%20v0.1.md)
- [`CoachOS Intelligence Map v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Intelligence%20Map%20v0.1.md)
- [`Intelligence Layer Design Standard v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/Intelligence%20Layer%20Design%20Standard%20v1.0.md)
- [`Workout Sequence Knowledge Domain v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/20_Architecture/Workout%20Sequence%20Knowledge%20Domain%20v0.1.md)

Within that system, this document should be treated as:

- the first reference intelligence implementation
- the first practical proof of Continuity Intelligence
- the first evidence-driven test of Worldview v1

## Core Goal

The goal of Workout Sequence Reference Intelligence is:

`Prove that the CoachOS worldview can produce a better coaching explanation than activity-only analysis.`

This is a reference-intelligence goal, not a feature goal.

## Reasoning Responsibility

Workout Sequence Reference Intelligence is responsible for understanding how today's workout preserves, advances, delays, or interrupts training continuity.

It does not answer:

- how fast today's workout was
- whether today's HR was high or low in isolation
- whether this week is progressing overall
- whether this month is adapting overall

It answers:

- why today's workout belongs here
- what mission it serves between surrounding workouts
- whether that mission was fulfilled
- what continuity state it leaves for the following sequence

## Layer Contract

### Creates

This layer creates:

- continuity understanding
- mission understanding
- transition understanding
- coach-readable sequence reasoning

### Consumes

This layer consumes:

- execution understanding from Activity / Execution Intelligence
- local sequence context from surrounding workouts
- confirmed workout-purpose context where available

### Exposes

This layer exposes:

- mission category
- mission phrase
- mission status
- continuity state
- continuity reasoning

### Depends On

This layer depends on:

- Observation
- Execution Intelligence
- Workout Sequence Knowledge Domain

### Should Not Re-analyze

This layer should not re-analyze as its default path:

- raw split interpretation
- raw HR trend reading
- power drift calculation
- workout-quality judgment already created by Execution Intelligence

It may reference lower evidence for explanation or audit.

It should not recompute lower reasoning as its normal architecture path.

### Decision Quality Contribution

This layer should improve decisions such as:

- whether the next key workout is still ready to proceed
- whether today's easy run actually protected the next sequence
- whether continuity was preserved after a quality session
- whether the coach should treat the following workout as ready, delayed, or overloaded

## Map Position

This reference intelligence sits at:

- Training Abstraction: `Sequence`
- Cognitive Abstraction: `Knowledge`
- Reasoning Responsibility: `Continuity`

Its decision horizon is near-forward:

- the next workout
- the next key workout
- the following short sequence

## Knowledge Domain Mapping

This reference intelligence maps directly to the Workout Sequence knowledge domain.

The domain entities used here are:

- Workout
- Transition
- Mission
- Continuity

The working ontology used here is:

- Mission Category
- Mission Phrase
- Mission Status
- Continuity State

This document should not expand that ontology unless repeated validation proves it necessary.

## Knowledge Contract v0.1

The first stable output contract for this reference intelligence is:

### 1. Previous Workout

The most relevant prior workout or prior key state in the local sequence.

### 2. Current Workout

The current workout interpreted through execution understanding, not raw observation only.

### 3. Next Workout

The next relevant workout or next key sequence target.

### 4. Transition

The local sequence relationship.

Examples:

- Tempo -> Easy
- Rest -> Easy
- Easy -> LSD

### 5. Mission Category

Current working set:

- Recover
- Absorb
- Prepare
- Activate
- Build
- Maintain
- Validate
- Transition

### 6. Mission Phrase

Coach-readable expression of the mission.

Examples:

- Reconnect aerobic rhythm
- Prepare for long run
- Recover from accumulated fatigue
- Maintain aerobic continuity

### 7. Mission Status

Current working set:

- Completed
- Partial
- Incomplete

### 8. Continuity State

Current working set:

- Ready
- Maintained
- Delayed
- Interrupted
- Overloaded

### 9. Reasoning

A short coach-readable explanation of why the current workout did or did not fulfill its sequence mission.

## Reference Reasoning Shape

The default reasoning path should look like this:

```text
Previous Workout
    ↓
Current Workout
    ↓
Next Workout
    ↓
Transition
    ↓
Mission Category
    ↓
Mission Phrase
    ↓
Mission Status
    ↓
Continuity State
    ↓
Coach-readable Reasoning
```

This path exists to deepen understanding.

It does not exist to restate lower evidence.

## Example Cases

### Example 1

```text
Previous: HM Tempo
Current: Easy Run
Next: LSD
```

Possible reading:

- Mission Category: Activate
- Mission Phrase: Reconnect aerobic rhythm
- Mission Status: Completed
- Continuity State: Ready

Interpretation:

Today's workout was not meant to build new capacity.

Its job was to reconnect aerobic rhythm after a prior quality stimulus and leave the following long run in a prepared state.

### Example 2

```text
Previous: LSD
Current: Recovery Run
Next: Easy + Strides
```

Possible reading:

- Mission Category: Recover
- Mission Phrase: Recover from accumulated fatigue
- Mission Status: Completed
- Continuity State: Maintained

Interpretation:

Today's run protected continuity by reducing stress and preserving freshness rather than advancing workload directly.

### Example 3

```text
Previous: Rest
Current: Easy + Strides
Next: Threshold
```

Possible reading:

- Mission Category: Activate
- Mission Phrase: Reopen leg turnover
- Mission Status: Completed
- Continuity State: Ready

Interpretation:

The current workout exists to wake the body back up and prepare the next quality session without consuming too much continuity budget.

## Evidence-driven Refinement Rule

This reference intelligence should be refined through repeated real coaching cases.

It should not be expanded through conceptual completeness alone.

### Working Rule

`No ontology expansion before twenty validated sequence cases.`

This means:

- do not add new mission categories early
- do not enlarge continuity-state vocabulary casually
- do not introduce more sequence concepts unless repeated real cases demand them

The first job is to test whether the current ontology is already sufficient.

## Validation Plan v0.1

This reference intelligence should be validated through real sequence cases.

The validation question is not:

`Can WSI produce more language?`

The validation question is:

`Does this reference intelligence explain sequence meaning better than activity-only analysis?`

### Validation Targets

- at least twenty real sequence cases
- repeated use across different workout relationships
- explicit comparison against activity-only reading

### Validation Criteria

The reference intelligence should be treated as successful only if it repeatedly shows that it can:

- explain why the workout belongs here
- identify the correct mission more often than activity-only reading
- produce more coach-like continuity reasoning
- improve near-forward coaching judgment for the following sequence

## Admission Test Result

- Creates new knowledge: yes
- Consumable independently: yes
- Reduces upward reasoning burden: yes
- Exposes a stable contract: yes

## Current Status

This document should currently be treated as:

- a reference implementation target
- a validation artifact
- an evidence-driven refinement surface

It should not yet be treated as:

- a final production intelligence layer
- a frozen ontology
- a release feature specification

## Status

`Workout Sequence Reference Intelligence v0.1`

- Status: Active
- Scope: First reference implementation for Continuity Intelligence
- Classification: Architecture / Reference Intelligence Implementation
