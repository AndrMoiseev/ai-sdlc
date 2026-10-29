---
schema_version: 2
work_kind: change
document_type: review
change_id: sdd-explorer
language: ru
run_id: 20261029T072150Z-explorer-plan
stage: plan_review
lens_id: plan
result: completed_with_findings
started_at: '2026-10-29T07:29:40Z'
finished_at: '2026-10-29T07:42:01Z'
reviewed_commit: 3d6eccf648aae378826314468ec703a10789849b
limitations:
  - 'Выполнено статическое ревью плана; реализация, тесты и поведенческие оценки не запускались.'
  - 'Фактическое время обязательных наборов и поведение выбранного хоста не измерялись; возможность завершить будущие проверки за 60 секунд не подтверждена.'
  - 'Согласование спецификации, дизайна и границ работы принято из задания; происхождение решений по историческим журналам повторно не проверялось.'
---

# Отчёт независимого ревью плана

Проверены все восемь задач, их зависимости и содержательное покрытие 22 AC. Найдены два блокирующих пробела в проверках и одна рекомендация по работоспособности промежуточных состояний. Изменять согласованную архитектуру для их устранения не требуется.

Основание ревью — исключительно дерево коммита `3d6eccf648aae378826314468ec703a10789849b`. Команда `git cat-file -t` подтвердила тип `commit`. Оцениваемые документы и проектные источники читались через `git show` этого OID. Рабочее дерево, текущий HEAD, чужие отчёты и история автора основанием выводов не были. Файлы не изменялись.

### Отложенная поведенческая проверка sdd-spec не получила конкретного финального сценария

```yaml
sdd_record: finding
id: FIND-spec-explorer-final-verification
source: >-
  AC-explorer-assignment, AC-spec-research-handoff, AC-spec-check-delegation;
  tasks.md, TASK-spec-explorer и TASK-explorer-workflow;
  design.md, раздел «Поручение до execution».
target:
  path: tasks.md
  element_id: TASK-spec-explorer
severity: blocker
problem: >-
  Задача 3 предусматривает fixtures и contract tests по текстам flows,
  а поведенческое исполнение ролей явно откладывает до финальной приёмки
  задачи 8. Однако конкретная финальная процедура задачи 8 находится
  в skills/sdd-apply/evals/explorer.md и описывает только три сценария
  передачи результатов проверок в apply: успех, многословное падение
  и обязательный skip. Для sdd-spec не назначены процедура, входы
  и наблюдаемые результаты проверки research до change/execution,
  сохранения внешнего request/result и восстановления после очистки
  временного каталога. Общая фраза «spec consumer references и eval
  procedures» этот пробел не закрывает.
impact: >-
  Эти операции реализуются прежде всего инструкциями агента, без нового
  CLI или execution engine. Детерминированная проверка подготовленной
  фикстуры и наличия формулировок в Markdown не устанавливает, что агент
  действительно сохраняет абсолютный путь, передаёт поручение explorer
  и признаёт удалённый результат unavailable. План позволяет завершить
  финальную приёмку, так и не выполнив обещанную проверку поведения
  sdd-spec по назначенным задаче 3 критериям.
suggestion: >-
  В задаче 3 назначить подготовку минимальной финальной процедуры
  sdd-spec с явным location и соответствием существующим AC:
  поручение до change, передача результата и ссылки в checkpoint,
  делегированный documents/plan check и продолжение при недоступном
  внешнем результате. Указать в задаче 8 запуск этой подготовленной
  процедуры только на финале всего плана. Сохранить владельцев AC,
  внешний каталог результатов и отдельный лимит набора sdd-spec;
  дополнительный runner или новый протокол не нужны.
```

### Общая команда обязательного набора не фиксирует набор sdd-apply

