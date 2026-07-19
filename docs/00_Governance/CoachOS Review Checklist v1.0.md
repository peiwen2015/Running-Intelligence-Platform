# CoachOS Review Checklist v1.0

## Purpose

This checklist is used to review any CoachOS change before merge.

The goal is not to slow down work.

The goal is to make sure every meaningful change still fits the current CoachOS governance stack:

```text
Manifesto
  ↓
Knowledge Philosophy
  ↓
Intelligence Architecture
  ↓
Knowledge Domains
  ↓
Implementation
```

## Review Questions

### 1. Knowledge Philosophy

- Does this change deepen understanding rather than only add information?
- Does it keep understanding as the goal and treat knowledge as reusable understanding rather than an end in itself?
- Does it prefer refinement over expansion when a new abstraction would not improve understanding or decision quality?

### 2. Intelligence Architecture

- Does the change respect reasoning responsibility instead of mixing multiple layers together?
- Does it deepen understanding rather than repeat lower-layer analysis?
- Does it move reasoning upward while keeping evidence downward?
- Does it create reusable understanding that upper layers can reliably consume?

### 3. Interaction Principles

- Does it follow `Verdict Before Evidence`?
- Does it follow `Fast Before Perfect`?
- Does it follow `Suggest Before Ask`?
- Does it keep `Confidence Must Be Visible`?
- Does every action improve understanding?
- Does missing information become the next best action?
- Does it teach from history?
- Does the product learn with the runner?
- Does it stay honest about uncertainty?
- Does it avoid unnecessary information density?

### 4. Experience Guide

- Is there a clear experience guide for this surface or workflow?
- Does the user know what the system thinks, why, and what to do next?
- Is the interaction consistent with the surrounding product surfaces?
- Does the change make the workflow easier to trust?

### 5. Canonical Language Check

- Is `Evidence` used only for what was observed?
- Is `Understanding` used for what CoachOS can currently explain?
- Is `Knowledge` used only for understanding that is stable enough to preserve and reuse?
- Is `Judgment` used for evaluation rather than raw interpretation?
- Is `Decision` used only for next-step action rather than analysis output?
- Are `Mission`, `Continuity`, and `Reasoning Responsibility` used consistently with the architecture?
- If `Canonical` appears, does it mean `stable enough to build upon` rather than `permanent truth`?

### 6. Implementation

- Is the implementation aligned with the governing documents?
- Is the relevant semantic layer or shared logic used where appropriate?
- Is the code duplicating meaning that should live in a higher layer?
- Are the tests, data, or UI states covered well enough?

## Data And Trust

- Does the change improve tagging, coverage, or contextual understanding?
- Does it avoid inventing facts that are not governed?
- Does it preserve traceability?
- Does it make future AI or coaching output better rather than noisier?

## Merge Gate

A change should be ready to merge when:

- the knowledge philosophy is preserved
- the intelligence responsibility is clear
- the language is canonical
- the interaction is consistent
- the implementation is aligned
- the product becomes easier to understand and more useful after the change

## Status

`CoachOS Review Checklist v1.0`

- Status: Active
- Scope: Product-facing changes, AI conversation flows, metadata workflows, review pages, and experience updates
- Classification: Governance / Review Standard
