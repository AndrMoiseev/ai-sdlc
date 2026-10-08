---
schema_version: 1
document_type: tasks
change_id: sdd-execution-skill
language: ru
---
# План реализации sdd-apply

План реализует текущие [proposal](proposal.md), [спецификацию](specs/sdd-execution/spec.md)
и [design](design.md). Пользователь поручил перейти к плану без повторного
ревью документов; основания сохранены в [решениях](review/decisions.md).
План содержит 14 задач и покрывает 61 критерий приёмки. Все задачи имеют
статус pending; реализация начинается после согласования плана и поручения
на исполнение.

## Порядок и границы работы

Исходный пакет создаётся в skills/sdd-apply. Имена модулей и тестов ниже
задают границы задач; при реализации допустимо уточнить внутреннее
разбиение с сохранением контрактов. Существующие пакеты sdd-spec
и sdd-implement сохраняют свои назначения. Для работы над скиллом применять
sdd-skill-conductor и writing-for-agents. Инструкции ролей писать с участием
свежего автора по правилам conductor, затем проверять поведением.

Обычное исполнение этого плана последовательное. Граф зависимостей
описывает техническую доступность задач и сам по себе не разрешает
параллельный запуск. После задачи 6 задачи 7 и 8 могут разрабатываться
независимо: они владеют разными модулями и тестами. Задача 12 зависит
от схемы состояния и может идти отдельной ветвью графа. Сборка общего
процесса в задаче 13 ожидает обе ветви. Центральную точку входа создаёт
задача 1, а окончательно подключает задача 13; промежуточные задачи
работают через интерфейсы своих модулей. Общие фикстуры и схема состояния
закрепляются задачей 2. При необходимости их несовместимой правки
параллельные работы сериализуются; общие файлы не редактируются одновременно.

Каждая задача включает реализацию, отрицательные случаи, необходимые
фикстуры и проверки своих AC. Сквозные сценарии задачи 13 проверяют
итоговую приёмку и соединение модулей; тесты предыдущих задач к ней
не откладываются. Для проверок с агентами сохраняются фактические трассы
чистых контекстов; имитация адаптера не выдаётся за проверку реального хоста.
Недоступная обязательная проверка остаётся ограничением.

Команды ниже запускаются от корня репозитория. Будущий scripts/test.py
принимает пути относительно корня skills/sdd-apply; задача 1 создаёт
этот запускатель и его lock-файл. Для поведенческих и браузерных проверок
подготовка конкретного запуска включена в соответствующую задачу.
После подготовки команда, cwd и конфигурация сохраняются в записи
исполнения; согласованный tasks.md не меняется.

Результаты запусков, временные проекты, копии установок и браузерные
материалы размещаются вне каталогов скиллов, например в
skill-workspaces/sdd-execution-skill/implementation/. Для uv используются
внешние пользовательские кэши. Очистка касается только проверенных
путей временных данных текущего запуска.

## Задачи

### 1. Проверить входы и подготовить основу пакета

```yaml
sdd_record: task
id: TASK-validated-input
number: 1
covers: [AC-approved-start, AC-invalid-input, AC-existing-work, AC-companion-scope]
depends_on: []
status: pending
verification:
  - criteria: [AC-approved-start, AC-invalid-input]
    test_description: "На реальных фикстурах SDD вызвать штатный валидатор для согласованного комплекта, отсутствующего approval, устаревшего манифеста, открытого блокирующего вопроса и несовместимой зависимости; проверить сохранённое основание и отсутствие запуска реализации при отказе."
    location: skills/sdd-apply/tests/test_inputs.py
    run:
      setup_required: "В этой задаче создать scripts/test.py с PEP 723, lock-файлом и фикстурами SDD/Git; выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_inputs.py -q. Перед написанием инструкций сохранить отдельный исходный прогон без нового скилла."
  - criteria: [AC-existing-work]
    test_description: "В отдельном Git-репозитории с чужими staged, unstaged и untracked файлами и исходно падающей проверкой сравнить байты, индекс и HEAD до и после входа; проверить разделение или блокировку затронутой работы."
    location: skills/sdd-apply/tests/test_inputs.py
    run:
      setup_required: "В этой задаче создать scripts/test.py с PEP 723, lock-файлом и фикстурами SDD/Git; выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_inputs.py -q. Перед написанием инструкций сохранить отдельный исходный прогон без нового скилла."
  - criteria: [AC-companion-scope]
    test_description: "В явном сценарии с отсутствующим планом проверить возврат к sdd-spec и отсутствие созданных спецификаций, плана или автоматических правок проектных инструкций."
    location: skills/sdd-apply/tests/test_inputs.py
    run:
      setup_required: "В этой задаче создать scripts/test.py с PEP 723, lock-файлом и фикстурами SDD/Git; выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_inputs.py -q. Перед написанием инструкций сохранить отдельный исходный прогон без нового скилла."
```

