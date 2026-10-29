"""Read-only, operation-sized public API help without loading execution state."""
from copy import deepcopy
from .common import require


def contract(summary, required=(), optional=(), **details):
    return {"summary": summary, "required": list(required), "optional": list(optional), **details}


VALIDATION = ("project_root", "instruction")
SELECTORS = ("change", "work_kind")
OPERATIONS = {
    "help": contract("List names, or return one operation/event contract; no state or filesystem access.",
                     optional=("operation", "event")),
    "validate": contract("Validate approved documents and execution instruction; return the basis.",
                         VALIDATION, SELECTORS, instruction={"text": "actual instruction", "source": "message/trace"},
                         defaults={"work_kind": "change"}, choices={"work_kind": ["change", "refactoring", None]},
                         rules=["Critical dependency sdd-shared must be installed alongside sdd-apply.",
                                "work_kind=null discovers both roots; ambiguous identity returns explicit candidates."]),
    "initialize": contract("Validate, create execution state and render its initial dashboard.",
                           VALIDATION, (*SELECTORS, "isolation"),
                           defaults={"isolation": False, "work_kind": "change"},
                           rules=["Execution requires verified worktree isolation; unavailable isolation blocks execution.",
                                  "Existing executions use resume; initialization never overwrites state.",
                                  "instruction contains actual user text and source."]),
    "read": contract("Validate the current manifest and accessed objects; return statuses or the manifest with references.",
                     ("directory",), ("view",), defaults={"view": "compact"}, choices={"view": ["compact", "full"]},
                     rules=["Use compact for revision, status, blockers and budgets; full returns stored references without expanding them.",
                            "Reading state does not establish candidate freshness or authorize an event."]),
    "read_object": contract("Verify and read one immutable object; nested references remain encoded.", ("directory", "reference")),
    "audit": contract("Verify every current object, the complete event chain and its event-ID index.", ("directory",)),
    "resolve_agent": contract("Resolve a role's launch configuration at the original project root; does not launch it.",
                              ("directory", "kind", "host", "parent_model"),
                              ("parent_effort", "available_agents", "user_agent_dir"),
                              rules=["Preserve the result as agent_selection in role_register.",
                                     "For Claude Code supply the observed available_agents."]),
    "available": contract("Return task IDs eligible under dependencies and conflicts; other admission gates still apply.", ("directory",)),
    "event": contract("Apply one typed event using current run and revision; render the dashboard.", ("directory", "event")),
    "dashboard": contract("Regenerate views from verified saved state.", ("directory",)),
    "recover_lock": contract("Remove a state lock only after proving its local owner exited.", ("directory",)),
    "serve": contract("Serve the generated dashboard through a local read-only server.", ("directory",), ("port",), defaults={"port": 0}),
    "stop_server": contract("Stop the registered local dashboard server.", ("directory",)),
}

