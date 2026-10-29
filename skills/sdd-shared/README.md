# SDD Shared

`sdd-shared` provides the common document formats, checks and role contracts used
by the SDD skills. It lets those skills exchange requirements and evidence while
keeping user decisions with the workflow that requested them.

[sdd-spec](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-spec/README.md)
prepares the plan; [sdd-apply](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-apply/README.md)
implements it, and [sdd-sync](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-sync/README.md)
promotes completed requirements. Shared contracts define what each result means.
Explorer gathers source facts or runs deterministic checks. A separate verifier
assesses implementation criteria; a successful command alone does not accept work.

Use the relevant workflow for project work. Invoke this package directly when
you want to inspect its contracts.

| Request | Example prompt | Result |
|---|---|---|
| Understand a document format | `Use sdd-shared to explain how task checks refer to acceptance criteria.` | The applicable format and relationships, with source references. |
| Inspect role responsibilities | `Use sdd-shared to explain what Explorer returns and what the verifier assesses.` | The assignment, evidence and assessment boundaries. |
| Inspect an interface | `Use sdd-shared to explain the document check result and its exit codes.` | The public contract and limits of a successful structural check. |

See the [resource map](SKILL.md) for the contract needed by a calling skill.
