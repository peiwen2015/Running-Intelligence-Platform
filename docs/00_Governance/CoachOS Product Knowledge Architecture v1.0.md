# CoachOS Product Knowledge Architecture v1.0

## Purpose

This document defines the high-level knowledge structure of CoachOS.

CoachOS is not only a product.

It is also a product knowledge system that preserves why decisions are made, how the product should behave, what each surface should do, and how implementation should follow.

## The Four Layers

### 1. Product Philosophy

This layer answers:

- Why does CoachOS exist?
- What does the product believe?
- What should the product optimize for?

Representative documents:

- `Product Design Principles v1.0`
- `Product UX Polish Sprint v1.0`

### 2. Interaction Principles

This layer answers:

- How should CoachOS behave across all surfaces?
- How should the product help the runner understand and decide?
- What interaction patterns should remain consistent?

Representative documents:

- `CoachOS Interaction Principles v1.0`

### 3. Experience Guides

This layer answers:

- What should a specific product surface feel like?
- How should a workflow be shaped?
- What should the runner see and do in that context?

Representative documents:

- `Metadata Tagging Experience v1.0`
- future Journey experience chapters
- future AI Conversation Loop guides

### 4. Implementation

This layer answers:

- How is the product actually built?
- Which files, views, and UI surfaces implement the experience?
- How does the code stay aligned with the higher-level principles?

Representative documents:

- Application code in `analysis_platform/`
- Physical model documents
- Semantic Layer documents
- SQLite schema and mapping documents

## Reading Order

The recommended reading order for design work is:

```text
Product Philosophy
  ↓
Interaction Principles
  ↓
Experience Guides
  ↓
Implementation
```

If a design decision is only visible at the implementation level, but it should change how the product thinks, the decision should move upward into the relevant knowledge layer.

## Product Pattern

Across all layers, CoachOS should optimize for:

- understanding before density
- verdict before evidence
- suggestion before ask
- confidence before assumption
- improvement after every action

## Review Standard

Product-facing changes should be checked against:

- `CoachOS Review Checklist v1.0`
- `CoachOS Interaction Principles v1.0`
- `Metadata Tagging Experience v1.0` when the change affects metadata or knowledge workflows

## Status

`CoachOS Product Knowledge Architecture v1.0`

- Status: Draft
- Scope: Product philosophy, interaction principles, experience guides, and implementation alignment
- Classification: Governance / Knowledge Architecture
