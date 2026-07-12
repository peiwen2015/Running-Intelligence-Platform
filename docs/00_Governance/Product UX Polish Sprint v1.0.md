# Product UX Polish Sprint

## Purpose

Move the product from a functional dashboard to a cohesive coaching experience.

The goal is not to add more features.

The goal is to make every product surface feel like the same coach is speaking.

This document belongs in Governance because it defines a product quality standard, not a temporary sprint backlog.

From Dashboard App v0.5 onward, new product surfaces should be reviewed against this standard.

## Sprint Goal

Transform the Personal Running Intelligence Platform from:

`Analytics Dashboard`

into:

`Coach Workspace`

by improving consistency, readability, and coaching experience.

## Relationship to Product Design Principles

If `Product Design Principles v1.0` defines:

`What a coaching product should believe`

then this document defines:

`How that belief becomes a real user experience`

## Design Themes

### Theme 1: Coach Language

Replace BI language with coaching language.

Examples:

| Current | Future |
|---|---|
| Slightly Behind | 可追回 |
| Ahead | 超前進度 |
| Normal | 穩定累積 |
| Confidence: Medium | 信心水準：中（因本月完成 32%） |
| Load Delta | 訓練負荷狀態 |

The user should feel that a coach is speaking.

Not a reporting system.

### Theme 2: Information Hierarchy

Every page follows:

```text
Verdict
  ↓
Reason
  ↓
Recommendation
  ↓
Evidence
  ↓
Exploration
```

Never:

```text
Metrics
  ↓
More Metrics
  ↓
User guesses
```

### Theme 3: Visual Hierarchy

Review:

- Typography
- Card priority
- White space
- Icon consistency
- Progress indicators
- Color meaning

The first screen should answer:

`What is my current state?`

within five seconds.

### Theme 4: Product Consistency

All modules should feel like one coach.

Review:

- Overview
- Weekly Review
- Monthly Coaching Review
- Shoes
- Training
- Metadata

The wording, tone, and interaction should remain consistent.

### Theme 5: Product Polish

Review:

- Empty State
- Loading State
- Error State
- Responsive Layout
- Hover State
- Click Feedback
- Card Alignment

## First Sprint Tasks

### Monthly Coaching Review

- Refine coaching wording
- Replace BI status labels
- Improve signal language
- Improve recommendation wording

### Shoes

- Refine shoe intelligence language
- Emphasize coaching insight
- Reduce raw metric focus

### Training

- Improve metadata quality explanation
- Make training balance easier to understand

### Global

- Consistent icons
- Consistent spacing
- Consistent typography
- Consistent status chips

## Definition of Done

The product passes UX Polish Sprint when:

- Users understand their current state within five seconds.
- Coaching language is consistent across all modules.
- Product pages answer:
  - Current state
  - Why
  - What next
- Raw metrics become supporting evidence instead of primary content.
- Every page feels like it is written by the same coach.

## Product Quality Standard

This document should be used as a recurring review standard for product-facing work.

It is not limited to a single dashboard milestone.

It should guide:

- Dashboard App
- future AI Coach surfaces
- review pages
- recommendation modules
- metadata workflows that affect user trust

## Vision

A runner should leave every page with more confidence than when they entered it.

Truly useful coaching products do more than report data.

They help the runner understand their state, trust the explanation, and feel clear about the next step.

## Status

`Product UX Polish Sprint v1.0`

- Status: Active
- Scope: Dashboard App, future AI Coach, and all product-facing coaching surfaces
- Classification: Governance / Product Quality Standard
