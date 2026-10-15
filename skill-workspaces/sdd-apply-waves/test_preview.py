"""Render illustrative snapshots through the real dashboard renderer."""
from copy import deepcopy
from pathlib import Path
import subprocess

from lib import dashboard
from lib.state import new_task


def test_render_preview(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parent / "preview"
    records = [
        ("TASK-database-schema", [], "accepted"),
        ("TASK-ui-shell", [], "accepted"),
        ("TASK-orders-api", ["TASK-database-schema"], "accepted"),
        ("TASK-order-form", ["TASK-database-schema"], "reviewing"),
        ("TASK-validation", ["TASK-database-schema"], "running"),
        ("TASK-notifications-api", ["TASK-ui-shell"], "accepted"),
        ("TASK-notification-panel", ["TASK-ui-shell"], "running"),
        ("TASK-checkout-flow", ["TASK-orders-api", "TASK-notifications-api"], "pending"),
        ("TASK-accessibility", ["TASK-database-schema"], "blocked"),
        ("TASK-end-to-end-tests", ["TASK-checkout-flow"], "pending"),
        ("TASK-validation-migration", ["TASK-database-schema"], "pending"),
    ]
    state = dict(schema_version=1, change_id="Оформление заказа · пример исполнения", run_id="illustrative-demo",
                 revision=12, updated_at="2026-10-15T12:00:00Z", mode="parallel", status="active",
                 tasks={}, blockers=[], final=None)
    for number, (key, deps, status) in enumerate(records, 1):
        task = new_task(dict(id=key, number=number, depends_on=deps, covers=[f"AC-{number:02d}"]))
        task.update(status=status, attempt=0 if status == "pending" else 1)
        if status in {"accepted", "reviewing"}:
            task["review_rounds_started"] = 1
        if status == "accepted":
            task["review_rounds_completed"] = 1
        state["tasks"][key] = task
    state["tasks"]["TASK-accessibility"]["blockers"] = [
        {"reason": "Test fixture unavailable", "resume_condition": "Подготовить тестовые данные для проверки клавиатурной навигации."}
    ]
    state["tasks"]["TASK-validation"]["plan"]["cannot_parallel_with"] = ["TASK-validation-migration"]
    state["tasks"]["TASK-validation-migration"]["plan"]["cannot_parallel_with"] = ["TASK-validation"]
    for mode in ("parallel", "sequential"):
        example = deepcopy(state)
        example["mode"] = mode
        if mode == "sequential":
            for key, task in example["tasks"].items():
                task.update(status="pending", attempt=0, review_rounds_started=0, review_rounds_completed=0, blockers=[])
            example["tasks"]["TASK-database-schema"].update(status="accepted", attempt=1, review_rounds_started=1, review_rounds_completed=1)
            example["tasks"]["TASK-ui-shell"].update(status="running", attempt=1)
        monkeypatch.setattr(dashboard, "read", lambda directory: example)
        directory = root / mode
        directory.mkdir(parents=True, exist_ok=True)
        dashboard.render(directory)
        page = directory / "dashboard.html"
        note = ('Демонстрационные данные. Волны 2 и 3 выполняются одновременно. '
                'Волна 4 готова к запуску после приёмки двух конкретных задач. '
                'Ниже показаны ожидание зависимости и запрет совместного запуска.') if mode == "parallel" else (
                'Демонстрационные данные. Каждая задача занимает отдельную волну. '
                'Первая задача принята, вторая выполняется; остальные показывают причину ожидания.')
        nav = '<aside style="margin:0 0 26px;padding:16px;border:1px solid var(--line);border-radius:10px"><strong>Пример для визуальной оценки</strong><p>' + note + '</p><nav aria-label="Варианты примера"><a href="../parallel/dashboard.html">Параллельный режим</a> · <a href="../sequential/dashboard.html">Последовательный режим</a></nav></aside>'
        page.write_text(page.read_text(encoding="utf-8").replace('<main>', '<main>' + nav), encoding="utf-8")
        chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        result = subprocess.run([str(chrome), "--headless", "--disable-gpu", "--no-first-run",
                                 "--no-default-browser-check", "--window-size=1280,2400",
                                 "--user-data-dir=" + str(tmp_path / mode), "--virtual-time-budget=3000",
                                 "--screenshot=" + str(directory / "preview.png"), "--dump-dom", page.as_uri()],
                                capture_output=True, timeout=40)
        assert result.returncode == 0, result.stderr
        dom = result.stdout.decode("utf-8", "replace")
        assert 'data-wave="wave-1"' in dom and "Live view" in dom
        if mode == "parallel":
            assert 'data-wave="wave-4" data-status="ready"' in dom
            assert "Cannot run alongside: TASK-validation" in dom
        else:
            assert dom.count('class="wave" data-wave=') == len(records)
            assert "Sequential mode; waiting for: TASK-ui-shell" in dom
        (directory / "browser-dom.html").write_text(dom, encoding="utf-8")
