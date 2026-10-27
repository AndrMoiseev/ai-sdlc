# Формат обсуждения и восстановления

Читай вместе с [общей основой](document-format.md) при обсуждении, записи
checkpoint и resume. При проверке сохранённых отчётов или USER-разрешений
добавь [формат ревью и согласований](document-format-review.md).

## State и вопросы

Сохраняй checkpoint двумя файлами: `state.yaml` — машинное состояние по
[шаблону](../../sdd-spec/templates/state.yaml), `state.md` — пояснения по
[шаблону](../../sdd-spec/templates/state.md), без frontmatter и машинных Q-записей.
Каждое машинное поле имеет один источник истины в YAML. Проза объясняет следующий
шаг, выполненную часть поручения, ограничения, основания и выбор пояснения/гуманизации.
Требования и design остаются в своих документах.

В `state.yaml` сохраняй общие поля schema_version: 1, document_type: state,
change_id, language; для refactoring добавь work_kind: refactoring.
Дополнительные поля: phase, awaiting, updated_at (quoted ISO UTC), document_links,
review_links, approval_refs. Phase: discovery/drafting/document_review/user_review/planning/plan_review/plan_approved.
Awaiting: none/clarification/review_consent/planning_command/final_approval.
Пути относительны изменению; approval_refs содержит ссылки USER-ID на согласования
и поручения, содержание и действительность которых проверяются в review/decisions.md.

Текущий флоу хранится в `flow`: explore/draft/revise/explain/review/user-review/plan/resume.
`next_question` — ID открытого вопроса из questions.md либо null, если вопросов нет.
`checks.structure`: not_run/passed/failed; `checks.freshness`: not_checked/current/stale/missing.
Freshness отражает наличие и актуальность проверяемых оснований: missing при
недостающих основаниях, иначе stale при устаревших, иначе current после сверки.
Статусы проверок — сохранённый итог, они не заменяют повторную проверку готовности
и согласований. Все перечисленные поля, включая flow, next_question и checks,
обязательны при чтении и записи; дополнительные поля не допускаются, кроме work_kind.

Поддерживается только пара `state.yaml` и `state.md`. Frontmatter и машинные
записи в `state.md` запрещены. Старый формат отклоняй без чтения его метаданных,
извлечения вопросов или миграции. Отсутствие YAML не разрешает использовать Markdown
как машинное состояние. Все Q-записи хранятся только в `questions.md`.
Пара считается сохранённой после записи и проверки обоих файлов. Неполную пару
восстанавливай по исходным документам; автоматически считать её согласованной нельзя.

Поврежденный state восстанавливается как черновик по документам и доступным проверенным решениям. Phase не подтверждает разрешения. Отмена или замена последним ответом пользователя прекращает старое поручение; наличие tasks не восстанавливает его.

## Журнал решений и вопросы

Машинный вид Q-записи — `sdd_record: question`; blocking — boolean,
status — open/resolved.

Журнал `decisions.md` в корне изменения — обычный Markdown по
[шаблону](../../sdd-spec/templates/discussion-decisions.md), без frontmatter, sdd_record и
новых ID. Устойчивые заголовки связывают авторство предложения, статус, автора
принятия и основание с вопросами и нормативными документами. Этот журнал
не заменяет USER-записи в `review/decisions.md`.

`questions.md` имеет ровно общие поля frontmatter: schema_version: 1,
document_type: questions, change_id и language. Каждая Q-запись содержит text,
blocking и status; открытая неблокирующая требует reason и return_at.
Для status: resolved обязательно resolution — непустая строка с относительным
путём от каталога изменения к существующему файлу основания, при наличии `#`
якорь должен быть непустым. Например, `decisions.md#режим-выполнения`.
Путь остаётся внутри изменения; внешний источник сначала зафиксируй
в локальном исследовании со ссылкой и результатом проверки. Скрипт проверяет
файл и форму ссылки; наличие якоря и смысл основания проверяет агент.
Каждый Q-ID уникален в `questions.md`; закрытый вопрос всегда требует resolution.
Восстановление обсуждения выполняй по [discussion](../../sdd-spec/references/discussion.md).

## Премортем

`premortem.md` в каталоге изменения хранит исследование по
[контракту премортема](../../sdd-spec/references/premortem.md); создавай его только при находках по
[шаблону](../../sdd-spec/templates/premortem.md). Это обычный Markdown без frontmatter,
нового document_type, sdd_record или вида USER. Заголовки находок служат
якорями; вопросы используют Q-ID в questions.md, а не FIND ревью.

Раздел «Премортем» в state.md содержит краткий итог: отсутствие находок либо
наличие находок со ссылкой на документ. Закрытые находки и ссылка сохраняются.
Разбор не входит в манифест documents или plan. Выбранные изменения цели,
поведения и подхода переноси в proposal, specs с AC и design; после нормативной
правки действуют обычные правила актуальности ревью и согласований.
Завершение проверки не заменяет условия перехода к плану.
