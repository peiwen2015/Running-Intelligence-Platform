# CoachOS Review Checklist v1.0

## Purpose

This checklist is used to review any CoachOS change before merge.

The goal is not to slow down work.

The goal is to make sure every meaningful change still fits the product knowledge architecture:

```text
Product Philosophy
  ↓
Interaction Principles
  ↓
Experience Guides
  ↓
Implementation
```

## Review Questions

### 1. Product Philosophy

- Does this change strengthen `Understand. Improve. Become.`?
- Does it stay aligned with `CoachOS optimizes for understanding, not information density.`?
- Does it reduce confusion rather than add more surface area?

### 2. Interaction Principles

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

### 3. Experience Guide

- Is there a clear experience guide for this surface or workflow?
- Does the user know what the system thinks, why, and what to do next?
- Is the interaction consistent with the surrounding product surfaces?
- Does the change make the workflow easier to trust?

### 4. Implementation

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

- the philosophy is clear
- the interaction is consistent
- the experience is understandable
- the implementation is aligned
- the product becomes more useful after the change

## Status

`CoachOS Review Checklist v1.0`

- Status: Active
- Scope: Product-facing changes, AI conversation flows, metadata workflows, review pages, and experience updates
- Classification: Governance / Review Standard
