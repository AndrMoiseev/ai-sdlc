"""Disposable project inputs; no executor prompts or grading data are written."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

STAMP = "2026-10-01T08:00:00Z"


def _write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")


def _front(kind: str, change: str, **extra: object) -> str:
    fields = dict(schema_version=1, document_type=kind, change_id=change, language="ru", **extra)
    return "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()) + "\n---\n"


def _record(heading: str, **fields: object) -> str:
    return f"### {heading}\n\n```yaml\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()) + "\n```\n"


def _manifest(change: Path) -> list[dict]:
    paths = [change / "proposal.md", change / "design.md", *change.glob("specs/**/spec.md")]
    return [{"path": p.relative_to(change).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(paths, key=lambda p: p.relative_to(change).as_posix())]


def _normative(root: Path, change: str, time: str = "08:00") -> None:
    prefix = f"sdd/changes/{change}/"
    typo = change == "label-typo"
    behavior = "Кнопка показывает «Отправить» вместо «Отпавить»; обработчик и доступность прежние." if typo else f"Ежедневно к {time} диспетчер получает CSV с просроченными доставками. Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер."
    requirement = "REQ-label-text" if typo else "REQ-report-export"
    acceptance = "AC-label-correct" if typo else "AC-report-delivered"
    _write(root, prefix + "proposal.md", _front("proposal", change) + f"# {change}\n\n## Проблема и результат\n" + ("Исправить опечатку без изменения поведения." if typo else "Снизить просрочки: диспетчер использует отчёт до назначения исполнителей.") + f"\n\n## Объем\n[Спецификация](specs/main/spec.md). {behavior}\n\n## Исключения\nАвтоматическое назначение исполнителей не входит в объём.\n\n## Влияние\n" + ("Только текст кнопки." if typo else "Новый CSV для диспетчера; существующая система назначения не меняется."))
    spec = _front("spec", change, capability="main") + "# Наблюдаемое поведение\n\n## " + requirement + "\n\n```yaml\nsdd_record: requirement\nid: " + requirement + "\noperation: add\n```\n\n" + behavior + "\n\n"
    spec += _record("Критерий приемки", sdd_record="acceptance", id=acceptance, requirement=requirement, conditions="Открыта форма отправки" if typo else "Наступил срок ежедневного отчёта; имеются просроченные доставки", expected="Текст кнопки — Отправить" if typo else f"Диспетчеру доступен CSV к {time} с колонками delivery_id, overdue_minutes, responsible")
    _write(root, prefix + "specs/main/spec.md", spec)
    _write(root, prefix + "design.md", _front("design", change) + "# Дизайн\n\n## Контекст\n[Объем](proposal.md), [требования](specs/main/spec.md).\n\n## Модули и контракты\n" + ("Изменить только строку в src/labels.json." if typo else f"Планировщик запускает сборку CSV из хранилища доставок к {time}; диспетчер получает файл через существующий канал. Назначение остаётся ручным.") + "\n\n## Термины\nНовых терминов нет.\n\n## Риски\nВопросы и ответы сохранены в [state](state.md).")


def _review(root: Path, change: str, waiver: bool, planning: bool) -> list[str]:
    prefix = f"sdd/changes/{change}/"
    manifest = _manifest(root / prefix)
    records = []
    records.append(_record("Согласование документов", sdd_record="user", id="USER-documents-approved", kind="document_approval", scope={"stage": "document_review"}, response="Согласую proposal, specs и design в приложенной версии.", date=STAMP, inputs=manifest, status="active"))
    refs = ["USER-documents-approved"]
    if waiver:
        records.append(_record("Пропуск consistency", sdd_record="user", id="USER-consistency-waived", kind="review_waiver", scope={"stage": "document_review", "lenses": ["consistency"]}, response="Разрешаю пропустить consistency для текущего комплекта документов delivery-report.", date=STAMP, inputs=manifest, status="active"))
        refs.append("USER-consistency-waived")
    else:
        run = "20261001T080000Z-prior"
        _write(root, prefix + f"review/{run}/consistency.md", _front("review", change, run_id=run, stage="document_review", lens_id="consistency", result="completed_no_findings", started_at=STAMP, finished_at=STAMP, inputs=manifest, inputs_after=manifest, freshness="current", limitations=[]) + "# Consistency\n\nСохранённое независимое ревью: противоречий в комплекте не найдено.")
    if planning:
        records.append(_record("Команда планирования", sdd_record="user", id="USER-plan-request", kind="planning_command", scope={"stage": "document_review", "work": "Подготовить план delivery-report по согласованным документам"}, response="Создай план delivery-report по этим документам.", date=STAMP, inputs=manifest, status="active"))
        refs.append("USER-plan-request")
    _write(root, prefix + "review/decisions.md", _front("decisions", change) + "# Сохранённые ответы пользователя\n\n" + "\n".join(records))
    return refs


def prepare_fixture(root: Path, eval_id: int) -> None:
    """Populate a fresh workspace with the scenario's prior project state."""
    if eval_id not in range(13, 32):
        raise ValueError("Supported fixture IDs: 13 through 31")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Fixture destination must be empty")
    typo = eval_id in {15, 25}
    change = "label-typo" if typo else "delivery-report"
    prefix = f"sdd/changes/{change}/"
    if typo:
        _write(root, "docs/labels.md", "# Текст интерфейса\nВ форме отправки кнопка должна называться «Отправить». Изменяются только буквы: обработчик, права и доступность прежние.")
        _write(root, "src/labels.json", '{"submit": "Отпавить"}')
        _write(root, "change.diff", '--- a/src/labels.json\n+++ b/src/labels.json\n@@ -1 +1 @@\n-{"submit": "Отпавить"}\n+{"submit": "Отправить"}')
    else:
        assignment = "07:30" if eval_id == 24 else "08:30"
        report = "09:00" if eval_id < 22 and eval_id != 20 else "08:00"
        text = f"# Ежедневный отчёт\nПолучатель: диспетчер доставки. Отчёт ежедневно в {report}. CSV: delivery_id, overdue_minutes, responsible. Цель — снизить просрочки."
        if eval_id not in {13, 14, 16}:
            text += f" Диспетчер назначает исполнителей в {assignment}."
        if eval_id in {19, 21}:
            text += " Пока не выбрано, будет ли только отчёт или также автоматическое назначение. Три колонки CSV согласованы для обоих вариантов."
        elif eval_id == 20:
            text += " Пользователь подтвердил пилот на 10 строк. Массовый запуск не входит в текущий объём; расчёт ёмкости отложен до расширения."
        elif eval_id not in {13, 14, 16}:
            text += " Диспетчер по списку выбирает исполнителей для просроченных доставок."
        _write(root, "docs/report.md", text)
        if eval_id in {16, 18, 20, 22, 23, 24, 28, 29, 30, 31}:
            _write(root, "docs/decision.md", "# Ответ пользователя, 2026-10-01\nОтчёт нужен к 08:00: в 08:30 диспетчер назначает исполнителей по списку просроченных доставок. CSV с колонками delivery_id, overdue_minutes, responsible подходит. Автоматическое назначение не требуется.")
        if eval_id == 16:
            _write(root, "docs/decision.md", "# Ответ пользователя, 2026-10-01\nПо отчёту в 09:00 диспетчер выбирает исполнителей для просроченных доставок на сессии назначения в 09:30. CSV с колонками delivery_id, overdue_minutes, responsible подходит. Автоматическое назначение не требуется.")
        if eval_id == 21:
            _write(root, "docs/manager-note.md", "# Предложение менеджера\nПредлагаю автоматическое назначение или принятие риска бесполезного отчёта. Пользователь эти варианты ещё не выбирал.")
        if eval_id == 28:
            _write(root, "docs/evidence.md", "# Уточнение основания\nПод назначением в 08:30 имеется в виду начало утренней сессии диспетчера в рабочие дни. Это уточнение формулировки прежнего основания; решение о CSV к 08:00 не менялось.")
        if eval_id in {26, 27}:
            _write(root, "docs/report.md", "# Ежедневный отчёт\nПолучатель: диспетчер доставки. CSV: delivery_id, overdue_minutes, responsible. Цель — снизить просрочки. Решение о времени и его обоснование были сохранены отдельно в docs/decision.md; текущий рабочий график диспетчера здесь не указан.")
    history = eval_id in {18, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31}
    if not history:
        return
    _normative(root, change, "09:00" if eval_id == 18 else "08:00")
    refs = _review(root, change, waiver=eval_id == 31, planning=eval_id == 31) if eval_id in {25, 28, 30, 31} else []
    links = ["proposal.md", "design.md", "specs/main/spec.md"]
    body = "# Точка продолжения\n\n## Следующий шаг\nПродолжить подготовку документов; реализацию не начинать.\n"
    if eval_id != 25:
        body += "\n## Проверка предпосылок\nСохранённый разбор: [premortem.md](premortem.md). Проверены потребитель, назначение и CSV.\n"
        if eval_id != 26:
            details = "# Проверка предпосылок delivery-report\n\n## Основания\n[Исходные данные](../../../docs/report.md).\n\n## CSV\nТри согласованные колонки: delivery_id, overdue_minutes, responsible; формат не зависит от времени отчёта.\n\n## Время отчёта\n"
            if eval_id == 18:
                details += "Отчёт в 09:00 поступает после назначения в 08:30. Последствие: список не влияет на утреннее назначение. Открыт Q-report-time в state; ответ пока не перенесён в документы.\n"
            else:
                details += "Ранее выявлено: отчёт в 09:00 опаздывал к назначению в 08:30. Пользователь выбрал 08:00; вопрос Q-report-time разрешён. Основание ответа: [решение пользователя](../../../docs/decision.md). Повторный выбор формата не требуется.\n"
            _write(root, prefix + "premortem.md", details)
        if eval_id == 18:
            body += "\n" + _record("Время отчёта", sdd_record="question", id="Q-report-time", text="К какому времени нужен отчёт до назначения в 08:30?", blocking=True, status="open")
        elif eval_id not in {26, 27}:
            body += "\n" + _record("Время отчёта", sdd_record="question", id="Q-report-time", text="К какому времени нужен отчёт?", blocking=True, status="resolved") + "\nОтвет сохранён в docs/decision.md: 08:00.\n"
        if eval_id == 20:
            body += "\n" + _record("Ёмкость массового запуска", sdd_record="question", id="Q-bulk-capacity", text="Какова ёмкость массового запуска?", blocking=False, status="open", reason="Текущий пилот ограничен подтверждёнными 10 строками", return_at="Перед расширением пилота до массового запуска")
    review_links = ["review/decisions.md"] if refs else []
    if refs and eval_id != 31:
        review_links.append("review/20261001T080000Z-prior/consistency.md")
    _write(root, prefix + "state.md", _front("state", change, phase="drafting", awaiting="clarification" if eval_id == 18 else "none", updated_at=STAMP, document_links=links, review_links=review_links, approval_refs=refs) + body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("eval_id", type=int)
    args = parser.parse_args()
    prepare_fixture(args.root, args.eval_id)
