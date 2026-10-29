---
schema_version: 1
document_type: tasks
change_id: sdd-explorer
language: ru
---
# План реализации

План, спецификация и [дизайн](design.md) согласованы. После независимого ревью все три замечания исправлены. Пользователь [утвердил план без перехода к реализации](review/decisions.md#утвердить-план-без-перехода-к-реализации): все задачи pending, запуск sdd-apply и исполнение требуют отдельного поручения. [Происхождение поручений](review/decisions.md). Существующие обязательные проверки сохраняются независимо от перечисленных новых проверок.

По [уточнению пользователя](decisions.md#эвалы-только-по-отдельному-поручению) никакие эвалы не запускаются автоматически при выполнении плана, включая финальную приёмку. Это относится и к контрольным прогонам, old-skill сравнениям и микрооценкам из conductor. В ходе реализации разрешены подготовка процедур и фикстур, детерминированные тесты скриптов и проверки пакета. Запуск эвалов требует отдельного явного поручения пользователя; согласование плана, переход к задаче 8 и требования скиллов таким поручением не являются. До него фиксировать «эвал не запускался», не приписывать успешную поведенческую проверку и явно показывать неподтверждённое покрытие критериев при приёмке.

### 1. Добавить общий контракт explorer и настройку профилей

```yaml
sdd_record: task
id: TASK-explorer-contract
number: 1
covers: [AC-explorer-selection, AC-explorer-capabilities]
depends_on: []
status: pending
verification:
  - criteria: [AC-explorer-selection]
    test_description: Общий resolver принимает две новые роли; precedence, fallback при отсутствии выбора и ошибки определений сохраняются
    location: skills/sdd-shared/tests/test_contract.py
    run:
      setup_required: Расширить существующие проверки реестра и resolver, выполнить полный shared scripts/test.py через uv с абсолютными путями
  - criteria: [AC-explorer-selection]
    test_description: Setup согласует обе роли с общим наследуемым профилем и раздельными overrides без перезаписи чужих настроек
    location: skills/sdd-setup/tests/test_setup.py
    run:
      setup_required: Добавить случаи к текущей setup fixture; проверить inspect/plan/apply и неизменность при чтении, затем полный setup scripts/test.py
  - criteria: [AC-explorer-capabilities]
    test_description: Название встроенного агента не заменяет проверку инструментов, разрешений и фактического launch; недоступность останавливает зависимую работу
    location: skills/sdd-shared/tests/test_explorer_contract.py
    run:
      setup_required: Создать контрактные тесты пакета поручения и проверки host capabilities на данных, без запуска LLM
```

Область: `sdd-shared/agents/explorer.md`, описание компактного поручения и ответа в общем reference, `scripts/sdd_shared/subagents.py`, `schemas/settings.schema.json`, `templates/settings.example.json`; `sdd-setup/assets/defaults.json`, `scripts/setup_core.py`, соответствующие тесты. Обновить потребителей вместе без повышения версий и нового feature negotiation. Не менять `.sdd/settings.json` пользователя как побочный эффект. Настройка проекта в будущем только через обычный setup по поручению.

Здесь фиксируются общие формы и инструкции; применение независимости execution реализуется задачей 4. Обновить собственные README/reference-разделы настройки. Никакого автоматического выбора «дешёвой модели».

### 2. Выделить общий runner и компактную машинную сводку

```yaml
sdd_record: task
id: TASK-check-summary
number: 2
covers: [AC-check-summary-content, AC-check-summary-skips, AC-check-summary-integrity]
depends_on: [TASK-explorer-contract]
status: pending
verification:
  - criteria: [AC-check-summary-content, AC-check-summary-skips]
    test_description: Generic metadata и JUnit fixtures сохраняют exit code, duration, skips и неизвестные counts; verbose failure и повреждённый report не маскируются успехом; summary и ссылки доступны без разворачивания raw logs
    location: skills/sdd-shared/tests/test_check_summary.py
    run:
      setup_required: Создать parser/summary tests на строках и bytes с границами excerpt; минимальный файловый тест нужен только для сохранения и чтения полных raw artifacts
  - criteria: [AC-check-summary-integrity]
    test_description: Diagnosis не меняет outcome; неверный digest, foreign basis и отсутствие raw evidence отклоняются через существующий artifact adapter
    location: skills/sdd-apply/tests/test_verification.py
    run:
      setup_required: Расширить memory fixtures для раздельных raw и summary, выполнить полный apply scripts/test.py
```

Область: новый общий модуль runner/summary в `sdd-shared/scripts/sdd_shared/`, shared API; адаптация `sdd-apply/scripts/lib/verification.py`, `final_checks.py` и их tests к общему runner. Перевести все текущие вызовы напрямую и удалить прежнюю реализацию без временного совместимого import. stdout/stderr остаются за references. JUnit читается только из предусмотренного зарегистрированным запуском пути, без изменения команды. Существующий read/read_object позволяет получателю summary прочитать нужный raw artifact без нового check_run; проверку доступа и неизменности данных выполнять через memory artifact adapter, без нового транспорта.

Уже существующие проверки subprocess timeout/kill и аргументов переиспользовать. Новый реальный subprocess-тест добавлять только при обнаруженном непокрытом риске, с пояснением невозможности проверить его текущим адаптером. Матрица outcome/parser cases выполняется без процессов.

### 3. Реализовать поручения до execution и подключить sdd-spec

```yaml
sdd_record: task
id: TASK-spec-explorer
number: 3
covers: [AC-explorer-research, AC-explorer-assignment, AC-spec-research-handoff, AC-spec-check-delegation]
depends_on: [TASK-explorer-contract, TASK-check-summary]
status: pending
verification:
  - criteria: [AC-explorer-assignment]
    test_description: Временная область выбирается через API среды без фиксированных путей ОС; абсолютные ссылки из checkpoint восстанавливают поручение без execution/TASK, отсутствие ответа и удалённый временный артефакт не становятся доказательством выполнения
    location: skills/sdd-spec/tests/test_explorer.py
    run:
      setup_required: Дополнить существующие fixtures восстановления spec примерами request/result и очищенного временного каталога; выбор базы проверить подстановкой temp API без новых реальных прогонов для разных ОС; отдельные journal/store/atomicity tests не нужны
  - criteria: [AC-explorer-research, AC-spec-research-handoff, AC-spec-check-delegation]
    test_description: Пакеты исследовательского и check поручения различаются, сохраняют read/output scope, sources и document basis; check exit 0 не создаёт USER approval
    location: skills/sdd-spec/tests/test_explorer.py
    run:
      setup_required: Добавить фикстуры пакета и contract tests flows на источниках; подготовка финальной поведенческой проверки не разрешает её запуск, для него требуется отдельное явное поручение пользователя
  - criteria: [AC-explorer-research, AC-explorer-assignment, AC-spec-research-handoff, AC-spec-check-delegation]
    test_description: При отдельно порученном эвале агент передаёт исследование explorer до change/execution, сохраняет request/result и абсолютную ссылку в checkpoint, делегирует documents/plan check без создания USER approval и после очистки временных результатов сообщает unavailable
    location: skills/sdd-spec/evals/manual.md
    run:
      setup_required: Дополнить существующую процедуру разделом explorer с входными fixtures, наблюдаемыми результатами и связями с четырьмя указанными AC; проверить fixtures детерминированно, передать подготовленную процедуру в финальную приёмку задачи 8; агентские и контрольные прогоны не запускать без отдельного явного поручения пользователя
```

Область: `sdd-spec/flows/{explore,draft,revise,plan,resume}.md`, `references/{runtime-setup,codex,claude-code,generic,resume-recovery}.md`, инструкция поручения, tests и существующая `evals/manual.md`. Использовать request/result-файлы в отдельном подкаталоге системного временного каталога, определённого через API текущей среды, существующий checkpoint/resume и штатный check.py; новый CLI и journal не создавать. Основной агент хранит краткое резюме и абсолютные ссылки в state, explorer не пишет авторские документы. Процедура для финала задачи 8 сохраняет владельцев AC в задаче 3 и не требует нового runner.

Проверить workflow до change ID и null task, расположение результатов в системной временной области вне проекта, коллекций скиллов и uv cache, сохранение абсолютного пути и unavailable после очистки. Для восстановления использовать существующие fixtures; не вводить отдельный протокол переходов и его инфраструктуру тестирования.

### 4. Подключить explorer к execution и всем стадиям запуска

```yaml
sdd_record: task
id: TASK-apply-explorer
number: 4
covers: [AC-explorer-context-reuse, AC-explorer-final-independence, AC-explorer-check-stages, AC-check-evidence-invariants, AC-check-procedure-boundary, AC-check-budget-preservation]
depends_on: [TASK-explorer-contract, TASK-check-summary]
status: pending
verification:
  - criteria: [AC-explorer-context-reuse, AC-explorer-final-independence, AC-explorer-check-stages]
    test_description: Проверки role/stage/task scope допускают продолжение explorer своей задачи, сохраняют отдельную свежую final пару и отклоняют роль автора; research null scope работает без final registry
    location: skills/sdd-apply/tests/test_roles.py
    run:
      setup_required: Расширить существующие memory role fixtures новыми поручениями и evidence, проверять запреты без реальных spawn
  - criteria: [AC-check-evidence-invariants, AC-check-procedure-boundary]
    test_description: Planned absence, location, frozen basis и registry сохраняют смысл; deterministic/behavioral/manual имеют разных авторов, неизвестный procedure type не выводится из имени
    location: skills/sdd-apply/tests/test_verification.py
    run:
      setup_required: Обновить baseline/self/independent/integration/task final cases и процедуры на memory repository/artifacts
  - criteria: [AC-check-procedure-boundary]
    test_description: Общий parser поддерживает execution_kind, command default и обязательный тип procedure; отсутствующий обязательный тип отклоняется
    location: skills/sdd-shared/tests/test_contract.py
    run:
      setup_required: Дополнить parser/schema contracts без изменения номера версии; проверить допустимые command/procedure записи нового контракта
  - criteria: [AC-check-budget-preservation]
    test_description: Замена explorer и duplicate event не сбрасывают счётчик, failure retry требует reservation, общий deadline включает весь набор и прекращает последующие команды
    location: skills/sdd-apply/tests/test_budgets.py
    run:
      setup_required: Дополнить существующие budget tests искусственными часами и runner adapter; переиспользовать отдельный реальный контракт остановки процесса
```

Область: `roles.py`, `verification.py`, `final_checks.py` авторизация ролей, `api_help.py`, `check_registry.py`, `budgets.py`; общий parser/schema tasks; собственные API reference и tests. Вместе с API обновить в `sdd-apply/flows/execute-parallel.md`, `agents/{executor,verifier}.md` и `references/{roles,role-coordination}.md` минимальные инструкции поручений baseline/self/independent/integration: детерминированные команды выполняет explorer, прежний прямой check_run от verifier удаляется. Не откладывать эти рабочие инструкции до задачи 8; их соответствие разрешениям проверить существующими package contracts вместе с тестами задачи. Добавить поручение explorer в role_register и исследовательский ответ в role_result, отделить null-scope research packet от final packet. Новых exploration events и assignment-state не вводить. Для следующего поручения допускается новая role-запись с прежним context/profile в рамках одной задачи. Поля сохраняются в текущей schema 3 без повышения номера, legacy-reader и миграции.

Реестр, изменяющие код операции, checkpoints и приёмка остаются у оркестратора. Сохранять ограничения scope и budgets, не добавлять собственные настройки max retries. Не выводить тип процедуры из её имени или отсутствующего поля.

### 5. Сделать заключение verifier условием приёмки задачи

```yaml
sdd_record: task
id: TASK-verification-result
number: 5
covers: [AC-verification-dual-gate, AC-verification-gaps]
depends_on: [TASK-apply-explorer]
status: pending
verification:
  - criteria: [AC-verification-dual-gate, AC-verification-gaps]
    test_description: Отдельное событие принимает полный критерийный результат только от verifier; missing/failed/stale/foreign/duplicate criteria и новый непрошедший attempt закрывают gate
    location: skills/sdd-apply/tests/test_verification_results.py
    run:
      setup_required: Создать матрицу в памяти с подстановкой repository/artifacts; проверить review_start/transfer/commit/accept и integration basis
  - criteria: [AC-verification-gaps]
    test_description: Зелёные A/B и неподтверждённый AC позволяют checks_extend по актуальному запросу verifier до review_start; новый registry сохраняет A/B, добавляет C и требует полный повтор и новое заключение; stale/foreign/passed основания отклоняются, прежний reviewer more_checks работает
    location: skills/sdd-apply/tests/test_verification.py
    run:
      setup_required: Дополнить существующие memory fixtures достижимым переходом от failed/unavailable заключения к расширению без review_round и фиктивного test failure; проверить сохранение счётчиков и самостоятельные основания verifier/reviewer
```

Область: новый модуль заключений в apply, `transitions.py`, `roles.py`, `verification.py` (checks_extend), `integration.py`, `commits.py`, `api_help.py`, `agents/verifier.md`, `flows/execute-parallel.md`, `references/{api-checks,roles,role-coordination}.md`, соответствующие tests. Вместе с обязательным verification_result описать в основном flow получение заключения verifier и условие review_start, включая путь checks_extend при недостаточном evidence; сверить эти инструкции существующими package contracts, не откладывая правку до задачи 8. Заключение связывается с evidence IDs/digests и basis, не с общим success-флагом роли. В поручении verifier передавать актуальные summary/evidence references через оркестратора, отдельно от переписки explorer; проверяющий сопоставляет AC с исходниками и читает raw artifacts через существующий read_object по необходимости. Добавить checks_extend основание от verifier до review_start, сохранив альтернативу reviewer more_checks. Проверять достаточность тестов по AC; spec_conflict применять к изменению или противоречию требований. Не расходовать test-repair budget и review round на сам запрос дополнительной проверки без фактического падения; подготовку проверки при необходимости поручать executor существующим путём.

### 6. Разделить финальный запуск и итоговое заключение

```yaml
sdd_record: task
id: TASK-final-explorer
number: 6
covers: [AC-final-explorer-pair, AC-final-incomplete-evidence]
depends_on: [TASK-verification-result]
status: pending
verification:
  - criteria: [AC-final-explorer-pair, AC-final-incomplete-evidence]
    test_description: Ordinary task final и дополнительные project checks требуют свежих run и conclusion, прежние task pass не заменяют final; missing conclusion даёт partial
    location: skills/sdd-apply/tests/test_final_project_checks.py
    run:
      setup_required: Расширить текущие ordinary fixtures, включая change без дополнительного project registry
  - criteria: [AC-final-explorer-pair, AC-final-incomplete-evidence]
    test_description: Refactoring whole union сохраняет persistent/preservation/result scope, confirmed retirement и обязательные project checks; новая неуспешная процедура инвалидирует прежний aggregate/conclusion
    location: skills/sdd-apply/tests/test_refactoring_final_verification.py
    run:
      setup_required: Обновить текущие refactoring fixtures через memory adapters; проверить basis drift и owned repair без реального Git
```

Область: `final_checks.py`, `finalize.py`, `roles.py` final packet, `flows/finalize.md`, verifier final sections, соответствующие API help и tests. У final_verifier сохраняется ответственность за behavioral/manual процедуры и содержательный whole result. Не объединять обычный task registry с optional project registry в новую синтетическую задачу. Отчёт явно различает логи и заключения.

### 7. Подключить восстановление и представления состояния

```yaml
sdd_record: task
id: TASK-explorer-recovery
number: 7
covers: [AC-explorer-resume, AC-explorer-visibility]
depends_on: [TASK-final-explorer]
status: pending
verification:
  - criteria: [AC-explorer-resume]
    test_description: Lost task/run explorer, abandoned procedure, successor и revised_plan сохраняют бюджеты, registry transitions и обязательства; не дают passed из незавершённой работы
    location: skills/sdd-apply/tests/test_resume.py
    run:
      setup_required: Расширить существующие resume fixtures для explorer и раздельных conclusions
  - criteria: [AC-explorer-visibility]
    test_description: Compact и dashboard показывают отдельные статусы без разворачивания логов
    location: skills/sdd-apply/tests/test_read_views.py
    run:
      setup_required: Дополнить существующие model/view fixtures; выполнить полный apply scripts/test.py
  - criteria: [AC-explorer-visibility]
    test_description: Sync через apply read отличает completed с обоими доказательствами от partial, не трактует один успешный command как полную приёмку
    location: skills/sdd-sync/evals/manual.md
    run:
      setup_required: Дополнить существующую процедуру сохранёнными read-response fixtures нового контракта; поведенческий проход инструкции не запускать автоматически, в том числе на финальной приёмке, без отдельного явного поручения пользователя
```

Область: существующие state/read-view adapters, `resume.py`, `api_help.py`, `dashboard.py`, storage reference, recovery flow и tests. Встроить explorer и conclusions в текущую сериализацию и восстановление; не вводить миграционные операции, маркеры и резервные форматы. В `skills/sdd-sync/references/workflow.md` уточнить чтение завершённого результата через apply read, в `evals/manual.md` добавить соответствующий сценарий. У sync нет собственного scripts/test.py; не создавать новый runner для этой правки.

### 8. Согласовать инструкции комплекта и подготовить проверку сквозного поведения

```yaml
sdd_record: task
id: TASK-explorer-workflow
number: 8
covers: [AC-explorer-workflow]
depends_on: [TASK-spec-explorer, TASK-explorer-recovery]
status: pending
verification:
  - criteria: [AC-explorer-workflow]
    test_description: Все инструкции и API help передают deterministic execution explorer, сохраняют отдельную оценку verifier и правила полномочий; отсутствуют прежние прямые verifier check_run поручения
    location: skills/sdd-apply/tests/test_package.py
    run:
      setup_required: Дополнить существующий package contract минимальными связями инструкций, без дублирующего текстового линтера; выполнить полные обязательные наборы затронутых скиллов отдельно
  - criteria: [AC-explorer-workflow]
    test_description: При отдельно порученном финальном эвале чистые agent traces подтверждают передачу summary и evidence references от explorer через оркестратора независимому verifier, чтение нужных raw artifacts без повторного запуска, сохранность primary evidence и блокировку обязательного skip в трёх сценариях
    location: skills/sdd-apply/evals/explorer.md
    run:
      setup_required: Подготовить процедуру и fixtures трёх сценариев с описанием old-skill control по conductor, проверить fixtures детерминированно; сами эвалы и контрольные прогоны запускать только по отдельному явному поручению пользователя на финале, с общим лимитом набора и внешними результатами
```

Область: согласование `SKILL.md` и README четырёх скиллов, `sdd-shared/references/{subagents,coordination,api}.md`, `sdd-apply/agents/{executor,verifier,reviewer}.md`, `references/{roles,role-coordination,api-checks,api-tasks}.md`, `flows/{start,execute-parallel,repair,resume,finalize}.md`, spec consumer references и eval procedures. Пользовательский поток описывает действия и результаты без лишних внутренних деталей.

Рабочие инструкции запуска и заключения уже обновлены в задачах 4–5, финальные инструкции — в задаче 6; здесь выполняется общая сверка. В состав подготовленной финальной оценки входят сценарии explorer в `skills/sdd-spec/evals/manual.md` из задачи 3, `skills/sdd-apply/evals/explorer.md` из этой задачи и процедура sync из задачи 7. Проверить наличие входов, ожидаемых результатов и связей с AC у каждой процедуры. При отдельном поручении пользователя выполнить выбранные эвалы на финале, измеряя наборы каждого скилла раздельно; без такого поручения сохранить процедуры и отметить отсутствие поведенческих результатов. Владельцы AC остаются в исходных задачах.

Задача готовит процедуру финальной поведенческой проверки и детерминированно проверяет её fixtures. Эвалы не запускаются автоматически ни как локальный task check, ни при финальной приёмке всего плана. При отсутствии отдельного поручения сохранить подготовленную процедуру и сообщить, что поведение не проверено эвалом. Отрицательные контрольные случаи не получают false pass только из совпадения текста инструкций. При отдельно разрешённом запуске наблюдать: кто запустил команды, прочитал ли verifier полный лог, повторил ли запуск без причины, увидел ли skip, сохранился ли raw artifact. Неизвестные token/cost metrics обозначать null. Перед поставкой проверить source/relocated bundle, lock-файлы, отсутствие hidden/ignored runtime-мусора; использовать существующие проверки пакета.

## Обоснование разбиения

Выбраны границы контракта роли, evidence, spec-потребителя и последовательных состояний apply. Альтернатива «одна задача на скилл» создала бы одну большую задачу apply с ролями, логами, приёмкой и восстановлением одновременно. Разделение по стадиям проверяемо: задача 4 вводит исполнение поручений, задача 7 подключает его к восстановлению и представлениям состояния. Поддержка прежнего формата отсутствует.

Задача 1 задаёт единый формат для 2–4. Задача 2 даёт runner и summary для spec и apply. Задача 5 опирается на реальное evidence из 4; задача 6 расширяет conclusion на final; задача 7 использует готовые записи поручений и заключений обеих областей final. Задача 8 согласует завершённые потребители, выполняет разрешённые детерминированные проверки и готовит финальные эвалы; запуск эвалов остаётся отдельным поручением пользователя.

После задачи 2 задачи 3 и 4 могут выполняться параллельно: задача 3 меняет spec flows/recovery, задача 4 — apply role/check API и общий parser tasks/execution_kind. Общее описание поручения уже готово в задаче 1. Задача 3 также независима от последующих apply-задач 5–7. Все остальные зависимости отражают передачу результата; отдельно запрещённых пар нет. Фактический запуск параллельных работ подчинён действующему режиму sdd-apply, наличие графа само по себе не даёт разрешений.

## Обязательная проверка времени и пакета

До первого добавления тестов измерить полный существующий последовательный набор каждого изменяемого скилла; при исходном превышении 60 секунд остановиться и сначала согласовать/выполнить оптимизацию по AGENTS.md. После изменения измерить полный набор вновь, без xdist и без разделения одного набора на независимые лимиты. Команда для каждого `sdd-shared`, `sdd-setup`, `sdd-spec` отдельно:

```text
uv run --python "<system-python>" --locked --script "<absolute-skill-root>/scripts/test.py" -q -x --basetemp "<unique-external-run-directory>"
```

Для `sdd-apply` всегда указывать абсолютный каталог тестов и отключать xdist явно: отдельное значение `--basetemp` иначе мешает runner добавить собственный `tests`, и обнаружение зависит от cwd. Все ссылки задач на полный apply scripts/test.py означают эту команду:

```text
uv run --python "<system-python>" --locked --script "<absolute-apply-root>/scripts/test.py" "<absolute-apply-root>/tests" -q -x -n 0 --basetemp "<unique-external-run-directory>"
```

`-x` не заменяет полный успешный набор: после исправления предыдущего отказа нужен новый полный успешный прогон. Процедуру sdd-sync из evals/manual.md запускать и измерять отдельно только при явном поручении на эвал, без выдуманного scripts/test.py. Фиксировать полную команду, состав, cache state, elapsed time с учётом uv/setup/cleanup, exit code, skips и ссылки на внешние логи. При превышении любого одиночного набора немедленно остановить его процессы и всю текущую работу, сообщить причину и ждать нового указания пользователя. Для известного Windows pytest WinError 5 запрашивать штатное расширение доступа конкретной команды сразу; не повторять известный отказ.

Матрицы проверять через memory adapters. Новые реальные Git/browser/network/process интеграционные тесты допустимы только с документированным риском и объяснением недостаточности текущего адаптера. Инфраструктуру эвалов не расширять сверх нужных контрактов. При отдельном поручении на поведенческий набор финала измерять его для соответствующего скилла с тем же пределом; невозможность уложиться сообщать как ограничение приёмки. Сам лимит и включение сценария в план не разрешают запуск; без поручения сохранять явное отсутствие результата.
