# Workout Sequence Knowledge Domain v0.1

## Purpose

This is the first knowledge-domain document explicitly written under the CoachOS intelligence governance layer.

Its job is not to define UI, prompt structure, engine rules, or page behavior.

Its job is to define how CoachOS should understand workout sequence as a coaching knowledge domain.

The purpose of this domain is not to accumulate sequence concepts, but to improve how CoachOS understands sequence meaning.

This document therefore answers:

`What should CoachOS actually know about workout sequence?`

## Position in CoachOS

This domain should be read under:

- [`CoachOS Intelligence Architecture v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Intelligence%20Architecture%20v0.1.md)
- [`CoachOS Intelligence Map v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Intelligence%20Map%20v0.1.md)
- [`Intelligence Layer Design Standard v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/Intelligence%20Layer%20Design%20Standard%20v1.0.md)

Within that system, workout sequence belongs primarily to:

- Training Abstraction: `Sequence`
- Cognitive Abstraction: `Knowledge`
- Reasoning Responsibility: `Continuity`

This domain is therefore the knowledge foundation for the future Workout Sequence Intelligence layer.

## Core Question

**How should a good coach understand the meaning of today’s workout inside the surrounding training sequence?**

## Why Workout Sequence Exists

A workout sequence does not exist simply because several activities happened near each other.

A workout sequence exists because each workout changes the meaning of the workouts around it.

In coaching terms, the important question is not:

`How did today's workout perform in isolation?`

The important question is:

`Why does today's workout belong here, and what did it do to the continuity of training?`

That means workout sequence is not mainly about order.

It is about continuity.

## What This Domain Tries to Understand

Workout Sequence knowledge should help CoachOS understand:

- why a workout exists here
- what mission it serves between nearby workouts
- what kind of transition it creates
- whether continuity was preserved, advanced, delayed, or interrupted
- how today's workout changes the state of the following sequence

This domain is not trying to replace execution analysis.

It starts only after today's workout has already been understood as a workout.

## Domain Boundary

Workout Sequence knowledge is about sequence meaning.

It is not about:

- split-level execution details
- raw HR analysis
- one-workout pacing judgment
- weekly narrative as a whole
- monthly adaptation as a whole

Those belong to other layers.

Workout Sequence knowledge begins after Activity Intelligence has already created execution knowledge.

## Domain Entities

The core entities in this domain are:

### 1. Workout

A workout is the local training event being placed into sequence context.

In this domain, a workout is not treated mainly as raw evidence.

It is treated as a unit that already carries execution meaning.

### 2. Transition

A transition is the relationship between surrounding workouts.

Examples:

- Recovery -> Easy
- Easy -> Tempo
- Tempo -> Rest
- Rest -> Easy
- Easy -> LSD

Transition is the method through which sequence meaning becomes visible.

### 3. Mission

Mission is the intended role of the current workout inside the surrounding sequence.

Mission answers:

- what today is supposed to do
- why it belongs here
- what continuity work it is performing

### 4. Continuity

Continuity is the real object being protected, advanced, or disrupted.

Continuity answers:

- whether training rhythm is still coherent
- whether nearby work still connects productively
- whether the following sequence is now in a better or worse state

## Domain Principle

Workout Sequence knowledge evaluates training continuity through workout transitions.

Transition is the method.

Continuity is the purpose.

## Mission Categories

These categories are the current working set for this domain.

They should remain small and stable until repeated real-case use proves a need to expand them.

### 1. Recover

Purpose:

- reduce accumulated fatigue
- restore freshness
- protect continuity by lowering stress

Typical context:

- Tempo -> Easy
- Long Run -> Recovery
- Race -> Recovery

### 2. Absorb

Purpose:

- convert previous stress into adaptation
- preserve the value of a prior stimulus

Typical context:

- Tempo -> Rest
- Quality block -> easier follow-up day

### 3. Prepare

Purpose:

- create the right state for the next key workout

Typical context:

- Easy -> LSD
- Easy -> Threshold
- Easy -> Interval

### 4. Activate

Purpose:

- wake the body back up
- reconnect rhythm
- restore running feel

Typical context:

- Rest -> Easy
- Recovery -> Easy + Strides

### 5. Build

Purpose:

- create new ability directly

Typical context:

- Tempo
- Marathon Pace
- Interval
- Long Run with specific training intent

### 6. Maintain

Purpose:

- preserve continuity without materially changing stress direction

Typical context:

- stable aerobic support days
- consistency-preserving easy days

### 7. Validate

Purpose:

- check whether a capability or readiness claim is true

Typical context:

- benchmark session
- tune-up race
- race simulation

### 8. Transition

Purpose:

- change training state without yet fully becoming recovery, build, or validation

Typical context:

- lighter bridging day between two qualitatively different workloads

## Mission Phrase

Mission category should remain more stable than mission phrase.

Mission phrase is the coach-readable expression of the mission.

Examples:

| Mission Category | Mission Phrase |
|---|---|
| Activate | Reconnect aerobic rhythm |
| Activate | Reopen leg turnover |
| Prepare | Prepare for long run |
| Prepare | Prepare for threshold |
| Build | Build threshold durability |
| Build | Build marathon pace |
| Maintain | Maintain aerobic continuity |
| Recover | Recover from accumulated fatigue |
| Absorb | Absorb previous stimulus |
| Validate | Validate threshold fitness |

Category is ontology.

Phrase is surface language.

## Mission Status

Mission Status answers:

`Did today's workout fulfill the role it was supposed to play?`

Current working set:

- Completed
- Partial
- Incomplete

This should remain intentionally small in early versions.

## Continuity State

Continuity State answers:

`What state did today's workout leave the following sequence in?`

Current working set:

- Ready
- Maintained
- Delayed
- Interrupted
- Overloaded

This is not the same as mission status.

A workout may complete its own mission but still leave the following sequence in a worse state than intended.

That distinction is one of the most important ideas in this domain.

## Example Readings

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

The current workout was not meant to build new capacity.

It was meant to reconnect aerobic rhythm after prior stress so the long run can still happen productively.

### Example 2

```text
Previous: Threshold
Current: Rest Day
Next: Easy Run
```

Possible reading:

- Mission Category: Absorb
- Mission Phrase: Absorb previous stimulus
- Mission Status: Completed
- Continuity State: Maintained

Interpretation:

The rest day exists to let the prior stress remain meaningful, not simply to insert empty time.

### Example 3

```text
Previous: Rest
Current: Easy Run run too hard
Next: Long Run
```

Possible reading:

- Mission Category: Prepare
- Mission Phrase: Prepare for long run
- Mission Status: Partial
- Continuity State: Overloaded

Interpretation:

The workout happened, but it did not leave the next sequence in the intended state.

## Signals

Workout Sequence knowledge may use signals such as:

- previous workout type
- current workout type
- next key workout type
- spacing between workouts
- whether the previous workout was key, support, recovery, or rest
- whether the next workout is key, support, recovery, or rest
- current execution summary
- continuity of recent load
- environmental stress context

These are supporting signals only.

They do not define the domain by themselves.

## Context

The same workout may serve very different sequence missions depending on context.

Important context includes:

- what immediately came before
- what is expected next
- whether the current day is a bridge, support, or key day
- whether continuity is already fragile
- whether the sequence is inside build, absorb, or maintenance rhythm
- whether environmental stress is distorting the intended sequence

## Failure Modes

This domain should explicitly recognize failure modes such as:

- reading a workout in isolation and missing its sequence meaning
- confusing execution success with continuity success
- assuming the next workout is the only thing affected
- treating all easy runs as the same mission
- treating rest as empty space instead of meaningful sequence function
- collapsing transition interpretation back into raw split analysis

## What This Domain Does Not Do Yet

- It does not define engine rules.
- It does not define thresholds.
- It does not define final ontology boundaries.
- It does not define product copy for UI.
- It does not define prompt wording.
- It does not assume all sequence missions can be inferred from FIT-only data.

## What Comes Next

If this domain remains useful after review, the next step is to derive:

1. a formal knowledge contract for Workout Sequence Intelligence
2. candidate transition patterns
3. candidate mission-category assignment logic
4. candidate continuity-state rules
5. example reasoning outputs for real sequence cases

Only after that should this domain move into a reference intelligence implementation.
