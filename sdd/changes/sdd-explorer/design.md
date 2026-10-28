---
schema_version: 1
document_type: design
change_id: sdd-explorer
language: ru
---
# Дизайн роли explorer

## Статус и контекст

Роль и границы приняты, технический дизайн предложен: [журнал](decisions.md#предлагаемый-дизайн), [Q-design-and-plan](questions.md#согласование-дизайна-и-плана). Цель и исключения заданы в [proposal](proposal.md); наблюдаемое поведение задано в двух [спецификациях](specs/sdd-explorer/spec.md).

Основание проверки кода: `ac83d5fbab13492d697e581e185e9dca7890afd9`. Изучены:

| Точка | Текущее поведение и необходимая перемена |
|---|---|
| `skills/sdd-shared/scripts/sdd_shared/subagents.py`, `schemas/settings.schema.json` | Восемь ролей; добавить два ключа explorer, сохранив правила resolver |
| `skills/sdd-setup/scripts/setup_core.py`, `assets/defaults.json` | Точное равенство реестра ролей и presets; общий профиль уже может обслуживать несколько ролей |
| `skills/sdd-spec/flows/explore.md`, `draft.md`, `plan.md`, `resume.md` | Исследование и check выполняются в авторском процессе; добавить сохраняемые поручения |
| `skills/sdd-apply/scripts/lib/roles.py` | Только четыре вида ролей; null task scope допускается только для final_verifier в ограниченных случаях |
| `verification.py`, `final_checks.py` | Авторизация запуска привязана к executor/verifier/reviewer/final_verifier; заменить матрицей explorer |
| `commits.py`, `finalize.py` | Приёмка проверяет логи и ревью; обязательной типизированной записи заключения verifier нет |
| `state.py`, `state_objects.py`, `state_history.py`, `resume.py` | Execution schema 3, объектное хранилище, повтор событий и восстановление потерянных ролей |
| `artifact_storage.py`, `repository.py`, `tests/memory_state.py`, `tests/memory_repository.py` | Есть адаптеры для тестов без реального Git и процессов; сохранить эти границы |
| `skills/sdd-sync/references/workflow.md` | Читает execution через apply read и проверяет completed/accepted/final; собственного Python runner у sync нет, уточнить чтение пары evidence/conclusion |

`sdd/changes/sdd-execution-skill/specs/sdd-execution/spec.md` содержит историческое описание, в том числе уже изменённый режим исполнения. Отдельного текущего baseline capability не найдено. Изменяемые требования ниже используют честный evidence-source по актуальному коду, а не объявляют исторический change действующим baseline.

## Термины

| Термин | Значение |
|---|---|
| Explorer | Роль SDD, исполняющая поручения research или checks; не встроенный тип агента конкретного хоста |
| Поручение / assignment | Ограниченная работа с идентичностью, основанием, разрешёнными действиями и ожидаемым результатом |
| Запуск проверки / check run | Фактическое исполнение зарегистрированного набора на конкретном основании |
| Сводка / summary | Машинное представление результатов запуска и отдельно помеченная диагностика агента |
| Заключение / verification result | Оценка AC проверяющим, связанная с точными доказательствами и проверенным основанием |
| Основание / basis | Идентичность работы, версия источников и нормативных документов, реестр и конфигурация проверок |

Имена `explorer`, `check_run`, `role_register`, `role_result`, `final_verifier` продолжают существующий язык. Новые имена операций ниже являются предложением контракта; библиотечные классы и внутренние функции выбираются при реализации.

## Модули и ответственность

| Владелец | Контракт |
|---|---|
| sdd-shared | `agents/explorer.md`, формат assignment/result, роли и resolver, общий запуск команды и машинная сводка; не принимает задачи и не меняет execution |
| sdd-spec | Постановка research и documents/plan checks, request/result во внешних файлах со ссылкой из текущего checkpoint, перенос подтверждённых фактов в документы основным агентом |
| sdd-apply | Регистрация ролей и поручений в execution, реестры проверок, бюджеты, разрешения стадий, заключения, приёмка и восстановление |
| sdd-setup | Установка и настройка профиля; обычное использование ничего не устанавливает |

Общий runner извлекается из `verification.run_command` с сохранением запуска argument array через `shell=False`, stdout/stderr, exit code, monotonic duration и остановки дерева процессов. Apply сохраняет сведения через текущий artifact/object store. Для документов spec сохраняет JSON и stderr штатного check.py во внешнем каталоге; JSON checker уже содержит машинный результат. Общая библиотека не импортирует apply и не создаёт второй журнал исполнения.

### Роли и профиль

```yaml
sdd_record: decision
id: DEC-explorer-profile
requirements: [REQ-explorer-selection, REQ-explorer-independence]
```

Добавить `sdd-spec.explorer` и `sdd-apply.explorer`. Оба preset выбирают профиль `sdd-explorer`; в создаваемом профиле модель и effort наследуются от родителя. Это устраняет недоказанное предположение о достаточности дешёвой модели. Пользователь может назначить разные существующие профили обычным sdd-setup. Сохраняются lookup precedence, строгие ошибки и действующий fallback при отсутствии выбора/определения. Выбор профиля не заменяет проверку инструментов хоста.

Контекст explorer не используется как executor, verifier, reviewer или final_verifier. Один explorer одной задачи может последовательно выполнять research, baseline, self, independent и integration при неизменном профиле. Каждое поручение содержит актуальный basis; изменение входов требует нового фактического запуска, но не нового инструментального контекста. Для final всегда создаётся свежий explorer и отдельный свежий final_verifier. Между задачами контекст не переносится. Verifier/reviewer сохраняют существующее разрешение совместного контекста при доказанной идентичности launch profile; explorer в это исключение не входит. Упрощение принято в рамках [поручения на минимальный дизайн](decisions.md#упрощения-по-ревью).

### Поручение до execution

```yaml
sdd_record: decision
id: DEC-explorer-assignment
requirements: [REQ-bounded-assignment, REQ-spec-exploration]
```

Компактное поручение содержит ID, `kind: research|checks`, project/work/task scope (до их появления допустим null), вопрос либо набор проверок, basis, область чтения, разрешённые выходы и лимиты. Сохраняются обычные selection/launch evidence. Форма поручения описана в общей инструкции explorer; отдельная машина состояний ему не нужна. В apply ID поручения — существующий role_id, в spec — имя пары внешних request/result-файлов.

Spec хранит request/result/launch trace во внешнем workspace, выбранном по правилам проекта, вне uv cache. В `state.md` после появления change сохраняются assignment ID, краткий итог, ссылка и digest; в `state.yaml.document_links` включаются только существующие локальные Markdown-материалы. Не добавлять JSON-поручения в нормативный manifest. До создания change путь workspace возвращается пользователю и сохраняется в доступной точке продолжения; это не требует фиктивного execution или TASK.

Отдельный CLI или журнал для spec не вводится. Оркестратор сохраняет запрос, запускает агента и сохраняет ответ с фактическим launch evidence. Штатный resume читает checkpoint и эти файлы, проверяет basis и живой контекст через хост. Неполученный ответ остаётся незавершённым поручением; утраченный артефакт означает unavailable. При необходимости нового запуска сохраняется новый запрос со ссылкой на предыдущий; запись файла сама по себе не гарантирует однократный запуск агента.

В apply поручение входит в пакет существующего `role_register`, ответ исследования — в типизированное содержимое `role_result` с trace. Для следующего поручения создаётся новая role-запись; допустимое продолжение explorer сохраняет context/profile. Research поддерживает task scope и run scope даже до регистрации final checks. Для null scope формируется исследовательский пакет без вызова final-check-specific basis. Checks используют прежние `check_run` и `procedure_begin/result`. Новых событий исследования и отдельного assignment-state нет; запись и повторы обслуживает существующий event store.

Research возвращает ответ, пути/строки или идентификаторы объектов, просмотренную область, ограничения, непроверенные предположения и вопросы. Поиск, чтение и инспекция справки разрешены как средства исследования. Тест, линтер, сборка или валидатор оформляются checks-поручением. Изменение кода, нормативных документов, реестра и настроек explorer не разрешено.

### Делегирование детерминированных запусков

```yaml
sdd_record: decision
id: DEC-check-execution
requirements: [REQ-independent-verification, REQ-check-summary]
```

Оркестратор сохраняет реестр и basis, останавливает авторов, запускает explorer и регистрирует роль. Explorer запрашивает `check_run`; реальный API-вызов может сделать оркестратор, сохранив запрос и trace explorer. Подмена роли строкой `role_id` без фактического launch недопустима. Прямой запуск verifier больше не является допустимым путём.

| Стадия | Состояние и scope | Исполнитель детерминированной части |
|---|---|---|
| baseline | До изменений, clean task worktree; setup_required обозначен planned_absence | Task explorer |
| self | После остановки автора и frozen local commit | Task explorer; self не допускает приёмку |
| independent | Frozen local commit, полный применимый task registry | Task explorer, независимый от автора |
| integration | Новый интегрированный commit и его реестр | Task explorer с новым фактическим запуском |
| final, ordinary task | Принятая задача на итоговом HEAD | Свежий task explorer |
| final, null task | Refactoring whole union либо ordinary additional project registry | Свежий run-level explorer |

На baseline сохраняется отсутствие исходных проверок, но оно не считается успехом. Planned setup разрешает только подготовку зарегистрированной будущей проверки. Ошибка существующей команды и отсутствие location не становятся planned_absence. Проверка новых тестов не доказывает старое поведение.

Запуск commands всегда исполняет полный применимый набор стадии. В поручении передаются exact check IDs и registry revision; engine отклоняет расхождение и не позволяет explorer сокращать набор. Успешный self не заменяет independent; historical task evidence не заменяет final.

Разделить режим процедуры явным полем `execution_kind: deterministic|behavioral|manual` для `run.procedure` и дополнительных проверок. `run.command` по умолчанию deterministic; команда, запускающая агентскую оценку, явно помечается behavioral. Поле принадлежит verification-записи, не нарушает правило одного ключа в run. Для procedure тип обязателен; отсутствие типа — ошибка валидации. Путь/имя файла не определяют тип автоматически, отдельного legacy-режима нет.

Deterministic procedure_begin/result принадлежат explorer. Behavioral/manual procedure остаются у verifier/final_verifier, с сохранением фактических шагов и trace; инструментальные подшаги можно делегировать explorer и включить их references в аттестацию проверяющего. Для скиллов behavioral допустим только в final. `check_run` агрегирует оба вида результатов, но explorer не подписывает чужую смысловую оценку.

### Машинная сводка

Сводка создаётся runner, имеет schema_version 1 и привязку к immutable raw artifact. Обязательные поля: work/run/assignment identity, role/launch trace, stage, basis before/after, registry revision, check ID, command arguments или procedure ref, cwd, configuration reference, start time, duration, exit code или null, outcome, limitation, ссылки и digest stdout/stderr/structured report.

Агрегат содержит requested/completed/missing check IDs, per-check outcomes, `source_unchanged`, `evidence_complete`. Отдельный результат инструмента `test_counts` содержит collected/passed/failed/skipped/xfailed/xpassed и `unknown_fields`; неизвестные значения null. Счётчики не заменяют list of checks и не оцениваются по свободному тексту модели.

Первая реализация поддерживает generic command metadata и pytest JUnit XML, если отчёт уже предусмотрен зарегистрированной командой. Добавлять `--junitxml` или менять команду за спиной реестра нельзя. Другие форматы сохраняются как primary artifacts без угадывания метрик. Указанный, но отсутствующий/повреждённый обязательный structured report делает `evidence_complete: false` при неизменном фактическом exit code. Для голого generic runner counts неизвестны; verifier должен получить достаточное другое подтверждение полноты, иначе заключение unavailable.

Обычный результат API не разворачивает stdout/stderr. Машинный diagnostic excerpt ограничен 4096 символами на check, с offset/line reference и признаком truncation; крупные списки остаются за существующими object references. Лог сохраняется полностью. `diagnosis` explorer отделена от машинных полей и не меняет outcome. Успех command с восемью skips отображает восемь skips; verifier устанавливает их связь с обязательными AC. Неподтверждённая обязательная область блокирует приёмку.

### Заключение verifier и переходы

```yaml
sdd_record: decision
id: DEC-verification-result
requirements: [REQ-verification-result, REQ-final-acceptance]
```

Добавить событие `verification_result` с payload: `role_id`, `stage: independent|integration|final`, `basis`, `evidence_refs`, `criteria_results` (criterion ID, passed/failed/unavailable, reason и references), `limitations`, `trace`. Explorer не может его отправить. Verifier читает исходные AC, изменённый код и тесты; summary является указателем, а не авторским заявлением о соответствии.

Для independent/integration отправитель verifier; для final — final_verifier. Scope совпадает с evidence. Неполные/дублирующиеся/чужие criteria, роль автора, другая стадия, registry revision или commit отклоняются. Сохраняются и отрицательные заключения. Последнее применимое заключение обязательно; новая неуспешная попытка не позволяет выбрать старое passed. `role_result` лишь завершает агента и не заменяет verification_result.

Переходы `review_start`, `transfer`, `commit`, `accept` требуют одновременно успешного обязательного запуска и passed verification_result на том же basis. Reviewer затем оценивает качество реализации и целостность тестов; его заключение остаётся отдельным. После интеграции требуется новое заключение integration. Baseline/self содержательного допуска не создают.

Final сохраняет существующее различие task-level и run-level реестров. Ordinary final: по каждой задаче новый запуск и task final_verifier conclusion; при дополнительных project checks — также null-scope запуск и conclusion. Refactoring final: null-scope union подтверждённых task/project/whole checks и conclusion, покрывающий design results, preservation и применимые persistent local criteria. Retired checks сохраняют историю и не возвращаются в применимый набор. `finalize` проверяет оба вида доказательств на одном текущем integrated HEAD и основании; successful log или role_result отдельно недостаточны.

Не добавляется кандидат-хранилище: basis сверяется с фактическим commit, Git cleanliness, document snapshot и registry revision существующими механизмами. После изменения любого входа создаются новые результаты. Нормативный conflict возвращается в sdd-spec; сбой/исправление следует прежним бюджетам. Когнитивный пробел без падения команды не списывает test-repair cycle как тестовую ошибку: используется существующий путь review/more_checks или spec_conflict с причиной.

### Восстановление

```yaml
sdd_record: decision
id: DEC-explorer-recovery
requirements: [REQ-explorer-recovery]
```

Поручения explorer в существующих role packets/results и отдельные verification results сохраняются в текущей execution schema 3. Номера settings, нормативных документов и shared API также не повышаются. Parser/schema и потребители обновляются вместе в одном bundle. Дополнительного механизма согласования версий или feature negotiation не вводится.

Обратная совместимость и миграция исключены [решением пользователя](decisions.md#без-обратной-совместимости). Нет `migrate_execution`, конвертера, legacy-reader, переходных aliases и отдельных тестов прежних форматов. Новый контракт применяется напрямую; обязательные поля и доказательства проверяются обычной валидацией. Совпадение номера schema_version не заменяет наличие требуемого содержимого. Существующие артефакты не удаляются и автоматически не переписываются.

В исполнениях по новому контракту сохраняются бюджеты, reservations, baseline, setup, revisions, inventory, retired checks и project obligations. Наличие passed-лога не создаёт заключение verifier; финальная приёмка получает свежую пару доказательств.

При потере explorer штатный `resume` использует существующее восстановление роли через host trace, predecessor и successor, сохраняя basis и бюджеты. Незавершённые deterministic procedures следуют действующему правилу abandoned, successor начинает новую попытку. Существующий лимит нельзя обойти новым агентом или поручением. Неизменённая недоступность не запускает автоматические повторы. `revised_plan` переносит обязательства и историю, но инвалидирует основания активных заключений. Compact view показывает scope/stage/status роли с поручением и отдельные статусы execution/verification; подробности доступны через references.

## Runtime и хранение

Временные файлы, uv cache/tools, test workspaces, stdout/stderr внешних проверок и новые spec assignments размещаются вне проекта и коллекций скиллов. В проекте сохраняются запрошенные авторские SDD-документы и краткие ссылки на evidence. Apply сохраняет нормативные execution-записи через существующий store; он не является заменой каталога временных файлов команды. Изменение общей политики расположения старого execution — отдельная задача вне этого change.

Новые entry points имеют PEP 723 и соседние lock-файлы, отключают bytecode. До запуска explorer проверяет реальные возможности Python/процесса в выбранных каталогах. Учитываются AGENTS.md, разрешения среды и остановка дерева процессов. Никакой новый уровень прав не следует из названия роли. Ограничение времени набора передаётся в assignment как общий deadline, а не как новый тайм-аут на каждый check; смена исполнителя его не сбрасывает. Для этого репозитория превышение 60 секунд останавливает текущий прогон и всю работу до нового указания пользователя.

## Проверка решения

[План](tasks.md) проверяет роль/стадию/полноту/актуальность преимущественно через существующие memory adapters. Реальные subprocess, Git и filesystem используются только для контрактов границы. Три поведенческих сценария финальной приёмки: обычный успех без повторного запуска verifier; многословное падение с сохранённым логом; exit 0 с пропущенным обязательным тестом. Отдельно проверяется восстановление и отсутствие подмены behavioral procedure детерминированной командой.

Для каждого затронутого скилла полный обязательный набор измеряется последовательно до и после добавления тестов, отдельно от остальных скиллов. Время включает uv, setup, выполнение и cleanup; предел — 60 секунд на набор. При исходном превышении сначала оптимизация, при любом фактическом превышении немедленная остановка согласно AGENTS.md. Ни параллельный прогон, ни разбивка одного набора не заменяют эту проверку. Обязательные behavioral оценки тоже не исключаются из лимита: состав и возможность их исполнения проверяются до приёмки, превышение не выдаётся за успех.

## Альтернативы и риски

- Только компактный runner без роли не соответствует принятому направлению: нужна ещё передача исследований.
- Второй execution-engine не нужен: spec использует внешние request/result-файлы и текущий checkpoint, apply — существующие role events и recovery. Shared содержит только общую инструкцию, runner и summary.
- Поддержка прежнего формата исключена пользователем: схема обновляется на месте, без адаптеров и миграционных операций.
- Автоматическая бюджетная модель смешивает выбор роли и непроверенные возможности. Предложено наследование модели до настройки.
- Ограниченный summary может пропустить важное сообщение; raw artifacts сохраняются, parser errors и unknown metrics видны, verifier запрашивает нужные фрагменты.

Оставшееся согласование конкретного решения: [Q-design-and-plan](questions.md#согласование-дизайна-и-плана). Неизвестные метрики стоимости остаются ограничением, а не условием принятия роли.
