"""Cross-document traceability, coverage, graph and verification checks."""
from pathlib import Path
from urllib.parse import urlsplit

from .documents import InputError, ValidationError, read_document, valid_id, parse_markdown, MAX_DOCUMENT_CHARS
from .paths import contained, change_root as resolve_change


def validate_documents(project_root: Path, change_root: Path, stage: str):
    project_root, change_root = Path(project_root).resolve(), Path(change_root).resolve()
    if not change_root.is_relative_to(project_root):
        raise InputError("path_escape", "Change directory must be inside the project", change_root)
    if stage not in {"documents", "plan"}:
        raise InputError("invalid_stage", "Expected documents or plan")
    errors, warnings, docs = [], [], []
    def issue(code, message, path="", element_id=None):
        errors.append(dict(code=code, path=str(path), element_id=element_id, message=message))
    def guarded_path(value, exists=True):
        return contained(project_root, value.split("#", 1)[0], must_exist=exists)
    specs_root = contained(change_root, "specs")
    paths = [change_root / "proposal.md", change_root / "design.md"]
    paths += sorted(specs_root.glob("**/spec.md"))
    if len(paths) == 2:
        issue("missing_specs", "At least one capability spec is required", specs_root)
    if stage == "plan":
        paths.append(change_root / "tasks.md")
    for path in paths:
        try:
            contained(change_root, path.relative_to(change_root))
            doc = read_document(path)
            expected = "spec" if path.name == "spec.md" else path.stem
            if doc.meta.get("document_type") != expected or doc.meta.get("change_id") != change_root.name:
                raise ValidationError("document_identity", "Document type/change_id does not match its location", path)
            if expected == "spec" and doc.meta["capability"] != path.parent.relative_to(specs_root).as_posix():
                raise ValidationError("capability", "Capability does not match spec directory", path)
            docs.append(doc)
        except InputError:
            raise
        except ValidationError as exc:
            issue(exc.code, exc.message, exc.path or path, exc.element_id)
    index, origins = {}, {}
    for doc in docs:
        for record in doc.records:
            rid = record["id"]
            if rid in index:
                issue("duplicate_id", f"ID occurs in multiple documents: {rid}", doc.path, rid)
            index[rid], origins[rid] = record, doc.path
    def problem(record, code, message):
        issue(code, message, origins[record["id"]], record["id"])
    def refs(record, field, prefix, nonempty=True, local_only=False):
        values = record.get(field)
        if not isinstance(values, list) or (nonempty and not values) or any(not isinstance(x, str) for x in values):
            problem(record, "reference_list", f"{field} must be a {'nonempty ' if nonempty else ''}list of IDs")
            return []
        if len(set(values)) != len(values):
            problem(record, "duplicate_reference", f"Duplicate links in {field}")
        valid = []
        for value in values:
            if "/" in value:
                if local_only:
                    problem(record, "external_reference", f"{field} requires local {prefix} IDs: {value}")
                else:
                    try:
                        other, remote_id = value.split("/", 1)
                        remote_root = resolve_change(project_root, other)
                        if not valid_id(remote_id, prefix):
                            raise ValidationError("invalid_reference", f"Invalid external reference: {value}")
                        found = any(any(r.get("id") == remote_id for r in read_document(contained(remote_root, p.relative_to(remote_root))).records) for p in contained(remote_root, "specs").glob("**/spec.md"))
                        if not found:
                            raise ValidationError("missing_reference", f"Unresolved external reference: {value}")
                        warnings.append(dict(code="external_context", path=str(origins[record['id']]), element_id=record['id'], message=f"External context does not satisfy local traceability: {value}"))
                    except ValidationError as exc:
                        if isinstance(exc, InputError):
                            raise
                        problem(record, exc.code, exc.message)
                continue
            if not valid_id(value, prefix) or value not in index:
                problem(record, "missing_reference", f"{field}: unresolved {prefix} reference {value}")
            else:
                valid.append(value)
        return valid
    requirements = {k: r for k, r in index.items() if r["sdd_record"] == "requirement"}
    acceptance = {k: r for k, r in index.items() if r["sdd_record"] == "acceptance"}
    tasks = {k: r for k, r in index.items() if r["sdd_record"] == "task"}
    children = {k: [] for k in requirements}
    for record in index.values():
        kind = record["sdd_record"]
        if kind == "acceptance":
            req = record["requirement"]
            if not isinstance(req, str) or req not in requirements:
                problem(record, "acceptance_requirement", f"Acceptance requires one local requirement: {req}")
            else:
                children[req].append(record["id"])
            for field in ("conditions", "expected"):
                if not isinstance(record[field], str) or not record[field].strip():
                    problem(record, "acceptance_text", f"{field} must be nonempty text")
        elif kind == "decision":
            refs(record, "requirements", "REQ")
        elif kind == "requirement":
            if record["operation"] not in ("add", "modify", "remove"):
                problem(record, "operation", "operation must be add, modify or remove")
            if record["operation"] in ("modify", "remove") or "source" in record:
                try:
                    source = record.get("source")
                    if not isinstance(source, dict):
                        raise ValidationError("source", "modify/remove requires source")
                    if source.get("kind") == "specification":
                        if set(source) != {"kind", "path", "requirement"} or not all(isinstance(source[x], str) and source[x].strip() for x in ("path", "requirement")):
                            raise ValidationError("source", "specification source requires path and requirement")
                        baseline = guarded_path(source["path"])
                        with baseline.open(encoding="utf-8-sig") as stream:
                            content = stream.read(MAX_DOCUMENT_CHARS + 1)
                        tokens = parse_markdown(content)
                        headings = [tokens[i + 1].content for i, t in enumerate(tokens[:-1]) if t.type == "heading_open"]
                        ids = []
                        from .documents import safe_yaml
                        for token in tokens:
                            if token.type == "fence" and token.info.strip() == "yaml" and "sdd_record:" in token.content:
                                ids.append(safe_yaml(token.content).get("id"))
                        if source["requirement"] not in headings + ids:
                            raise ValidationError("source_requirement", "Baseline requirement ID or exact heading was not found")
                    elif source.get("kind") == "evidence":
                        if set(source) != {"kind", "baseline_missing", "references", "observed", "assumptions"} or source["baseline_missing"] is not True:
                            raise ValidationError("source", "Evidence must explicitly declare baseline_missing: true")
                        if not all(isinstance(source[x], str) and source[x].strip() for x in ("observed", "assumptions")):
                            raise ValidationError("source", "Evidence requires observed behavior and assumptions")
                        if not isinstance(source["references"], list) or not source["references"]:
                            raise ValidationError("source", "Evidence requires references")
                        for reference in source["references"]:
                            if not isinstance(reference, str) or not reference.strip():
                                raise ValidationError("source", "Evidence references must be nonempty strings")
                            try:
                                url = urlsplit(reference)
                            except ValueError as exc:
                                raise ValidationError("source", f"Invalid evidence URL: {reference}") from exc
                            if url.scheme in {"http", "https"} and url.netloc:
                                continue
                            guarded_path(reference)
                    else:
                        raise ValidationError("source", "Unknown source kind")
                except (OSError, UnicodeError) as exc:
                    raise InputError("unreadable_input", str(exc), origins[record["id"]]) from exc
                except ValidationError as exc:
                    problem(record, exc.code, exc.message)
    for rid, kids in children.items():
        if not kids:
            problem(requirements[rid], "requirement_without_acceptance", "Requirement must have at least one acceptance criterion")
    result = dict(errors=errors, warnings=warnings)
    if stage != "plan":
        return result
    owners = {k: [] for k in acceptance}
    deps, incompatible = {}, {k: set() for k in tasks}
    numbers = []
    for rid, record in tasks.items():
        covers = refs(record, "covers", "AC", local_only=True)
        for criterion in covers:
            owners[criterion].append(rid)
        deps[rid] = refs(record, "depends_on", "TASK", nonempty=False, local_only=True)
        conflicts = refs(record, "cannot_parallel_with", "TASK", nonempty=False, local_only=True) if "cannot_parallel_with" in record else []
        for target in deps[rid] + conflicts:
            if target == rid:
                problem(record, "self_reference", "Task may not reference itself")
        for target in conflicts:
            incompatible[rid].add(target)
            incompatible[target].add(rid)
        numbers.append(record["number"])
        if record["status"] not in ("pending", "in_progress", "done", "blocked"):
            problem(record, "task_status", "Unknown task status")
        checks = record["verification"]
        verified = set()
        if not isinstance(checks, list) or not checks:
            problem(record, "verification", "verification must be a nonempty list")
            checks = []
        for check in checks:
            if not isinstance(check, dict) or set(check) != {"criteria", "test_description", "location", "run"}:
                problem(record, "verification", "Each verification requires criteria, test_description, location and run")
                continue
            criteria = check["criteria"]
            if not isinstance(criteria, list) or not criteria or any(not isinstance(x, str) or x not in covers for x in criteria):
                problem(record, "verification_criteria", "Verification criteria must be a nonempty subset of covers")
            else:
                verified.update(criteria)
            for field in ("test_description", "location"):
                if not isinstance(check[field], str) or not check[field].strip():
                    problem(record, "verification", f"{field} must be nonempty text")
            run = check["run"]
            if not isinstance(run, dict) or len(run) != 1 or next(iter(run), None) not in {"command", "procedure", "setup_required"} or not all(isinstance(x, str) and x.strip() for x in run.values()):
                problem(record, "verification_run", "run requires exactly one nonempty command, procedure or setup_required")
            elif "procedure" in run:
                try:
                    guarded_path(run["procedure"])
                except ValidationError as exc:
                    problem(record, exc.code, exc.message)
        if set(covers) - verified:
            problem(record, "verification_coverage", f"Missing verification for: {sorted(set(covers) - verified)}")
    for ac, assigned in owners.items():
        if len(assigned) != 1:
            problem(acceptance[ac], "task_coverage", f"Expected one task owner, got {assigned}")
    if any(type(n) is not int for n in numbers) or sorted(numbers) != list(range(1, len(tasks) + 1)):
        issue("task_numbers", "Task numbers must be a permutation of 1..N", change_root / "tasks.md")
    # Iterative topological elimination avoids recursion limits on large plans.
    remaining = {rid: set(values) for rid, values in deps.items()}
    while remaining:
        ready = {rid for rid, values in remaining.items() if not values}
        if not ready:
            issue("task_cycle", f"Dependency cycle or tasks downstream of cycle: {sorted(remaining)}", change_root / "tasks.md")
            break
        remaining = {rid: values - ready for rid, values in remaining.items() if rid not in ready}
    done = {rid for rid, record in tasks.items() if record["status"] == "done"}
    result["progress"] = dict(done=len(done), total=len(tasks))
    result["tasks"] = dict(available_by_graph=sorted(rid for rid, record in tasks.items() if record["status"] == "pending" and set(deps[rid]) <= done), cannot_parallel_with={rid: sorted(values) for rid, values in incompatible.items()}, parallel_safety="Requires reviewer assessment of shared files and other conflicts")
    return result
