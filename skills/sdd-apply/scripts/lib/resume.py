"""Reconcile admitted execution scope, Git and host observations."""
from .repository import repository
from copy import deepcopy
from pathlib import Path
from . import artifact_storage as artifacts
from .common import digest, require, write_json
from .state import assert_basis, snapshot, execution_source


def revised_checks(state, old, plan, basis, event):
    """Reconcile approved plan definitions without dropping registered obligations."""
    fresh = deepcopy(old)
    registry = old.get("check_registry", {})
    pending = registry.get("transition") and registry["revision"] > registry.get("confirmed_revision", 0)
    if pending:
        transition = registry["transition"]
        criteria = {criterion for check in old["checks"] for criterion in check["criteria"]}
        criteria.update(criterion for field in ("before", "after")
                        for check in transition.get(field, []) for criterion in check["criteria"])
        criteria.update(transition.get("basis", {}).get("transitional_criteria", []))
        acceptance = {item["id"]: item for item in basis.get("acceptance", [])}
        def contract(record, fields):
            # Approved prose changes need fresh assessment, not registry rejection.
            return {key: sorted(record[key]) if isinstance(record[key], list) else record[key]
                    for key in fields if record is not None and key in record}
        acceptance_fields = ("id", "task", "lifetime", "until_task", "replaced_by")
        permission_fields = ("id", "action", "criteria", "replacement_criteria", "decision")
        prior_permissions = {item["id"]: item for item in old["plan"].get("test_changes", [])}
        next_permissions = {item["id"]: item for item in plan.get("test_changes", [])}
        require(all(set(old["plan"].get(key, [])) == set(plan.get(key, [])) for key in ("preserves", "covers"))
                and old["plan"].get("scope") == plan.get("scope")
                and all(contract(state.get("acceptance", {}).get(key), acceptance_fields)
                        == contract(acceptance.get(key), acceptance_fields) for key in criteria)
                and all(key in prior_permissions and key in next_permissions
                        and contract(prior_permissions[key], permission_fields)
                        == contract(next_permissions[key], permission_fields)
                        for key in transition.get("basis", {}).get("test_changes", [])),
                "pending_registry_conflict", "Reconcile the pending registry transition at its valid basis or adjust the approved plan before revised_plan")
    def definitions(record):
        return {(record["id"] + "/" + check["id"] if basis.get("work_kind") == "refactoring" else f"plan-{i + 1}"):
                {"id": record["id"] + "/" + check["id"] if basis.get("work_kind") == "refactoring" else f"plan-{i + 1}",
                 "criteria": check["criteria"], "source": "tasks.md", "location": check["location"],
                 "run": check["run"], "cwd": ".", "configuration": {}, "setup": None,
                 **({"execution_kind": check["execution_kind"]} if "execution_kind" in check else {})}
                for i, check in enumerate(record["verification"])}
    before, after = definitions(old["plan"]), definitions(plan)
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    if old["checks"] and changed:
        require(not pending, "pending_registry_conflict", "Preserve the pending registry transition before changing plan checks")
        evolved = set()
        for entry in registry.get("history", []):
            transition = entry.get("transition", {})
            prior = {item["id"]: item for item in transition.get("before", [])}
            following = {item["id"]: item for item in transition.get("after", [])}
            evolved.update(key for key in prior.keys() | following.keys() if prior.get(key) != following.get(key))
        require(not changed & evolved, "registry_plan_conflict",
                "Preserve evolved check definitions; reconcile their approved transition before changing the plan")
        require(not any(check["id"] in changed and check["id"] not in before for check in old["checks"]),
                "duplicate_check", "Revised plan check ID conflicts with a registered project obligation")
        fresh["checks"] = [check for check in fresh["checks"] if check["id"] not in changed]
        fresh["checks"].extend(deepcopy(after[key]) for key in after if key in changed)
        from .verification import record_registry
        record_registry(state, fresh, event)
        fresh["check_registry"]["history"][-1]["basis_commit"] = basis["head"]
    return fresh


def reconcile_task_procedures(state, task, predecessor, successor, resolution, event, directory):
    pending = {key: value for key, value in task.get("procedures", {}).items()
               if value["role_id"] == predecessor["role_id"]}
    supplied = resolution.get("abandon_procedures", [])
    require(isinstance(supplied, list) and all(isinstance(key, str) for key in supplied)
            and len(supplied) == len(set(supplied)) and set(supplied) == set(pending),
            "procedure_reconciliation", "Explicitly list every unfinished predecessor check in abandon_procedures")
    for key, attempt in pending.items():
        relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/{event['event_id']}-{digest(key)[:16]}.json"
        record = {**attempt, "check_id": key, "outcome": "abandoned", "successor": successor["role_id"],
                  "resolution": resolution, "trace": event["payload"]["host_trace"]}
        path = artifacts.contained(directory, relative)
        write_json(path, record)
        task["evidence"].append({"check_id": key, "stage": attempt["stage"], "role_id": predecessor["role_id"],
                                 "outcome": "abandoned", "procedure": True, "log": relative,
                                 "log_hash": digest(artifacts.read_bytes(path)), "head": attempt["before"]["commit"]})
        del task["procedures"][key]
    if pending:
        state["final"] = None


