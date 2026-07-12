# Narrative Engine Boundary Draft v0.1

## Position

Narrative Engine is the next architecture layer after Semantic Layer.

It is the **Source of Understanding** for the Personal Running Intelligence Platform.

Its job is not to generate pages.

Its job is to generate coach understanding.

## Knowledge Flow

```text
Reality
    ↓
Metadata Repository
    (What is true?)
    ↓
Canonical Data Model
    (How should it be represented?)
    ↓
Physical Data Layer
    (How is it stored?)
    ↓
Semantic Layer
    (What does this generally mean?)
    ↓
Narrative Engine
    (What does this mean to this runner, at this moment?)
    ↓
Surface Adapters
    Weekly / Monthly / Journey / Overview / Shoes
    ↓
Voice Layer
    (How should the coach say it?)
    ↓
Dashboard Surfaces
```

## Boundaries

### Narrative Engine

Narrative Engine reads governed facts and aggregates from the layers below it and produces structured coach understanding.

Narrative Engine may depend on:

- Metadata Repository
- Canonical Data Model
- Semantic Layer
- Runner context such as recent history, chapter position, and current training phase

Narrative Engine does not know:

- page layouts
- cards
- HTML
- CSS
- button copy
- dashboard routing

### Context Injection Rule

Context injection should follow one rule:

**Inject the smallest context that changes understanding.**

Context refines interpretation.

It does not expand ontology.

In practice, this means context should make an existing coach understanding more accurate, more situationally correct, or more temporally aware.

It should not be used to create unnecessary new themes, proliferate categories, or hide weak interpretation behind more rules.

### Surface Adapters

Surface Adapters translate the same Narrative Object into page-specific reading experiences.

Examples:

- Weekly emphasizes `Learning`
- Monthly emphasizes `Verdict`
- Journey emphasizes `Theme`
- Overview emphasizes `Recommendation`
- Shoes emphasizes equipment-specific recommendation

### Voice Layer

Voice Layer changes expression, not understanding.

It can make the same coach understanding sound warmer, clearer, or more natural.

It must never change the underlying interpretation.

## Narrative Object

The first frozen output schema for Narrative Engine is:

- `Theme`
- `Verdict`
- `Learning`
- `Recommendation`
- `Evidence`
- `Confidence`

These are not page sections.

They are coach thinking objects that can be adapted differently by each surface.

Example:

```json
{
  "theme": "Recovery",
  "verdict": "Intentional recovery",
  "learning": "Recovery is part of training.",
  "recommendation": "Reintroduce quality gradually.",
  "evidence": [
    "Training load down 15%",
    "Long run maintained"
  ],
  "confidence": "High"
}
```

## Non-goals

Narrative Engine does not:

- generate UI
- generate HTML
- generate dashboard pages
- know page order
- know card hierarchy
- rewrite understanding to match tone
- replace Semantic Layer
- invent facts not supported by Source of Truth

## Future Questions

- Should Interpretation become a separately governed layer?
- Should runner context become an explicit architecture layer?
- Should conversation continuity become its own engine later?
- How much of Voice Layer should remain deterministic before optional AI polish?

## Closing

**The Engine should understand. The Surfaces should communicate.**
