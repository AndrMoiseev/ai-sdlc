"""Execution waves describe the plan without introducing admission barriers."""
from copy import deepcopy

import pytest

from lib.dashboard import projection
from lib.state import new_task


def wave_state():
    """Projection fixture: task phases exercise layout; execution proofs are absent."""
    dependencies = {"A": [], "B": [], "C": ["A"], "D": ["A"], "E": ["A"],
                    "F": ["B"], "G": ["B"], "H": ["C", "F"]}
    tasks = {key: new_task(dict(id=key, number=i, depends_on=deps, covers=["AC-demo"]))
             for i, (key, deps) in enumerate(dependencies.items(), 1)}
    return dict(schema_version=3, change_id="Execution waves", run_id="demo", revision=0,
                updated_at="2026-10-15T12:00:00Z", status="active",
                basis={"work_kind": "change"}, roles={}, tasks=tasks, blockers=[], final=None)


def membership(data):
    return [(w["id"], w["tasks"], w["depends_on"]) for w in data["waves"]]


def test_waves_remain_stable_as_branches_advance():
    state = wave_state()
    before = deepcopy(state)
    initial = projection(state)
    assert state == before
    assert [w["tasks"] for w in initial["waves"]] == [["A", "B"], ["C", "D", "E"], ["F", "G"], ["H"]]
    state["tasks"]["A"]["status"] = "accepted"
    state["tasks"]["B"]["status"] = "running"
    advanced = projection(state)
    assert membership(initial) == membership(advanced)
    assert advanced["waves"][1]["status"] == "ready"
    assert advanced["waves"][2]["status"] == "waiting_dependencies"
    state["tasks"]["C"]["status"] = "accepted"
    state["tasks"]["B"]["status"] = "accepted"
    state["tasks"]["F"]["status"] = "accepted"
    state["tasks"]["G"]["status"] = "running"
    assert projection(state)["waves"][3]["status"] == "ready"


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_candidates_do_not_share_wave(reverse):
    state = wave_state()
    left, right = ("B", "A") if reverse else ("A", "B")
    state["tasks"][left]["plan"]["cannot_parallel_with"] = [right]
    data = projection(state)
    assert data["next"] == ["A", "B"]  # Candidates are not a jointly admissible batch.
    assert data["waves"][0]["tasks"] == ["A"]
    assert data["waves"][1]["tasks"] == ["B"]
    state["tasks"]["A"]["status"] = "running"
    reason = next(t for t in projection(state)["tasks"] if t["id"] == "B")["waiting"]
    assert any(r["kind"] == "conflict" and r["tasks"] == ["A"] for r in reason)


def test_review_is_not_acceptance_and_blockers_do_not_hide_active_work():
    state = wave_state()
    state["tasks"]["A"]["status"] = "reviewing"
    state["tasks"]["B"]["status"] = "blocked"
    state["tasks"]["B"]["blockers"] = [{"reason": "needs decision"}]
    data = projection(state)
    assert data["waves"][0]["status"] == "in_progress"
    assert data["waves"][0]["blocked"] == ["B"]
    assert data["waves"][1]["status"] == "waiting_dependencies"
    state["status"] = "blocked"
    state["blockers"] = [{"reason": "budget"}]
    state["tasks"]["A"]["status"] = "accepted"
    assert projection(state)["waves"][1]["status"] == "waiting"


def test_order_is_topological_even_when_numbers_and_input_order_are_not():
    state = wave_state()
    state["tasks"]["A"]["plan"]["number"] = 100
    state["tasks"] = dict(reversed(list(state["tasks"].items())))
    data = projection(state)
    positions = {key: i for i, w in enumerate(data["waves"]) for key in w["tasks"]}
    for key, task in state["tasks"].items():
        assert all(positions[dep] < positions[key] for dep in task["plan"]["depends_on"])


def test_runtime_conflicts_explained_without_rearranging_plan():
    state = wave_state()
    initial = membership(projection(state))
    state["tasks"]["A"].update(status="running", paths=["Shared.py"], worktree={"resources": ["db"]})
    state["tasks"]["B"].update(paths=["shared.py"], worktree={"resources": ["db"]})
    data = projection(state)
    assert membership(data) == initial
    task = next(t for t in data["tasks"] if t["id"] == "B")
    assert {r["kind"] for r in task["waiting"]} == {"files", "resources"}


def test_empty_and_completed_plans():
    state = wave_state()
    for task in state["tasks"].values():
        task["status"] = "accepted"
    state["status"] = "completed"
    data = projection(state)
    assert all(w["status"] == "completed" for w in data["waves"])
    # Layout phases alone must never synthesize execution or conclusion proof.
    assert data["explorer_assignments"] == []
    for task in data["tasks"]:
        proof = task["verification"]["final"]
        assert proof["execution"]["status"] == proof["conclusion"]["status"] == "missing"
    state["tasks"] = {}
    assert projection(state)["waves"] == []


def test_dependency_order_is_a_set_and_greedy_groups_are_pairwise_compatible():
    state = wave_state()
    state["tasks"]["D"]["plan"]["cannot_parallel_with"] = ["E"]
    data = projection(state)
    groups = [w["tasks"] for w in data["waves"]]
    assert ["C", "D"] in groups and ["E"] in groups
    state["tasks"]["H"]["plan"]["depends_on"].reverse()
    assert membership(data) == membership(projection(state))


@pytest.mark.parametrize("dependency", ["H", "missing"])
def test_invalid_graph_reports_a_useful_error(dependency):
    state = wave_state()
    state["tasks"]["A"]["plan"]["depends_on"] = [dependency]
    with pytest.raises(ValueError, match="wave_dependencies"):
        projection(state)


def test_static_html_and_summary_include_waves_and_safe_dependency_links(monkeypatch, tmp_path):
    from lib import dashboard
    state = wave_state()
    state["tasks"]["A"]["status"] = "running"
    monkeypatch.setattr(dashboard, "read", lambda directory: state)
    before = deepcopy(state)
    dashboard.render(tmp_path)
    html = (tmp_path / "dashboard.html").read_text(encoding="utf-8").split("<script>")[0]
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert html.count('class="wave"') == 4
    assert 'href="#task-A"' in html
    assert "Waiting for acceptance: A" in html
    assert "Wave 2: C, D, E; after acceptance: A" in summary
    assert before == state
    data = projection(state)
    data["tasks"][0]["waiting_text"] = ['<script>bad()</script>']
    assert '<script>' not in dashboard.static_waves(data)
