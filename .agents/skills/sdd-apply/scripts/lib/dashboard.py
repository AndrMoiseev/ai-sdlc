"""Atomic, disposable views of state; never write execution decisions."""
from html import escape
import json
from pathlib import Path
from .common import atomic, contained
from .state import read
from .scheduler import available
from .review_policy import technical_debt


def projection(state):
    tasks = []
    for key, task in state["tasks"].items():
        tasks.append({"id": key, "status": task["status"], "criteria": task["plan"]["covers"], "attempt": task["attempt"], "review": f"{task['review_rounds_started']}/{task['review_limit']}", "repair": f"{task['test_repair_cycles_started']}/{task['test_repair_limit']}", "commits": [c["sha"] for c in task["commits"]], "evidence": [{k: e[k] for k in ("stage", "outcome", "log")} for e in task["evidence"]], "blockers": task["blockers"]})
    return {"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], "revision": state["revision"], "updated_at": state["updated_at"], "status": state["status"], "mode": state["mode"], "accepted": sum(t["status"] == "accepted" for t in tasks), "total": len(tasks), "tasks": tasks, "blockers": state["blockers"], "next": available(state), "final": state["final"], "technical_debt": technical_debt(state)}


def render(directory):
    directory = Path(directory)
    data = projection(read(directory))
    serialized = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    summary = [f"# {data['change_id']}", f"Run: {data['run_id']} · revision {data['revision']}", f"{data['status']} · {data['mode']} · accepted {data['accepted']}/{data['total']}", f"Snapshot: {data['updated_at']}", ""]
    for task in data["tasks"]:
        summary.append(f"- {task['id']}: {task['status']}; review {task['review']}; test repairs {task['repair']}; commits {', '.join(task['commits']) or 'none'}")
    summary.extend(["", "Blockers: " + json.dumps(data["blockers"], ensure_ascii=False)])
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
    static = "".join(f"<article><h2>{escape(t['id'])}</h2><p>{escape(t['status'])} · Review {escape(t['review'])} · Repairs {escape(t['repair'])}</p></article>" for t in data["tasks"])
    html = template.replace("__SNAPSHOT__", serialized).replace("__STATIC_TASKS__", static).replace("__CHANGE__", escape(data["change_id"])).replace("__SAVED_AT__", escape(data["updated_at"]))
    atomic(directory / "dashboard.html", html)
    return {"dashboard": str(directory / "dashboard.html"), "summary": str(directory / "summary.md"), "technical_debt": str(directory / "technical-debt.md"), "revision": data["revision"]}