EVENTS = {
    "checks_register": contract("Register task checks before start, or additional ordinary project checks after task acceptance.",
        ("inventory",), ("additional",), inventory={"instructions": [], "ci": []},
        rules=["Ordinary task_id=null registers only additional final project checks after all tasks are accepted and integrated.",
               "Bind each additional command/procedure to approved covers criteria; task final checks remain mandatory."],
        additional={"id": "unique check ID", "source": "requirement source", "criteria": ["AC-ID"],
                    "run": {"command": ["executable", "argument"]}, "cwd": ".", "configuration": {}, "location": "optional project-relative path"}),
    "role_register": contract("Register an actually launched fresh host context; return its packet path.",
        ("role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"),
        ("successor_of", "agent_selection", "model_observation", "assignment"),
        choices={"kind": ["executor", "verifier", "reviewer", "final_verifier", "explorer"], "host": ["codex", "claude-code"]},
        rules=["fresh and capabilities.fresh_context must be true; launch_ref records the actual host launch.",
               "With project settings, supply resolve_agent's result as agent_selection.",
               "Explorer requires the shared assignment with id=role_id, exact scope/current basis, full check IDs and registry revision, plus capabilities.observations.",
               "Finished non-final explorer contexts may continue only their own task with the same launch profile and a new assignment; final requires a fresh separate explorer.",
               "A lost-role successor names successor_of; resume resolves that specific predecessor."]),
    "role_result": contract("Finish registered role work; this does not accept its task.", ("role_id", "result", "trace"),
        rules=["Research result is an object: kind=research, answer, references, inspected_scope, limitations, assumptions and questions; role retains assignment identity/basis/launch."]),
    "start": contract("Admit an eligible task with checks, dashboard and active executor.", ("role_id", "paths"),
        rules=["List canonical project-relative owned files individually; each task requires an isolated worktree."]),
    "check_run": contract("Explorer executes the complete registered check set and saves actual results.", ("role_id", "stage"), ("timeout",),
        choices={"stage": ["baseline", "self", "independent", "integration", "final"]}, defaults={"timeout": 300},
        rules=["Baseline precedes implementation in a clean worktree; self/independent/integration require a frozen local commit.",
               "Only a registered matching explorer checks assignment may run; timeout covers the full assigned attempt including prior deterministic procedures and setup/report capture, capped by assignment limits and any explicit absolute deadline.",
               "Ordinary changes retain task-scoped final explorer checks; an optional additional project registry uses task_id=null, only at final.",
               "Refactoring uses task_id=null and the whole confirmed applicable union."]),
    "check_setup": contract("Resolve planned setup/procedure after baseline while running or repairing.",
        ("check_id", "command", "description"), ("cwd", "configuration"),
        rules=["command is the exact executable argument array; keep existing checks and assertions."]),
    "checks_extend": contract("After more_checks, add mandatory checks without replacing the existing registry.",
        ("review_round", "additional"),
        additional={"id": "unique ID", "source": "review", "criteria": ["scoped AC-ID"], "run": {"command": ["executable", "argument"]}},
        rules=["review_round names the requesting round; the new candidate requires new checks and review.",
               "Each addition has one exact command or existing contained procedure with scoped criteria; procedures require explicit execution_kind.",
               "Refactoring IDs cannot reuse another task's registered, historical or planned generated check ID."]),
    "checks_revise": contract("Stage an approved refactoring registry revision; confirm only with task acceptance.",
        ("registry_revision", "before", "after", "basis", "preserves", "reason", "mapping"),
        basis={"test_changes": ["local test-change ID"], "transitional_criteria": ["AC-ID ending at this task"]},
        mapping={"changed-check-ID": "approved group or lifetime basis and actual affected tests"},
        rules=["before is the exact applicable registry; after contains complete exact check records, including unchanged project checks.",
               "Use the current task registry_revision; each changed payload needs a new revision and fresh checks/review.",
               "Capture baseline first; use only running or reserved repair work with its assigned active executor.",
               "preserves lists exactly the affected preserved criterion IDs. Their identity survives test moves.",
               "Pending checks apply to this candidate; accepted checks stay confirmed for other tasks until atomic acceptance.",
               "Failure/unavailability keeps the revision unconfirmed and retains repair/review budgets.",
               "Changing approved obligations, groups or lifetimes requires spec_conflict/revised_plan."]),
    "procedure_begin": contract("Bind the procedure to the clean Git commit before its assigned role executes it.", ("check_id", "role_id", "stage"), ("timeout",),
        choices={"stage": ["baseline", "self", "independent", "integration", "final"]},
        rules=["execution_kind belongs to the check record outside run: command defaults deterministic; procedure requires an explicit deterministic/behavioral/manual type.",
               "Deterministic begin starts or continues the full assignment attempt deadline; execute within returned remaining_timeout and check_deadline. Expired starts are rejected; over-budget results retain actual steps and reported_outcome but cannot pass.",
               "Deterministic procedures belong to explorer; behavioral/manual including typed commands belong to verifier or final_verifier, and explorer only aggregates their attestation.",
               "Behavioral checks of assigned skill packages execute only at final."]),
    "procedure_result": contract("Record actual steps/outcome and host trace for the same pending procedure role.",
        ("check_id", "role_id", "outcome", "steps", "trace"),
        choices={"outcome": ["passed", "failed", "unavailable", "skipped", "unstable"]},
        rules=["Then check_run reconciles the full registry; edits during a procedure make evidence stale."]),
    "candidate": contract("Commit owned paths locally and enter verification after task writers stop.",
        rules=["Returns commit metadata; no candidate artifact or reference is stored."]),
    "review_start": contract("Reserve one review round after current independent checks pass.", ("role_id",)),
    "review_result": contract("Complete the reserved independent review.",
        ("role_id", "verdict", "findings", "test_integrity", "trace"),
        choices={"verdict": ["pass", "changes", "more_checks"]},
        finding={"severity": "blocker|recommendation", "criteria": ["AC-ID"], "path": "affected path", "problem": "finding", "resolution": "required result", "proof": "optional structured proof; see review policy"},
        rules=["Candidate references are no longer accepted.",
               "test_integrity covers assertions, skips/xfail and command weakening; only proven violations block."]),
    "repair": contract("Reserve any required repair budget and reopen the assigned executor with evidence.",
        ("reason",), ("defect_evidence", "executor", "test_failure", "final_checks", "paths"),
        rules=["Supply defect_evidence unless a failure is already recorded; self-check failure needs test_failure:true.",
               "Run-level final failures require final_checks IDs, reproducible defect_evidence and owned paths; task_id selects the responsible task.",
               "Unknown or out-of-scope ownership returns to sdd-spec before edits; established ownership reserves the existing task test-repair budget."]),
    "commit": contract("Confirm the existing integration commit after current independent evidence and passing review."),
    "accept": contract("Accept only the confirmed task commit with current evidence and review."),
    "block": contract("Preserve partial work and record the condition for resuming.", ("reason", "resume_condition")),
    "budget_extend": contract("Record the user's explicit finite increase to a task-lifetime budget.",
        ("budget", "limit", "source", "text"), choices={"budget": ["review", "test"]}),
    "worktree_create": contract("Create a named isolated worktree for an available task or repair of an integrated result.",
        ("workspace",), ("resources",), rules=["workspace must be outside skill collections; allocate distinct named resources."]),
    "worktree_remove": contract("Remove only accepted, confirmed worktrees with stopped roles and no unknown data."),
    "worktree_refresh": contract("Preserve unfinished task work and budgets in a replacement at current execution HEAD.",
        ("reason", "evidence"), rules=["Stop task roles and resolve run blockers; no pending integration may remain."]),
    "worktree_refresh_resolve": contract("Adopt a preserved replacement after a registered resolver finishes conflicts.",
        ("intent_id", "role_id", "resolution")),
    "transfer": contract("Save a complete binary transfer package of the independently reviewed worktree candidate."),
    "integrate": contract("Serialize integration of the unchanged transfer into the execution branch.",
        rules=["Integrated bytes require a new candidate, independent integration checks and review."]),
    "integration_resolve": contract("Record a finished registered resolver's result for a prepared integration intent.",
        ("intent_id", "role_id", "resolution")),
    "resume": contract("Reconcile admitted scope, Git and actual host liveness without discarding work.",
        ("host_trace", "live_contexts"), ("resolutions",),
        resolution={"reason": "blocker reason", "task_id": "TASK-ID or null", "evidence": "recorded resolution",
                      "role_id": "lost predecessor for lost_role", "successor": "active registered successor for lost_role",
                      "head": "exact observed clean HEAD for execution_head_changed",
                      "instruction": {"text": "actual user acceptance", "source": "actual message or decision source"}},
        rules=["Resolve each lost role separately. A successor must name that predecessor and have the same task/kind.",
               "Legacy resolutions may omit role_id: successor_of supplies the specific predecessor.",
               "For a lost run-level final verifier with pending procedures, resolution.abandon_procedures must list every unfinished check ID. Resume archives each predecessor attempt as abandoned with its trace; the successor starts a fresh procedure.",
               "Task phase restores only after every task blocker is resolved; review and repair reservations survive.",
               "Refactoring returns check_registries with confirmed_revision/confirmed_checks and pending_transition separately; resume never confirms a revision.",
               "Budget, normative and spec-conflict blockers require their dedicated operations."]),
    "spec_conflict": contract("Save reproduction and conflicting contract, block, and return to sdd-spec.",
        ("reproduction", "criteria", "contract")),
    "revised_plan": contract("Validate a newly approved basis while preserving accepted tasks and lifetime budgets.",
        ("instruction",), ("completed_followups",),
        completed_followups=[{"completed_task": "accepted TASK-ID", "followup_task": "new dependent TASK-ID"}],
        rules=["Stop/reconcile active roles first; completed tasks remain unchanged and new tasks append.",
               "instruction contains actual execution text and source authorizing the revised plan and any mapped follow-up.",
               "Each completed_followups mapping replaces only that accepted task's obsolete budget stop with a new approved dependent task; counters and unrelated blockers remain.",
               "Unfinished tasks and active review/repair reservations cannot use completed_followups. Ordinary final project obligations survive revision; old attempts are archived and current-basis evidence is required."]),
    "finalize": contract("Require accepted commits and fresh independent final-HEAD evidence for every AC.",
        optional=("recommendation_decisions",),
        decision={"finding_id": "journal finding ID", "action": "defer|reject", "reason": "decision rationale"},
        rules=["Omission defers every recommendation; explicit decisions cover every finding exactly once."]),
}

