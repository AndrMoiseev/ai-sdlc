"""Read-only, operation-sized public API help without loading execution state."""
from copy import deepcopy
from .common import require


def contract(summary, required=(), optional=(), **details):
    return {"summary": summary, "required": list(required), "optional": list(optional), **details}


VALIDATION = ("project_root", "instruction")
SELECTORS = ("change", "work_kind", "sdd_shared", "sdd_spec")
OPERATIONS = {
    "help": contract("List names, or return one operation/event contract; no state or filesystem access.",
                     optional=("operation", "event")),
    "validate": contract("Validate approved documents and execution instruction; return the basis.",
                         VALIDATION, SELECTORS, instruction={"text": "actual instruction", "source": "message/trace"},
                         defaults={"work_kind": "change"}, choices={"work_kind": ["change", "refactoring", None]},
                         rules=["Use only one dependency selector: sdd_shared, or legacy sdd_spec.",
                                "work_kind=null discovers both roots; ambiguous identity returns explicit candidates."]),
    "initialize": contract("Validate, create execution state and render its initial dashboard.",
                           (*VALIDATION, "owner"), (*SELECTORS, "mode", "parallel_request", "isolation"),
                           defaults={"mode": "parallel", "isolation": False, "work_kind": "change"},
                           rules=["Both modes require verified worktree isolation; unavailable isolation blocks execution.",
                                  "Existing executions use resume; initialization never overwrites state.",
                                  "instruction and optional parallel_request contain actual user text and source."]),
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
    "available": contract("Return task IDs eligible under dependencies and mode; other admission gates still apply.", ("directory",)),
    "event": contract("Apply one typed event using current revision and owner; render the dashboard.", ("directory", "event")),
    "dashboard": contract("Regenerate views from verified saved state.", ("directory",)),
    "recover_lock": contract("Remove a state lock only after proving its local owner exited.", ("directory",)),
    "serve": contract("Serve the generated dashboard through a local read-only server.", ("directory",), ("port",), defaults={"port": 0}),
    "stop_server": contract("Stop the registered local dashboard server.", ("directory",)),
}

