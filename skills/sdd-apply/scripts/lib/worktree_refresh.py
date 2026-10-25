"""Replace stale task worktrees without discarding unfinished work or evidence."""
from .repository import repository
from .path_resolution import resolve
from copy import deepcopy
import json
from pathlib import Path

from .common import contained, digest, require, write_json
from . import artifact_storage as artifacts
from .artifact_storage import write as atomic
from .effects import intent, observed
from .state import snapshot
from .worktrees import inventory


def registered(root, path):
    return repository(root).worktree(path) is not None


def owned_tree(root, paths, base):
    return repository(root).tree_for_paths(paths, base)


def source_unchanged(state, old, saved):
    path = old["path"]
    require(repository(path).head() == old["base"]
            and not repository(path).branch(),
            "executor_commit", "Preserve unexpected task commits or branch changes")
    require(inventory(path) == saved["inventory"] and snapshot(state, path) == saved["source"]
            and repository(path).index_patch(full=True) ==
            artifacts.read_bytes(artifacts.contained(saved["artifacts"], "index.patch")),
            "refresh_source_changed", "Source worktree changed; preserve both trees")


def finish(state, task, directory, effect, journal, resolution=None):
    saved = journal["request"]["precondition"]
    old, new = saved["old"], saved["new"]
    root = state["basis"]["project_root"]
    require(repository(root).head() == saved["base"], "refresh_head_changed",
            "Execution HEAD changed during refresh; preserve both trees")
    require(registered(root, new) and repository(new).head() == saved["base"]
            and not repository(new).branch(),
            "refresh_destination_changed", "Expected registered detached replacement")
    require(not repository(new).has_conflicts(), "refresh_conflict",
            f"Resolve the recorded transfer in {new}; preserve the old worktree")
    after = snapshot(state, new)
    files = inventory(new)
    baseline = journal["baseline"]
    if journal.get("expected_tree") and not resolution and not journal.get("validated", {}).get("resolution"):
        actual_tree = owned_tree(new, task["paths"], saved["base"])
        require(actual_tree == journal["expected_tree"], "refresh_destination_changed",
                "Replacement differs from the recorded merge; preserve both trees")
    changed = {p for p in set(files) | set(baseline["inventory"])
               if files.get(p) != baseline["inventory"].get(p)}
    changed |= {p for p in set(after["files"]) | set(baseline["snapshot"]["files"])
                if after["files"].get(p) != baseline["snapshot"]["files"].get(p)}
    changed.update(repository(new).changed_index_paths(saved["base"]))
    require(changed <= set(task["paths"]), "refresh_scope", "Replacement changed files outside task ownership")
    # Persist the verified destination before deletion, so a crash between Git
    # cleanup and the state transaction can safely finish the same operation.
    if "validated" in journal:
        require(journal["validated"]["snapshot"] == after and journal["validated"]["inventory"] == files,
                "refresh_destination_changed", "Replacement changed after transfer validation")
    else:
        require(Path(old["path"]).exists() and registered(root, old["path"]),
                "refresh_source_missing", "Preserve the intent; source disappeared before validation")
        source_unchanged(state, old, saved)
        journal["validated"] = {"snapshot": after, "inventory": files, "resolution": resolution}
        write_json(effect, journal)
    if Path(old["path"]).exists():
        require(registered(root, old["path"]), "unregistered_worktree", "Source is no longer registered")
        source_unchanged(state, old, saved)
        workspace = resolve(old["workspace"])
        source = contained(workspace, str(Path(old["path"]).relative_to(workspace)))
        require(str(source) == old["path"] and source != resolve(root),
                "worktree_escape", "Only the registered task worktree may be removed")
        repository(root).remove_worktree(source)
    require(not registered(root, old["path"]), "refresh_cleanup", "Old worktree is still registered")
    task.setdefault("worktree_history", []).append({
        "worktree": old, "refresh_event": journal["request"]["event"]["event_id"],
        "candidate": task["candidate"], "transfer": task.get("transfer"),
        "baseline_checks": task.get("baseline_checks"), "start_snapshot": task.get("start_snapshot"),
        "active_review": task["active_review"], "active_reviewer": task.get("active_reviewer"),
    })
    task["worktree"] = {**old, "path": new, "base": saved["base"], "owner": state["owner"],
                        "snapshot": baseline["snapshot"], "inventory": baseline["inventory"], "integrated": False}
    task["start_snapshot"] = baseline["snapshot"]
    task["candidate"] = None
    for field in ("transfer", "freeze_base", "active_reviewer"):
        task.pop(field, None)
    task["active_review"] = None
    if journal["validated"].get("resolution"):
        task["executor"] = journal["validated"]["resolution"]["role_id"]
    # Historical evidence remains available, but its old root cannot validate
    # a replacement candidate. Repair reservations and lifetime counters survive.
    phase = "repairing" if task["active_repair"] else "running"
    if task["status"] == "blocked":
        task["before_block"] = phase
    elif task["status"] != "pending":
        task["status"] = phase
    state["final"] = None
    result = {"worktree": task["worktree"], "removed": old["path"],
              "next": "Finish implementation; freeze a new candidate and run independent checks and review"}
    return observed(effect, journal, result)


