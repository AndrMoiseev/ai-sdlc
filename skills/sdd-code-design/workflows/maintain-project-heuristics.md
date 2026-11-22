# Maintain project heuristics

Use this workflow when the user or calling task asks to assess a review comment
for reuse, record the agreed lesson or compare project heuristics with shared
guidance. Start at the requested heading. The [file contract](../references/project-heuristics.md)
defines project paths, entries and grouping.

## Assess a review comment

If the discussion has already settled the wording to record, use that decision
and continue at [Record agreed wording](#record-agreed-wording).

1. Recover the disputed decision, the expected result and the requirements in force
   when it was made. Distinguish an existing requirement from a preference or a
   requirement first introduced in review. Reuse an adequate prior diagnosis.
   For an unresolved claim about code or design, use [focused diagnosis](diagnose-code.md#establish-a-consequential-finding)
   on the relevant source and consumers.
2. Give the strongest supported reason to keep the original choice. Compare it with
   the reviewer's alternative under the same conditions. Trace who would see a
   material difference, in which quality property, at what cost, and what evidence
   could reverse the judgment. Evaluate the objection and the proposed remedy
   separately. Distinguish an observed effect from a predicted risk.
   If the original choice stands, or a missing fact prevents a decision, report the
   reason and finish the discussion there.
3. For a justified correction, identify a cue the next agent could recognize
   **before** making the choice. Name another decision affected by the same
   mechanism and a nearby case where the advice would be wasteful or harmful.
   Weigh likely reuse and the cost of the mistake against the cost of misleading
   prompts. One serious case can justify a local entry. For a one-off correction,
   return the case-specific recommendation and stop.
4. Compare the cue, action and boundary with relevant project and shared guidance.
   Point to an existing entry if it already guides the decision. Identify a
   missed cue when supported by the review. Propose a refinement if a local
   cue or exception adds information the next agent would need. Propose a new
   entry for an uncovered decision. When the selected remedy is an enforceable
   constraint and the task authorizes a gate, use [operationalize a finding](operationalize-finding.md).

### Record agreed wording

In a direct maintenance task, save the wording the user has agreed to record.
If the user asked only for an assessment, return the conclusion and any proposed
entry. In a read-only assignment, return the proposal and its destination to the caller.

## Compare project and shared heuristics

Start with the project's entry point. If it is absent, report that there are no
project entries to compare. Otherwise use its inline entries or, for a grouped
collection, visit each group in the requested scope once. Compare each entry
against the relevant bundled guidance in the skill version available to this
project. Compare the choice an agent would make, including its conditions and
exceptions. Similar wording alone is weak evidence of coverage.

| Finding | Proposal |
| --- | --- |
| The choice depends on a project condition | Keep the local entry or narrow it to the condition that matters. |
| The available shared guidance covers the cue, action and boundary | Identify the covering section and propose removing the duplicate. Retain any useful local cue or exception with a reference to that section. |
| The rationale could change a decision in another setting and shared guidance has a gap | Propose wording for the shared source, name the receiving situation, the evidence for transfer and a limit. Mark untested transfer as a hypothesis. |
| The project conditions or evidence have changed | Identify what changed and propose revising or retiring the entry. |

Return the comparison and proposed changes. Apply only the project edits authorized
by the user. A proposal for shared guidance goes to the skill's source in a separate
change. Keep the local coverage until the version actually available to the project
contains the applicable shared guidance.
