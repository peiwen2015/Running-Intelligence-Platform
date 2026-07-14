# CoachOS Coach Knowledge Lineage v1.0

## Purpose

This note preserves the early `Coach Knowledge` thread and shows how it evolved into later governance, metadata, and product architecture documents.

It is not a release note.

It is not a technical spec.

It is a lineage record for a product idea that shaped the system.

## Origin Thread

`CoachOS v1.1 - Coach Knowledge` introduced the first explicit learning loop:

```text
CoachOS doesn't know
  ↓
CoachOS thinks
  ↓
Runner confirms
  ↓
CoachOS learns
  ↓
Weekly becomes better
```

The original emphasis was:

- coach language instead of form language
- one learning at a time
- suggestion before ask
- explanation before trust
- confirmation as learning, not paperwork

## What It Was Trying to Solve

The early problem was not data capture.

The problem was trust in coaching assistance.

CoachOS needed to help the runner feel that:

- the system could make a reasonable guess
- the guess had a reason
- the runner could correct it easily
- the correction would improve later reasoning

That is the core of the learning loop.

## Lineage Map

```text
CoachOS v1.1 - Coach Knowledge
  ↓
CoachOS Interaction Principles v1.0
  ↓
Metadata Tagging Experience v1.0
  ↓
Running Analytics Metadata Repository v1.1
  ↓
Canonical Data Model / Final LDMs
  ↓
Semantic Layer v1.0
  ↓
Dashboard / CoachOS surfaces
```

## What Survived

The following ideas are now clearly present in later governance:

- `Verdict Before Evidence`
- `Suggest Before Ask`
- `Confidence Must Be Visible`
- `Every Action Should Improve Understanding`
- `Missing Information Should Become the Next Best Action`
- `Be Honest About Uncertainty`
- `History Should Teach`
- `The Product Should Learn With Me`

These are no longer just interaction ideas.

They are part of the product's governing language.

## Where Each Idea Landed

### 1. Interaction Principles

[`CoachOS Interaction Principles v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Interaction%20Principles%20v1.0.md)

This document made the learning loop general.

It broadened the early Coach Knowledge idea into a reusable product standard across:

- Overview
- Weekly
- Monthly
- Activity
- Shoes
- AI Conversation Loop
- metadata workflows

### 2. Metadata Tagging Experience

[`Metadata Tagging Experience v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/Metadata%20Tagging%20Experience%20v1.0.md)

This document applied the learning-loop idea to real tagging workflows.

It translated the concept into:

- `What is already known?`
- `What is most likely correct?`
- `What is still missing?`
- `What should I do next?`

Its practical reading is simple:

`Coach Knowledge` exists so tagging becomes a learning loop that helps CoachOS understand the runner better.

### 3. Metadata Repository

[`Running Analytics Metadata Repository v1.1.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/Running%20Analytics%20Metadata%20Repository%20v1.1.md)

This document turned the product idea into governed truth.

The repository became the SSOT for:

- Excel schema
- LDM
- SQLite schema
- parser design
- dashboard and AI coach design

### 4. Product Knowledge Architecture

[`CoachOS Product Knowledge Architecture v1.0.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Product%20Knowledge%20Architecture%20v1.0.md)

This document gave the early idea a durable structure.

It separated:

- product philosophy
- interaction principles
- experience guides
- implementation

That separation is why the original Coach Knowledge idea could evolve without staying trapped inside one page or one workflow.

## What Changed Over Time

The original idea was a page-level learning loop.

Later the project became more structural:

- first the product learned how to tag and remember
- then the metadata became governed
- then the canonical model became complete
- then the semantic layer carried product meaning
- then the dashboard could consume stable meaning instead of re-deriving it

So the idea expanded from:

`How should this page learn?`

to:

`How should the whole product learn?`

## Current Reading

In the current architecture, `Coach Knowledge` should be read as the ancestor of:

- coaching-aware tagging
- suggest-before-ask flows
- confidence display
- learning from confirmation
- metadata-backed product intelligence

It is still relevant.

It just no longer lives as a standalone surface idea.

## Relationship to Current Roadmap

The product roadmap draft now formalizes the next product milestone as `v1.3 - Connected Coach Knowledge`.

The architecture roadmap still emphasizes:

- `v1.2` Canonical Data Model complete
- `v1.3` SQLite schema stable
- `v1.32` Semantic Layer v1.0
- `v1.4` Parser stable against Metadata Repository

The early Coach Knowledge thread sits underneath all of those milestones, while the product roadmap gives the learning loop a product-facing version name.

It explains why the architecture is metadata-first and why the product cares so much about governed meaning.

## Status

`CoachOS Coach Knowledge Lineage v1.0`

- Status: Active
- Scope: Historical lineage and product meaning preservation
- Classification: Governance / Knowledge Lineage
