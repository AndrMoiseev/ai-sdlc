---
schema_version: 1
document_type: spec
change_id: sdd-explorer
language: ru
capability: sdd-execution
---
# Запуск проверок и содержательная приёмка

Принятое распределение ответственности: [журнал](../../decisions.md#принятое-направление). Конкретные REQ/AC и дизайн согласованы [пользователем](../../decisions.md#согласование-документов-и-ревью-плана); план после ревью утверждён [без перехода к реализации](../../decisions.md#план-утверждён-без-запуска-реализации). Evidence-source означает отсутствие выделенного актуального baseline; исторический change не подменяет текущее поведение кода.

## 6. Исполнение обязательных проверок

```yaml
sdd_record: requirement
id: REQ-independent-verification
operation: modify
source:
  kind: evidence
  baseline_missing: true
  references:
    - skills/sdd-apply/scripts/lib/verification.py
    - skills/sdd-apply/scripts/lib/final_checks.py
    - skills/sdd-apply/references/api-checks.md
    - skills/sdd-apply/scripts/lib/budgets.py
  observed: Запуски привязаны к executor и проверяющим ролям; сохраняются реестр, basis, логи и бюджеты, отдельного типизированного заключения verifier нет
  assumptions: Историческая спецификация sdd-execution-skill не является актуальным baseline после последующих изменений runtime
```

Оркестратор до реализации сохраняет полный обязательный набор из плана, инструкций проекта и CI. Все детерминированные тесты, линтеры, сборки, валидаторы и процедуры baseline/self/independent/integration/final выполняет explorer через существующий engine. Исполнитель реализует и исправляет код; verifier и reviewer запрашивают запуски и оценивают доказательства. Прямое исполнение детерминированных проверок этими ролями не даёт допустимого доказательства нового контракта.

Сохраняются: clean/frozen источники, остановка авторов, привязка к commit/document/configuration/registry, полнота набора, неизменность зарегистрированной команды, доступность location и история попыток. Self не разрешает приёмку. Independent/integration требуют нового фактического запуска независимым от автора explorer; контекст explorer той же задачи можно продолжить. Обязательный failed/unavailable/stale/missing результат блокирует приёмку независимо от текста summary.

Setup_required до подготовки обозначает planned_absence, не успех и не расход repair budget. Существующие проверки выполняются отдельно. После согласованной подготовки конкретная команда сохраняется и становится обязательной, tasks не переписывается; выход за объём возвращается в sdd-spec. После изменений повторяется затронутый набор, при неизвестной области влияния полный обязательный набор.

Сохраняются текущие task-lifetime test/review budgets, reservations и правила повторов. Исходное падение не расходует repair cycle, повтор после падения без правок требует его резервирования; повтор того же события не расходует второй цикл. Новая роль, стадия, сессия или план не обнуляют расход. Недоступность не превращается в success и не запускает автоматические неизменённые повторы. Ограничение времени относится ко всему назначенному набору, включая подготовку и дочерние процессы.

### Матрица ролей и стадий

```yaml
sdd_record: acceptance
id: AC-explorer-check-stages
requirement: REQ-independent-verification
conditions: Запрашивается детерминированная проверка на каждой из пяти стадий с подходящим scope и ролью либо со старой ролью executor/verifier/reviewer/final_verifier
expected: Только реально зарегистрированный explorer нужной стадии и scope запускает полный набор; неверные роль, свежесть, task/run scope или состояние отвергаются до запуска процесса
```

### Сохранение доказательств и подготовки

```yaml
sdd_record: acceptance
id: AC-check-evidence-invariants
requirement: REQ-independent-verification
conditions: Применимы setup_required, отсутствующий location, изменённый registry или входы, падение обязательной команды либо успешный self
expected: Сохраняются исходные сведения и все попытки; planned_absence допускается только до согласованной подготовки, ошибки и stale/missing evidence блокируют приёмку, self не заменяет независимый запуск
```

### Процедуры и поведенческие оценки

```yaml
sdd_record: acceptance
id: AC-check-procedure-boundary
requirement: REQ-independent-verification
conditions: Зарегистрированы deterministic, manual и behavioral процедуры, включая команду запуска агентской оценки, либо процедура без обязательного явного типа
expected: Deterministic исполняет explorer; смысловые процедуры аттестует проверяющая роль с отдельными ссылками на инструментальные результаты; behavioral скилла выполняется только в final; отсутствие обязательного типа отклоняется валидацией
```

### Бюджеты и ограничение времени

```yaml
sdd_record: acceptance
id: AC-check-budget-preservation
requirement: REQ-independent-verification
conditions: После падения меняется explorer, повторяется событие или исчерпывается общий deadline набора
expected: Повтор идентичного события не дублирует запуск, новый повтор подчинён прежнему repair budget; смена агента не сбрасывает счётчики и deadline; превышение прекращает дерево процессов и работу согласно проектным правилам
```

## 7. Компактный результат с первичными данными

```yaml
sdd_record: requirement
id: REQ-check-summary
operation: add
```

Каждый запуск сохраняет полные stdout/stderr и поддерживаемые structured reports, идентичность и условия исполнения. Машинная сводка перечисляет все назначенные и фактически полученные результаты, outcome, exit code, duration, skips и ограничения с references/digests. Агентская диагностика отделена от этих полей. Полные логи не загружаются автоматически в ответ. Неизвестные метрики сохраняются как null, отсутствие результата не считается нулём ошибок. Парсинг не меняет фактический exit code.

Explorer передаёт оркестратору ссылки на сохранённый запуск и summary. Оркестратор включает их в поручение независимому verifier вместе со scope, stage, basis и registry revision. Verifier читает сводку и исходные критерии, реализацию и тесты; необходимые подробности получает по ссылкам на первичные артефакты без повторного запуска команды. Пересказ explorer и завершение его роли не заменяют сохранённое доказательство. Для final применяется тот же порядок с final_verifier. Подробности передачи описаны в [дизайне](../../design.md#передача-результата-от-explorer-к-verifier).

### Успех, многословная ошибка и неизвестные показатели

```yaml
sdd_record: acceptance
id: AC-check-summary-content
requirement: REQ-check-summary
conditions: Команда проходит, падает с большим логом, завершается timeout либо не предоставляет машиночитаемого числа тестов
expected: Summary сохраняет command/cwd/configuration, basis, stage, duration, exit code или null, outcome/limitation и ссылки с digest; verifier получает идентичность запуска и summary через оркестратора, нужный полный лог читает по ссылке без повторного исполнения; excerpt ограничен и обозначает обрезку, неизвестные counts равны null
```

### Пропуски при нулевом коде выхода

```yaml
sdd_record: acceptance
id: AC-check-summary-skips
requirement: REQ-check-summary
conditions: Pytest JUnit сообщает восемь skips при exit 0 либо заявленный обязательный structured report отсутствует или повреждён
expected: Summary явно сохраняет skips либо неполноту evidence и ошибку разбора; не объявляет все тесты выполненными, verifier устанавливает обязательность пропусков и не принимает неподтверждённые AC
```

### Невозможность подменить доказательство пересказом

```yaml
sdd_record: acceptance
id: AC-check-summary-integrity
requirement: REQ-check-summary
conditions: Текст explorer утверждает успех при failed/missing evidence либо summary ссылается на изменённый, чужой или недоступный raw artifact
expected: Машинные результаты не меняются от diagnosis; несовпадение references/digests/basis блокирует использование, API возвращает конкретную неполноту и не принимает задачу
```

## 8. Отдельное содержательное заключение

```yaml
sdd_record: requirement
id: REQ-verification-result
operation: add
```

Verifier независимо сопоставляет требования, реализацию, исходники тестов и точные доказательства. Заключение содержит результат по каждому применимому критерию, основания, пробелы, references, stage и basis. Его нельзя заменить кодом выхода, role_result, заключением explorer или общим reviewer verdict. Допуск к ревью, передаче, коммиту и приёмке требует успешного обязательного запуска и актуального passed заключения. После интеграции заключение получается заново.

При неподтверждённом AC verifier может запросить дополнительную проверку в своём failed/unavailable заключении. Для independent/integration оркестратор вправе расширить реестр по этому актуальному заключению до допуска к ревью, без предварительного reviewer more_checks. Добавления относятся к критериям той же задачи и не заменяют прежние обязательства. Изменение реестра требует нового полного запуска explorer и нового заключения verifier; прежний passed не переносится. Запрос без фактического падения не расходует test-repair cycle и не требует review round; действующие бюджеты и путь reviewer more_checks сохраняются. Изменение самих требований по-прежнему возвращается в sdd-spec. [Решение пользователя](../../decisions.md#расширение-проверок-и-передача-результата).

### Два необходимых результата

```yaml
sdd_record: acceptance
id: AC-verification-dual-gate
requirement: REQ-verification-result
conditions: Есть только passed команды, только положительное заключение, неполные критерии либо оба актуальных результата independent/integration
expected: Первые варианты не допускают review_start, transfer, commit и accept; последняя комбинация проходит этот gate при выполнении остальных существующих условий, self и role_result его не заменяют
```

### Содержательный пробел и актуальность

```yaml
sdd_record: acceptance
id: AC-verification-gaps
requirement: REQ-verification-result
conditions: В independent/integration тесты зелёные, но для AC нужна новая проверка в реестре, либо после заключения изменились код, нормативное основание, конфигурация, реестр или применимая попытка
expected: Актуальное failed/unavailable заключение verifier с конкретным запросом разрешает оркестратору checks_extend до review_start без reviewer verdict; чужое, устаревшее или passed заключение не разрешает этот путь; прежние проверки и бюджеты сохраняются, новый полный запуск explorer и новое passed заключение требуются до допуска к ревью, фиктивное падение теста и расход review round не создаются
```

## 9. Финальная приёмка

```yaml
sdd_record: requirement
id: REQ-final-acceptance
operation: modify
source:
  kind: evidence
  baseline_missing: true
  references:
    - skills/sdd-apply/scripts/lib/finalize.py
    - skills/sdd-apply/scripts/lib/final_checks.py
    - skills/sdd-apply/references/api-checks.md
  observed: Finalize использует свежие final-verifier command/procedure evidence для task и run scope; refactoring имеет whole union, ordinary может иметь дополнительные project checks
  assumptions: Наборы обязательств сохраняются, меняется исполнитель команд и добавляется отдельное проверяемое заключение
```

После принятия и интеграции задач свежий explorer исполняет полный применимый final набор на актуальном clean HEAD. Отдельный свежий final_verifier оценивает весь обязательный результат. Ordinary task final и дополнительные run-level project checks сохраняются раздельно; refactoring использует подтверждённый union whole/task/project checks и применимые persistent criteria. Подтверждённые retired checks остаются историей. Успех всех задач или прежний лог не заменяют новую финальную пару.

Complete требует актуального запуска и заключения по всем обязательным критериям на одном basis. Отчёт и dashboard содержат TASK-ID/SHA, evidence и заключения, ограничения и решения по рекомендациям. Неполный результат остаётся partial с конкретными AC и следующим действием. Локальные коммиты остаются результатом исполнения; push/PR/merge/publish/sync/archive не добавляются.

### Полнота итогового набора

```yaml
sdd_record: acceptance
id: AC-final-explorer-pair
requirement: REQ-final-acceptance
conditions: Завершается ordinary change с task checks и дополнительными project checks либо refactoring с whole union и retired checks
expected: Каждый применимый набор получает свежий explorer run и отдельное final_verifier заключение на том же итоговом basis; retired checks сохраняют историю; только полная успешная пара позволяет complete
```

### Отрицательный финальный результат

```yaml
sdd_record: acceptance
id: AC-final-incomplete-evidence
requirement: REQ-final-acceptance
conditions: Финальный запуск неуспешен, устарел, неполон, использует старый лог либо отсутствует или отрицательно новое заключение
expected: Finalize возвращает partial и неподтверждённые критерии; ремонт назначается владельцу с прежним budget, новая проверка после ремонта выполняется на новом basis без скрытого повторного использования прежнего pass
```

## 10. Восстановление и представления состояния

```yaml
sdd_record: requirement
id: REQ-explorer-recovery
operation: add
```

Поручение explorer входит в существующую role registration, ответ исследования сохраняется через role_result; новые lifecycle и события исследования не требуются. Null task research допустим до final registry. Потерянный explorer восстанавливается обычным механизмом роли; незавершённая работа не считается выполненной, процедуры сохраняются abandoned. Повтор события использует существующую идемпотентность. Прогресс показывает execution evidence и verification conclusion раздельно.

Новый контракт применяется напрямую при текущих номерах версий. Обратная совместимость и миграция старых executions не требуются [по решению пользователя](../../decisions.md#без-обратной-совместимости). Старые артефакты автоматически не переписываются и не удаляются. Восстановление исполнений нового контракта сохраняет историю, бюджеты и обязательства; положительные заключения не синтезируются из логов.

### Потеря роли и пересмотр плана

```yaml
sdd_record: acceptance
id: AC-explorer-resume
requirement: REQ-explorer-recovery
conditions: Теряется task/run explorer во время процедуры или поступает revised_plan
expected: Resume сохраняет фактические роли, evidence, pending/confirmed registry и budgets; abandoned попытка не считается passed, successor начинает новую; revised_plan сохраняет обязательства и историю, но не переносит актуальность старых заключений
```

### Наблюдаемость

```yaml
sdd_record: acceptance
id: AC-explorer-visibility
requirement: REQ-explorer-recovery
conditions: Пользователь читает compact/dashboard, а sdd-sync получает завершённый результат через apply read
expected: Видны scope/stage/status поручения и отдельные статусы запуска/заключения без полных логов; sdd-sync проверяет оба доказательства по новому контракту
```