До написания инструкций выполнить в отдельной копии фикстуры один согласованный план без нового скилла. Сохранить исходы и трассу для сравнения на том же хосте и модели. Использовать sdd-skill-conductor; отсутствие возможности запуска обозначить явно.

Создать основу skills/sdd-apply, точки входа scripts/execute.py и scripts/test.py с PEP 723 и соседними lock-файлами. Подготовить общий запуск pytest, который разрешает переданные пути тестов относительно корня пакета, отключает байткод и кэш pytest. Фикстуры Git, логи и окружения размещать вне каталогов скиллов. Это подготовка проверок, предусмотренная данной задачей.

В scripts/lib/inputs.py реализовать обнаружение установленного sdd-spec, вызов его штатных check/snapshot и проверку оснований исполнения обеих стадий. Сохранить выбранное изменение, поручение, манифест, исходный HEAD, локальную ветку, индекс и незакоммиченные изменения. Проверить доступность Git и записи коммитов без изменения глобальной конфигурации. Не копировать парсер SDD. При неоднозначном выборе вернуть кандидатов; при неисправной зависимости или исходной проверке сохранить причину блокировки.

Входной модуль возвращает проверенное основание, а запуск задач подключается после реализации остальных модулей. Зафиксировать постоянную границу с sdd-spec; существующий skills/sdd-implement использует OpenSpec и не заменяется этим пакетом.

### 2. Реализовать состояние, события и условия переходов

```yaml
sdd_record: task
id: TASK-state-store
number: 2
covers: [AC-stable-plan, AC-no-unproven-done, AC-scripted-state-update, AC-transition-rejected, AC-state-concurrency, AC-event-idempotency]
depends_on: [TASK-validated-input]
status: pending
verification:
  - criteria: [AC-scripted-state-update, AC-stable-plan]
    test_description: "Применить допустимую цепочку событий к фикстуре; проверить согласованность истории с revision, изоляцию execution/ и побайтовую неизменность нормативного комплекта."
    location: skills/sdd-apply/tests/test_state.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_state.py -q"
  - criteria: [AC-transition-rejected, AC-no-unproven-done]
    test_description: "Передать неизвестное событие, запуск зависимой задачи и приёмку без команды, ревью или коммита, включая DONE автора; проверить отказ, неизменность JSON и недоступность потомков."
    location: skills/sdd-apply/tests/test_state.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_state.py -q"
  - criteria: [AC-state-concurrency]
    test_description: "Запустить два отдельных процесса с одной revision и прервать запись перед заменой; проверить отсутствие потери события, частичного JSON и двух владельцев, отказ при неподтверждённой устаревшей блокировке."
    location: skills/sdd-apply/tests/test_state.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_state.py -q"
  - criteria: [AC-event-idempotency]
    test_description: "Повторить успешное событие после потери ответа, затем заменить его payload при том же ID; первый повтор не меняет историю, второй отклоняется."
    location: skills/sdd-apply/tests/test_state.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_state.py -q"
```

В scripts/lib/state.py и схемах пакета описать execution/state.json, основание запуска, задачи, роли, события и доказательства по design. Реализовать типизированные события с expected_revision и event_id, проверку разрешённых переходов и единый интерфейс всех изменений состояния.

Сохранять состояние, revision и историю вместе под блокировкой через атомарную замену. Проверять владельца блокировки перед восстановлением. При отказе не менять состояние. Повтор того же события возвращает прежний результат; другой payload с тем же ID отклоняется. Приёмка требует актуальных независимых доказательств и подтверждённого коммита; произвольное поле DONE не удовлетворяет условию.

Проверять корни и принадлежность путей, неизвестные версии и повреждение истории. Нормативные proposal, specs, design и tasks остаются в исходных байтах. Подключаемые проверки ролей, Git и бюджетов имеют явные интерфейсы; отсутствие реализации обязательной проверки означает отказ.

### 3. Собирать проверки и привязывать доказательства к кандидату

