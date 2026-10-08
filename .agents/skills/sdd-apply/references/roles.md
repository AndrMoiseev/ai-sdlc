# Fresh roles and attestations

Launch each task's executor in a genuinely fresh context. Launch its verifier and reviewer separately from all authors. They may share one fresh context for that task, with distinct registered role IDs and separate verification and review results. A final verifier also starts fresh. Repair may return to the original executor while available; a lost executor is replaced with a fresh successor and a recorded handoff.

The host adapter performs the actual native launch. The script checks host attestations and creates packets; it does not launch or simulate native agents. `context_id` and `launch_ref` must come from observed host launches. Their strings cannot cryptographically prove freshness or identity. Preserve raw launch/tool traces and disclose inherited instructions, skills, workspace exposure, and permission limits. A unit-test stub or fabricated attestation must never be reported as a real role run.

The packet identifies task, relevant REQ/AC, approved design, project instructions, files/interfaces, exact checks, candidate, previous commits, blockers and rejected approaches. Supply paths to original sources and a bounded summary; exclude the author's conversation, grading answers, and unrelated task histories. Roles read only their role contract and assigned task material, not orchestration mode algorithms.

Prepare a launch in a waiting state with role identity and file boundaries; register the observed host launch, then send its generated packet. A reviewer waits for a successful `review_start` reservation before beginning substantive review. When host tools cannot support that sequence, record the capability gap rather than running an unreserved review.

Collect role output as: task/role/context IDs; status; exact candidate or source snapshot; owned/inspected paths; AC-to-evidence mapping; commands and log paths; remaining blockers/limitations; host trace. A verifier can finish before a separate reviewer proceeds, but when one context serves both roles retain two results. Keep role IDs active until their last API operation has completed.

If no fresh-context mechanism exists, block role-dependent execution. If slots are merely busy, preserve state and wait for capacity. If a role is lost, reconcile its actual work before replacement. A request to behave read-only is not a sandbox capability; report actual permissions.
