"""Structural refactoring checks; runtime evidence and semantic review stay with callers."""
from pathlib import Path
import re
from urllib.parse import urlsplit

from .documents import (InputError, ValidationError, MAX_DOCUMENT_CHARS, parse_markdown,
                        read_document, safe_yaml, valid_id, valid_slug)
from .paths import contained, verification_location


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def cycle_members(graph):
    """Bounded iterative elimination also identifies nodes downstream of a cycle."""
    remaining = {key: set(values) for key, values in graph.items()}
    while remaining:
        ready = {key for key, values in remaining.items() if not values}
        if not ready:
            return sorted(remaining)
        remaining = {key: values - ready for key, values in remaining.items() if key not in ready}
    return []


def ancestors(task, graph):
    found, pending = set(), list(graph.get(task, []))
    while pending:
        predecessor = pending.pop()
        if predecessor not in found:
            found.add(predecessor)
            pending.extend(graph.get(predecessor, []))
    return found


class RefactoringValidation:
    def __init__(self, project, root):
        self.project, self.root = project, root
        self.errors, self.records, self.origins = [], {}, {}

    def issue(self, record, code, message, path=None):
        rid = record.get("id") if record else None
        self.errors.append(dict(code=code, path=str(path or self.origins.get(rid, self.root)),
                                element_id=rid, message=message))

    def read(self, stage):
        paths = [self.root / "proposal.md", self.root / "design.md"]
        if stage == "plan":
            paths.append(self.root / "tasks.md")
        for path in paths:
            try:
                contained(self.root, path.relative_to(self.root))
                document = read_document(path, work_kind="refactoring")
                if document.meta["document_type"] != path.stem or document.meta["change_id"] != self.root.name:
                    raise ValidationError("document_identity", "Document type/change_id does not match its location", path)
                for record in document.records:
                    rid = record["id"]
                    if rid in self.records:
                        self.issue(record, "duplicate_id", f"ID occurs in multiple documents: {rid}", path)
                    else:
                        self.records[rid], self.origins[rid] = record, path
            except InputError:
                raise
            except ValidationError as exc:
                self.errors.append(dict(code=exc.code, path=str(exc.path or path),
                                        element_id=exc.element_id, message=exc.message))
        self.criteria = self.of_kind("criterion")
        self.local = self.of_kind("acceptance")
        self.tasks = self.of_kind("task")
        self.decisions = self.of_kind("decision")
        self.whole = self.of_kind("verification")

    def of_kind(self, kind):
        return {key: record for key, record in self.records.items() if record["sdd_record"] == kind}

    def text(self, record, *fields):
        for field in fields:
            if not nonempty_text(record.get(field)):
                self.issue(record, "record_text", f"{field} must be nonempty text")

    def refs(self, record, field, targets, nonempty=True, values=None):
        values = record.get(field) if values is None else values
        if not isinstance(values, list) or (nonempty and not values) or any(not isinstance(value, str) for value in values):
            self.issue(record, "reference_list", f"{field} must be a {'nonempty ' if nonempty else ''}list of local IDs")
            return []
        if len(set(values)) != len(values):
            self.issue(record, "duplicate_reference", f"Duplicate links in {field}")
        valid = []
        for value in values:
            if value not in targets:
                self.issue(record, "missing_reference", f"{field}: unresolved or wrong-kind reference {value}")
            else:
                valid.append(value)
        return valid

    def existing(self, relative):
        if not nonempty_text(relative):
            raise ValidationError("invalid_path", "Expected a nonempty project-relative path")
        return contained(self.project, relative.split("#", 1)[0], must_exist=True)

    def baseline(self, path):
        try:
            with path.open(encoding="utf-8-sig") as stream:
                tokens = parse_markdown(stream.read(MAX_DOCUMENT_CHARS + 1))
        except (OSError, UnicodeError) as exc:
            raise InputError("unreadable_input", str(exc), path) from exc
        headings = [tokens[i + 1].content for i, token in enumerate(tokens[:-1]) if token.type == "heading_open"]
        ids = {}
        for token in tokens:
            if token.type == "fence" and token.info.strip() == "yaml":
                try:
                    record = safe_yaml(token.content)
                except ValidationError as exc:
                    if exc.code == "yaml_mapping":
                        continue
                    raise
                if "sdd_record" in record:
                    rid = record.get("id")
                    if isinstance(rid, str):
                        ids[rid] = record["sdd_record"]
        return headings, ids

    def source(self, record):
        source = record.get("source")
        try:
            if not isinstance(source, dict):
                raise ValidationError("source", "preservation requires source")
            if source.get("kind") == "specification":
                if set(source) != {"kind", "path", "requirement"} or not nonempty_text(source["requirement"]):
                    raise ValidationError("source", "specification source requires path and requirement")
                headings, ids = self.baseline(self.existing(source["path"]))
                if source["requirement"] not in headings and source["requirement"] not in ids:
                    raise ValidationError("source_requirement", "Baseline requirement ID or exact heading was not found")
            elif source.get("kind") == "evidence":
                if set(source) != {"kind", "baseline_missing", "references", "observed", "assumptions"} or source["baseline_missing"] is not True:
                    raise ValidationError("source", "Evidence must explicitly declare baseline_missing: true")
                if not all(nonempty_text(source[key]) for key in ("observed", "assumptions")):
                    raise ValidationError("source", "Evidence requires observed behavior and assumptions")
                if not isinstance(source["references"], list) or not source["references"]:
                    raise ValidationError("source", "Evidence requires references")
                for reference in source["references"]:
                    if not nonempty_text(reference):
                        raise ValidationError("source", "Evidence references must be nonempty strings")
                    try:
                        url = urlsplit(reference)
                    except ValueError as exc:
                        raise ValidationError("source", f"Invalid evidence URL: {reference}") from exc
                    if url.scheme in {"http", "https"} and url.netloc:
                        continue
                    self.existing(reference)
            else:
                raise ValidationError("source", "Unknown source kind")
        except InputError:
            raise
        except ValidationError as exc:
            self.issue(record, exc.code, exc.message)

    def supersedes(self, record):
        links = record.get("supersedes")
        if not isinstance(links, list) or not links:
            self.issue(record, "supersedes", "supersedes must be a nonempty list of path/id or path/anchor links")
            return
        for link in links:
            try:
                if not isinstance(link, dict) or set(link) not in ({"path", "id"}, {"path", "anchor"}):
                    raise ValidationError("supersedes", "Each supersedes link requires path and either id or anchor")
                headings, ids = self.baseline(self.existing(link["path"]))
                if "id" in link:
                    if not valid_id(link["id"], "DEC") or ids.get(link["id"]) != "decision":
                        raise ValidationError("supersedes", "Superseded DEC was not found at path")
                else:
                    anchors = [re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings]
                    if not nonempty_text(link["anchor"]) or link["anchor"] not in headings + anchors:
                        raise ValidationError("supersedes", "Superseded heading/anchor was not found at path")
            except InputError:
                raise
            except ValidationError as exc:
                self.issue(record, exc.code, exc.message)

    def design(self):
        results = {key: record for key, record in self.criteria.items() if record["purpose"] == "result"}
        if not results:
            self.issue(None, "missing_results", "Design requires at least one result criterion", self.root / "design.md")
        parents = {key: [] for key in results}
        for rid, record in self.criteria.items():
            self.text(record, "conditions", "expected")
            scope = record["scope"]
            if not isinstance(scope, list) or not scope or not all(nonempty_text(value) for value in scope):
                self.issue(record, "criterion_scope", "scope must be a nonempty list of described areas")
            if record["purpose"] not in ("result", "preservation"):
                self.issue(record, "criterion_purpose", "purpose must be result or preservation")
            if record["purpose"] == "preservation" or "source" in record:
                self.source(record)
            if "parent" in record:
                target = record["parent"]
                if record["purpose"] != "result" or not isinstance(target, str) or target not in results:
                    self.issue(record, "criterion_parent", "parent must link a result to another local result criterion")
                elif target == rid:
                    self.issue(record, "self_reference", "Criterion may not parent itself")
                else:
                    parents[rid] = [target]
        cyclic = cycle_members(parents)
        if cyclic:
            self.issue(None, "parent_cycle", f"Criterion parent cycle: {cyclic}", self.root / "design.md")
        for record in self.decisions.values():
            self.refs(record, "criteria", self.criteria)
            if "supersedes" in record:
                self.supersedes(record)

    def scope(self, record):
        scope = record["scope"]
        if not isinstance(scope, list) or not scope:
            self.issue(record, "task_scope", "scope must be a nonempty list of modules and known relative paths")
            return
        for area in scope:
            if not isinstance(area, dict) or not {"module"} <= area.keys() or area.keys() - {"module", "paths"} or not nonempty_text(area["module"]):
                self.issue(record, "task_scope", "Each scope requires module and optional paths")
                continue
            if "paths" in area:
                paths = area["paths"]
                if not isinstance(paths, list) or not paths or not all(nonempty_text(value) for value in paths):
                    self.issue(record, "task_scope", "scope.paths must be a nonempty list of project-relative paths")
                    continue
                for path in paths:
                    try:
                        contained(self.project, path)
                    except ValidationError as exc:
                        self.issue(record, exc.code, exc.message)

    def check(self, record, check, allowed, whole=False):
        required = {"criteria", "test_description", "location", "run"}
        optional = {"execution_kind", "setup_task"} if whole else {"execution_kind"}
        if not whole:
            required.add("id")
        if not isinstance(check, dict) or not required <= check.keys() or check.keys() - required - optional:
            self.issue(record, "verification", f"Verification requires {sorted(required)}")
            return []
        if not whole and not valid_slug(check["id"]):
            self.issue(record, "verification_id", "Verification id must be a stable lowercase-kebab-case slug")
        from .check_kinds import execution_kind
        try:
            execution_kind(check)
        except ValueError as exc:
            self.issue(record, 'execution_kind', str(exc))
        criteria = self.refs(record, "verification.criteria", allowed, values=check["criteria"])
        if not nonempty_text(check["test_description"]):
            self.issue(record, "verification", "test_description must be nonempty text")
        try:
            verification_location(self.project, check["location"])
        except ValidationError as exc:
            self.issue(record, exc.code, exc.message)
        run = check["run"]
        if not isinstance(run, dict) or len(run) != 1 or next(iter(run), None) not in {"command", "procedure", "setup_required"}:
            self.issue(record, "verification_run", "run requires exactly one command, procedure or setup_required")
        elif "command" in run:
            command = run["command"]
            if not (isinstance(command, list) and command and all(isinstance(arg, str) and "\0" not in arg for arg in command) and command[0].strip()):
                self.issue(record, "verification_run", "command must be a nonempty argument array with a nonempty executable and no NUL")
        elif not all(nonempty_text(value) for value in run.values()):
            self.issue(record, "verification_run", "procedure and setup_required require nonempty text")
        elif "procedure" in run:
            try:
                self.existing(run["procedure"])
            except ValidationError as exc:
                self.issue(record, exc.code, exc.message)
        if whole:
            if isinstance(run, dict) and "setup_required" in run and "setup_task" not in check:
                self.issue(record, "setup_task", "A whole-work setup_required check requires setup_task")
            if "setup_task" in check and (not isinstance(check["setup_task"], str) or check["setup_task"] not in self.tasks):
                self.issue(record, "setup_task", "setup_task must name an existing local task")
        return criteria

    def test_changes(self, record):
        changes = record.get("test_changes")
        if not isinstance(changes, list):
            self.issue(record, "test_changes", "test_changes must be a list")
            return
        seen = set()
        required = {"id", "action", "group", "criteria", "reason"}
        for change in changes:
            if not isinstance(change, dict) or not required <= change.keys() or change.keys() - required - {"decision", "replacement_criteria"}:
                self.issue(record, "test_changes", "A test change requires id/action/group/criteria/reason and optional decision/replacement_criteria")
                continue
            cid = change["id"]
            if not valid_slug(cid) or cid in seen:
                self.issue(record, "test_change_id", "Test-change IDs must be unique stable slugs within their task")
            else:
                seen.add(cid)
            if change["action"] not in ("add", "adapt", "move", "remove"):
                self.issue(record, "test_changes", "Unknown test-change action")
            if not nonempty_text(change["group"]) or not nonempty_text(change["reason"]):
                self.issue(record, "test_changes", "Test group and reason must be nonempty text")
            affected = self.refs(record, "test_changes.criteria", self.criteria | self.local, values=change["criteria"])
            replacements = []
            if "replacement_criteria" in change:
                replacements = self.refs(record, "replacement_criteria", self.criteria | self.local, nonempty=False, values=change["replacement_criteria"])
            decision = change.get("decision")
            if "decision" in change and (not isinstance(decision, str) or decision not in self.decisions):
                self.issue(record, "test_change_decision", "decision must name a local DEC")
            if change["action"] == "remove" and not replacements and not (isinstance(decision, str) and decision in self.decisions):
                self.issue(record, "test_change_basis", "Removal requires replacement_criteria or an architectural decision retiring the old boundary")
            if change["action"] == "remove" and any(self.criteria.get(key, {}).get("purpose") == "preservation" for key in affected) and not replacements:
                self.issue(record, "test_change_preservation", "Removing a preservation check requires replacement criteria; a DEC alone cannot retire the obligation")

    def plan(self):
        results = {key: record for key, record in self.criteria.items() if record["purpose"] == "result"}
        preservation = {key: record for key, record in self.criteria.items() if record["purpose"] == "preservation"}
        local_owners = {key: [] for key in self.tasks}
        for rid, record in self.local.items():
            owner = record["task"]
            if not isinstance(owner, str) or owner not in self.tasks:
                self.issue(record, "acceptance_task", "Local acceptance must belong to an existing local task")
            else:
                local_owners[owner].append(rid)
            self.text(record, "conditions", "expected")
            if record["lifetime"] not in ("persistent", "transitional"):
                self.issue(record, "acceptance_lifetime", "lifetime must be persistent or transitional")
            if record["lifetime"] == "transitional":
                if "until_task" not in record or "replaced_by" not in record:
                    self.issue(record, "acceptance_transition", "Transitional acceptance requires until_task and nonempty replaced_by")
            elif "until_task" in record or "replaced_by" in record:
                self.issue(record, "acceptance_transition", "Only transitional local acceptance may have until_task/replaced_by")
        deps, incompatible, verified, contributions = {}, {key: set() for key in self.tasks}, {}, set()
        for rid, record in self.tasks.items():
            self.scope(record)
            contributions.update(self.refs(record, "contributes_to", results))
            preserved = self.refs(record, "preserves", preservation, nonempty=False)
            if record["preserves"] == [] and not nonempty_text(record.get("preservation_reason")):
                self.issue(record, "preservation_reason", "Empty preserves requires a nonempty preservation_reason for semantic review")
            if "preservation_reason" in record:
                self.text(record, "preservation_reason")
            deps[rid] = self.refs(record, "depends_on", self.tasks, nonempty=False)
            conflicts = self.refs(record, "cannot_parallel_with", self.tasks, nonempty=False) if "cannot_parallel_with" in record else []
            for target in deps[rid] + conflicts:
                if target == rid:
                    self.issue(record, "self_reference", "Task may not reference itself")
            for target in conflicts:
                incompatible[rid].add(target)
                incompatible[target].add(rid)
            if record["status"] not in ("pending", "in_progress", "done", "blocked"):
                self.issue(record, "task_status", "Unknown task status")
            if not local_owners[rid]:
                self.issue(record, "local_acceptance", "Each task requires at least one local acceptance criterion")
            allowed = set(local_owners[rid]) | set(preserved)
            checks = record["verification"]
            if not isinstance(checks, list) or not checks:
                self.issue(record, "verification", "verification must be a nonempty list")
                checks = []
            verified[rid], seen = set(), set()
            for check in checks:
                verified[rid].update(self.check(record, check, allowed))
                cid = check.get("id") if isinstance(check, dict) else None
                if isinstance(cid, str):
                    if cid in seen:
                        self.issue(record, "verification_id", f"Duplicate verification id: {cid}")
                    seen.add(cid)
            if allowed - verified[rid]:
                self.issue(record, "verification_coverage", f"Missing local/preservation verification for: {sorted(allowed - verified[rid])}")
            if "test_changes" in record:
                self.test_changes(record)
        if set(results) - contributions:
            self.issue(None, "contribution_coverage", f"No task contributes to result criteria: {sorted(set(results) - contributions)}", self.root / "tasks.md")
        numbers = [record["number"] for record in self.tasks.values()]
        if any(type(number) is not int for number in numbers) or sorted(numbers) != list(range(1, len(self.tasks) + 1)):
            self.issue(None, "task_numbers", "Task numbers must be a permutation of 1..N", self.root / "tasks.md")
        cyclic = cycle_members(deps)
        if cyclic:
            self.issue(None, "task_cycle", f"Dependency cycle or tasks downstream of cycle: {cyclic}", self.root / "tasks.md")
        self.transitions(deps, verified)
        whole_verified = set()
        for record in self.whole.values():
            allowed = set(self.criteria) | {key for key, local in self.local.items() if local["lifetime"] == "persistent"}
            whole_verified.update(self.check(record, {key: value for key, value in record.items() if key not in {"sdd_record", "id"}}, allowed, whole=True))
        if not self.whole:
            self.issue(None, "whole_verification", "Plan requires at least one whole-work verification record", self.root / "tasks.md")
        if set(self.criteria) - whole_verified:
            self.issue(None, "whole_coverage", f"Missing whole-work verification for: {sorted(set(self.criteria) - whole_verified)}", self.root / "tasks.md")
        persistent = {key for key, record in self.local.items() if record["lifetime"] == "persistent"}
        local_verified = set().union(*verified.values()) if verified else set()
        if persistent - local_verified - whole_verified:
            self.issue(None, "persistent_coverage", "Persistent local results require applicable task or whole-work checks", self.root / "tasks.md")
        done = {key for key, record in self.tasks.items() if record["status"] == "done"}
        return dict(progress=dict(done=len(done), total=len(self.tasks)), tasks=dict(
            available_by_graph=sorted(key for key, record in self.tasks.items() if record["status"] == "pending" and set(deps[key]) <= done),
            cannot_parallel_with={key: sorted(values) for key, values in incompatible.items()},
            parallel_safety="Requires reviewer assessment of shared files and other conflicts"))

    def transitions(self, deps, verified):
        replacements = {key: [] for key in self.local}
        for rid, record in self.local.items():
            if record["lifetime"] != "transitional":
                continue
            targets = self.refs(record, "replaced_by", self.criteria | self.local)
            replacements[rid] = [key for key in targets if key in self.local]
            until, owner = record.get("until_task"), record["task"]
            if not isinstance(until, str) or until not in self.tasks:
                self.issue(record, "until_task", "until_task must name an existing local task")
                continue
            predecessors = ancestors(until, deps)
            if not isinstance(owner, str) or until == owner or owner not in predecessors:
                self.issue(record, "until_task_reachability", "until_task must be another task downstream of the acceptance owner")
            for target in targets:
                if target == rid:
                    self.issue(record, "self_reference", "A criterion cannot replace itself")
                # Predecessor-owned checks remain owned there. Runtime must rerun them on
                # until_task's candidate and bind fresh evidence before retiring protection.
                target_owner = self.local.get(target, {}).get("task")
                available = isinstance(target_owner, str) and target_owner in predecessors | {until}
                if not available or target not in verified.get(target_owner, set()):
                    self.issue(record, "replacement_verification", f"Replacement {target} needs a check owned by until_task or a dependency predecessor; final-only evidence is insufficient")
        cyclic = cycle_members(replacements)
        if cyclic:
            self.issue(None, "replacement_cycle", f"Criterion replacement cycle: {cyclic}", self.root / "tasks.md")


def validate_refactoring(project_root, work_root, stage):
    project, root = Path(project_root).resolve(), Path(work_root).resolve()
    if stage not in {"documents", "plan"}:
        raise InputError("invalid_stage", "Expected documents or plan")
    if not root.is_relative_to(project):
        raise InputError("path_escape", "Work directory must be inside the project", root)
    expected = contained(project, f"sdd/refactoring/{root.name}")
    if root != expected or not valid_slug(root.name):
        raise ValidationError("work_kind_mismatch", "Refactoring documents require sdd/refactoring/<change_id>; correct the selected work or directory", root)
    validator = RefactoringValidation(project, root)
    validator.read(stage)
    validator.design()
    extra = validator.plan() if stage == "plan" else {}
    return dict(errors=validator.errors, warnings=[], **extra)
