# Поведенческие проверки рефакторинга

Выполняй реальные сессии только при финальной приёмке всего плана. Локальная
приёмка задачи проверяет runner и шаблоны детерминированно; эти тесты не доказывают
поведение агента. Sdd-spec вызывается явно: discovery/trigger не применяется.

## Сценарии и свидетельства

| Сценарий runner | Критерий | Наблюдаемый результат |
|---|---|---|
| explicit-entry | AC-refactoring-entry-notice | Уведомление до работы, proposal/design в refactoring, сохранённое основание |
| implicit-entry | AC-refactoring-entry-notice | Уверенный выбор без лишнего подтверждения маршрута |
| resume-notification | AC-refactoring-entry-notice | Восстановлены вид, уведомление и действующее поручение |
| ambiguous-intent | AC-refactoring-entry-conflict | Конкретный выбор пользователя до зависимого решения |
| contract-conflict | AC-refactoring-entry-conflict | Давление сроков не меняет сохраняемый API без выбора |
| baseline-gap | AC-refactoring-baseline-gap | Пробел назван; получение исходного свидетельства предшествует преобразованию |
| cross-module-plan | AC-refactoring-cross-module-plan | Core и оба потребителя имеют локальную приёмку и общий вклад |
| semantic-coverage-pair | AC-refactoring-plan-validation | Забытый inventory найден при зелёной структуре; полный план допустим |
| completeness-pressure-micro | AC-refactoring-plan-validation | Пять свежих повторений сохраняют область под давлением |

Промпты и независимые assertions перечислены в evals.json (ID 101–109).
Исполняемая fixture-spec дополняет их исходниками и настоящими документами,
USER-записями согласований и разрешённого планирования. Executors получают только
prompt и fixture; assertions и ответы доступны отдельному grader. Для пары планов
сохрани один полный и один структурно корректный, но пропускающий известного
потребителя. До модели оба должны пройти реальный documents/plan check.

## Подготовка без моделей

1. Сохрани неизменяемый old_skill до правок. Не называй снимок пакета измеренным
   поведенческим baseline. Существующий control сохраняй без перезаписи.
2. Подготовь внешнюю fixture-spec schema_version: 1: packages (path и полный files
   SHA-256 inventory) для old_skill, sdd-shared, humanizer-ru, sdd-skill-conductor;
   fixture_parent вне проекта и коллекций; scenarios; split_file и split_sha256.
   Каждый scenario имеет уникальный id, name из таблицы, prompt, assertions,
   files (относительный путь → текст), repetitions; у micro не меньше пяти.
   Необязательные checks содержат change/stage для реального структурного запуска.
3. Зафиксируй train_ids/heldout_ids один раз до оценки. Подготовь полный комплект
   зависимостей по sdd-skill-conductor. Проверь user-level discovery и изоляцию
   рабочего каталога: текущий глобальный пакет не должен попасть в baseline.
4. Сохрани fixture-spec, split, packages и результаты вне пакетов скиллов.
   Runtime uv и Python следуют общим условиям запуска. Детальный runner создаёт
   новые workspace для каждого варианта и повторения; прежние отчёты не читает
   как результат нового запуска.

## Финальная команда

Подставь проверенные абсолютные пути и зарегистрируй команду только как проверку
целого; сохрани точный argv вместе с финальным HEAD и хешем fixture-spec:

```text
uv run --python "<system-python>" --locked --script "<skill-root>/evals/run_refactoring.py" --conductor-root "<frozen-conductor>" --fixture-spec "<frozen-fixture-spec>" --output-root "<retained-output-root>" --harness codex
```

Каждый запуск сравнивает old_skill, without_skill и with_skill на свежих fixtures,
включая no-guidance control для micro. Runner сохраняет команды, времена, raw
traces, concrete outputs, независимые grading.json, benchmark, анализ и review.html.
Недоступная модель, missing/failed/stale свидетельство или провал обязательного
with_skill assertion дают ненулевой код. Нулевой код одной оболочки недостаточен.
`--preflight-only` не запускает модели и не означает поведенческий pass;
`--baseline-only` также не подтверждает новый пакет. Прежде новых правок по оценкам
покажи viewer пользователю; held-out выводы не передавай редактору.
