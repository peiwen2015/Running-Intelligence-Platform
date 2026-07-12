# Narrative Engine Evolution v0.1

## Purpose

This artifact is not a large specification.

Its job is only to help each Narrative Engine sprint answer one question:

**What new kind of context is the engine learning to understand?**

## Evolution Map

```text
Generation 0
Human-understood
System displays
        ↓
Generation 1
Signal-aware
System interprets governed signals
        ↓
Generation 2
Time-aware
System understands sequence and period completeness
        ↓
Generation 3
Training-aware
System understands training blocks, continuity, and stimulus structure
        ↓
Generation 4
Runner-aware
System understands recovery, health, environment, and personal history
```

## Current Status

| Generation | Name | Status | Meaning |
|---|---|---|---|
| G0 | Human-understood | Historical baseline | Human coaching interpretation lived outside the engine |
| G1 | Signal-aware | Verified | Engine can interpret governed signals and produce stable Narrative Objects |
| G2 | Time-aware | Initial validation passed | `previous_theme` and `period_completeness` have been shown to change and improve monthly understanding |
| G3 | Training-aware | Next candidate | Next smallest slice should teach the engine how to read training structure |
| G4 | Runner-aware | Future | Later generations should understand recovery, health, environment, and personal patterns |

Time Context validation already showed that `previous_theme` and `period_completeness` can improve monthly interpretation, and every interpretation change can be traced back to the context that caused it. See [Time Context Shadow Report v0.1.md](/Users/perryliu/Documents/Running%20Analytics/docs/20_Architecture/Time%20Context%20Shadow%20Report%20v0.1.md).

## Generation Definitions

| Generation | What the Engine Knows | Core Question |
|---|---|---|
| G0 | No engine understanding; humans interpret | How does the human coach read this? |
| G1 | Signal | What pattern happened? |
| G2 | Signal + Time | Where does this come from, and is this story complete yet? |
| G3 | Signal + Time + Training | What role does this play inside the training cycle? |
| G4 | Signal + Time + Training + Runner | What does this mean to this runner, right now? |

## Learning Loop

```text
Boundary
   ↓
Shadow
   ↓
Gap
   ↓
Context
   ↓
Shadow
   ↓
Learning
```

The engine should not evolve by accumulating more rules alone.

It should evolve by injecting the smallest traceable context that changes understanding.

Two boundary rules already apply:

- `Inject the smallest context that changes understanding.`
- `Context refines interpretation. It does not expand ontology.`

## Architecture Principles

**The Engine should understand. The Surfaces should communicate.**

**Understanding should improve through evidence, not intuition.**

**Every interpretation change must be traceable to the context that caused it.**
