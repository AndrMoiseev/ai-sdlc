"""Atomic, disposable views of state; never write execution decisions."""
from html import escape
import json
from pathlib import Path
from .artifact_storage import write as atomic
from .state import read
from .scheduler import available
from .review_policy import technical_debt
from .waves import projection as wave_projection, waiting_text
from .state_view import assignments, task_verification


def projection(state):
    waves, waiting = wave_projection(state)
    tasks = []
    for key, task in sorted(state["tasks"].items(), key=lambda pair: pair[1]["plan"]["number"]):
        tasks.append({"id": key, "status": task["status"], "criteria": task["plan"].get("covers", [record["id"] for record in state.get("acceptance", {}).values() if record["task"] == key]), "attempt": task["attempt"], "review": f"{task['review_rounds_started']}/{task['review_limit']}", "repair": f"{task['test_repair_cycles_started']}/{task['test_repair_limit']}", "commits": [c["sha"] for c in task["commits"]], "evidence": [{k: e[k] for k in ("stage", "outcome", "log")} for e in task["evidence"]], "blockers": task["blockers"], "depends_on": task["plan"]["depends_on"], "cannot_parallel_with": task["plan"].get("cannot_parallel_with", []), "waiting": waiting[key], "waiting_text": waiting_text(waiting[key])})
    for item in tasks:
        item["verification"] = task_verification(state, state["tasks"][item["id"]])
    whole = {"explorer_assignments": assignments(state)}
    if state.get("work_kind", state.get("basis", {}).get("work_kind")) == "refactoring":
        from .final_checks import progress
        whole["whole_result"] = progress(state)
    elif state.get("final_checks"):
        from .final_checks import progress
        whole["final_project_checks"] = progress(state)
    return {**whole, "schema_version": 1, **({"work_kind": state["work_kind"]} if "work_kind" in state else {}), "change_id": state["change_id"], "run_id": state["run_id"], "revision": state["revision"], "updated_at": state["updated_at"], "status": state["status"], "accepted": sum(t["status"] == "accepted" for t in tasks), "total": len(tasks), "tasks": tasks, "waves": waves, "blockers": state["blockers"], "next": available(state), "final": state["final"], "technical_debt": technical_debt(state)}


def static_waves(data):
    """Keep the wave structure and wait explanations readable without JavaScript."""
    from urllib.parse import quote
    tasks = {t["id"]: t for t in data["tasks"]}
    blocks = []
    for wave in data["waves"]:
        dependencies = " ".join(
            f'<a class="dependency" href="#{quote("task-" + dep, safe="")}">{escape(dep)} · {escape(tasks[dep]["status"])}</a>'
            for dep in wave["depends_on"])
        cards = []
        for key in wave["tasks"]:
            t = tasks[key]
            waiting = "".join(f'<p class="waiting">{escape(reason)}</p>' for reason in t["waiting_text"])
            waiting += "".join(f'<p>{escape(stage)} · Execution {escape(proof["execution"]["status"])} · Conclusion {escape(proof["conclusion"]["status"])}</p>'
                               for stage, proof in t["verification"].items())
            waiting += "".join(f'<p>Explorer {escape(role["role_id"])} · {escape(role["kind"])} · {escape(role["stage"] or "research")} · {escape(role["status"])}</p>'
                               for role in data["explorer_assignments"] if role["scope"]["task"] == key)
            cards.append(f'<article id="{escape("task-" + key, quote=True)}" tabindex="-1"><h3>{escape(key)}</h3><p class="badge">{escape(t["status"])}</p>{waiting}<p>Review {escape(t["review"])} · Test repairs {escape(t["repair"])}</p></article>')
        blocks.append(f'<section class="wave" data-wave="{wave["id"]}"><div class="wave-heading"><h2>Wave {wave["number"]}</h2><span class="badge">{wave["label"]}</span><span class="muted">{wave["accepted"]} / {len(wave["tasks"])} accepted</span></div><div class="dependencies">After acceptance: {dependencies or "No dependencies"}</div><div class="wave-tasks">{"".join(cards)}</div></section>')
    return "".join(blocks)


