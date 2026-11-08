# SDD Shared

`sdd-shared` provides the common document formats, checks and role contracts used
by the SDD skills. It lets those skills exchange requirements and evidence while
keeping user decisions with the workflow that requested them.

[sdd-architect](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-architect/README.md)
investigates refactoring opportunities;
[sdd-spec](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-spec/README.md)
prepares the plan; [sdd-apply](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-apply/README.md)
implements it, and [sdd-sync](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-sync/README.md)
promotes completed requirements. Shared contracts define what each result means.
The architect synthesizes findings, compares solutions and authors assigned
materials. Explorer gathers assigned source facts or runs exact assigned checks.
Each workflow chooses the documents, checks, role sequence and context policy;
its orchestrator handles user decisions, assignments and transitions. Shared
coordination preserves actual results, one writer for each output area and a
confirmed stop before write authority changes hands.

Use the relevant workflow for project work. Invoke this package directly when
you want to inspect its contracts.

| Request | Example prompt | Result |
|---|---|---|
| Understand a document format | `Use sdd-shared to explain how task checks refer to acceptance criteria.` | The applicable format and relationships, with source references. |
| Inspect role responsibilities | `Use sdd-shared to explain what the architect authors, what Explorer returns and which decisions stay with the calling workflow.` | The authorship, evidence and workflow boundaries. |
| Inspect a handoff | `Use sdd-shared to explain when another worker may continue writing an unfinished report.` | The required result, current inputs and confirmation that the previous writer stopped. |
| Inspect an interface | `Use sdd-shared to explain the document check result and its exit codes.` | The public contract and limits of a successful structural check. |

See the [resource map](SKILL.md) for the contract needed by a calling skill.