```yaml
sdd_record: task
id: TASK-verification-evidence
number: 3
covers: [AC-independent-test-run, AC-test-integrity, AC-required-check-blocker, AC-planned-verification-setup, AC-verification-setup-boundary, AC-verification-snapshot]
depends_on: [TASK-state-store]
status: pending
verification:
  - criteria: [AC-independent-test-run, AC-test-integrity]
    test_description: "Сопоставить успешный отчёт автора с независимым запуском команды, которая выявляет дефект; отдельный поведенческий сценарий с зелёными, но ослабленными тестами должен дать обоснованный отказ рецензента."
    location: skills/sdd-apply/tests/test_verification.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_verification.py -q"
  - criteria: [AC-required-check-blocker, AC-verification-snapshot]
    test_description: "Выполнить падающую, пропущенную, нестабильную и недоступную проверку; изменить код, конфигурацию и основание после успеха. Проверить сохранение всех исходов и запрет приёмки устаревшего кандидата."
    location: skills/sdd-apply/tests/test_verification.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_verification.py -q"
  - criteria: [AC-planned-verification-setup, AC-verification-setup-boundary]
    test_description: "Сравнить отсутствующий новый запускатель по setup_required с неисправным существующим. Проверить исходный снимок, подготовку в рамках задачи, сохранение команды, независимый запуск, неизменность tasks.md и запрет повторно объявлять готовую команду ожидаемо отсутствующей после перезапуска."
    location: skills/sdd-apply/tests/test_verification.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_verification.py -q"
```

В scripts/lib/verification.py реализовать реестр обязательных команд и процедур из плана, инструкций проекта и CI. Сохранить этап, AC, роль, cwd, конфигурацию, снимки до и после, stdout/stderr, код выхода, время и хеш лога. Запускать согласованную команду без подмены; фиксировать кандидата на время проверки.

Различать самопроверку, независимый запуск, интеграцию и итоговую проверку. Устаревшее доказательство не разрешает переход. Неизвестная область влияния требует полного обязательного набора. Проверять независимость зарегистрированной роли; недоступная, пропущенная или нестабильная обязательная проверка блокирует приёмку.

Реализовать setup_required: сохранить исходное состояние, выполнить существующие проверки либо зафиксировать их отсутствие, разрешить только плановую подготовку, записать конкретную команду без правки tasks.md. После подготовки её недоступность блокирует работу и после смены сессии. Добавить в контракт рецензента проверку соответствия assertions критериям, skip/xfail и ослабления команд.

### 4. Подключить свежие роли и цикл ревью

```yaml
sdd_record: task
id: TASK-independent-roles
number: 4
covers: [AC-review-repair, AC-review-freshness, AC-host-limits]
depends_on: [TASK-verification-evidence]
status: pending
verification:
  - criteria: [AC-review-repair, AC-review-freshness]
    test_description: "В чистых сессиях дать исполнителю задачу с воспроизводимым дефектом; проверить отдельный запуск рецензента, адресное исправление, новые доказательства после правки и отказ использовать старое ревью."
    location: skills/sdd-apply/tests/test_roles.py
    run:
      setup_required: "Подготовить реальные изолированные сценарии для доступных Codex и Claude Code с трассами запуска ролей; выполнить описанные случаи и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_roles.py -q. Недоступные хосты и чистые контексты отметить как непроверенные."
  - criteria: [AC-host-limits]
    test_description: "В адаптерах проверить отсутствие свежего контекста, потерянного агента и занятые слоты; прогресс и ограничение сохраняются, автор не подменяет независимого проверяющего. Сохранить трассы доступных реальных хостов; имитацию недоступного хоста обозначить отдельно."
    location: skills/sdd-apply/tests/test_roles.py
    run:
      setup_required: "Подготовить реальные изолированные сценарии для доступных Codex и Claude Code с трассами запуска ролей; выполнить описанные случаи и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_roles.py -q. Недоступные хосты и чистые контексты отметить как непроверенные."
```

В scripts/lib/roles.py реализовать подготовку входных пакетов и регистрацию ролей с проверкой принадлежности результата кандидату. Написать отдельные задания исполнителю, проверяющему и рецензенту, адаптеры Codex и Claude Code. Реальный вызов инструмента среды остаётся за адаптером, если скрипт его не поддерживает.

Каждой задаче назначать свежего исполнителя; проверки и ревью поручать отдельному контексту без истории автора. Допустить совмещение независимого проверяющего и рецензента только с двумя отдельными результатами. Различать занятые слоты, потерю роли и отсутствие механизма запуска; ограничение прав инструкцией описывать честно.

Ревью связывает дефект с AC, файлом и условием устранения. Исправление возвращается исполнителю, новая версия требует затронутых проверок и ревью. Рекомендации сохраняются для итогового разбора. Бюджетный интерфейс подключается следующей задачей; без него обычный запуск ревью не разрешается.