def render(directory):
    directory = Path(directory)
    data = projection(read(directory))
    serialized = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    summary = [f"# {data['change_id']}", f"Run: {data['run_id']} · revision {data['revision']}", f"{data['status']} · accepted {data['accepted']}/{data['total']}", f"Snapshot: {data['updated_at']}", ""]
    summary.extend(["Waves group planned parallel work. Task dependencies require acceptance; launch checks still apply. Integration is sequential.", ""])
    for wave in data["waves"]:
        summary.append(f"- Wave {wave['number']}: {', '.join(wave['tasks'])}; after acceptance: {', '.join(wave['depends_on']) or 'none'}; {wave['label']}; accepted {wave['accepted']}/{len(wave['tasks'])}")
    summary.append("")
    for task in data["tasks"]:
        summary.append(f"- {task['id']}: {task['status']}; review {task['review']}; test repairs {task['repair']}; commits {', '.join(task['commits']) or 'none'}")
        summary.extend(f"  - {reason}" for reason in task["waiting_text"])
        summary.extend(f"  - {stage}: execution {proof['execution']['status']}; conclusion {proof['conclusion']['status']}"
                       for stage, proof in task["verification"].items())
    for role in data["explorer_assignments"]:
        summary.append(f"- Explorer {role['role_id']}: scope {role['scope']['task'] or 'run'}; {role['kind']}; stage {role['stage'] or 'research'}; {role['status']}")
    summary.extend(["", "Blockers: " + json.dumps(data["blockers"], ensure_ascii=False)])
    if "whole_result" in data or "final_project_checks" in data:
        whole = data.get("whole_result", data.get("final_project_checks"))
        label = "Whole criteria confirmed: " if "whole_result" in data else "Final project checks; criteria confirmed: "
        summary.extend(["", label + ", ".join(whole["confirmed_criteria"]),
                        "Gaps: " + json.dumps(whole["gaps"], ensure_ascii=False),
                        "Retired checks and reasons: " + json.dumps(whole["retired_checks"], ensure_ascii=False)])
    debt = ["# Technical debt", "", "Recorded review findings; fixes require explicit user approval after plan completion.", ""]
    for finding in data["technical_debt"]:
        debt.extend([f"## {finding['finding_id']}", "", f"Path: {finding['path']}",
                     f"Problem: {finding['problem']}", f"Proposed fix: {finding['resolution']}", ""])
    if not data["technical_debt"]:
        debt.append("No technical debt recorded.")
    summary.extend(["", f"Technical debt: {len(data['technical_debt'])} finding(s). [Journal](technical-debt.md)."])
    atomic(directory / "technical-debt.md", "\n".join(debt) + "\n")
    atomic(directory / "summary.md", "\n".join(summary) + "\n")
    atomic(directory / "dashboard-state.js", "window.sddApplyUpdate(" + serialized + ");\n")
    template = (Path(__file__).resolve().parents[2] / "assets/dashboard.html").read_text(encoding="utf-8")
    static = static_waves(data)
    run_roles = [role for role in data["explorer_assignments"] if role["scope"]["task"] is None]
    static = '<section><h2>Run explorers</h2>' + ''.join(
        f'<p>{escape(role["role_id"])} · {escape(role["stage"] or "research")} · {escape(role["status"])}</p>'
        for role in run_roles) + '</section>' + static
    if "whole_result" in data or "final_project_checks" in data:
        whole = data.get("whole_result", data.get("final_project_checks"))
        label = "Whole result" if "whole_result" in data else "Final project checks"
        static = '<section><h2>' + label + '</h2><pre>' + escape(json.dumps(whole, ensure_ascii=False, indent=2)) + '</pre></section>' + static
    html = template.replace("__SNAPSHOT__", serialized).replace("__STATIC_TASKS__", static).replace("__CHANGE__", escape(data["change_id"])).replace("__SAVED_AT__", escape(data["updated_at"]))
    atomic(directory / "dashboard.html", html)
    return {"dashboard": str(directory / "dashboard.html"), "summary": str(directory / "summary.md"), "technical_debt": str(directory / "technical-debt.md"), "revision": data["revision"]}
