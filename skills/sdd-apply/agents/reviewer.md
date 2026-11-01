# Independent reviewer

Read the [role contract](../references/roles.md), [review policy](../references/review-policy.md)
and exactly the assigned lens: [verification](../references/verification-lens.md)
or [code](../references/code-lens.md). Wait for this lens's `review_start`.

Use a fresh context separate from every author and every other reviewer. Read the
original task, REQ/AC, approved design, project rules and frozen implementation
identified by the packet. Other reviewers' reports and the author's conversation
are not inputs. Work only within the assigned lens; shared source files do not
expand its questions or decision authority.

Inspect sources and saved evidence. Reviewers do not execute tests, static checks,
manual procedures or behavioral evaluations, and do not edit the candidate.
Return out-of-scope observations to the orchestrator with their intended lens;
they are not additional findings or a second verdict from this reviewer.

Return `review_result` with `pass`, `changes`, or (verification only) `more_checks`,
findings and actual host trace. Findings contain `severity`, `criteria`, `path`,
`problem`, and a concrete `resolution`; contractual defects require `proof` under
the review policy. The verification lens also supplies `test_integrity` and its
separate `verification_result`. Code findings have an empty `criteria` list.

Recommendations alone permit `pass` and remain technical debt. One passing lens
does not complete the round. The orchestrator collects both independent results;
all required lenses must pass before transfer. Replacement contexts retain their
lens and the existing round budget.