### 5. Ограничить ревью и исправления тестов

```yaml
sdd_record: task
id: TASK-repair-budgets
number: 5
covers: [AC-bounded-repair, AC-review-round-count, AC-review-third-success, AC-review-limit-decision, AC-review-limit-parallel, AC-test-repair-limit, AC-test-repair-counting, AC-test-repair-last-success, AC-test-repair-resume]
depends_on: [TASK-independent-roles]
status: pending
verification:
  - criteria: [AC-bounded-repair, AC-review-round-count, AC-review-third-success, AC-review-limit-decision]
    test_description: "Проверить раунды от 1 до 3 в разных фазах, дубликат события и восстановление раунда; успешный третий проходит дальше, дефект или необходимость четвёртого блокирует запуск до конечного разрешённого расширения."
    location: skills/sdd-apply/tests/test_budgets.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_budgets.py -q"
  - criteria: [AC-test-repair-limit, AC-test-repair-counting, AC-test-repair-last-success]
    test_description: "Воспроизвести исходное падение и пять циклов, несколько ошибок набора, повтор без правок, повтор event_id и второй активный цикл. Проверить успешный пятый и отказ шестого без решения."
    location: skills/sdd-apply/tests/test_budgets.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_budgets.py -q"
  - criteria: [AC-review-limit-parallel, AC-test-repair-resume]
    test_description: "При двух активных задачах исчерпать каждый бюджет отдельно; проверить сохранение работ, запрет новых ревью, исправлений, переносов и коммитов, сохранение блокировки после смены сессии и независимость двух лимитов."
    location: skills/sdd-apply/tests/test_budgets.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_budgets.py -q"
```

В scripts/lib/budgets.py реализовать атомарное резервирование раунда ревью и цикла тестового исправления через интерфейс состояния. Исходные пределы на TASK-ID: 3 раунда и 5 циклов. Первый раунд входит в лимит, исходное падение тестов не расходует цикл.

Учёт сохраняется между фазами, интеграцией, итоговой проверкой, попытками, режимами и сессиями. Повтор события и восстановление того же незавершённого действия не увеличивают расход. Повтор после падения без правок расходует цикл; несколько ошибок одного набора относятся к одному циклу. Недоступная проверка оставляет цикл незавершённым.

При исчерпании применимого предела блокировать весь запуск, прекращать новые работы и сохранять активные роли и внешние операции до однозначного результата. Успешные третий раунд и пятый цикл сами по себе не блокируют приёмку. Продолжение требует записанного решения пользователя с конечным новым лимитом; второй бюджет и остальные блокировки сохраняются.

### 6. Фиксировать проверенные результаты задач в Git

```yaml
sdd_record: task
id: TASK-task-commits
number: 6
covers: [AC-task-commit, AC-commit-recovery, AC-followup-commit]
depends_on: [TASK-repair-budgets]
status: pending
verification:
  - criteria: [AC-task-commit]
    test_description: "В настоящем временном Git-репозитории закоммитить только проверенные изменения задачи при наличии чужого индекса и правок в соседних участках; сравнить tree, TASK-ID и SHA, проверить отказ при неразделимом пересечении."
    location: skills/sdd-apply/tests/test_commits.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_commits.py -q"
  - criteria: [AC-commit-recovery]
    test_description: "Смоделировать ошибку Git и остановку после создания коммита до записи SHA; повторное продолжение находит ровно один результат либо блокируется при неоднозначности. Hook, меняющий кандидат, не позволяет принять прежние доказательства."
    location: skills/sdd-apply/tests/test_commits.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_commits.py -q"
  - criteria: [AC-followup-commit]
    test_description: "Обнаружить дефект после принятого коммита, исправить с новыми проверками и ревью; проверить дополнительный SHA, тот же TASK-ID и сохранение исходной истории."
    location: skills/sdd-apply/tests/test_commits.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_commits.py -q"
```

В scripts/lib/commits.py реализовать операции оркестратора с намерением коммита, ожидаемым родителем, составом кандидата и TASK-ID. Выделять только принадлежащие задаче файлы и участки; сохранять чужой индекс и рабочие изменения. Неоднозначную принадлежность блокировать.

Перед accepted сверять фактический SHA, родителя и содержимое с проверенным кандидатом. Ошибка Git сохраняет непринятую задачу. После сбоя между коммитом и JSON искать подтверждённый результат в истории без повторного коммита. Изменение hook при коммите отменяет применимость доказательства.