RUN_EVENTS = {"resume", "revised_plan", "finalize"}
WHOLE_EVENTS = {"checks_register", "check_setup", "check_run", "procedure_begin", "procedure_result", "role_register", "role_result", "repair"}
ENVELOPE = {"event_id": "unique filesystem-safe ID", "run_id": "saved run ID",
            "expected_revision": "current integer revision",
            "type": "event name", "task_id": "TASK-ID or null for run event", "payload": {}}


def describe(operation=None, event=None):
    require(not (operation is not None and event is not None), "help_selector", "Select one operation or event")
    if operation is None and event is None:
        return {"operations": sorted(OPERATIONS), "events": sorted(EVENTS),
                "usage": "--help-operation NAME or --help-event TYPE; JSON: operation=help, args={operation:NAME} or {event:TYPE}"}
    records, name, selector = (OPERATIONS, operation, "operation") if operation is not None else (EVENTS, event, "event")
    require(isinstance(name, str) and name in records, "help_unknown", "Unknown " + selector + ": " + str(name))
    result = {selector: name, **deepcopy(records[name])}
    if event is not None:
        result["task_id"] = "null" if event in RUN_EVENTS else "TASK-ID or null" if event == "block" or event in WHOLE_EVENTS else "TASK-ID"
        if event in WHOLE_EVENTS:
            result.setdefault("rules", []).append("Null-scope research explorer registration/results need no final registry. Refactoring null-scope checks use the whole union, final explorer and separate final_verifier; check_setup uses the approved setup_task.")
            result["rules"].append("For ordinary changes, null-scope checks address the optional final project registry, fresh explorer and separate final_verifier; check_setup is unavailable. Task-scoped final checks still apply.")
        result["envelope"] = {**ENVELOPE, "type": event}
    elif operation == "event":
        result["envelope"] = deepcopy(ENVELOPE)
    return result
