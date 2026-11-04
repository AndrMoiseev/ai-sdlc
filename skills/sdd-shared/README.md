# SDD Shared

`sdd-shared` provides the common document formats, checks and role contracts used
by the SDD skills. It lets those skills exchange requirements and evidence while
keeping user decisions with the workflow that requested them.

[sdd-spec](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-spec/README.md)
prepares the plan; [sdd-apply](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-apply/README.md)
implements it, and [sdd-sync](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-sync/README.md)
promotes completed requirements. Shared contracts define what each result means.
In sdd-spec, a separate architect authors the document bundle and explanations.
The orchestrator handles user decisions, assignments and workflow state.
One reviewer role serves every bundle review lens, including plan checks when
tasks exist; each lens retains its own independent context. An authorized prose
editing pass uses one editor role for editing and checking, with the check in a
separate fresh context.
Explorer gathers assigned source facts or runs the exact checks selected by the
orchestrator. In sdd-apply, the full project tests and static checks must pass before
two reviewers start in parallel, each in a separate fresh context. The verification
lens owns criteria, tests and evidence; the code lens owns architecture and code
quality. Reviewers execute no checks. Acceptance requires both lens results.

Use the relevant workflow for project work. Invoke this package directly when
you want to inspect its contracts.

| Request | Example prompt | Result |
|---|---|---|
| Understand a document format | `Use sdd-shared to explain how task checks refer to acceptance criteria.` | The applicable format and relationships, with source references. |
| Inspect role responsibilities | `Use sdd-shared to explain what Explorer returns and what each review lens assesses.` | The assignment, evidence and assessment boundaries. |
| Inspect an interface | `Use sdd-shared to explain the document check result and its exit codes.` | The public contract and limits of a successful structural check. |

See the [resource map](SKILL.md) for the contract needed by a calling skill.