Последующее исправление принятой задачи проходит новый цикл проверок и ревью и создаёт дополнительный коммит с тем же TASK-ID. Сохранять исходную историю. Подключить Git-проверки к условиям состояния.

### 7. Выполнять задачи строго последовательно

```yaml
sdd_record: task
id: TASK-sequential-execution
number: 7
covers: [AC-continue-plan, AC-block-dependents, AC-sequential-default, AC-sequential-blocked-stop]
depends_on: [TASK-task-commits]
status: pending
verification:
  - criteria: [AC-continue-plan, AC-sequential-default]
    test_description: "Пройти план из нескольких независимых и зависимых задач; трасса должна показать один активный цикл до accepted с коммитом и автоматический запуск следующей задачи без нового разрешения."
    location: skills/sdd-apply/tests/test_sequential.py
    run:
      setup_required: "Подготовить согласованную фикстуру плана и свежий контекст оркестратора; пройти описанный сценарий с записью трассы и выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_sequential.py -q."
  - criteria: [AC-block-dependents, AC-sequential-blocked-stop]
    test_description: "Заблокировать текущую задачу с частичными правками при наличии независимой; проверить отказ запуска обеих следующих задач, сохранение файлов после перезапуска и продолжение исходной до приёмки."
    location: skills/sdd-apply/tests/test_sequential.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_sequential.py -q"
```

В scripts/lib/scheduler.py реализовать доступность задач по TASK-ID, depends_on, cannot_parallel_with и принятым результатам. В flows/execute-sequential.md описать цикл одной задачи до проверки, ревью, коммита и accepted. Запуск следующей доступной задачи продолжает исходное поручение без отдельного согласия.

При отсутствии явного параллельного запроса одновременно вести только одну задачу. Блокировка текущей останавливает весь последовательный запуск, включая независимые задачи. После восстановления продолжать ту же задачу с сохранёнными правками. Проверять ограничения при каждом событии, включая повторный вход в сессию.

### 8. Создавать и восстанавливать рабочие деревья задач

```yaml
sdd_record: task
id: TASK-worktree-lifecycle
number: 8
covers: [AC-task-worktree, AC-worktree-recovery]
depends_on: [TASK-task-commits]
status: pending
verification:
  - criteria: [AC-task-worktree]
    test_description: "Запустить две разрешённые независимые задачи в настоящем Git-репозитории; проверить detached HEAD, отдельные индексы, сохранённые SHA, отсутствие веток и коммитов исполнителей и разделение изменяемых тестовых ресурсов."
    location: skills/sdd-apply/tests/test_worktrees.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_worktrees.py -q"
  - criteria: [AC-worktree-recovery]
    test_description: "Прервать работу, затем сверить существующие деревья и материалы. Проверить сохранение непринятого результата и отказ очистки при живом писателе, неизвестном файле или пути вне рабочей области; подтверждённое принятое дерево удаляется без повторного коммита."
    location: skills/sdd-apply/tests/test_worktrees.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_worktrees.py -q"
```

В scripts/lib/worktrees.py реализовать зарегистрированные worktrees в detached HEAD от SHA с принятыми предшественниками. Хранить владельца, абсолютный путь, исходное состояние и ресурсы проверки. Исполнители оставляют изменения без создания веток и коммитов.

Разделять рабочие файлы, индексы, порты, базы и временные каталоги; при общем ресурсе последовательно выполнять конфликтующие проверки. При продолжении сверять записи с фактическими деревьями и сохранять незавершённую работу.

Удалять только дерево принятой задачи после подтверждения коммита, сохранённого пакета переноса и отсутствия активного писателя или неучтённых файлов. Проверять разрешённую рабочую область по абсолютному пути. Наличие исходных незакоммиченных правок задачи допустимо лишь при доказанном сохранении результата; неизвестные данные блокируют удаление.

### 9. Переносить изменения и восстанавливать внешние операции

```yaml
sdd_record: task
id: TASK-worktree-integration
number: 9
covers: [AC-worktree-integration, AC-scripted-effect-recovery]
depends_on: [TASK-worktree-lifecycle]
status: pending
verification:
  - criteria: [AC-worktree-integration]
    test_description: "Перенести в изменившуюся ветку набор новых, удалённых, переименованных и бинарных файлов; проверить полноту и сохранение ранее принятых изменений. Варианты с конфликтом и без него требуют независимой проверки интегрированного кандидата и подтверждённого коммита."
    location: skills/sdd-apply/tests/test_integration.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_integration.py -q"
  - criteria: [AC-scripted-effect-recovery]
    test_description: "Прервать процесс после переноса, после коммита и после записи JSON перед генерацией представления; продолжение восстанавливает один результат, не повторяет Git-эффект и блокирует неоднозначность, сохраняя работу."
    location: skills/sdd-apply/tests/test_integration.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_integration.py -q"
```

