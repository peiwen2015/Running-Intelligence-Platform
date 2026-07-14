# Metadata Tagging Experience v1.0

## Purpose

This chapter shows how CoachOS Interaction Principles v1.0 apply to metadata tagging.

The goal is not to add more fields.

The goal is to make `workout type`, `training purpose`, and `shoe` tagging feel like a helpful part of understanding the runner.

Coach Knowledge's final purpose is to make tagging a learning process, not an admin task:

- tagging should happen faster
- tagging should be easier to trust
- tagging should teach CoachOS something useful
- tagging results should improve later coaching

## Product Goal

CoachOS should make metadata tagging feel like part of the coaching workflow, not a separate admin task.

When a runner opens an activity or batch review page, the product should help answer:

- What is already known?
- What is most likely correct?
- What is still missing?
- What should I do next?

## Applied Principles

This chapter applies the broader CoachOS Interaction Principles in the tagging workflow:

- Verdict Before Evidence
- Fast Before Perfect
- Suggest Before Ask
- Confidence Must Be Visible
- Every Action Should Improve Understanding
- Missing Information Should Become the Next Best Action
- History Should Teach
- The Product Should Learn With Me
- Be Honest About Uncertainty

## Proposed Experience

### Activity Page

- Show a compact tagging panel beside the activity review.
- Pre-fill likely values from recent history when possible.
- Offer a `Use last similar` action for workout type, purpose, and shoe.
- Show a small note explaining why the suggestion appeared.

### Metadata Page

- Sort untagged or incomplete activities by likely impact first.
- Show a `Next best to tag` queue.
- Keep batch editing, but make single-activity correction easier to reach.
- After save, show what improved:
  - coverage
  - remaining gaps
  - next best queue item

### Batch Workflow

- Keep batch editing for efficient cleanup.
- Use it for repetitive fixes, not for every decision.
- Show whether the batch changed a core signal or only a display field.

## Governance Rules

- Suggestions must never overwrite governed metadata without confirmation.
- The system may recommend values, but only the user may confirm them.
- Uncertain values should remain explicitly uncertain rather than forced into a false category.
- Metadata changes should be traceable to the activity and the saved action.

## Success Criteria

This experience is working when:

- tagging common activities takes less time
- users trust the system suggestions
- more activities reach full tagging
- AI replies can rely on richer context
- weekly and monthly review feel more complete

## Status

`Metadata Tagging Experience v1.0`

- Status: Draft
- Scope: Activity page, Metadata page, batch tagging, and coaching-aware suggestion flows
- Classification: Governance / Product Experience Chapter
