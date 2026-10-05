# Локальные проверки пояснений

Пользователь выбрал только локальные проверки. Парные прогоны старой/новой
версий, micro repetitions, LLM grading и benchmark не выполнялись. Ранее
завершённый CLI smoke проверял только окружение; он не является оценкой навыка.

Старая полная копия до правок и SHA256-манифест:
`C:/Users/Andrew/AppData/Local/Temp/sdd-spec-explanatory-evals-caafff7c123f4f4b8dbd3e7402072026/old_skill/`
и соседний `old-manifest.json`. В том же внешнем каталоге находятся
`smoke/`, `smoke-escalated/`, `archify-probe/` и первоначальный preflight-report.md.
Секреты не копировались. Исходный smoke занял 36.609 секунды, 34063 токена по
метрикам CLI; subsequent behavioral payload отклонён auto-review до исполнения.
После выбора пользователя внешние LLM-запуски не возобновлялись.

## Подготовленные входы

`prepare-fixtures.py` создаёт базовый комплект proposal/design/orders/refunds/state
и девять отдельных входов из evals.json в `fixtures/`. Контрольные хеши лежат
в `fixtures/base-inputs.sha256.json`; prompts и критерии разделены между fixtures
и `prepared/`. Это базовые входы: варианты browser failure, stale receipts,
согласований и многошаговые ответы требуют подготовки по evals/manual.md.
Их наличие не означает выполнения сценария. Запуск скрипта не вызывает LLM.

## Реальный Archify

Использован установленный `.agents/skills/archify`, версия 3.0.1, Node 24.19.0
и `C:/Program Files/Google/Chrome/Application/chrome.exe`. Системный sandbox
блокировал spawn EPERM; локальные команды запускались с разрешённой эскалацией.
Это ограничение запуска процесса, не отсутствие браузера.

Синтетические кандидаты находятся в
`markers/sdd/changes/sample-change/archify/{architecture,workflow,sequence}/`.
Они созданы ведущим проверки для проверки отображения, а не независимым
исполнителем sdd-spec. Для каждого выполнены реальные finalize и visual-check:

```text
node <archify>/bin/archify.mjs finalize <type> candidate.json diagram.html --quality showcase --out-dir <review-dir> --json
node <archify>/bin/archify.mjs visual-check diagram.html --out-dir <capture-dir> --summary --require-provenance
```

| Тип | Текущий finalize | Текущие captures | Результат |
|---|---|---|---|
| architecture | review-3/diagram.finalize-summary.json | visual-check-3/ | validate/deliver/check/browser-check pass; capture pass |
| workflow | review-4/diagram.finalize-summary.json | visual-check-3/ | validate/deliver/check/browser-check pass; capture pass |
| sequence | review-3/diagram.finalize-summary.json | visual-check-3/ | validate/deliver/check/browser-check pass; capture pass |

Receipts привязаны к SHA256 текущего HTML. Прежние review/capture каталоги сохранены
как история и не считаются актуальными для изменённого HTML.

## Осмотр и найденное ограничение

Фактически осмотрены light/dark PNG 1440x900 всех трёх типов из текущих каталогов
таблицы; также осмотрены предыдущие 1440x900 пары. Файлы называются
`diagram.visual-check.1440x900.light.png` и `diagram.visual-check.1440x900.dark.png`.
2048x1320 captures созданы браузером, но отдельно не осмотрены.

В версии review-2 у architecture/workflow поле tag присутствовало в JSON,
но отсутствовало на default read-view PNG. Автоматические gates при этом прошли.
После сохранения tag и дублирования маркера в sublabel исходные PNG показывают
статус без наведения или переключения режима. Это конкретное основание для
условного fallback в инструкции навыка.

- Architecture: `[=]` на обоих прежних API/Payment Service независимо от новой
  связи `[+] keyed refund`; прежняя `[=] POST order` и изменённая `[~] insert if
  new key` видны. Подписи назначения сохранены. Обрезания не обнаружено.
- Workflow: видны `[=]` прежний Request, `[+]` Check key, `[~]` Reply и независимые
  метки переходов. В BEFORE видны удалённые `[-]` узлы и связь. Полный AFTER
  для самого удалённого retry не изображён: объяснение 410 в карточке не
  заменяет такую проверку, этот аспект остаётся непроверенным.
- Sequence: в прежнем visual-check-2 карточка с расшифровкой `[=]/[+]/[~]`
  оказалась за нижним краем превью. В review-3 символы заменены полными
  статусами «Без изменений», «Новый», «Изменён» в sublabel и label.
  Повторно осмотренные light/dark 1440x900 показывают их полностью без обрезания;
  расшифровка из невидимой карточки теперь не нужна. Прежний API отправляет
  `Изменён: 200 same order`. Возврат отличим от прямого сообщения,
  `Новый: async OrderCreated` имеет самостоятельную подпись. `note` хранится в JSON,
  но его текст не виден в default PNG; существенные условия должны оставаться
  в видимой подписи/пояснении. Маркер сообщения не зависит от note.

Подписи связей architecture/workflow относительно мелкие и малоконтрастные,
но читаются на осмотренных исходных 1440 PNG. При уменьшении превью требуется
отдельный осмотр; общей гарантии читаемости миниатюр нет. Sequence после spread
использует ширину и читается заметно лучше первоначальной версии.

Ни один из этих локальных результатов не доказывает, что независимый агент
следует новым инструкциям, правильно возобновляет handoff, сохраняет отказ,
повторно использует PNG или обнаруживает stale manifest. Эти проверки
пропущены по выбранному пользователем ограничению.