EVENTS = {
    "checks_register": contract("Register once before start; preserve planned checks and inspected project/CI checks.",
        ("inventory",), ("additional",), inventory={"instructions": [], "ci": []},
        additional={"id": "unique check ID", "source": "requirement source", "criteria": ["AC-ID"],
                    "run": {"command": ["executable", "argument"]}, "cwd": ".", "configuration": {}, "location": "optional project-relative path"}),
    "role_register": contract("Register an actually launched fresh host context; return its packet path.",
        ("role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"),
        ("successor_of", "agent_selection", "model_observation"),
        choices={"kind": ["executor", "verifier", "reviewer", "final_verifier"], "host": ["codex", "claude-code"]},
        rules=["fresh and capabilities.fresh_context must be true; launch_ref records the actual host launch.",
               "With project settings, supply resolve_agent's result as agent_selection.",
               "A lost-role successor names successor_of; resume resolves that specific predecessor."]),
    "role_result": contract("Finish registered role work; this does not accept its task.", ("role_id", "result", "trace")),
    "start": contract("Admit an eligible task with checks, dashboard and active executor.", ("role_id", "paths"),
        rules=["List canonical project-relative owned files individually; both modes require an isolated worktree."]),
    "check_run": contract("Run the complete registered check set and save actual results.", ("role_id", "stage"), ("timeout",),
        choices={"stage": ["baseline", "self", "independent", "integration", "final"]}, defaults={"timeout": 300},
        rules=["Baseline precedes implementation in a clean worktree; self/independent/integration require a frozen local commit.",
               "Ordinary changes use task-scoped final_verifier; refactoring uses task_id=null and the whole confirmed applicable union."]),
    "check_setup": contract("Resolve planned setup/procedure after baseline while running or repairing.",
        ("check_id", "command", "description"), ("cwd", "configuration"),
        rules=["command is the exact executable argument array; keep existing checks and assertions."]),
    "checks_extend": contract("After more_checks, add mandatory checks without replacing the existing registry.",
        ("review_round", "additional"),
        additional={"id": "unique ID", "source": "review", "criteria": ["scoped AC-ID"], "run": {"command": ["executable", "argument"]}},
        rules=["review_round names the requesting round; the new candidate requires new checks and review.",
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
    "procedure_begin": contract("Bind the procedure to the clean Git commit before its assigned role executes it.", ("check_id", "role_id", "stage"),
        choices={"stage": ["baseline", "self", "independent", "integration", "final"]}),
    "procedure_result": contract("Record actual steps/outcome and host trace for the same pending procedure role.",
        ("check_id", "role_id", "outcome", "steps", "trace"),
        choices={"outcome": ["passed", "failed", "unavailable", "skipped", "unstable"]},
        rules=["Then check_run reconciles the full registry; edits during a procedure make evidence stale."]),
    "candidate": contract("Commit owned paths locally and freeze the clean commit, change documents, registry and root after task writers stop.",
        rules=["Returns candidate_id, sha256, path and root; path is relative to execution directory.",
               "Only current-change documents have file hashes; source identity is the Git commit and clean worktree."]),
    "review_start": contract("Reserve one review round after current independent checks pass.", ("role_id",)),
    "review_result": contract("Complete the reserved independent review against the exact candidate.",
        ("role_id", "candidate", "verdict", "findings", "test_integrity", "trace"),
        choices={"verdict": ["pass", "changes", "more_checks"]},
        finding={"severity": "blocker|recommendation", "criteria": ["AC-ID"], "path": "affected path", "problem": "finding", "resolution": "required result", "proof": "optional structured proof; see review policy"},
        rules=["candidate is the complete script-issued reference; legacy source snapshots require explicit rebaseline.",
               "test_integrity covers assertions, skips/xfail and command weakening; only proven violations block."]),
    "repair": contract("Reserve any required repair budget and reopen the assigned executor with evidence.",
        ("reason",), ("defect_evidence", "executor", "test_failure", "final_checks", "paths"),
        rules=["Supply defect_evidence unless a failure is already recorded; self-check failure needs test_failure:true.",
               "Refactoring final failures require final_checks IDs, reproducible defect_evidence and owned paths; task_id selects the responsible task.",
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
    "resume": contract("Reconcile normative bytes, Git and actual host liveness without discarding work.",
        ("host_trace", "live_contexts"), ("resolutions",),
        resolution={"reason": "blocker reason", "task_id": "TASK-ID or null", "evidence": "recorded resolution",
                    "role_id": "lost predecessor for lost_role", "successor": "active registered successor for lost_role"},
        rules=["Resolve each lost role separately. A successor must name that predecessor and have the same task/kind.",
               "Legacy resolutions may omit role_id: successor_of supplies the specific predecessor.",
               "For a lost run-level final verifier with pending procedures, resolution.abandon_procedures must list every unfinished check ID. Resume archives each predecessor attempt as abandoned with its trace; the successor starts a fresh procedure.",
               "Task phase restores only after every task blocker is resolved; review and repair reservations survive.",
               "Refactoring returns check_registries with confirmed_revision/confirmed_checks and pending_transition separately; resume never confirms a revision.",
               "Budget, normative, spec-conflict and mode blockers require their dedicated operations."]),
    "spec_conflict": contract("Save reproduction and conflicting contract, block, and return to sdd-spec.",
        ("reproduction", "criteria", "contract")),
    "revised_plan": contract("Validate a newly approved basis while preserving accepted tasks and lifetime budgets.",
        ("instruction",), rules=["Stop/reconcile active roles first; completed tasks remain unchanged and new tasks append.",
                                  "instruction contains actual execution text and source."]),
    "mode": contract("Record the actual user mode decision and require fresh-context handoff.",
        ("mode", "source", "text"), ("isolation_available",), choices={"mode": ["sequential", "parallel"]},
        rules=["Changing to parallel requires isolation_available:true."]),
    "handoff": contract("Transfer ownership to a distinct actual fresh context, applying any pending mode decision.",
        ("new_owner", "fresh", "launch_ref"), rules=["fresh must be true; preserve existing task branches and worktrees."]),
    "finalize": contract("Require accepted commits and fresh independent final-HEAD evidence for every AC.",
        optional=("recommendation_decisions",),
        decision={"finding_id": "journal finding ID", "action": "defer|reject", "reason": "decision rationale"},
        rules=["Omission defers every recommendation; explicit decisions cover every finding exactly once."]),
}

RUN_EVENTS = {"resume", "revised_plan", "handoff", "mode", "finalize"}
WHOLE_EVENTS = {"checks_register", "check_setup", "check_run", "procedure_begin", "procedure_result", "role_register", "role_result", "repair"}
ENVELOPE = {"event_id": "unique filesystem-safe ID", "run_id": "saved run ID",
            "expected_revision": "current integer revision", "owner": "registered owner context",
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
            result.setdefault("rules", []).append("For refactoring, task_id=null addresses whole-result checks or the final_verifier; check_setup uses the check's approved setup_task.")
        result["envelope"] = {**ENVELOPE, "type": event}
    elif operation == "event":
        result["envelope"] = deepcopy(ENVELOPE)
    return result