```yaml
sdd_record: finding
id: FIND-apply-suite-selection
source: >-
  tasks.md, раздел «Обязательная проверка времени и пакета», строка 246;
  skills/sdd-apply/scripts/test.py:27–33;
  skills/sdd-apply/tests/pytest.ini;
  skills/sdd-apply/references/maintenance.md:146 и раздел
  «Commands and verification scope»; AGENTS.md.
target:
  path: tasks.md
  element_id: TASK-explorer-workflow
severity: blocker
problem: >-
  План задаёт всем четырём скиллам одинаковую команду test.py -q -x
  --basetemp <absolute-directory>, не указывая каталог тестов или cwd.
  У sdd-apply runner добавляет собственный tests только тогда, когда
  среди аргументов нет ни одной строки без начального дефиса.
  Значение --basetemp удовлетворяет этому условию, поэтому runner
  не добавит tests. Его pytest.ini не задаёт testpaths.
  В результате команда не фиксирует обещанный полный набор именно
  sdd-apply и оставляет выбор области обнаружения тестов зависимым
  от текущего каталога. Maintenance прямо требует явного пути тестов
  при аргументах с отдельными значениями.
impact: >-
  Запуск из корня проекта или внешнего рабочего каталога может проверить
  другую область. Такой результат нельзя использовать как подтверждение
  полного обязательного набора sdd-apply и его отдельного лимита
  60 секунд. Возможное обнаружение тестов нескольких скиллов также
  противоречит предусмотренному раздельному измерению.
suggestion: >-
  Для sdd-apply указать отдельную команду с явным абсолютным путём
  skills/sdd-apply/tests и -n 0, сохранив уникальный внешний --basetemp,
  -x и остальные runtime-параметры. Например:
  uv run --python "<system-python>" --locked --script
  "<absolute-apply-root>/scripts/test.py"
  "<absolute-apply-root>/tests" -q -x -n 0
  --basetemp "<unique-external-run-directory>".
  Остальные runner уже добавляют собственный каталог tests;
  менять их ради этой поправки не требуется.
```

### Минимальные инструкции запуска стоит переносить вместе с изменением API

```yaml
sdd_record: finding
id: FIND-runtime-instructions-late
source: >-
  TASK-apply-explorer, TASK-verification-result, TASK-explorer-workflow;
  AC-explorer-check-stages, AC-verification-dual-gate;
  skills/sdd-apply/flows/execute-parallel.md:7–10;
  skills/sdd-apply/agents/verifier.md.
target:
  path: tasks.md
  element_id: TASK-apply-explorer
severity: recommendation
problem: >-
  Задача 4 запрещает прежним ролям детерминированный check_run,
  но обновление execute-parallel и части ролевых инструкций отнесено
  к задаче 8. В исходном execute-parallel baseline и independent
  явно поручены verifier; инструкция verifier также требует самому
  инициировать check_run. Задача 5 добавляет обязательное
  verification_result, тогда как основной flow до задачи 8
  не описывает новый переход. Поэтому между задачами 4 и 8
  основной пользовательский маршрут расходится с уже изменённым API.
impact: >-
  Промежуточный пакет можно проверить прямыми API-тестами, но пройти
  его штатный flow без самостоятельного исправления инструкций
  агентом нельзя: предписанный запуск отвергается либо отсутствует
  необходимое заключение. Это ослабляет заявленную проверяемость
  последовательных состояний apply.
suggestion: >-
  Перенести минимальные рабочие правки пунктов execute-parallel
  и инструкций запуска в задачу 4, а описание verification_result
  и нового допуска к review_start — в задачу 5. Финальные пункты
  оставить в задаче 6, где уже назначен flows/finalize.md.
  Задаче 8 сохранить общую сверку комплекта, пользовательские
  пояснения и финальные сценарии. Новые задачи, AC и совместимый
  переходный режим для этого не нужны.
```

### Оценка задач и графа

