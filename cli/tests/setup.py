"""Run S00–S09 through both setup executables and compare their project effects.

The command boundary is needed here because argv, cwd, report files, and the
settings transaction are observable parts of the contract. The native fake
serves only mise and Node. The Python baseline runs without monkeypatches.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time

from pilot import (
    PYTHON_COMMIT, TIME_LIMIT, PilotFailure, build_cli, compare_stderr,
    compare_stdout, file_digest, prepare_baseline, run, snapshot, time_remaining,
)


def require(condition, message):
    if not condition:
        raise PilotFailure(message)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def load(path):
    return json.loads(path.read_bytes())


@contextmanager
def environment(**values):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update({key: os.fspath(value) for key, value in values.items()})
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def normalize_release_probes(body):
    # The probes go to a deliberately unavailable proxy. urllib and net/http
    # expose different network error types. Compare their failure observation,
    # while retaining dependency status, release source, and every other field.
    if isinstance(body, dict):
        for key, value in body.items():
            if key == "release_error":
                require(isinstance(value, str) and value, "expected a release lookup diagnostic")
                body[key] = "<release unavailable>"
            else:
                normalize_release_probes(value)
    elif isinstance(body, list):
        for value in body:
            normalize_release_probes(value)
    return body


class Comparison:
    def __init__(self, workspace, baseline, commands, fake, deadline):
        self.workspace, self.baseline, self.commands = workspace, baseline, commands
        self.fake, self.deadline = fake, deadline
        self.cwd = workspace / "caller"
        self.cwd.mkdir()
        self.project = workspace / "same project path"
        self.transport = workspace / "external files"
        self.last = ""

    def execute(self, *args):
        args = [os.fspath(arg) for arg in args]
        self.last = f"{self.label} {args!r}"
        result = run([*self.prefix, *args], self.cwd, self.deadline)
        require(result.returncode in {0, 1}, f"{self.last}: exit {result.returncode}: {result.stderr!r}")
        compare_stderr(b"", result.stderr)
        try:
            body = json.loads(result.stdout)
        except ValueError as exc:
            raise PilotFailure(f"{self.last}: invalid JSON: {result.stdout!r}") from exc
        require(body["ok"] is (result.returncode == 0), f"{self.last}: inconsistent response")
        return result.returncode, body

    def success(self, *args):
        code, body = self.execute(*args)
        require(code == 0, f"{self.last}: expected success, received {body!r}")
        return body["result"]

    def failure(self, expected, *args):
        code, body = self.execute(*args)
        require(code == 1 and body["code"] == "sdd_setup" and expected in body["message"],
                f"{self.last}: expected failure containing {expected!r}, received {body!r}")
        return body

    def artifact(self, name, *args):
        output = self.transport / name
        receipt = self.success(*args, "--output", output)
        require(receipt["output_file"] == str(output) and receipt["sha256"] == file_digest(output),
                f"{self.last}: incorrect transfer receipt")
        full = load(output)
        before = output.read_bytes()
        rejected = self.failure("--output already exists", *args, "--output", output)
        require(output.read_bytes() == before, f"{self.last}: an existing artifact was overwritten")
        return output, full, receipt, rejected

    def both(self, identifiers, variant):
        observed = []
        for self.label, self.prefix in self.commands:
            time_remaining(self.deadline)
            for directory in (self.project, self.transport):
                if directory.exists():
                    shutil.rmtree(directory)
                directory.mkdir()
            try:
                observed.append(variant())
            except Exception as exc:
                raise PilotFailure(f"{identifiers} {self.last}: {exc}") from exc
        compare_stdout(*observed)
        print(f"{identifiers} PASS", flush=True)

    def fake_mise(self):
        tools = self.transport / "native tools"
        tools.mkdir()
        suffix = self.fake.suffix
        shutil.copy2(self.fake, tools / f"mise{suffix}")
        install = self.transport / "fake installation"
        install.mkdir()
        binaries = "git scc rg node rga apm java javac gradle".split()
        paths = {}
        for binary in binaries:
            path = install / (binary + suffix)
            if binary == "node":
                shutil.copy2(self.fake, path)
            else:
                path.touch()
            paths[binary] = str(path)
        source = str(self.project / "mise.toml")
        record = {"source": {"path": source}, "active": True,
                  "installed": True, "install_path": str(install)}
        versions = dict.fromkeys(binaries, "1.2.3")
        versions.update(java="temurin-21.0.4", javac="temurin-21.0.4", gradle="8.10")
        fixture = self.transport / "native fixture.json"
        payload = {"tools": {binary: [record] for binary in binaries}, "paths": paths, "versions": versions}
        dump(fixture, payload)
        return tools, fixture, payload

    def help(self):
        result = []
        names = "progress,audit,jvm-step,typespec,detekt,collection,inspect,plan,apply"
        for label, command in self.commands:
            observation = run([*command, "--help"], self.cwd, self.deadline)
            require(observation.returncode == 0 and not observation.stderr, f"{label}: help failed")
            output = observation.stdout.decode().replace("\r\n", "\n")
            program = "setup.py" if label == "Python" else "sdd setup"
            require(output.startswith(f"usage: {program} ") and "{" + names + "}" in output,
                    f"{label}: help is missing the executable or commands")
            result.append(" ".join(output.replace("usage: " + program, "usage: <program>", 1).split()))
        require(result[0] == result[1], f"S00 help differs: {result!r}")
        print("S00 PASS", flush=True)

    def progress(self):
        args = ("progress", "--project-root", self.project, "--applicable", "common-tools", "ktlint", "detekt", "roles")
        rows = [self.success(*args)]
        require(rows[-1]["next_step"] == "common-tools" and rows[-1]["stop"] is False, "incorrect initial route")
        rows.append(self.success(*args, "--complete", "common-tools", "--project-changed"))
        require(rows[-1]["next_step"] == "ktlint" and rows[-1]["stop"] is True, "completion did not pause route")
        check = "--check-exit-code"
        rows.append(self.success(*args, "--complete", "ktlint", check, "0", check, "4"))
        require(rows[-1]["failed_step"] == "ktlint" and rows[-1]["completed_steps"] == ["common-tools"],
                "a failed check was recorded as complete")
        rows.append(self.success(*args, "--complete", "ktlint", check, "0", check, "0"))
        rows.append(self.success(*args, "--complete", "detekt", check, "0", check, "-1"))
        require(rows[-1]["failed_step"] == "detekt", "detekt check failure was not reported")
        rows.append(self.success(*args, "--complete", "detekt", check, "0", check, "0"))
        rows.append(self.success(*args, "--failed", "roles"))
        require(rows[-1]["failed_step"] == "roles" and rows[-1]["stop"] is True, "explicit failure did not pause route")
        rows.append(self.success(*args, "--reset", "ktlint"))
        require(rows[-1]["completed_steps"] == ["common-tools", "detekt"] and rows[-1]["next_step"] == "ktlint",
                "partial reset changed the wrong steps")
        rows.append(self.success(*args, "--reset", "all"))
        require(rows[-1]["completed_steps"] == [], "reset all retained steps")
        return [rows, snapshot(self.project, self.deadline)]

    def audit(self):
        def normalize(result):
            timestamp = datetime.fromisoformat(result["checked_at"])
            require(timestamp.utcoffset() == timedelta(0) and
                    abs(datetime.now(timezone.utc) - timestamp) < timedelta(minutes=2), "incorrect audit timestamp")
            result["checked_at"] = "<UTC observation time>"
            return normalize_release_probes(result)

        args = ("audit", "--project-root", self.project)
        tools, fixture, _ = self.fake_mise()
        with environment(PATH=str(self.transport), HTTPS_PROXY="http://127.0.0.1:1", NO_PROXY=""):
            non_jvm = self.success(*args, "--no-jvm", "--no-ktlint", "--no-detekt")
        require(non_jvm["build_root"] is None and non_jvm["requirements"][0]["status"] == "not_found", "fake no-mise path leaked")
        build = self.project / "multi-module"
        wrapper = build / "gradle" / "wrapper"
        wrapper.mkdir(parents=True)
        launcher = build / ("gradlew.bat" if os.name == "nt" else "gradlew")
        launcher.write_bytes(b"launcher")
        launcher.chmod(0o755)
        (wrapper / "gradle-wrapper.jar").write_bytes(b"fixture wrapper")
        (wrapper / "gradle-wrapper.properties").write_bytes(b"distributionUrl=https\\://mirror.invalid/gradle-8.9-bin.zip\n")
        multi = (*args, "--build-root", build.name, "--jvm", "21", "--junit", "5.11.0", "app build file",
                 "--junit", "missing", "lib build file", "--jacoco-module", ":app", "--jacoco-module", ":lib",
                 "--jacoco", ":app", "satisfied", "coverage verified", "--archunit", "missing", "test dependencies",
                 "--ktlint", ":app", "satisfied", "task listed", "--detekt", ":lib", "unverified", "not run")
        with environment(PATH=tools, SDD_SETUP_FIXTURE=fixture, HTTPS_PROXY="http://127.0.0.1:1", NO_PROXY=""):
            _, full, receipt, rejected = self.artifact("audit.json", *multi)
        require(full == receipt["summary"] and full["compliant"] is False and full["build_root"] == str(build),
                "audit summary or compliance differs")
        requirements = {row["id"]: row for row in full["requirements"]}
        require(requirements["jacoco"]["evidence"]["missing_modules"] == [":lib"]
                and requirements["junit"]["status"] == "failed" and requirements["java"]["status"] == "satisfied"
                and requirements["gradle"]["status"] == "satisfied" and "release_error" in requirements["gradle"],
                "wrong requirements for the partially checked multi-module build")
        return [normalize(non_jvm), normalize(full), rejected]

    def jvm_steps(self):
        tools, fixture, _ = self.fake_mise()
        (self.project / "build").mkdir()
        base = ("--project-root", self.project, "--build-root", "build")
        steps = {
            "jdk": ("satisfied", ("--jdk", "21")),
            "gradle": ("satisfied", ()),
            "junit5": ("satisfied", ("--observation", "5.11.0", "test plan")),
            "jacoco": ("unverified", ("--jacoco-module", ":app", "--jacoco-module", ":lib",
                                    "--jacoco", ":app", "satisfied", "coverage XML")),
            "archunit": ("failed", ("--observation", "missing", "test dependencies")),
        }
        output = {}
        with environment(PATH=tools, SDD_SETUP_FIXTURE=fixture, HTTPS_PROXY="http://127.0.0.1:1", NO_PROXY=""):
            for step, (status, observations) in steps.items():
                result = self.success("jvm-step", step, *base, *observations)
                require(result["status"] == status, f"{step} returned unexpected status")
                if step == "jacoco":
                    require(result["evidence"]["missing_modules"] == [":lib"], "missing module was omitted")
                output[step] = normalize_release_probes(result)
        return output

    def typespec(self):
        tools, fixture, _ = self.fake_mise()
        project_package = self.project / "packages" / "typed package"
        project_package.mkdir(parents=True)
        arguments = ("typespec", "--project-root", self.project, "--package-dir", project_package.relative_to(self.project))
        rows = []
        with environment(PATH=tools, SDD_SETUP_FIXTURE=fixture):
            rows.append(self.success(*arguments))
            dump(self.project / "package.json", {"devDependencies": {"@typespec/compiler": "~1.2.3"}})
            rows.append(self.success(*arguments))
            installed = self.project / "node_modules" / "@typespec" / "compiler"
            dump(installed / "package.json", {"name": "@typespec/compiler", "bin": {"tsp": "cli.js"}, "version": "1.2.3"})
            (installed / "cli.js").touch()
            _, full, receipt, rejected = self.artifact("typespec.json", *arguments)
            rows.append(full)
            (self.project / ".pnp.cjs").touch()
            rows.append(self.success(*arguments))
        require([row["status"] for row in rows] == ["missing", "restore", "installed", "check_with_yarn"]
                and full == receipt["summary"] and full["version"] == "1.2.3" and full["node_version"] == "v22.6.0",
                "incorrect dependency, Yarn or local compiler observation")
        return [rows, rejected]

    def detekt(self):
        defaults = self.transport / "native.yml"
        defaults.write_bytes(b"naming:\n  active: true\n  VariableMaxLength:\n    active: true\n    maximumVariableNameLength: 21\n"
                             b"coroutines:\n  active: true\n  RedundantSuspendModifier:\n    active: true\n")
        (self.project / "first.yml").write_bytes(b"naming:\n  VariableMaxLength:\n    active: true\n")
        (self.project / "second.yml").write_bytes(b"naming:\n  VariableMaxLength:\n    active: false\n")
        args = ("detekt", "--project-root", self.project, "--version", "1.23.9", "--defaults", defaults,
                "--config", "first.yml", "--config", "second.yml", "--ktlint")
        merged = self.success(*args)
        _, full, receipt, rejected = self.artifact("detekt.json", *args, "--standalone", "--accept",
                                                    "naming.VariableMaxLength.active", "--accept", "formatting.active")
        key = "naming.VariableMaxLength.active"
        require(full["differences"][key]["source"] == str(self.project / "second.yml") and
                full["yaml_edits"]["naming"]["VariableMaxLength"]["active"] is True and
                "formatting" in full["yaml_edits"] and receipt["summary"]["differences"] == len(full["differences"]),
                "configuration precedence or proposed edits differ")
        return [merged, full, receipt["summary"], rejected]

    def collection(self):
        tools, fixture, payload = self.fake_mise()
        assets = self.baseline / "assets"
        request = load(assets / "collection.example.json")
        request["tools"] = {"git": ["git"], "java": ["java", "javac"]}
        request["scope"] = {"source_roots": ["src"], "package_prefixes": ["demo"], "modules": {"demo": ["demo"]},
                            "class_files": {"demo.A": "src/A.kt"}}
        request_path = self.transport / "collection request.json"
        dump(request_path, request)
        settings = self.project / ".sdd" / "settings.json"
        original = {"schema_version": 1, "subagents": {"roles": {}}, "architect": {"other": 3}}
        dump(settings, original)
        (self.project / "src").mkdir()
        (self.project / "src" / "A.kt").write_bytes(b"package demo\nclass A")
        reports = {
            "dependencies": "", "complexity": '{"runs":[]}',
            "coverage": '<report><package name="demo"><class name="demo/A"/></package></report>',
            "history": json.dumps({"format": "git-history", "first_parent": True, "renames": True,
                                   "since": "2000-01-01", "until": datetime.now(timezone.utc).date().isoformat(), "commits": []}),
            "sizes": '[{"Name":"Kotlin","Files":[{"Location":"src/A.kt","Lines":2,"Code":2,"Comment":0,"Blank":0}]}]',
            "kotlin": json.dumps({"format": "kotlin-measurements", "version": 2, "complete": True,
                                  "tool_version": "1.23.8", "measurement_profile": "kotlin-tokens-functions-1",
                                  "files": [{"file": "src/A.kt", "package": "demo", "tokens": [],
                                             "functions": [], "containers": []}]}),
        }
        artifacts = request["collection"]["artifacts"]
        payload["reports"] = {artifacts[name]["path"]: text for name, text in reports.items()}
        dump(fixture, payload)
        args = ("collection", "--project-root", self.project, "--request", request_path)
        rows = []
        with environment(PATH=tools, SDD_SETUP_FIXTURE=fixture):
            rows.append(self.success(*args))
            rows.append(self.success(*args))
            before = settings.read_bytes()
            payload["mode"] = "fail"
            dump(fixture, payload)
            rows.append(self.failure("fixture task failed", *args))
            require(settings.read_bytes() == before, "failed course changed settings")
            payload["mode"] = "ok"
            payload["reports"][artifacts["complexity"]["path"]] = "{}"
            dump(fixture, payload)
            rows.append(self.failure("detekt SARIF requires a runs array", *args))
            require(settings.read_bytes() == before, "invalid report changed settings")
            payload["reports"][artifacts["complexity"]["path"]] = reports["complexity"]
            malformed = json.loads(reports["kotlin"])
            del malformed["files"][0]["tokens"]
            payload["reports"][artifacts["kotlin"]["path"]] = json.dumps(malformed)
            dump(fixture, payload)
            rows.append(self.failure("'tokens'", *args))
            require(settings.read_bytes() == before, "incomplete Kotlin measurements changed settings")
        runs = [json.loads(line) for line in (self.project / "task.log").read_bytes().splitlines()]
        require(runs == [{"argv": request["collection"]["command"], "cwd": str(self.project)}] * 5,
                "collection did not invoke the project task once per request")
        saved = load(settings)
        require(saved["subagents"] == original["subagents"] and saved["architect"]["other"] == 3
                and saved["architect"]["collection"] == request["collection"] and rows[0]["changed"]
                and rows[0]["reports"] == sorted(reports) and rows[1]["changed"] is False, "settings did not round-trip")
        return [rows, snapshot(self.project, self.deadline)]

    def inspect_args(self, host):
        users = self.transport / "user definitions"
        users.mkdir(exist_ok=True)
        return ("inspect", "--project-root", self.project, "--host", host, "--user-agent-dir", users,
                "--sdd-shared", self.baseline.parent / "sdd-shared")

    def inspect(self):
        codex = self.inspect_args("codex")
        without = self.success(*codex)
        require(self.success(*codex[:-2]) == without, "adjacent shared package must supply the same inspection evidence")
        agents = codex[6]
        (agents / "custom.toml").write_bytes(b'name = "custom"\ndescription = "Personal"\ndeveloper_instructions = "Work"\n'
                                             b'model = "gpt-6-luna"\nmodel_reasoning_effort = "low"\n')
        settings = self.project / ".sdd" / "settings.json"
        dump(settings, {"schema_version": 1, "subagents": {"roles": {"sdd-spec.architect": "custom"}}})
        local = self.project / ".codex" / "agents"
        local.mkdir(parents=True)
        (local / "same.toml").write_bytes(b'name = "custom"\ndescription = "Project"\ndeveloper_instructions = "Work"\n'
                                          b'model = "gpt-6-luna"\nmodel_reasoning_effort = "high"\n')
        _, configured, receipt, rejected = self.artifact("inspect.json", *codex, "--names", "custom", "extra", "custom")
        require(without["evidence"]["settings"] is None and configured["agents"]["custom"]["scope"] == "project"
                and configured["agents"]["custom"]["effort"] == "high" and len(configured["evidence"]["agents"]) == 2
                and receipt["summary"]["roles"] == configured["roles"], "Codex inspection or precedence differs")
        catalog = self.transport / "host catalog.json"
        dump(catalog, ["sdd-executor", "custom", "local-role"])
        claude = self.inspect_args("claude-code")
        local = self.project / ".claude" / "agents" / "nested"
        local.mkdir(parents=True)
        (local / "an-agent.md").write_bytes(b"---\nname: local-role\ndescription: Local scope\nmodel: sonnet\n---\n\nWork\n")
        with_settings = self.success(*claude, "--available-agents", catalog, "--names", "local-role")
        settings.unlink()
        without_settings = self.success(*claude, "--available-agents", catalog)
        require(with_settings["agents"]["local-role"]["scope"] == "project" and
                with_settings["agents"]["custom"]["scope"] == "native" and
                without_settings["agents"]["sdd-executor"]["scope"] == "native",
                "Claude catalog, nested definitions or native scope differs")
        return [without, configured, receipt["summary"], rejected, with_settings, without_settings]

    def plan_apply(self):
        inspect_args = self.inspect_args("codex")
        settings = self.project / ".sdd" / "settings.json"
        initial = {"schema_version": 1, "note": "fixture", "setup": {"completed_steps": ["roles"]}}
        dump(settings, initial)
        agents = self.project / ".codex" / "agents"
        agents.mkdir(parents=True)
        # Noncanonical layout is valid TOML. Planned edits must preserve
        # comments and nested settings while updating the parsed root keys.
        architect = (b'name = "sdd-architect"\ndescription = "Project architect"\n'
                     b'developer_instructions = """\nmodel = "from instructions"\n"""\n'
                     b"  model\t= 'gpt-original' # project preference\n"
                     b'\t"model_reasoning_effort" = "low"\n'
                     b'\n[profile]\nmodel = "nested"\n')
        executor = (b'name = "sdd-executor"\ndescription = "Project executor"\ndeveloper_instructions = "Work"\n'
                    b'  "mo\\u0064el" = """\ngpt-original""" # replaced by inheritance\n'
                    b"\t'model_reasoning_effort' = 'high'\n"
                    b'\n[profile]\nmodel = "nested"\n')
        (agents / "sdd-architect.toml").write_bytes(architect)
        (agents / "sdd-executor.toml").write_bytes(executor)
        inspect = self.transport / "inspection.json"
        record = self.success(*inspect_args, "--output", inspect)
        view = load(inspect)
        require(file_digest(inspect) == record["sha256"], "wrong inspection SHA-256")
        request = {"inspection_file": inspect.name, "inspection_sha256": record["sha256"], "roles": {}, "agents": {}}
        for row in view["roles"]:
            request["roles"][row["role"]] = {"action": "default"}
            request["agents"][row["default"]] = {"model": {"action": "default"}, "effort": {"action": "default"}}
        request["agents"]["sdd-architect"] = {
            "model": {"action": "set", "value": "gpt-updated"}, "effort": {"action": "set", "value": "medium"},
        }
        request["agents"]["sdd-executor"] = {
            "model": {"action": "set", "value": "inherit"}, "effort": {"action": "set", "value": None},
        }
        request_path = self.transport / "decisions.json"
        dump(request_path, request)
        plan_args = ("plan", "--request", request_path)
        original = inspect.read_bytes()
        inspect.write_bytes(original + b"\n")
        stale_file = self.failure("Inspection file changed", *plan_args)
        inspect.write_bytes(original)
        dump(settings, initial | {"note": "changed"})
        stale_settings = self.failure("Project or agent catalog changed", *plan_args)
        dump(settings, initial)
        path, plan, receipt, rejected = self.artifact("plan.json", *plan_args)
        before_write = snapshot(self.project, self.deadline)
        require(plan == self.success(*plan_args) and
                receipt["summary"]["operations"] == [{key: row[key] for key in ("path", "diff")} for row in plan["operations"]]
                and all(row["diff"].startswith("--- ") and row["after_sha256"] for row in plan["operations"]),
                "full plan and diff summary disagree")
        profiles = {row["path"]: row["after"].encode() for row in plan["operations"]}
        edited = architect.replace(b"'gpt-original'", b'"gpt-updated"').replace(b'"low"', b'"medium"')
        inherited = executor.replace(b'  "mo\\u0064el" = """\ngpt-original""" # replaced by inheritance\n', b'').replace(
            b"\t'model_reasoning_effort' = 'high'\n", b'')
        require(profiles[".codex/agents/sdd-architect.toml"] == edited and
                profiles[".codex/agents/sdd-executor.toml"] == inherited,
                "formatted TOML plan differs from the requested model and effort decisions")
        lock = settings.with_name(".setup.lock")
        lock.write_bytes(b"foreign owner")
        apply_args = ("apply", "--plan", path)
        foreign = self.failure("Another setup owns .sdd/.setup.lock", *apply_args)
        require(lock.read_bytes() == b"foreign owner", "foreign lock was changed")
        lock.unlink()
        dump(settings, initial | {"note": "edited after planning"})
        stale_apply = self.failure("Project or agent catalog changed", *apply_args)
        dump(settings, initial)
        require(snapshot(self.project, self.deadline) == before_write, "a rejected application changed the project")
        partial = None
        if os.name == "nt":
            # Python's Windows file handle allows reads during re-verification
            # while denying replacement of this final operation's destination.
            with settings.open("rb"):
                failure = self.failure("completed file writes rolled back", *apply_args)
                require(settings.name in failure["message"], "partial failure did not identify the failed settings write")
                require(snapshot(self.project, self.deadline) == before_write
                        and not lock.exists() and load(settings) == initial
                        and not list(settings.parent.glob(".sdd-setup-*")),
                        "partial application did not restore earlier files")
                partial = {"code": failure["code"], "diagnostic": "failed settings write and rolled back"}
        inspect.unlink()
        request_path.unlink()
        applied = self.success(*apply_args)
        require(applied["changed"] == [row["path"] for row in plan["operations"]] and applied["plan_id"] == plan["plan_id"],
                "apply returned the wrong operation identity")
        for row in plan["operations"]:
            output = self.project / row["path"]
            require(file_digest(output) == row["after_sha256"] and output.read_bytes() == row["after"].encode(),
                    f"applied file differs: {output}")
        refreshed = self.success(*inspect_args)
        require(all(row["present"] for row in refreshed["roles"]) and not lock.exists()
                and refreshed["agents"]["sdd-architect"]["model"] == "gpt-updated"
                and refreshed["agents"]["sdd-architect"]["effort"] == "medium"
                and refreshed["agents"]["sdd-executor"]["model"] is None
                and refreshed["agents"]["sdd-executor"]["effort"] is None,
                "role inspection did not reflect written settings or the lock survived")
        return [plan, receipt["summary"], stale_file, stale_settings, rejected, foreign, stale_apply, partial,
                applied, refreshed, snapshot(self.project, self.deadline)]


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=TIME_LIMIT)
    args = parser.parse_args()
    if not 0 < args.timeout <= TIME_LIMIT:
        parser.error(f"--timeout must be between 0 and {TIME_LIMIT} seconds")
    if not args.python.is_absolute() or not args.python.is_file():
        parser.error("--python requires the selected absolute interpreter path")
    base = args.basetemp.resolve()
    if not base.is_dir() or any((parent / ".git").exists() for parent in (base, *base.parents)):
        parser.error("--basetemp requires an external directory")

    deadline = started + args.timeout
    try:
        workspace = Path(tempfile.mkdtemp(prefix="sdd-setup-", dir=base))
        print(f"Python commit {PYTHON_COMMIT}\nOS {platform.platform()}\nWorkspace {workspace}", flush=True)
        repository = args.repository.resolve()
        baseline = prepare_baseline(repository, workspace, deadline,
                                    skills=("sdd-spec", "sdd-shared", "sdd-setup", "sdd-architect")).parent / "sdd-setup"
        binary = build_cli(repository, workspace, deadline)
        # Put the two consumers alongside the same versioned sdd-shared payload.
        bundled = baseline.parent / binary.name
        shutil.copy2(binary, bundled)
        fake = workspace / ("fixture.exe" if os.name == "nt" else "fixture")
        built = run(["go", "build", "-mod=readonly", "-o", str(fake), "./tests/setupfixture"], repository / "cli", deadline)
        require(built.returncode == 0, f"cannot build native process fixture: {built.stderr!r}")
        uv = shutil.which("uv")
        require(uv is not None, "uv was not found on PATH")
        commands = (("Python", [uv, "run", "--quiet", "--python", str(args.python), "--locked", "--script",
                                 str(baseline / "scripts" / "setup.py")]), ("Go", [str(bundled), "setup"]))
        suite = Comparison(workspace, baseline, commands, fake, deadline)
        suite.help()
        for chosen, scenario in (
            ("S01", suite.progress), ("S02", suite.audit), ("S03", suite.jvm_steps),
            ("S04", suite.typespec), ("S05", suite.detekt), ("S06", suite.collection),
            ("S07", suite.inspect), ("S08–S09", suite.plan_apply),
        ):
            suite.both(chosen, scenario)
    except (OSError, PilotFailure, TimeoutError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Setup elapsed {time.monotonic() - started:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
