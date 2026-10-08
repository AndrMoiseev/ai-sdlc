# Baseline native verifier result

Task: TASK-add. Role: baseline. Context: /root/behavioral_eval/baseline.

Status: unavailable for behavioral assertions; accepted baseline_recorded with planned_absence. This is neither a passed test nor a blocker. Candidate: null. Source snapshot before and after: e1450054d65dc88e44bc9f30bda76098adbedad30330f3dae5bcc4f90fc0f0cd. No source changes occurred during the run.

Personally initiated check_run stage=baseline role_id=baseline through parent orchestrator after inspecting generated packet, original spec, design, and tasks. Raw evidence inspected: fixture/sdd/changes/add/execution/runs/1ce7765c054f4c80a39ac2c5640cbee8/tasks/TASK-add/1/85164adaa02048a0ac2333eb0ab1afbf.json, where fixture is C:/Users/Andrew/AppData/Local/Temp/sdd-apply-native-754imw39/project.

Registered plan-1 maps to AC-add and AC-invalid. Its setup_required declaration requires creation of check.py (PEP 723 standard-library script) and check.py.lock before running `uv run --locked --script check.py`, cwd fixture, configuration {}. No command ran, no individual exit code exists, and both ACs remain unverified. Raw outputs explicitly contain planned_absence. Snapshots omit check.py and check.py.lock and preserve calculator.py hash 808fa4f4a62373f15aaf326d0be71bc19d7cfd014eb76ebfa8813182cfb1b4fd.

AC-add requires finite int/float operands excluding bool and arbitrary precision integer sums. AC-invalid requires TypeError for invalid types and ValueError for non-finite operands/results. No baseline evidence claims these behaviors pass.

Inspected paths: package agents/verifier.md and references/roles.md; fixture generated roles/baseline.json, specs/calculator/spec.md, design.md, tasks.md, and raw baseline log. No package/fixture edits and no ad hoc tests.

Host trace: actual native launch registered as `native collaboration.spawn_agent task_name=baseline fork_turns=none returned /root/behavioral_eval/baseline`. Parent supplied only scoped task/packet instructions, not executor conversation. Inherited system/developer instructions, full skill catalog, repository AGENTS guidance, workspace context and tools remain available. This is a distinct context from authors but not an empty instruction environment. Actual permission boundary allows repository writes; read-only fixture behavior is an instruction, not a sandbox guarantee. Initial un-escalated packet read returned Access denied (tool chunk 06f6b8). Approved read-only escalations succeeded for packet (1b023f), original sources (078219), and raw evidence (884066). No automatic approval rejection occurred.
