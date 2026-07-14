# CoachOS v1.2.0

CoachOS v1.2.0 is the release that formalizes the Canonical Data Model and makes the repo's core product language stable around that model.

## Highlights

- Canonical Data Model v1.2 is complete
- Final LDMs are frozen for `Activity`, `Kilometer Split`, `Shoe`, `Workout Type`, `Training Purpose`, and `Activity Training Purpose`
- `SQLite Schema v1.0` and `Semantic Layer v1.0` remain the stable product backbone
- `CoachOS` continues to present `Activity`, `Overview`, `Weekly`, and `Monthly` as the public product surfaces
- `AI 延伸分析` remains available as the external analysis handoff

## What This Release Means

This release is less about adding a new surface and more about locking in the product's shared vocabulary.

The project now has a clearer boundary between:

- governed canonical meaning
- physical SQLite storage
- semantic SQL views
- product-facing dashboard experiences

## Notes

- `Journey` still exists in the codebase, but it is not a public product surface yet
- The release tag for this version is `v1.2.0`
- The README and launch announcement now point to this release version

## Looking Ahead

The next product milestone is being formalized as `v1.3 - Connected Coach Knowledge`.

Its direction is to make confirmed Activity knowledge visible in later coaching surfaces:

- Weekly reasoning
- Monthly reasoning
- Weekly / Monthly AI handoff
- faster metadata editing through suggested values, while still requiring explicit confirmation
