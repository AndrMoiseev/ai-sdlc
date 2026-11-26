"""Compare A01–A10 against the pinned architecture scripts, including output files.

The process boundary is necessary for the project command's cwd, argv and call
count, as well as stdin, exit codes, retained reports and atomic state replacement.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

import pilot


FULL = "2026-11-15T12-00-00Z"
FOCUSED = "2026-11-15T13-00-00Z"
STATE = "2026-11-15T14-00-00Z"
FAILED = "2026-11-15T15-00-00Z"
LEFT = "src/A.kt"
RIGHT = "src/B.kt"


def ensure(condition, message):
    if not condition:
        raise pilot.PilotFailure(message)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False) + "\n")


def as_json(data):
    return json.loads(data, object_pairs_hook=pilot.unique_object, parse_constant=pilot.invalid_constant,
                      parse_int=Decimal, parse_float=Decimal)


def load(path):
    return as_json(path.read_bytes())


def run_with_input(command, cwd, deadline, data):
    pilot.time_remaining(deadline)
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt"
               else {"start_new_session": True})
    with subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **options) as process:
        try:
            stdout, stderr = process.communicate(data, timeout=pilot.time_remaining(deadline))
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=5, **options)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if process.poll() is None:
                    process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            raise TimeoutError(f"architect deadline exceeded while running {command!r}") from exc
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def normalize_times(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "collected_at":
                timestamp = datetime.fromisoformat(item)
                ensure(timestamp.utcoffset().total_seconds() == 0 and
                       abs((datetime.now(timezone.utc) - timestamp).total_seconds()) <= pilot.TIME_LIMIT,
                       f"invalid collection timestamp {item!r}")
                value[key] = "<observed UTC collection time>"
            else:
                normalize_times(item)
    elif isinstance(value, list):
        for item in value:
            normalize_times(item)
    return value


def compare_value(left, right, channel):
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(left.keys() | right.keys()):
            compare_value(left.get(key, pilot.MISSING), right.get(key, pilot.MISSING), f"{channel}/{key}")
    elif isinstance(left, list) and isinstance(right, list):
        for index in range(max(len(left), len(right))):
            compare_value(left[index] if index < len(left) else pilot.MISSING,
                          right[index] if index < len(right) else pilot.MISSING, f"{channel}/{index}")
    elif isinstance(left, Decimal) and isinstance(right, Decimal) and (left % 1 or right % 1):
        # libm implementations can round powers differently by a few last-place bits.
        ensure(abs(left - right) <= max(abs(left), abs(right)) * Decimal("2e-15"),
               f"{channel}: Python={left}, Go={right}")
    else:
        pilot.equal(left, right, channel, ("Python", "Go"))


def capture_files(project, deadline):
    result = {}
    for relative, entry in pilot.snapshot(project, deadline).items():
        path = project / relative
        if entry[0] != "file" or path.name == "state.json" or "raw" in path.parts:
            result[relative] = entry
        elif path.suffix in (".json", ".jsonl", ".log", ".md") and ("memory" in path.parts or path.name == "task.log"):
            data = path.read_bytes()
            if path.suffix == ".json":
                try:
                    data = normalize_times(as_json(data))
                except ValueError:
                    pass  # Some prerequisite tests intentionally prepare invalid files.
            elif path.suffix in (".jsonl", ".log"):
                data = [normalize_times(as_json(line)) for line in data.splitlines() if line.strip()]
            elif path.name == "status.md":
                data = re.sub(rb"(?<=\xd0\xa1\xd0\xb1\xd0\xbe\xd1\x80: )\d{4}-\d\d-\d\dT[\d:.]+\+00:00", b"<observed UTC collection time>", data)
            result[relative] = data
        else:
            result[relative] = entry
    return result


def fixtures(revision, today):
    sources = {LEFT: "package sample.alpha\nclass A\n", RIGHT: "package sample.beta\nclass B\n"}
    files = []
    scc = []
    packages = []
    findings = []
    for index, file in enumerate(sources):
        package = ["sample.alpha", "sample.beta"][index]
        symbol = ["A", "B"][index]
        tokens = [{"start": offset*2, "end": offset*2+1, "type": "ID", "text": str(offset)} for offset in range(105)]
        files.append({"file": file, "package": package, "tokens": tokens,
                      "functions": [{"start": 0, "end": 210, "nested": False, "cognitive_complexity": 20 - index*10}],
                      "containers": [{"start": 0, "end": 210, "kind": "function"}]})
        scc.append({"Location": file, "Lines": 2, "Code": 2, "Comment": 0, "Blank": 0})
        packages.append(f'''<package name="{package.replace('.', '/')}"><class name="{package.replace('.', '/')}/{symbol}">
<method name="f" desc="()I"><counter type="INSTRUCTION" covered="4" missed="4"/>
<counter type="BRANCH" covered="1" missed="1"/><counter type="COMPLEXITY" covered="2" missed="2"/></method>
</class><sourcefile name="{symbol}.kt"><line nr="1" ci="2" mi="1"/><line nr="2" ci="0" mi="2"/>
<counter type="LINE" covered="1" missed="1"/><counter type="BRANCH" covered="1" missed="1"/>
</sourcefile></package>''')
        findings.append({"ruleId": "CyclomaticComplexMethod", "message": {"text": "Cyclomatic Complexity (complexity: 14)"},
                         "locations": [{"physicalLocation": {"artifactLocation": {"uri": file}, "region": {"startLine": 2}}}]})
    changes = {LEFT: {"added": 2, "deleted": 1, "binary": False},
               RIGHT: {"added": 1, "deleted": 0, "binary": False}}
    commits = [{"revision": f"{index:040x}", "date": today, "production_files": 2, "changes": changes}
               for index in range(1, 7)]
    report_specs = {
        "dependencies": ("jdeps", "build/dependencies.txt", "   sample.alpha.A -> sample.beta.B\n   sample.beta.B -> sample.alpha.A\n"),
        "history": ("git-history", "build/history.json", {"format": "git-history", "first_parent": True, "renames": True,
              "since": "2020-01-01", "until": "2099-01-01", "commits": commits}),
        "sizes": ("scc", "build/sizes.json", [{"Name": "Kotlin", "Files": scc}]),
        "kotlin": ("kotlin-measurements", "build/kotlin.json", {"format": "kotlin-measurements", "version": 2, "complete": True,
                     "measurement_profile": "kotlin-tokens-functions-1", "tool_version": "1.23.8", "files": files}),
        "complexity": ("detekt-sarif", "build/complexity.sarif", {"runs": [{"results": findings}]}),
        "coverage": ("jacoco", "build/coverage.xml", "<report>" + "".join(packages) + "</report>"),
    }
    reports, artifacts = {}, {}
    for name, (format_name, path, payload) in report_specs.items():
        reports[path] = payload if isinstance(payload, str) else json.dumps(payload)
        artifacts[name] = {"path": path, "format": format_name, "tool": name, "version": "fixture", "command": [name]}
    artifacts["coverage"].update(complete=True, test_result="passed")
    artifacts["complexity"]["complete_mcc"] = True
    settings = {"schema_version": 1, "architect": {"collection": {
        "command": ["mise", "run", "audit inputs"], "artifacts": artifacts,
    }}}
    config = {"source_roots": ["src"], "package_prefixes": ["sample"],
              "modules": {"alpha": ["sample.alpha"], "beta": ["sample.beta"]},
              "class_files": {"sample.alpha.A": LEFT, "sample.beta.B": RIGHT}}
    state = json.loads((revision / "assets/audit-state.example.json").read_bytes())
    state["report"] = STATE
    state["objective"] = "Продолжить аудит Kotlin"
    return sources, reports, settings, config, state


def scenario_calls(project, transport, revision, today, execute, cases):
    tech_debt = project / "memory/tech-debt"
    full, focused, state_dir, failed = [tech_debt / "audits" / name for name in (FULL, FOCUSED, STATE, FAILED)]
    sources, reports, settings, config, state = fixtures(revision, today)
    for file, text in sources.items():
        write(project / file, text)
    settings_path = project / ".sdd/settings.json"
    dump(settings_path, settings)
    override = project / ".sdd/architect/analysis-policy.json"
    dump(override, {"investigation": {"candidate_group_limit": 3}})
    report_fixture = transport / "reports.json"
    dump(report_fixture, {"reports": reports})
    os.environ["SDD_SETUP_FIXTURE"] = str(report_fixture)
    policy_path = full / "resolved-policy.json"
    collection_path = full / "collection.json"

    def call(case, command, *args, message="", code=0, data=None, check=lambda output: True, family="metrics", read_only=False):
        if case not in cases:
            return
        observed = execute(case, family, command, args, code, message, data, read_only)
        ensure(check(observed), f"{case} {command} {args!r}: independent expectation failed: {observed!r}")
        return observed

    call("A01", "policy", "--repository", project, "--get", "investigation.candidate_group_limit", check=lambda o: o == 3, read_only=True)
    call("A01", "policy", "--repository", project, "--output", policy_path, check=lambda o: o["output"] == str(policy_path))
    if "A01" in cases:
        ensure(load(policy_path)["investigation"]["candidate_group_limit"] == 3, "A01 resolved policy file omitted override")
    call("A01", "policy", "--repository", project, "--get", "investigation.missing", code=2, message="Unknown policy key: investigation.missing", read_only=True)
    call("A02", "collection-settings", "--repository", project, check=lambda o: o == settings["architect"]["collection"], read_only=True)
    broken_settings = deepcopy(settings)
    del broken_settings["architect"]["collection"]["artifacts"]["coverage"]
    dump(settings_path, broken_settings)
    call("A02", "collection-settings", "--repository", project, code=2, message="Missing configured sources: ['coverage']", read_only=True)
    dump(settings_path, settings)

    config_path = full / "collection-input.json"
    external_config = transport / "collection-input.json"
    dump(external_config, config)
    config_args = ["--repository", project, "--output", config_path]
    call("A03", "configure", *config_args, data=external_config.read_bytes(), check=lambda o: o["configuration"] == str(config_path))
    if "A03" in cases:
        before = config_path.read_bytes()
    call("A03", "configure", *config_args, "--input", external_config)
    call("A03", "configure", *config_args, data=b'{"source_roots": ["../escape"]}',
         code=2, message="use a project-relative path with / and no parent traversal", read_only=True)
    call("A03", "configure", "--repository", project, "--input", external_config, "--output", transport / "collection-input.json",
         code=2, message="Write outputs inside", read_only=True)
    if "A03" in cases:
        ensure(load(config_path) == config and config_path.read_bytes() == before, "A03 stdin and file writes differed")
    else:
        dump(config_path, config)
    metrics_cases = set(cases) & {"A01", "A03", "A04", "A05", "A06", "A07"}
    if metrics_cases:
        execute("A04", "metrics", "collect", ["--repository", project, "--config", config_path, "--output", full],
                0, "", None, False)
        ensure(load(collection_path)["status"] == "complete", "A04 full collection did not complete")
        launches = [as_json(line) for line in (project / "task.log").read_bytes().splitlines()]
        ensure(launches == [{"argv": ["mise", "run", "audit inputs"], "cwd": str(project)}], "A04 wrong process launch")
        ensure(load(full / "metrics/quality-indicators.json")["project"]["coverage"]["line"]["value"] == Decimal("0.5"),
               "A04 line coverage expected 1/2")
        ensure(load(full / "metrics/quality-indicators.json")["project"]["duplication"]["tokens"] == 210,
               "A04 expected two complete clone spans")
    call("A03", "configure", *config_args, "--input", external_config, code=2,
         message="Collection has started", read_only=True)
    call("A01", "policy", "--collection", collection_path, "--get", "investigation.candidate_group_limit", check=lambda o: o == 3, read_only=True)

    if "A04" in cases or "A07" in cases:
        focused_config = {**config, "artifacts": {name: settings["architect"]["collection"]["artifacts"][name]
                                                for name in ("coverage", "complexity")}}
        dump(focused / "collection-input.json", focused_config)
        execute("A04", "metrics", "collect", ["--repository", project, "--config", focused / "collection-input.json",
                "--output", focused, "--focused"], 0, "", None, False)
        result = load(focused / "collection.json")
        ensure(result["route"] == "focused" and len(result["gaps"]) == 4, "A04 partial inputs must describe four gaps")
        ensure((project / "task.log").read_bytes().count(b"\n") == 1, "A04 focused import ran the project command")
    if "A04" in cases:
        dump(failed / "collection-input.json", config)
        dump(report_fixture, {"mode": "fail", "reports": reports})
        call("A04", "collect", "--repository", project, "--config", failed / "collection-input.json", "--output", failed,
             code=2, message="Command failed (7): ['mise', 'run', 'audit inputs']")
        ensure(load(failed / "collection.json")["status"] == "blocked", "A04 failed command must leave a blocked description")
        ensure((project / "task.log").read_bytes().count(b"\n") == 2, "A04 failed command did not execute exactly once")
        for index, field, invalid, error in ((16, "tokens", None, "'NoneType' object is not iterable"),
                                            (17, "functions", {"invalid": 1}, "string indices must be integers, not 'str'"),
                                            (18, "containers", False, "'bool' object is not iterable")):
            malformed = full.with_name(f"2026-11-15T{index}-00-00Z")
            dump(malformed / "collection-input.json", config)
            bad_reports = deepcopy(reports)
            kotlin = json.loads(bad_reports["build/kotlin.json"])
            kotlin["files"][0][field] = invalid
            bad_reports["build/kotlin.json"] = json.dumps(kotlin)
            dump(report_fixture, {"reports": bad_reports})
            call("A04", "collect", "--repository", project, "--config", malformed / "collection-input.json", "--output", malformed,
                 code=2, message=error)
            blocked = load(malformed / "collection.json")
            ensure(blocked["status"] == "blocked" and not (malformed / "metrics").exists(),
                   f"A04 invalid Kotlin {field} published quality data")
        dump(report_fixture, {"reports": reports})

    if "A05" in cases:
        for query, terms in [("group", ["group-0001"]), ("files", [LEFT, RIGHT]),
                             ("co-change", [LEFT, RIGHT]), ("dependencies", [LEFT])]:
            output = full / "evidence" / f"{query}.json"
            call("A05", "evidence", "--repository", project, "--collection", collection_path, "--output", output,
                 "--" + query, *terms, check=lambda o: o["output"] == str(output))
            evidence = load(output)
            key = {"group": "measurements", "files": "measurements", "co-change": "commits", "dependencies": "edges"}[query]
            ensure(evidence[key], f"A05 {query} did not address observations")

    if "A06" in cases:
        cards_path = full / "cards.json"
        rows = []
        for identity, effect in [("A", "local"), ("B", "substantial")]:
            card = "recommendations/" + identity + ".md"
            write(full / card, f"# Direction {identity}\n" + "\n".join(f"## {i}. Section\n\nEvidence." for i in range(1, 7)) + "\n")
            rows.append({"id": identity, "status": "ready", "card": card,
                "source_evidence": [{"file": LEFT, "declaration": "A"}],
                "metric_evidence": [{"path": "metrics/source-files/file.jsonl", "key": {"file": LEFT}}],
                "effects": {"modularity": effect, "regression_risk": "not_shown", "change_cost_reduction": "not_shown"}})
        dump(cards_path, {"recommendations": rows})
        ranking, markdown = full / "ranked.json", full / "ranked.md"
        options = ["--repository", project, "--collection", collection_path, "--recommendations", cards_path]
        call("A06", "rank", *options, "--output", ranking, "--markdown", markdown)
        ensure(load(ranking)["priority_groups"] == [["B"], ["A"]] and b"Direction B" in markdown.read_bytes(), "A06 wrong score/order")
        call("A06", "rank", *options, "--output", ranking, code=2, message="Output already exists", read_only=True)
        rows[0]["metric_evidence"][0]["key"]["file"] = "src/lost.kt"
        dump(cards_path, {"recommendations": rows})
        call("A06", "rank", *options, "--output", full / "invalid-rank.json",
             code=2, message="Missing evidence key", read_only=True)

    if "A07" in cases:
        status_args = ["--repository", project, "--collection", collection_path]
        call("A07", "status", *status_args, code=2, message="Finish the report and tech debt plan", read_only=True)
        write(full / "report.md", "Finished audit\n")
        write(tech_debt / "plan/plan.md", "Finished plan\n")
        call("A07", "status", *status_args, check=lambda o: o["json"] == str(tech_debt / "status.json"))
        ensure((tech_debt / "status-indicators.md").read_bytes() == (revision / "assets/status-indicators.md").read_bytes(), "A07 guide bytes changed")
        call("A07", "status", "--repository", project, "--collection", focused / "collection.json",
             code=2, message="Publish status only after a complete full audit", read_only=True)

    if set(cases) & {"A08", "A09", "A10"}:
        target = state_dir / "state.json"
        candidate = transport / "state.json"
        dump(candidate, state)
        state_args = ["--report-dir", state_dir]
        def audit(case, cmd, *args, **options):
            return call(case, cmd, *state_args, *args, family="audit-state", **options)
        audit("A08", "write", "--input", candidate, check=lambda o: o["state"] == str(target))
        if "A08" not in cases:
            dump(target, state)
        audit("A08", "write", data=b"\xef\xbb\xbf" + candidate.read_bytes())
        audit("A08", "write", data=b'{"phase": "analysis", "phase": "complete"}',
              code=1, message="Duplicate JSON key: phase", read_only=True)
        invalid = {**state, "route": "focused", "phase": "publication"}
        audit("A08", "write", data=json.dumps(invalid).encode(), code=1, message="Only the full route has a publication phase", read_only=True)
        audit("A09", "read", check=lambda o: o == state, read_only=True)
        saved = target.read_bytes()
        write(target, "{")
        audit("A09", "read", code=1, message="Expecting property name enclosed in double quotes", read_only=True)
        write(target, b"\xff")
        audit("A09", "read", code=1, message="'utf-8' codec can't decode byte 0xff", read_only=True)
        write(target, saved)
        scope = {"project": "sample", "work": STATE, "task": None}
        state["phase"] = "evidence"
        state["active_assignment"] = "collect-1"
        state["assignments"] = [{"id": "collect-1", "assessment": {"status": "pending", "reason": None, "next_assignment": None},
                                "host_observation": {"state": "unknown", "worker_id": None, "observed_at": None, "source": None}}]
        request = state_dir / "assignments/collect-1/request.json"
        dump(request, {"report": STATE, "phase": "evidence", "role": "sdd-spec.explorer", "assignment": {"id": "collect-1", "scope": scope}})
        dump(target, state)
        audit("A10", "check", read_only=True, check=lambda o: o == {"valid": True, "issues": []})
        request.unlink()
        audit("A10", "check", code=1, read_only=True, check=lambda o: o["valid"] is False and len(o["issues"]) == 1 and "request.json" in o["issues"][0])


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--case", action="append", choices=[f"A{i:02d}" for i in range(1, 11)])
    args = parser.parse_args()
    deadline = started + pilot.TIME_LIMIT
    repository = Path(__file__).resolve().parents[2]
    basetemp = args.basetemp.resolve()
    if not basetemp.is_dir() or any((parent / ".git").exists() for parent in (basetemp, *basetemp.parents)):
        parser.error("--basetemp must be an existing directory outside Git worktrees")
    if not args.python.is_absolute() or not args.python.is_file():
        parser.error("--python must be the absolute path to the selected interpreter")
    cases = args.case or [f"A{i:02d}" for i in range(1, 11)]
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        workspace = Path(tempfile.mkdtemp(prefix="sdd-architect-parity-", dir=basetemp))
        caller = workspace / "caller"
        caller.mkdir()
        print(f"Architect workspace {workspace}", flush=True)
        revision = workspace / "skills/sdd-architect"
        archive = pilot.run(["git", "-C", str(repository), "archive", "--format=zip", pilot.PYTHON_COMMIT, "skills/sdd-architect"], workspace, deadline)
        ensure(archive.returncode == 0, f"Python archive failed: {archive.stderr!r}")
        with ZipFile(io.BytesIO(archive.stdout)) as zip_file:
            zip_file.extractall(workspace)
        binary = args.binary.resolve() if args.binary else pilot.build_cli(repository, workspace, deadline)
        fake = workspace / ("mise.exe" if os.name == "nt" else "mise")
        built = pilot.run(["go", "build", "-mod=readonly", "-o", str(fake), "./tests/setupfixture"], repository / "cli", deadline)
        ensure(built.returncode == 0, f"Collection command fixture build failed: {built.stderr!r}")
        os.environ["PATH"] = str(workspace) + os.pathsep + os.environ["PATH"]
        print(f"Python baseline {pilot.PYTHON_COMMIT}, {platform.platform()}", flush=True)
        project, transport = workspace / "project with spaces", workspace / "outside"
        today = datetime.now(timezone.utc).date().isoformat()
        observations = []
        for implementation in ("Python", "Go"):
            for path in (project, transport):
                ensure(path.resolve().parent == workspace.resolve(), "fixture reset would leave the workspace")
                if path.exists():
                    shutil.rmtree(path)
                path.mkdir()
            index = 0

            def execute(case, family, command, arguments, expected_code, message, data, read_only):
                nonlocal index
                context = f"{case} {implementation} {command} {list(map(os.fspath, arguments))!r}"
                python_script = "audit_state.py" if family == "audit-state" else "metrics.py"
                prefix = (["uv", "run", "--quiet", "--python", str(args.python), "--locked", "--script",
                           str(revision / "scripts" / python_script)] if implementation == "Python" else [str(binary), "architect", family])
                before = pilot.snapshot(project, deadline) if read_only else None
                argv = [*prefix, command, *map(os.fspath, arguments)]
                result = pilot.run(argv, caller, deadline) if data is None else run_with_input(argv, caller, deadline, data)
                ensure(result.returncode == expected_code,
                       f"{context}: expected exit {expected_code}, received {result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
                ensure(message.encode() in result.stderr and (message or not result.stderr), f"{context}: incorrect stderr {result.stderr!r}")
                output = as_json(result.stdout) if result.stdout else None
                if read_only:
                    ensure(before == pilot.snapshot(project, deadline), f"{context}: read-only or failed operation modified project files")
                files = capture_files(project, deadline)
                if implementation == "Python":
                    observations.append((result.stderr, output, files))
                else:
                    expected_stderr, expected_output, expected_files = observations[index]
                    try:
                        pilot.compare_stderr(expected_stderr, result.stderr)
                        compare_value(expected_output, output, "/stdout")
                        compare_value(expected_files, files, "/filesystem")
                    except pilot.PilotFailure as exc:
                        raise pilot.PilotFailure(f"{context}: {exc}") from exc
                index += 1
                return output

            scenario_calls(project, transport, revision, today, execute, cases)
        print(f"{', '.join(cases)} PASS ({len(observations)} paired invocations)", flush=True)
        pilot.time_remaining(deadline)
        return 0
    except (OSError, ValueError, pilot.PilotFailure, TimeoutError) as exc:
        print(f"Architect parity failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Architect elapsed {time.monotonic() - started:.2f} s", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