| Задача | Оценка в пределах линзы |
|---|---|
| `TASK-explorer-contract` | Resolver, settings schema и setup назначены совместно; проверены общий профиль, overrides и сохранение настроек. Подготовка новых тестов включена. |
| `TASK-check-summary` | Выделение runner охватывает существующих task/run потребителей. Проверки parser/outcome преимущественно используют данные и адаптеры; сохранение реальных process contracts предусмотрено. |
| `TASK-spec-explorer` | Область реализации соответствует согласованному хранению через API временных каталогов. Обнаружен пробел в назначении финальной проверки поведения. |
| `TASK-apply-explorer` | Назначены роли, пять стадий, scope, процедура, parser и budgets. Задача крупная, но объединена одной границей исполнения. Есть рекомендация перенести сюда необходимые инструкции запуска. |
| `TASK-verification-result` | Покрыты четыре допуска, integration basis и расширение A/B → A/B/C по verifier до review_start. Сохранение самостоятельного reviewer-основания и бюджетов указано явно. |
| `TASK-final-explorer` | Раздельно охвачены ordinary task final, optional project registry и refactoring whole union. Проверки включают отсутствие conclusion, устаревание и отрицательную новую попытку. |
| `TASK-explorer-recovery` | Назначены task/run recovery, abandoned procedures, revised_plan, компактные представления и потребитель sdd-sync. Существующая manual-процедура sync доступна; новый runner не требуется. |
| `TASK-explorer-workflow` | Три согласованных apply-сценария и проверки поставки назначены. Требуют уточнения финальная проверка sdd-spec и команда обязательного набора apply. |

Все 22 AC имеют ровно одного владельца; повторного назначения AC финальной интеграционной задаче нет. Все новые проверки используют `setup_required`, что соответствует их неготовности. Отсутствие будущих `test_explorer.py`, `test_check_summary.py`, `test_verification_results.py` и `evals/explorer.md` само по себе дефектом не является.

Граф ацикличен: `1 → 2 → {3, 4}`, затем `4 → 5 → 6 → 7`, после чего `{3, 7} → 8`. Параллельность задачи 3 с задачами 4–7 обоснована разными областями spec/apply и готовым общим контрактом. Зависимость восстановления от готовых task/run final-результатов имеет предметное основание.

Разбиение «по одному скиллу» действительно увеличило бы задачу apply. Существенной выгоды от дальнейшего дробления runtime-задач без дробления согласованных AC не установлено. Предлагаемое перемещение минимальных инструкций сохраняет граф и уменьшает рассогласование промежуточных состояний.

### Прочитанные материалы

Полностью прочитан нормативный комплект из указанного snapshot:

- `sdd/changes/sdd-explorer/proposal.md`;
- `sdd/changes/sdd-explorer/design.md`;
- `sdd/changes/sdd-explorer/specs/sdd-explorer/spec.md`;
- `sdd/changes/sdd-explorer/specs/sdd-execution/spec.md`;
- `sdd/changes/sdd-explorer/tasks.md`.

Также прочитаны `AGENTS.md` и `docs/decisions/research/0011-sdd-explorer-and-deterministic-checks.md`. Релевантные реализации, контракты и потребители проверены в том же дереве:

- **sdd-shared:** `subagents.py`, settings schema, coordination; соответствующие фрагменты `documents.py`, `validation.py`, refactoring schema; `scripts/test.py`.
- **sdd-setup:** presets, соответствующие части `setup_core.py`, `scripts/test.py`.
- **sdd-spec:** flows explore/draft/plan/resume, resume-recovery, task templates, package tests и runner; просмотрены существующие материалы evals и проверено наличие относящихся к новой роли сценариев.
- **sdd-apply:** `state.py`, `state_objects.py`, `roles.py`, `verification.py`, `budgets.py`, `transitions.py`, `integration.py`, `commits.py`, `finalize.py`; соответствующие части `final_checks.py`, `resume.py`, `check_registry.py` и `api_help.py`; event schema, API checks, verifier, execute-parallel/finalize, SKILL, maintenance, package/help tests, test runner и pytest configuration.
- **sdd-sync:** workflow и `evals/manual.md`.

Установленные инструкции рецензента, шаблон отчёта, четыре документа формата и применимые инструкции `sdd-skill-conductor` прочитаны с диска отдельно от оцениваемого snapshot.

Ревью завершено в пределах линзы `plan`. Отчёт не является `plan_approval` и не разрешает реализацию.
