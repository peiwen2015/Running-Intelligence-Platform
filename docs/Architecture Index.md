# Architecture Index

## Purpose

This index is the architecture dashboard for CoachOS.

It summarizes the current status of governance artifacts, canonical models, architecture design layers, physical models, parser, Excel schema, and application layers.

At this stage, CoachOS worldview v1 should be treated as established.

The priority now is not to add more governance abstractions.

The priority now is to validate more real training cases using the same canonical language and the same understanding-first architecture.

## Architecture Knowledge Base

```text
Governance
    ↓
Decision Records
    ↓
Canonical Data Model
    ↓
Architecture
    ↓
Implementation
    ↓
Application
```

## Artifact Status

| Artifact | Current Version | Role | Stability | Location |
|---|---:|---|---|---|
| Metadata Repository | v1.1 | Governance | Stable | `00_Governance/Running Analytics Metadata Repository v1.1.md` |
| Metadata Design Standard | v1.0 | Governance | Stable | `00_Governance/Metadata Design Standard v1.0.md` |
| CoachOS Knowledge Philosophy | v0.1 | Foundational | Stable | `00_Governance/CoachOS Knowledge Philosophy v0.1.md` |
| CoachOS Intelligence Architecture | v0.1 | Foundational | Stable | `00_Governance/CoachOS Intelligence Architecture v0.1.md` |
| CoachOS Intelligence Map | v0.1 | Foundational | Stable | `00_Governance/CoachOS Intelligence Map v0.1.md` |
| Intelligence Layer Design Standard | v1.0 | Foundational | Stable | `00_Governance/Intelligence Layer Design Standard v1.0.md` |
| CoachOS Product Knowledge Architecture | v1.0 | Governance | Evolving | `00_Governance/CoachOS Product Knowledge Architecture v1.0.md` |
| CoachOS Interaction Principles | v1.0 | Governance | Evolving | `00_Governance/CoachOS Interaction Principles v1.0.md` |
| CoachOS Review Checklist | v1.0 | Governance | Stable | `00_Governance/CoachOS Review Checklist v1.0.md` |
| CoachOS v1.1 Coach Knowledge | Draft | Product theme | Historical | `00_Governance/CoachOS v1.1 Coach Knowledge.md` |
| CoachOS Coach Knowledge Lineage | v1.0 | Governance | Stable | `00_Governance/CoachOS Coach Knowledge Lineage v1.0.md` |
| CoachOS Product Roadmap | v1.0 Draft | Governance | Evolving | `00_Governance/CoachOS Product Roadmap v1.0 Draft.md` |
| Activity Coach Knowledge Implementation Note | v0.1 | Implementation note | Evolving | `20_Architecture/Activity Coach Knowledge Implementation Note v0.1.md` |
| Metadata Tagging Experience | v1.0 | Governance | Evolving | `00_Governance/Metadata Tagging Experience v1.0.md` |
| Architecture Principles | v1.0 | Governance | Stable | `00_Governance/Architecture Principles.md` |
| Product Design Principles | v1.0 | Foundational | Stable | `00_Governance/Product Design Principles v1.0.md` |
| Journey Product Vision | v0.1 | Product vision | Evolving | `00_Governance/Journey Product Vision v0.1.md` |
| Journey Experience Blueprint | v0.1 | Product blueprint | Evolving | `00_Governance/Journey Experience Blueprint v0.1.md` |
| Worldview Milestones | v1.0 | Governance | Stable | `00_Governance/Worldview Milestones.md` |
| Product UX Polish Sprint | v1.0 | Working plan | Evolving | `00_Governance/Product UX Polish Sprint v1.0.md` |
| Architecture Roadmap | v1.0 | Governance | Evolving | `00_Governance/Architecture Roadmap.md` |
| Architecture Decision Records | 5 records | Decision record | Stable | `01_ADR/` |
| Canonical Data Model Release Notes | v1.0 | Governance | Stable | `00_Governance/Canonical Data Model Release Notes.md` |
| Narrative Engine Boundary Draft | v0.1 | Architecture draft | Evolving | `20_Architecture/Narrative Engine Boundary Draft v0.1.md` |
| Narrative Engine Evolution | v0.1 | Architecture note | Evolving | `20_Architecture/Narrative Engine Evolution v0.1.md` |
| Context Gap Log | v0.1 | Architecture note | Evolving | `20_Architecture/Context Gap Log v0.1.md` |
| Recovery Knowledge Model | v0.1 | Knowledge domain | Active | `20_Architecture/Recovery Knowledge Model v0.1.md` |
| Load Build Knowledge Domain | v0.1 | Knowledge domain | Active | `20_Architecture/Load Build Knowledge Domain v0.1.md` |
| Monthly Reading Pattern | v0.1 | Knowledge domain | Active | `20_Architecture/Monthly Reading Pattern v0.1.md` |
| Coach Letter Review | v0.1 | Knowledge domain | Evolving | `20_Architecture/Coach Letter Review v0.1.md` |
| Monthly Editorial Findings | v0.1 | Knowledge domain | Evolving | `20_Architecture/Monthly Editorial Findings v0.1.md` |
| Monthly Coach Briefing | v0.1 | Product draft | Evolving | `20_Architecture/Monthly Coach Briefing v0.1.md` |
| Workout Sequence Knowledge Domain | v0.1 | Knowledge domain | Active | `20_Architecture/Workout Sequence Knowledge Domain v0.1.md` |
| Workout Sequence Reference Intelligence | v0.1 | Reference intelligence | Active | `20_Architecture/Workout Sequence Reference Intelligence v0.1.md` |
| Workout Sequence Intelligence Validation | v0.1 | Training working document | Active | `20_Architecture/Workout Sequence Intelligence Validation v0.1.md` |
| Activity LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Activity LDM v1.1 Final.md` |
| Activity LDM Validation | Round 1 | Validation record | Stable | `10_Canonical_Data_Model/LDM Validation Round 1 - activity.md` |
| Kilometer Split LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Kilometer Split LDM v1.1 Final.md` |
| Shoe LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Shoe LDM v1.1 Final.md` |
| Shoe LDM Validation | Round 1 | Validation record | Stable | `10_Canonical_Data_Model/LDM Validation Round 1 - shoe.md` |
| Workout Type LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Workout Type LDM v1.1 Final.md` |
| Workout Type LDM Validation | Round 1 | Validation record | Stable | `10_Canonical_Data_Model/LDM Validation Round 1 - workout_type.md` |
| Training Purpose LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Training Purpose LDM v1.1 Final.md` |
| Training Purpose LDM Validation | Round 1 | Validation record | Stable | `10_Canonical_Data_Model/LDM Validation Round 1 - training_purpose.md` |
| Activity Training Purpose LDM | v1.1 | Canonical model | Stable | `10_Canonical_Data_Model/Activity Training Purpose LDM v1.1 Final.md` |
| Activity Training Purpose LDM Validation | Round 1 | Validation record | Stable | `10_Canonical_Data_Model/LDM Validation Round 1 - activity_training_purpose.md` |
| SQLite Mapping Specification | v1.0 | Physical model | Stable | `30_Physical_Model/SQLite Mapping Specification v1.0.md` |
| SQLite Schema | v1.0 | Physical model | Stable | `30_Physical_Model/SQLite Schema v1.0.sql` |
| Semantic Layer | v1.0 | Semantic model | Active | `30_Physical_Model/Semantic Layer v1.0.md` |
| SQLite Importer / Parser | Internal milestone E2E-002 | Implementation | Active | Project root |
| Excel Schema | v1.1 | File schema | Stable | `40_Excel/` |
| Query Layer | v1.0 | Implementation | Active | `analysis_platform/` |
| CoachOS | v1.2.0 | Product release line | Evolving | Project root |
| Dashboard App | v0.4.12-alpha | Implementation | Active | `analysis_platform/dashboard_app.py` |
| AI Coach | Not released | Product concept | Evolving | `50_AI/` |

## Current Architecture Maturity

| Area | Status |
|---|---|
| Metadata Governance | Complete for v1.1 |
| Design Standard | Complete for v1.0 |
| ADR Process | Established |
| LDM Validation Process | Established |
| Final LDM Release Process | Established |
| Architecture Thinking Layer | Narrative Engine is established, the first two Coach Knowledge domains exist, and Monthly now has an explicit reading pattern before rendering |
| Activity LDM | Production-ready |
| Remaining Core LDMs | Core Canonical Data Layer v1.0 complete for Activity, Kilometer Split, Shoe, Workout Type, Training Purpose, and Activity Training Purpose |
| SQLite Mapping Specification | v1.0 complete for Core Canonical Data Layer |
| SQLite Schema | v1.0 generated, syntax/view verified, and real-data verified |
| Semantic Layer | v1.0 now includes review, monthly, weekly, journey, distribution, shoe, training, tagged shoe intelligence, and recent-activity semantic views |
| Parser Alignment | Internal milestone E2E-002 imports real data into the six-table SQLite Schema v1.0 |
| Dashboard App | v0.4.12-alpha now reads Semantic Layer views for Journey, Overview, Monthly Coaching Review, Weekly Review, Shoes, Training, and tagged shoe intelligence surfaces, with Weekly refined toward a more review-like coaching surface |
| AI Coach | Pending |

## Next Recommended Work

1. Expand Semantic Layer only when a product question is reused across dashboard or query surfaces.
2. Keep Query Layer and Dashboard aligned to Semantic Layer instead of direct canonical table queries.
3. Keep parser/importer behavior aligned with Metadata Repository and SQLite Schema v1.0.

## Current Cadence

- Foundational governance artifacts should be treated as stable unless a change clearly improves understanding quality or decision quality.
- Knowledge-domain artifacts should be treated as active and case-tested rather than expanded casually.
- New abstractions should be avoided when refinement of existing concepts is sufficient.
- Review should include a canonical language check before merge.
- Worldview v1 is now considered stable. Future changes should be driven primarily by repeated real-world coaching cases rather than additional conceptual abstraction.

## Current Milestone

| Milestone | Status | Success Criteria | Next Milestone |
|---|---|---|---|
| Worldview v1 Established | Completed | Knowledge Philosophy stable; Intelligence Architecture stable; Intelligence Map stable; Design Standard stable; Canonical Language established; Review discipline aligned | CoachOS Intelligence Training Phase |
