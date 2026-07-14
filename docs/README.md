# Running Analytics Documentation

## Project Position

CoachOS is built Metadata-First.

Every data element is governed before it is implemented.

## Documentation Structure

```text
docs/
00_Governance/
    Principles

01_ADR/
    Architecture Decision Records

10_Canonical_Data_Model/
    Truth

20_Architecture/
    Thinking

30_Physical_Model/
    Implementation

40_Parser/
    Data Pipeline

50_AI/
    Intelligence

60_Excel/
    Excel Schema

```

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

## Architecture Flow

```mermaid
flowchart TD
    PRINCIPLES["Architecture Principles"]
    MR["Metadata Repository"]
    MDS["Metadata Design Standard"]
    ADR["Architecture Decision Records"]
    LDMV["LDM Validation"]
    FINAL["Final LDM"]
    ARCH["Architecture Thinking"]
    NARRATIVE["Narrative Engine"]
    MAP["SQLite Mapping Specification"]
    SQLITE["SQLite Schema"]
    SEMANTIC["Semantic Layer"]
    VOICE["Voice Layer"]
    PARSER["Parser"]
    DASH["Dashboard / AI Coach"]

    PRINCIPLES --> MR
    MR --> MDS
    MDS --> ADR
    ADR --> LDMV
    LDMV --> FINAL
    FINAL --> ARCH
    ARCH --> MAP
    MAP --> SQLITE
    SQLITE --> SEMANTIC
    SQLITE --> PARSER
    SEMANTIC --> NARRATIVE
    NARRATIVE --> VOICE
    VOICE --> DASH
```

## Reading Order

1. `Architecture Index.md`
2. `00_Governance/Architecture Principles.md`
3. `00_Governance/Product Design Principles v1.0.md`
4. `00_Governance/Journey Product Vision v0.1.md`
5. `00_Governance/Journey Experience Blueprint v0.1.md`
6. `00_Governance/Worldview Milestones.md`
7. `00_Governance/CoachOS Coach Knowledge Lineage v1.0.md`
8. `00_Governance/CoachOS Product Roadmap v1.0 Draft.md`
9. `00_Governance/Product UX Polish Sprint v1.0.md`
10. `00_Governance/Running Analytics Metadata Repository v1.1.md`
11. `00_Governance/Metadata Design Standard v1.0.md`
12. `01_ADR/`
13. `00_Governance/Canonical Data Model Release Notes.md`
14. `10_Canonical_Data_Model/Activity LDM v1.1 Final.md`
15. `10_Canonical_Data_Model/LDM Validation Round 1 - activity.md`
16. `10_Canonical_Data_Model/Kilometer Split LDM v1.1 Final.md`
17. `10_Canonical_Data_Model/LDM Validation Round 1 - kilometer_split.md`
18. `10_Canonical_Data_Model/Shoe LDM v1.1 Final.md`
19. `10_Canonical_Data_Model/LDM Validation Round 1 - shoe.md`
20. `10_Canonical_Data_Model/Workout Type LDM v1.1 Final.md`
21. `10_Canonical_Data_Model/LDM Validation Round 1 - workout_type.md`
22. `10_Canonical_Data_Model/Training Purpose LDM v1.1 Final.md`
23. `10_Canonical_Data_Model/LDM Validation Round 1 - training_purpose.md`
24. `10_Canonical_Data_Model/Activity Training Purpose LDM v1.1 Final.md`
25. `10_Canonical_Data_Model/LDM Validation Round 1 - activity_training_purpose.md`
26. `20_Architecture/Narrative Engine Boundary Draft v0.1.md`
27. `20_Architecture/Narrative Engine Evolution v0.1.md`
28. `20_Architecture/Context Gap Log v0.1.md`
29. `20_Architecture/Recovery Knowledge Model v0.1.md`
30. `20_Architecture/Load Build Knowledge Domain v0.1.md`
31. `20_Architecture/Activity Coach Knowledge Implementation Note v0.1.md`
32. `20_Architecture/Monthly Reading Pattern v0.1.md`
33. `30_Physical_Model/SQLite Mapping Specification v1.0.md`
34. `30_Physical_Model/SQLite Schema v1.0.sql`
35. `30_Physical_Model/Semantic Layer v1.0.md`

## Governance Principle

The Metadata Repository is the single source of truth.

LDM, SQLite schema, parser output, Excel schema, dashboard, and AI Coach behavior should be validated against it.