def transition(state, task, event, directory):
    require(task and task["worktree"] and state["mode"] == "parallel" and state["parallel_request"],
            "parallel_required", "Refresh requires an authorized parallel task")
    old = task["worktree"]
    require(task["status"] != "accepted" and not old.get("integrated") and not old.get("removed")
            and not task.get("integration_active"), "refresh_phase", "Refresh only unfinished, unintegrated worktrees")
    require(not any(state["roles"][r]["status"] == "active" for r in task["roles"]),
            "writer_active", "Stop and reconcile all task roles before refreshing")
    require(not task.get("procedures"), "procedure_active", "Finish pending procedures first")
    root = state["basis"]["project_root"]
    require(repository(root).branch() == state["basis"]["branch"],
            "branch_changed", "Restore the execution branch")
    effects = Path(directory) / "runs" / state["run_id"] / "effects"
    p = event["payload"]
    resolving = event["type"] == "worktree_refresh_resolve"
    original_id = p.get("intent_id") if resolving else event["event_id"]
    require(isinstance(original_id, str) and original_id, "refresh_intent", "Reference the original refresh event")
    effect = artifacts.contained(directory, f"runs/{state['run_id']}/effects/{original_id}.json")
    for pending in artifacts.paths(effects, "*.json"):
        record = json.loads(artifacts.read_text(pending))
        if record["phase"] != "prepared":
            continue
        operation = record["request"]["operation"]
        require(operation != "integrate", "integration_unresolved", "Reconcile pending integration before refresh")
        require(not (operation == "worktree_refresh" and record["request"]["task_id"] == task["plan"]["id"]
                     and pending != effect), "refresh_pending", "Recover the original refresh intent before starting another")
    if resolving:
        require(artifacts.is_file(effect) and p.get("resolution") and p.get("role_id"),
                "refresh_resolution", "Supply intent_id, resolution and finished resolver role_id")
        journal = json.loads(artifacts.read_text(effect))
        require(journal["request"]["operation"] == "worktree_refresh"
                and journal["request"]["task_id"] == task["plan"]["id"]
                and journal["request"]["precondition"]["old"] == old and journal.get("apply_started"),
                "refresh_intent", "Expected this task's pending refresh")
        role = state["roles"].get(p["role_id"])
        require(role and role["kind"] == "executor" and role["task_id"] == task["plan"]["id"]
                and role["status"] == "finished" and role.get("trace"),
                "resolution_role", "A registered resolver must finish and return its host trace")
        return finish(state, task, directory, effect, journal, p)
    require(p.get("reason") and p.get("evidence"), "refresh_evidence", "Record why refresh is needed and evidence of the fixed base")
    if artifacts.exists(effect):
        effect, journal = intent(directory, state, event, "worktree_refresh", {})
    else:
        require(registered(root, old["path"]), "unregistered_worktree", "Source must be a registered worktree")
        require(repository(old["path"]).head() == old["base"]
                and not repository(old["path"]).branch(),
                "executor_commit", "Executor changes must remain uncommitted")
        base = repository(root).head()
        require(base != old["base"], "refresh_unchanged", "Worktree already uses current HEAD")
        files, source = inventory(old["path"]), snapshot(state, old["path"])
        changed = {name for name in set(files) | set(old["inventory"])
                   if files.get(name) != old["inventory"].get(name)}
        changed |= {name for name in set(source["files"]) | set(old["snapshot"]["files"])
                    if source["files"].get(name) != old["snapshot"]["files"].get(name)}
        changed.update(repository(old["path"]).changed_index_paths(old["base"]))
        require(changed <= set(task["paths"]), "unknown_worktree_data",
                "Preserve and account for changed, untracked or ignored data outside task ownership")
        new = contained(old["workspace"], state["run_id"] + "/" + task["plan"]["id"] + "-" + event["event_id"])
        require(not new.exists() and not registered(root, new), "refresh_destination_exists", "Replacement path must be unused")
        artifact_directory = artifacts.contained(directory, f"runs/{state['run_id']}/refresh/{event['event_id']}")
        tree = owned_tree(old["path"], task["paths"], old["base"])
        patch = repository(old["path"]).diff_trees(old["base"], tree)
        atomic(artifact_directory / "task.patch", patch)
        atomic(artifact_directory / "index.patch", repository(old["path"]).index_patch(full=True))
        effect, journal = intent(directory, state, event, "worktree_refresh", {
            "old": deepcopy(old), "new": str(new), "base": base, "inventory": files,
            "source": source, "patch_hash": digest(patch), "artifacts": str(artifact_directory)})
    saved = journal["request"]["precondition"]
    require(repository(root).head() == saved["base"], "refresh_head_changed", "Execution HEAD changed during refresh")
    new = Path(saved["new"])
    if "validated" in journal:
        return finish(state, task, directory, effect, journal)
    source_unchanged(state, old, saved)
    if not new.exists():
        require(not journal.get("baseline"), "refresh_destination_missing", "Preserve the intent; replacement disappeared")
        repository(root).create_worktree(new, saved["base"])
    require(registered(root, new) and repository(new).head() == saved["base"],
            "refresh_destination_changed", "Expected the recorded replacement worktree")
    if "baseline" not in journal:
        require(not repository(new).dirty(include_ignored=True),
                "refresh_destination_changed", "New worktree must be pristine before transfer")
        journal["baseline"] = {"snapshot": snapshot(state, new), "inventory": inventory(new)}
        write_json(effect, journal)
    patch = artifacts.contained(saved["artifacts"], "task.patch")
    require(digest(artifacts.read_bytes(patch)) == saved["patch_hash"], "transfer_corrupt", "Saved refresh patch changed")
    pristine = (not repository(new).has_conflicts()
                and snapshot(state, new) == journal["baseline"]["snapshot"]
                and inventory(new) == journal["baseline"]["inventory"])
    if journal.get("apply_started") and not pristine:
        require(not repository(new).has_conflicts(), "refresh_conflict",
                f"Preserved both trees; resolve transfer in {new} using worktree_refresh_resolve")
        require(journal.get("expected_tree"), "refresh_ambiguous",
                "Inspect the recorded replacement; use worktree_refresh_resolve after resolving")
        require(owned_tree(new, task["paths"], saved["base"]) == journal["expected_tree"],
                "refresh_destination_changed", "Replacement differs from the recorded merge; preserve both trees")
    else:
        require(pristine, "refresh_destination_changed", "Replacement changed before transfer")
        # Compute the intended merge without touching the real index/worktree.
        # After a crash, reverse applicability alone cannot detect extra edits.
        journal["expected_tree"] = repository(new).preview_patch(saved["base"], patch)
        journal["apply_started"] = True
        write_json(effect, journal)
        if artifacts.read_bytes(patch):
            repository(new).apply_patch(patch)
    return finish(state, task, directory, effect, journal)