В scripts/lib/integration.py собирать через временный индекс бинарный патч и манифест всех принадлежащих задаче изменений: staged, unstaged, новые, удалённые, переименованные файлы и режимы. Игнорируемый нужный файл требует явного учёта. Неподдерживаемый тип изменения блокирует перенос.

Сохранить намерение, исходный HEAD ветки исполнения и хеш пакета. Переносить по одной задаче с учётом исходной версии; сохранять ранее принятую работу. Разрешение конфликта проходит независимую проверку интеграции и ревью затронутых контрактов в общем бюджете задачи. Подключить committing и приёмку после успеха.

После прерывания сверять намерение с Git и файлами, чтобы не повторять перенос или коммит. Ошибка производного представления после JSON требует его повторной генерации без отмены результата. Реализовать общий журнал внешних операций и точки восстановления, используемые генератором панели.

### 10. Подключить параллельный режим и изолировать инструкции

```yaml
sdd_record: task
id: TASK-execution-modes
number: 10
covers: [AC-isolated-work, AC-explicit-parallel, AC-mode-resume, AC-mode-instruction-isolation, AC-mode-shared-contracts, AC-mode-context-handoff]
depends_on: [TASK-sequential-execution, TASK-worktree-integration]
status: pending
verification:
  - criteria: [AC-isolated-work, AC-explicit-parallel, AC-mode-resume]
    test_description: "Проверить отсутствие запроса, явный запрос, его отмену, новый запуск и продолжение прежнего; автономность не включает parallel. Недоступный worktree даёт последовательное выполнение, а непринятые ранее начатые задачи препятствуют выдаче новых."
    location: skills/sdd-apply/tests/test_modes.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_modes.py -q"
  - criteria: [AC-mode-instruction-isolation, AC-mode-shared-contracts, AC-mode-context-handoff]
    test_description: "По трассам фактических чтений в свежих сессиях проверить отдельную загрузку sequential и parallel, общие контракты без чужого алгоритма, передачу смены режима свежему контексту и одного оркестратора. Недоступный свежий контекст сохраняет ограничение."
    location: skills/sdd-apply/tests/test_modes.py
    run:
      setup_required: "Подготовить свежие сессии для обоих режимов и смены режима, сохранить фактические чтения файлов и передачу управления; выполнить описанные случаи и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_modes.py -q."
```

Написать flows/execute-parallel.md и выбор сценария в SKILL.md. Режим определяется проверенным запросом пользователя для текущего исполнения. Сохранить запрос, отмену и область; новое исполнение по умолчанию последовательное. При недоступной изоляции до чтения сценария выбрать последовательный режим с объяснением.

Подключить scheduler к ограничениям параллельных задач, общих ресурсов и последовательной интеграции. Каждый сценарий загружает только свои инструкции. Общие схемы, роли и скрипты не содержат алгоритм другого режима. При смене уже загруженного режима передать управление свежему контексту, сохранив единственного владельца.

При возврате к последовательному режиму новые задачи ждут ранее начатые. Случай кандидата в worktree без разрешённого перехода после отмены parallel сохраняется для ручного разбора согласно USER-reject-mode-switch-worktree. План не добавляет автоматическое исправление отклонённого замечания.

### 11. Восстанавливать исполнение и возвращать изменения в sdd-spec

```yaml
sdd_record: task
id: TASK-resume-and-revision
number: 11
covers: [AC-spec-conflict, AC-revised-plan, AC-lost-executor, AC-resume-drift]
depends_on: [TASK-execution-modes]
status: pending
verification:
  - criteria: [AC-lost-executor, AC-resume-drift]
    test_description: "Прервать исполнителя с частичными изменениями и восстановить запуск без него; проверить сохранение файлов и передачу преемнику. Изменить нормативный файл и проверить запрет автоматического продолжения с точным расхождением."
    location: skills/sdd-apply/tests/test_resume.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_resume.py -q"
  - criteria: [AC-spec-conflict, AC-revised-plan]
    test_description: "На воспроизводимом конфликте контракта проверить материал возврата без правок specs/design/tasks; после нового согласованного комплекта и поручения проверить связанный запуск, пересмотр доказательств и сохранение истории и обоих бюджетов."
    location: skills/sdd-apply/tests/test_resume.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_resume.py -q"
```

