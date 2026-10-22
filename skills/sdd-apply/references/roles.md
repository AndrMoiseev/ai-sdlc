# Worker contract

Read your role instructions and generated packet. Use original REQ/AC, approved
design, project instructions and exact checks; the packet gives their paths,
owned files, candidate reference, prior commits, blockers and rejected approaches.
The author's conversation, grading answers and unrelated task history are not inputs.

Work only within the assignment. Verifiers and reviewers are independent of all
authors and do not edit the candidate. Wait for the generated packet; a reviewer
also waits for a successful `review_start` reservation. Report unavailable inputs,
permissions or tools rather than simulating a role or a successful check.

Return task/role/context IDs, status, unchanged candidate reference or source
snapshot path/hash, owned/inspected paths, AC-to-evidence mapping, commands and log
paths, blockers/limitations and actual host trace. Keep full evidence in artifacts;
the message gives the result and references. A combined verifier/reviewer context
returns distinct results for its two registered roles. Finish API work before
ending the role; DONE is an implementation claim, not acceptance.

The orchestrator handles launch, registration, replacement and state transitions
under [role coordination](role-coordination.md); workers need not load that procedure.
