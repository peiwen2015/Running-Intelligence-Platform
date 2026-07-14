# CoachOS Product Roadmap v1.0 Draft

## Purpose

This document is the product roadmap draft for CoachOS.

It formalizes the product version names we want to use going forward, so the release story, product story, and implementation story stay aligned.

This draft preserves the released truth of `v1.2.0` and defines the next product milestone as `v1.3 - Connected Coach Knowledge`.

## Roadmap Principle

CoachOS should evolve as a learning product, not just a data product.

The roadmap should therefore describe:

- what CoachOS learns
- how CoachOS applies that learning later
- how the runner can see the difference

The product should not claim a new version unless the runner can feel the change in later coaching surfaces.

## Version Line

```text
v1.0  Coach Review
v1.1  Product Knowledge
v1.2  Coach Knowledge
v1.3  Connected Coach Knowledge
v1.4  Coach Memory
v1.5  Coach Intelligence
```

## Version Meaning

### v1.0 - Coach Review

CoachOS established the core review surfaces:

- Activity
- Weekly
- Monthly
- AI conversation loop

The product could explain training, but it was still mostly a review surface.

### v1.1 - Product Knowledge

CoachOS established the product language and governance layer:

- interaction principles
- experience guides
- product knowledge architecture
- metadata governance mindset

This version defined how the product should think.

### v1.2 - Coach Knowledge

`v1.2.0` is already released.

Its job was to make the first learning loop real:

- Activity lets the runner confirm one thing at a time
- CoachOS learns from that confirmation
- the experience says `CoachOS 學會了`

This version proves that CoachOS can learn.

### v1.3 - Connected Coach Knowledge

This is the next product milestone.

Its job is not to add more metadata capture.

Its job is to make confirmed knowledge change later coaching.

In other words:

```text
Activity confirmation
  ↓
Coach Knowledge updates
  ↓
Weekly reasoning changes
  ↓
Monthly reasoning changes
  ↓
AI context changes
```

The core product promise is:

`A confirmed activity changes later coaching.`

The current build already implements the first connected loop:

- Weekly review reads confirmed Coach Knowledge and folds it into the weekly reasoning text
- Monthly review reads confirmed Coach Knowledge and folds it into the monthly reasoning text
- Weekly and Monthly AI handoff text both carry the same confirmed knowledge context
- Activity metadata editing can prefill likely values, but confirmation still happens explicitly

## v1.3 Definition of Done

`v1.3 - Connected Coach Knowledge` is complete when:

- Activity confirmations are visible as confirmed Coach Knowledge
- Weekly review reads confirmed knowledge, not just raw metadata
- Monthly review reads confirmed knowledge, not just raw metadata
- AI handoff text reflects the same confirmed knowledge state
- the runner can see that a confirmation made later coaching more specific or more confident
- metadata editing can start from a suggested value so tagging becomes faster, not just more explicit

## v1.3 Release Gate

`v1.3` can be released when the definition of done above is true in the real product and the following are also stable:

- the confirmed knowledge summary is readable on real weekly and monthly data
- the AI handoff text carries the same confirmed knowledge context without drift
- suggested values in Activity metadata editing are useful enough to speed up tagging without hiding uncertainty
- provenance remains visible when a field came from a coach-knowledge suggestion or a manual edit
- no major surface regresses when the user moves between Activity, Weekly, Monthly, and metadata editing

## v1.3 Non-Goals

`v1.3` is not:

- a memory system across long time spans
- a new tagging queue
- a new data synchronization layer
- a hidden metadata sync dressed up as product learning
- a replacement for manual confirmation
- a guarantee that every activity has enough context to infer a suggestion

Those belong later.

## v1.4 - Coach Memory

Once knowledge is connected across surfaces, CoachOS can start remembering patterns across time:

- repeated preferences
- recurring choices
- persistent coaching habits
- historical confidence growth

This version is about retaining what CoachOS has already learned.

## v1.5 - Coach Intelligence

CoachOS can then use stored knowledge and memory to reason more deeply:

- compare learning patterns over time
- explain why confidence changed
- make better coaching judgments from accumulated context

This version is about reasoning, not just remembering.

## Product Boundary

The roadmap should keep these ideas separate:

- `Learning` means CoachOS learns from a confirmation
- `Connection` means the learning changes later surfaces
- `Memory` means the learning persists across time
- `Intelligence` means the learning supports stronger reasoning

`v1.3` belongs to `Connection`, not `Memory`.

## Relationship to Existing Documents

This roadmap should be read together with:

- [`CoachOS Coach Knowledge Lineage v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Coach%20Knowledge%20Lineage%20v1.0.md)
- [`CoachOS Product Knowledge Architecture v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Product%20Knowledge%20Architecture%20v1.0.md)
- [`CoachOS v1.1 Coach Knowledge.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20v1.1%20Coach%20Knowledge.md)
- [`Activity Coach Knowledge Implementation Note v0.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/20_Architecture/Activity%20Coach%20Knowledge%20Implementation%20Note%20v0.1.md)

The lineage document preserves the meaning.

The implementation note preserves the surface behavior.

This roadmap turns the product direction into versioned intent.

## Status

`CoachOS Product Roadmap v1.0 Draft`

- Status: Draft
- Scope: Product version naming and product-capability direction
- Classification: Governance / Product Roadmap
