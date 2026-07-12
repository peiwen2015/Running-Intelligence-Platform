# Recovery Knowledge Model v0.1

## Purpose

This is the first Coach Knowledge artifact.

Its job is not to define engine rules yet.

Its job is to define how a good running coach understands recovery.

This document is the starting point for `Coach Knowledge Sprint 1 — Recovery`.

## Core Question

**How should a good running coach understand recovery?**

## Why Recovery Exists

Recovery is not the absence of training.

Recovery exists so that training can be absorbed, fatigue can be managed, and the next block of work can remain productive.

In coaching terms, recovery may serve different purposes:

- preserve adaptation from a previous build
- reduce fatigue before it starts to distort the next training cycle
- limit damage when training rhythm is disrupted
- maintain continuity without adding new stress
- allow the body to adapt to heat or accumulated environmental load

## Recovery Types

### 1. Planned Recovery

Recovery intentionally follows a heavier block or higher-load chapter.

Its purpose is to let previous stimulus remain in the body rather than immediately replacing it with more load.

### 2. Reactive Recovery

Recovery is introduced because fatigue is accumulating faster than the current block can absorb safely.

Its purpose is to protect the next training cycle before form starts to degrade.

### 3. Forced Recovery

Recovery is not chosen as part of the ideal plan.

It is caused by interruption such as illness, travel, work strain, or other constraints.

Its purpose is damage limitation, not training optimization.

### 4. Maintenance Week

Training load softens, but continuity remains intentionally present.

Its purpose is to keep rhythm alive while avoiding unnecessary accumulation.

### 5. Heat Recovery

Recovery is shaped by environmental stress, especially when heat load is high even if formal training load is not extreme.

Its purpose is to complete adaptation rather than simply lower mileage.

## Signals

A coach may look for signals such as:

- load versus recent baseline
- distance versus recent baseline
- long-run continuity
- activity continuity
- quality-session presence or absence
- changes in load concentration
- period completeness
- recent chapter / previous theme

These signals do not explain recovery by themselves.

They only become meaningful with context.

## Context

The same signals can mean different things depending on context.

Important recovery context includes:

- what chapter came immediately before
- whether the current week or month is complete
- whether continuity is still alive
- whether quality is being removed, maintained, or reintroduced
- whether the runner is in a build, absorb, or transition phase
- whether disruption was planned or forced
- whether environmental stress is present

## Interpretation

The coach should not ask only:

`Is load down?`

The coach should ask:

`Why is load down, and what is the role of this recovery right now?`

That produces different interpretations:

| Recovery Type | Coach Interpretation |
|---|---|
| Planned Recovery | The runner is intentionally absorbing prior work. |
| Reactive Recovery | The runner needs recovery so fatigue does not distort the next block. |
| Forced Recovery | The runner is not absorbing by plan; training rhythm has been externally interrupted. |
| Maintenance Week | The runner is holding continuity without adding new stress. |
| Heat Recovery | The runner is reducing training stress so environmental adaptation can complete. |

## Evidence Shape

The coach should be able to explain recovery using both signal and context.

Examples:

- `Load down 15%` + `previous theme = load_build` + `long run maintained`
  → likely Planned Recovery

- `Load down 12%` + `quality removed` + `fatigue signals rising`
  → likely Reactive Recovery

- `Load down 40%` + `continuity broken` + `external interruption`
  → likely Forced Recovery

## What This Model Does Not Do Yet

- It does not define engine rules.
- It does not define thresholds.
- It does not define UI copy.
- It does not decide which recovery type should be shown on which surface.
- It does not pretend FIT-only data can fully distinguish planned from forced recovery.

## What Comes Next

If this knowledge model remains useful after review, the next step is to derive:

1. candidate signals for each recovery type
2. candidate context inputs for each recovery type
3. interpretation contracts:
   - verdict
   - learning
   - recommendation
   - evidence

Only after that should Recovery knowledge move into Narrative Engine candidate logic.
