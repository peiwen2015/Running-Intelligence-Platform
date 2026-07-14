# CoachOS v1.3 Release Checklist

## Purpose

This checklist captures the release conditions for `v1.3 - Connected Coach Knowledge`.
It is the practical companion to the roadmap draft and the release notes draft.

## Release Goal

`v1.3` ships when confirmed Activity knowledge visibly changes later coaching surfaces.

## Must Pass

- [x] `v1.2.0` remains the released truth
- [x] The next milestone is named `v1.3 - Connected Coach Knowledge`
- [x] Weekly reasoning reads confirmed Coach Knowledge
- [x] Monthly reasoning reads confirmed Coach Knowledge
- [x] Weekly and Monthly AI handoff carry the same confirmed knowledge context
- [x] Activity metadata editing can start from suggested values
- [x] Metadata provenance stays visible for manual edits and coach-knowledge suggestions
- [x] The release story matches the README, launch announcement, and release notes

## Final Smoke Test

- [ ] Open a real weekly review and confirm the knowledge summary appears in the reasoning text
- [ ] Open a real monthly review and confirm the knowledge summary appears in the reasoning text
- [ ] Open Activity metadata editing and confirm suggested values prefill without hiding uncertainty
- [ ] Save a metadata edit and confirm provenance is still visible afterward
- [ ] Move between Activity, Weekly, Monthly, and metadata editing without page-jump regressions

## Release Decision

If the smoke test passes on real data, `v1.3` can be tagged and published.

If any smoke-test item fails, fix that surface first and keep `v1.3` untagged until the loop feels stable.