В scripts/lib/resume.py и сценариях продолжения сверять основание, историю состояния, процессы, незавершённые работы, Git, снимки и доказательства. Потерянная роль не остаётся активной по старому статусу. Новый исполнитель получает выполненное, оставшиеся AC, решения и отвергнутые подходы.

При изменении нормативных байтов остановить работу на прежнем основании. Противоречие обязательному контракту сохранять с воспроизведением и затронутыми задачами для sdd-spec. Самостоятельно не менять согласованные документы.

Новый согласованный комплект создаёт связанный запуск. Пересмотреть применимость прежних результатов по AC, зависимостям и коду; сохранить историю, счётчики продолжаемых задач и действующее поручение. Совпадение TASK-ID не означает автоматическую приёмку.

### 12. Показывать прогресс из состояния исполнения

```yaml
sdd_record: task
id: TASK-progress-dashboard
number: 12
covers: [AC-dashboard-start, AC-dashboard-progress, AC-dashboard-snapshot, AC-dashboard-recovery, AC-dashboard-generated-data]
depends_on: [TASK-state-store]
status: pending
verification:
  - criteria: [AC-dashboard-start, AC-dashboard-progress]
    test_description: "В настоящем браузере открыть file:// до первой задачи, затем менять состояние через API и проверять обновление по таймеру без перезагрузки. Сопоставить все задачи, этапы доказательств, счётчики и SHA с JSON."
    location: skills/sdd-apply/tests/test_dashboard_browser.py
    run:
      setup_required: "Подготовить браузерный запуск изолированной панели через file:// с локальным Chrome/Chromium и сохранением снимков; выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_dashboard_browser.py -q. Проверить браузерные зависимости и зафиксировать конкретную команду и версию браузера."
  - criteria: [AC-dashboard-snapshot, AC-dashboard-recovery]
    test_description: "Открыть отдельный итоговый HTML без JS, прервать генерацию и восстановить её; проверить явную отметку снимка и время данных. Отдельно проверить запасной loopback-просмотр и остановку только принадлежащего запуску сервера."
    location: skills/sdd-apply/tests/test_dashboard_browser.py
    run:
      setup_required: "Подготовить браузерный запуск изолированной панели через file:// с локальным Chrome/Chromium и сохранением снимков; выполнить uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_dashboard_browser.py -q. Проверить браузерные зависимости и зафиксировать конкретную команду и версию браузера."
  - criteria: [AC-dashboard-generated-data]
    test_description: "Подать кавычки, HTML-фрагменты, старую revision и чужой run_id, прервать запись JS; проверить отсутствие исполнения текста, отказ замены свежих данных старыми и восстановление из неизменённого JSON."
    location: skills/sdd-apply/tests/test_dashboard.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_dashboard.py -q"
```

В scripts/lib/dashboard.py и собственных шаблонах пакета реализовать summary.md, dashboard-state.js и dashboard.html из state.json. Перед первой задачей создать панель со всем планом; показывать режим, TASK-ID, принятые задачи, этапы проверок, причины блокировки, оба бюджета, SHA и ссылки на логи.

Публиковать каждый производный файл атомарно с change_id, run_id и revision. HTML содержит встроенный снимок и каждые две секунды перечитывает соседний JS с защитой от кэша. Обновлять элементы без перезагрузки страницы, отбрасывать старую revision и чужой запуск. Сообщения выводить текстовыми узлами с корректной сериализацией.

Основной просмотр работает с диска без сервера. При недоступности данных показывать сохранённое время и состояние снимка. Добавить ограниченный запасной сервер на loopback; останавливать только процесс этого исполнения. Сбой панели не меняет состояние задач; повторная генерация восстанавливает представления.

### 13. Собрать исполняемый процесс и итоговую приёмку