def completed_followups(state, plans, payload):
    """Resolve only an abandoned repair stop explicitly replaced by new work."""
    mappings = payload.get("completed_followups", [])
    require(isinstance(mappings, list), "completed_followup", "completed_followups must be a list")
    completed, targets, removed = set(), set(), []
    for mapping in mappings:
        require(isinstance(mapping, dict) and set(mapping) == {"completed_task", "followup_task"}
                and all(isinstance(value, str) and value for value in mapping.values()),
                "completed_followup", "Map the completed_task to its new followup_task")
        prior, target = mapping["completed_task"], mapping["followup_task"]
        old = state["tasks"].get(prior)
        require(old and old["status"] == "accepted" and old["commits"]
                and not old.get("active_review") and not old.get("active_repair"),
                "completed_followup", "Only an accepted task without active work can receive a follow-up")
        require(prior not in completed and target not in targets and target not in state["tasks"]
                and target in plans and prior in plans[target]["depends_on"],
                "completed_followup", "Each mapping needs a distinct newly appended dependent task")
        stops = [block for block in state["blockers"] if block.get("task_id") == prior
                 and block["reason"] in {"review_limit_reached", "test_repair_limit_reached"}]
        require(stops, "completed_followup", "Name an existing completed-task budget stop")
        completed.add(prior)
        targets.add(target)
        removed.extend(stops)
    return removed


