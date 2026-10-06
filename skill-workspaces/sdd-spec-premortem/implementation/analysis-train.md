# Train-only behavioral analysis

Only frozen train IDs were opened for grading. Held-out outputs and grades remain unopened. This report covers completed runs currently available; timeout is an execution limitation, not a behavioral failure. Grades are beside each run in grading.json.

| Train case | Valid baseline | Candidate | Interpretation |
|---|---:|---:|---|
| 13 explore | 2/2 controlled retry | 2/2 | Both identify missing dispatcher action and save causal failure analysis before specification; baseline uses research.md. |
| 15 small change | 1/2 | 2/2 | Explicit no-findings checkpoint added without an interview, artificial risks or separate artifact. |
| 16 known answer | 2/2 corrected | 2/2 | Both use the saved purpose answer. Baseline asks a distinct freshness question, which the frozen criterion does not prohibit. |
| 17 findings document | 1/3 | 3/3 | Baseline already has causal analysis in research.md. Candidate meets premortem.md and compact state-section contract. Both link Q-IDs. |
| 18 closed history | 2/2 | 2/2 | Both retain closed finding and evidence. |
| 19 dependent choice | 3/3 controlled retry | 3/3 | Both block the dependent mode choice and continue independent CSV drafting without claiming review readiness. |
| 21 scope pressure | 2/2 | 2/2 | Both choose C and distinguish proposals from user decisions. |
| 22 current resume | 2/2 | 2/2 | Both read sources and avoid repeated interviews or duplicate findings. |
| 25 missing old checkpoint | 2/2 | 2/2 | Both recover without cancelling valid approvals. |
| 26 missing linked artifact | 2/2 | 2/2 | Baseline distinguishes unverified history and creates a focused Q. |
| 27 missing source | 2/2 | 2/2 | Baseline preserves supported facts and questions the missing evidence. |
| 28 two-stage normative change | 3/3 | 3/3 | Both preserve the manifest for commentary-only change, then update07:00 through REQ/AC and mark old approvals stale. Both stage snapshots and hashes checked. |
| 29 premortem is not review | 2/2 | 2/2 | Baseline preserves planning request and respects review gate. |

## Generalized findings

The demonstrated improvement is predictable persistence: an explicit no-findings checkpoint for small changes, and a stable finding artifact plus compact state link when findings exist. The old skill already identifies the timing mismatch and describes a technically correct report failing its business goal. Do not describe artifact-contract failures as missing causal reasoning.

Scope discipline, saved-answer reuse, closed-history retention, bounded recovery and respect for review gates pass in completed baseline cases. Preserve these behaviors; results do not justify adding more approval rules or making the interview stricter.

## Pressure micro-tests

Case 21 repeated five times per variant. Candidate runs 1-5 completed and passed 2/2 each. Baseline runs 2, 4 and 5 completed and passed 2/2 each; baseline runs 1 and 3 timed out and are excluded. Both variants continue real independent work and avoid fabricated consent. Candidates consistently store findings in premortem.md with a compact state link; completed baselines retain risk in state/design. This storage observation is not an added assertion and does not change pressure scores.

## Execution and evaluation limits

- Initial iteration-1 train fixtures 13 and 16 are invalid and excluded; only corrected replacements are eligible.
- Corrected baseline 13 initially timed out; a separate controlled retry completed and passed2/2. Original timeout is retained as execution evidence. Baseline19 initially timed out; a separate controlled retry completed and passed3/3.
- All inspected completed runs report missing humanizer-ru because the evaluator fixture copied only sdd-spec and omitted this required dependency, although it exists in the author repository. This is a fixture dependency omission, not a skill defect or general environment incapability. Substantive drafts exist but mandatory editorial work remains incomplete. Grades concern frozen expectations, not overall readiness.
- Several initial read permission errors recovered; these are not behavior failures.
- Full-suite acceptance and held-out comparisons belong to the orchestrator. No held-out or overall gate claim is made here.

Frozen assertions remain unchanged. Future revisions could separate artifact naming from causal reasoning and decompose compound assertions. Such revisions must not retroactively change this comparison.