```yaml
sdd_record: task
id: TASK-final-acceptance
number: 13
covers: [AC-final-test-run, AC-final-complete, AC-final-incomplete, AC-deterministic-operations]
depends_on: [TASK-resume-and-revision, TASK-progress-dashboard]
status: pending
verification:
  - criteria: [AC-final-test-run, AC-final-complete]
    test_description: "Пройти весь план в каждом режиме; свежий итоговый проверяющий запускает обязательные команды и общие сценарии на конечном HEAD. Сравнить подтверждённые AC, локальные коммиты, отчёт и итоговую панель; убедиться, что этапы доставки не запускаются."
    location: skills/sdd-apply/tests/test_end_to_end.py
    run:
      setup_required: "Подготовить реальные сквозные сценарии во временных Git-проектах со свежими ролями, сохранить трассы и исходные логи; выполнить описанный случай и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_end_to_end.py -q. Сравнение с исходным прогоном использует тот же хост и модель."
  - criteria: [AC-final-incomplete]
    test_description: "На итоговом HEAD воспроизвести неработающий или недоступный обязательный сценарий; получить частичный результат с AC и причиной, без completed."
    location: skills/sdd-apply/tests/test_end_to_end.py
    run:
      setup_required: "Подготовить реальные сквозные сценарии во временных Git-проектах со свежими ролями, сохранить трассы и исходные логи; выполнить описанный случай и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_end_to_end.py -q. Сравнение с исходным прогоном использует тот же хост и модель."
  - criteria: [AC-deterministic-operations]
    test_description: "По трассам сквозного запуска сопоставить все операции с вызовами скриптов и структурированными результатами; удалить обязательную операцию и проверить блокировку вместо ручного алгоритма. Проверить, что структурный результат не выдаётся за содержательное ревью."
    location: skills/sdd-apply/tests/test_end_to_end.py
    run:
      setup_required: "Подготовить реальные сквозные сценарии во временных Git-проектах со свежими ролями, сохранить трассы и исходные логи; выполнить описанный случай и uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_end_to_end.py -q. Сравнение с исходным прогоном использует тот же хост и модель."
```

В scripts/lib/finalize.py реализовать итоговую независимую проверку полного обязательного набора на конечном HEAD, сверку всех AC и коммитов. Сформировать полный или частичный результат с TASK-ID, SHA, доказательствами, невыполненными критериями и решениями по рекомендациям. Завершать процесс локальными коммитами без последующих этапов доставки.

Подключить все модули к scripts/execute.py, схемам и инструкциям ролей. Каждый алгоритм состояния, выбора задач, снимков, команд, Git, восстановления и представлений должен вызываться через проверяемую операцию скрипта. Недоступная обязательная операция блокирует шаг; ручная правка состояния не становится штатным обходом. Перед первым запуском задачи обязательно генерировать панель.

В той же задаче выполнить сквозные сценарии на временных Git-проектах и чистых сессиях: последовательный успех, разрешённый параллельный успех с интеграцией, ложный DONE, недоступная обязательная проверка и дефект итогового HEAD. Сравнить доступный поведенческий прогон с исходным запуском без скилла из первой задачи, сохранив одинаковый хост и модель. Это проверки собранного процесса, а не отдельный этап дописывания тестов модулей.

### 14. Подключить установку и проверить переносимость пакета

```yaml
sdd_record: task
id: TASK-portable-installation
number: 14
covers: [AC-clean-install, AC-uv-script-runtime, AC-uv-runtime-failures]
depends_on: [TASK-final-acceptance]
status: pending
verification:
  - criteria: [AC-clean-install, AC-uv-script-runtime]
    test_description: "Для каждой точки входа выполнить первый и повторный штатный запуск из исходной и установленной копий, стороннего cwd без Python-проекта и проекта с конфликтующими зависимостями; очистить только собственный временный кэш и проверить восстановление. Сравнить файлы потребителя и lock-файлы, осмотреть скрытое и игнорируемое содержимое обоих пакетов."
    location: skills/sdd-apply/tests/test_runtime.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_runtime.py -q"
  - criteria: [AC-uv-runtime-failures]
    test_description: "В изолированных копиях проверить явный offline с пустым кэшем, устаревший lock-файл и ограничения сети или записи; ожидаются точный отказ, отсутствие скачивания при offline и отсутствие автоматической перезаписи lock-файла."
    location: skills/sdd-apply/tests/test_runtime.py
    run:
      command: "uv run --locked --script skills/sdd-apply/scripts/test.py tests/test_runtime.py -q"
```

Завершить метаданные явного вызова и интеграцию skills/sdd-apply с принятым способом установки репозитория, обнаружением sdd-spec и адаптерами Codex/Claude Code. Подготовить инструкции установки и восстановления окружения. Проверить все поставляемые точки входа, а не только тестовый запускатель.

Применить runtime-правила sdd-skill-conductor: PEP 723, соседние lock-файлы, штатный uv run --locked --script, отключение байткода до локальных импортов и внешние кэши. На Windows использовать пользовательскую настройку uv-runtime/cache в системном temp. Сохранять отчёты отдельно от очищаемого кэша.

В отдельной установленной копии выполнить матрицу runtime, осмотреть скрытые и игнорируемые файлы исходного и установленного пакетов и включить lock-файлы в поставку. Существующие пользовательские данные сохранять. Обновить реестр пакетов и установочные описания в рамках этой задачи; установка не должна менять зависимости проекта-потребителя.