def transition(state, task, event, directory):
    p, kind = event["payload"], event["type"]
    if kind == "spec_conflict":
        require(p.get("reproduction") and p.get("criteria") and p.get("contract"), "conflict_evidence", "Record reproduction, AC and conflicting contract")
        path = artifacts.contained(directory, f"runs/{state['run_id']}/spec-return/{event['event_id']}.json")
        write_json(path, {"task_id": event["task_id"], "change_root": state["basis"]["change_root"], **p})
        state["blockers"].append({"reason": "spec_conflict", "task_id": event["task_id"], "resume_condition": "Revised approved plan and execution instruction", "material": str(path)})
        state["status"] = "blocked"
        return {"return_to": "sdd-spec", "material": str(path)}
    if kind == "revised_plan":
        require(not any(r["status"] == "active" for r in state["roles"].values()), "active_roles", "Finish or reconcile active roles before replacing the basis")
        from .inputs import validate
        import uuid
        basis = validate(state["basis"]["project_root"], state["change_id"], p.get("instruction"),
                         work_kind=state["basis"].get("work_kind", "change"))
        require(basis["head"] != state["basis"]["head"], "plan_unchanged", "Use resume when the approved basis is unchanged")
        plans = {plan["id"]: plan for plan in basis["tasks"]}
        completed = [key for key, old in state["tasks"].items() if old["status"] == "accepted"]
        for key in completed:
            require(plans.get(key) == state["tasks"][key]["plan"], "completed_task_changed",
                    f"Preserve completed task {key} unchanged; append follow-up work as a new task")
        # Validate before archiving or creating a run so rejected revisions have
        # no side effects. New tasks follow the existing plan in file and number order.
        last_number = max([old["plan"]["number"] for old in state["tasks"].values()]
                          + [plan["number"] for plan in basis["tasks"] if plan["id"] in state["tasks"]])
        appended = False
        for plan in basis["tasks"]:
            if plan["id"] in state["tasks"]:
                require(not appended, "new_tasks_append_only", "Append new tasks after all existing tasks")
            else:
                appended = True
                require(plan["number"] > last_number, "new_tasks_append_only", "Number new tasks after the existing plan")
        resolved = completed_followups(state, plans, p)
        require(all(key in plans or not old["checks"] for key, old in state["tasks"].items()),
                "registered_task_removed", "Preserve tasks with registered obligations in the revised plan")
        # Validate every registry conflict before archive files or other effects.
        retained = {key: revised_checks(state, old, plans[key], basis, event)
                    for key, old in state["tasks"].items() if key in plans and old["status"] != "accepted"}
        from .final_checks import revised_registry
        final_registry = revised_registry(state, basis, event)
        previous_run = state["run_id"]
        from .state_objects import StateObjects
        objects = StateObjects(directory)
        write_json(artifacts.contained(directory, f"runs/{previous_run}/superseded-state.json"), objects.pack(state, root=True))
        previous_tasks = deepcopy(state["tasks"])
        state["run_id"] = uuid.uuid4().hex
        state["previous_run"] = previous_run
        state["basis"] = basis
        if basis.get("work_kind", "change") == "refactoring":
            state.update(work_kind="refactoring", **{kind: {record["id"]: record for record in basis[kind]}
                         for kind in ("acceptance", "verification")})
        if state.get("final_checks"):
            state["final_checks"] = final_registry
            # Accepted covers and registered project obligations survive. The
            # archived run owns interrupted attempts; new run identity makes all
            # retained evidence historical and requires a fresh complete run.
            state["final_checks"]["procedures"] = {}
            state["final_checks"]["failures"] = {}
        state["tasks"] = {}
        from .state import new_task
        for plan in basis["tasks"]:
            old = previous_tasks.get(plan["id"])
            if old and old["status"] == "accepted":
                state["tasks"][plan["id"]] = old
                continue
            fresh = new_task(plan)
            if old:
                for field in ("review_limit", "review_rounds_started", "review_rounds_completed", "test_repair_limit", "test_repair_cycles_started", "active_repair", "repair_cycles", "budget_decisions", "commits"):
                    fresh[field] = old[field]
                fresh["prior_result"] = {"$object": objects.put(objects.pack(old, root=True))}
                for field in ("checks", "inventory", "check_registry", "evidence", "verification_results", "roles", "last_check_failed"):
                    if field in retained[plan["id"]]:
                        fresh[field] = retained[plan["id"]][field]
            state["tasks"][plan["id"]] = fresh
        # Budget blockers survive a revised plan. Other old blockers are retained
        # in the archived run and checked again against the new basis.
        if p.get("completed_followups"):
            state["blockers"] = [b for b in state["blockers"] if b not in resolved]
        else:
            state["blockers"] = [b for b in state["blockers"] if b["reason"] in {"review_limit_reached", "test_repair_limit_reached"}]
        state["status"] = "blocked" if state["blockers"] else "active"
        state["baseline"] = snapshot(state)
        state["final"] = None
        write_json(artifacts.contained(directory, f"runs/{state['run_id']}/input.json"), objects.pack(basis, root=True))
        return {"run_id": state["run_id"], "previous_run": previous_run, "preserved_tasks": completed,
                **({"resolved_completed_repairs": {"mapping": deepcopy(p["completed_followups"]),
                    "removed_blockers": resolved, "authorization": deepcopy(p["instruction"])}} if resolved else {}),
                "reassessment": "Completed tasks preserved; unfinished tasks require reassessment"}
    require(kind == "resume", "resume_operation", kind)
    from .check_registry import recovery
    registries = recovery(state)
    issues = []
    try:
        assert_basis(state)
        state["blockers"] = [b for b in state["blockers"] if b["reason"] != "normative_drift"]
    except ValueError as exc:
        issues.append({"reason": "normative_drift", "detail": str(exc), "resume_condition": "Reconcile the approved plan through revised_plan; preserve current work"})
    root = state["basis"]["project_root"]
    observed_source = execution_source(state)
    state["blockers"] = [b for b in state["blockers"] if b["reason"] not in {"execution_dirty", "execution_head_changed"}]
    if observed_source["dirty_paths"]:
        issues.append({"reason": "execution_dirty", "paths": observed_source["dirty_paths"],
                       "resume_condition": "Preserve changes; obtain the user's commit or discard decision and restore a clean main tree"})
    if observed_source["head"] != state["execution_head"]:
        issues.append({"reason": "execution_head_changed", "head": observed_source["head"], "expected_head": state["execution_head"],
                       "resume_condition": "Inspect the new HEAD and record explicit current-state acceptance; new task scope requires revised_plan"})
    if repository(root).branch() != state["basis"]["branch"]:
        issues.append({"reason": "branch_changed", "resume_condition": "Restore execution branch"})
    require(p.get("host_trace") and isinstance(p.get("live_contexts"), list), "host_observation", "Supply actual host role liveness observation")
    for role in state["roles"].values():
        if role["status"] == "active" and role["context_id"] not in p["live_contexts"]:
            role["status"] = "lost"
            t = state["tasks"].get(role["task_id"])
            if t is None and role["kind"] in {"final_verifier", "explorer"}:
                issues.append({"reason": "lost_role", "task_id": None, "role_id": role["role_id"],
                               "resume_condition": "Register a fresh run-level successor of the same role kind"})
            if t and (t["status"] not in {"pending", "accepted"} or role["kind"] == "explorer"):
                if t["status"] not in {"blocked", "pending", "accepted"}:
                    t["before_block"] = t["status"]
                    t["status"] = "blocked"
                item = {"reason": "lost_role", "task_id": role["task_id"], "role_id": role["role_id"], "resume_condition": "Register a fresh successor with preserved files and task packet"}
                t["blockers"].append(item)
                issues.append(item)
    for issue in issues:
        if issue not in state["blockers"]:
            state["blockers"].append(issue)
    # Clearing semantic blockers needs a recorded resolution. Budgets and
    # normative drift cannot be waived by this generic resume operation.
    resolutions = p.get("resolutions", [])
    for resolution in resolutions:
        require(resolution.get("evidence") and resolution.get("reason") not in {"review_limit_reached", "test_repair_limit_reached", "normative_drift", "spec_conflict"}, "resume_resolution", "Use the dedicated operation for this blocker")
        reason = resolution["reason"]
        require(reason != "execution_dirty", "resume_resolution", "A dirty main tree must be reconciled before resuming")
        if reason == "execution_head_changed":
            instruction = resolution.get("instruction", {})
            require(not observed_source["dirty_paths"] and resolution.get("head") == observed_source["head"]
                    and instruction.get("text") and instruction.get("source"),
                    "resume_acceptance", "Record the actual user response and source for this exact clean HEAD")
            state["execution_head"] = observed_source["head"]
            issues = [item for item in issues if item["reason"] != reason]
        lost_role = None
        if reason == "lost_role":
            successor = state["roles"].get(resolution.get("successor"))
            require(successor and successor["status"] == "active" and successor.get("successor_of") and successor["task_id"] == resolution.get("task_id"), "successor_required", "Register a fresh successor first")
            # Older requests omit role_id; the registered lineage identifies the
            # one loss they resolve. Never clear another lost role on this task.
            lost_role = resolution.get("role_id", successor["successor_of"])
            predecessor = state["roles"].get(lost_role)
            require(predecessor and successor["successor_of"] == lost_role
                    and predecessor["status"] == "lost"
                    and predecessor["task_id"] == successor["task_id"]
                    and predecessor["kind"] == successor["kind"],
                    "successor_required", "Successor must replace the named lost role with the same task and kind")
            require(any(b["reason"] == reason and b.get("task_id") == resolution.get("task_id")
                        and b.get("role_id") == lost_role for b in state["blockers"]),
                    "successor_required", "No unresolved loss for this role")
            if predecessor["task_id"] is None and (predecessor["kind"] == "final_verifier"
                    or predecessor["kind"] == "explorer" and predecessor.get("assignment", {}).get("kind") == "checks"):
                from .final_checks import reconcile_procedures
                reconcile_procedures(state, predecessor, successor, resolution, event, directory)
            elif predecessor["task_id"] is not None:
                reconcile_task_procedures(state, state["tasks"][predecessor["task_id"]], predecessor,
                                          successor, resolution, event, directory)
        def resolved(blocker):
            return (blocker["reason"] == reason
                    and blocker.get("task_id", resolution.get("task_id")) == resolution.get("task_id")
                    and (lost_role is None or blocker.get("role_id") == lost_role))
        state["blockers"] = [b for b in state["blockers"] if not
                             (b.get("task_id") == resolution.get("task_id") and resolved(b))]
        t = state["tasks"].get(resolution.get("task_id"))
        if t:
            if reason == "lost_role" and successor["kind"] == "executor":
                t["executor"] = successor["role_id"]
            if reason == "lost_role" and successor["kind"] == "reviewer" and t.get("active_reviewer") == lost_role and t["active_review"]:
                t["active_reviewer"] = successor["role_id"]
            t["blockers"] = [b for b in t["blockers"] if not resolved(b)]
            if not t["blockers"] and t["status"] == "blocked":
                target = t.get("before_block", "running")
                if target == "accepted":
                    from .commits import confirm, reviewed
                    from .verification import valid_evidence
                    valid_evidence(state, t, directory)
                    reviewed(state, t)
                    require(t["commits"], "commit_required", "Accepted task needs confirmed commits")
                    confirm(state, t, t["commits"][-1])
                t["status"] = target
    state["status"] = "blocked" if state["blockers"] else "active"
    head = repository(root).head()
    stale_worktrees = [{"task_id": key, "path": t["worktree"]["path"], "base": t["worktree"]["base"],
                       "head": head, "next": "worktree_refresh"}
                      for key, t in state["tasks"].items()
                      if t["status"] != "accepted" and t["worktree"]
                      and not t["worktree"].get("integrated") and not t["worktree"].get("removed")
                      and t["worktree"]["base"] != head]
    return {"status": state["status"], "issues": issues, "preserved_roles": state["roles"],
            "stale_worktrees": stale_worktrees, **({"check_registries": registries} if registries else {})}
