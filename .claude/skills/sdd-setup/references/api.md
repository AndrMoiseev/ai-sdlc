# Скриптовый интерфейс

Все команды используют `uv run --locked --script "<skill-root>/scripts/setup.py"`.
Ответ — JSON `{"ok": true, "result": ...}` либо `{"ok": false, "code": "sdd_setup",
"message": ...}` с ненулевым exit code. В файлы для следующей операции сохраняй
объект `result`, без внешней оболочки. JSON читается как UTF-8, включая BOM.

## inspect — только чтение

```text
uv run --locked --script "<skill-root>/scripts/setup.py" inspect --project-root "<project>" --host codex
uv run --locked --script "<skill-root>/scripts/setup.py" inspect --project-root "<project>" --host claude-code --available-agents "<workspace>/catalog.json"
```

Необязательные параметры: `--sdd-spec <skill-root>`, `--user-agent-dir <path>`
(для отдельного пользовательского каталога/тестов), `--names <name> <name>`
(выбранные пользователем имена вне текущих настроек и пресетов).

Результат содержит `roles` с `present`, `current`, `default`, `profile_default`;
`agents` с текущими моделью, effort, областью и путём; `inputs`, `evidence`,
`snapshot`. Сохрани результат целиком. Ошибки JSON/TOML/YAML и дубликаты имён
не трактуются как отсутствие конфигурации. Пустой каталог допустим.

## plan — только чтение

Запиши request в отдельном рабочем каталоге:

```json
{
  "inspection": "ЗАМЕНИТЬ целым объектом result из inspect",
  "roles": {
    "sdd-spec.document_reviewer": {"action": "default"},
    "sdd-spec.plan_reviewer": {"action": "default"},
    "sdd-spec.editor": {"action": "default"},
    "sdd-spec.editorial_reviewer": {"action": "default"},
    "sdd-apply.executor": {"action": "default"},
    "sdd-apply.verifier": {"action": "default"},
    "sdd-apply.reviewer": {"action": "default"},
    "sdd-apply.final_verifier": {"action": "default"}
  },
  "agents": {
    "sdd-document-reviewer": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-plan-reviewer": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-editor": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-editorial-reviewer": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-executor": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-verifier": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-reviewer": {"model": {"action": "default"}, "effort": {"action": "default"}},
    "sdd-final-verifier": {"model": {"action": "default"}, "effort": {"action": "default"}}
  }
}
```

Это пример формы после согласия на пресеты, не разрешение применять их без
диалога. Для всех восьми ролей требуется решение; для каждого уникального
выбранного имени — решения по модели и effort.

| Решение | Значение |
| --- | --- |
| `{"action":"keep"}` | Сохранить заданное значение; для отсутствующего поля отклоняется |
| `{"action":"default"}` | Принять пресет роли в текущей среде |
| `{"action":"set","value":"..."}` | Выбранное пользователем имя/модель/effort |
| `{"action":"set","value":null}` | Убрать сопоставление роли или явное поле модели/effort |

Для имени только из нативного каталога Claude Code допустим лишь `keep` обоих
полей: их значения скрыты, сохраняется определение целиком. При разных пресетах
ролей одного агента выбирай явные `set`, либо раздели имена.

```text
uv run --locked --script "<skill-root>/scripts/setup.py" plan --request "<workspace>/request.json"
```

Результат содержит `operations` с путями, исходными текстами, новым содержимым,
хэшами и diff; `selected_roles`, предупреждения и `plan_id`. Сохрани result в
`plan.json`. Скрипт сравнивает переданный inspection с новым чтением; при
изменившихся данных нужно повторить inspect, а не редактировать хэши.

## apply — запись

```text
uv run --locked --script "<skill-root>/scripts/setup.py" apply --plan "<workspace>/plan.json"
```

Скрипт пересчитывает план, проверяет пути и исходное содержимое, блокирует
параллельный setup через `.sdd/.setup.lock`, записывает определения перед settings,
затем проверяет хэши. Отдельные файлы заменяются атомарно. При обычной ошибке
записи уже сделанные изменения откатываются, если их не изменил другой процесс.
Пустые созданные каталоги могут остаться. Произвольная правка плана отклоняется.

Это не транзакция файловой системы: аварийное завершение процесса/питания может
оставить часть записей и lock. Проверь PID и текущее содержимое, восстанови
данные из сохранённого плана, затем повтори inspect; не удаляй lock активного
процесса. Скрипт не защищает от всех одновременных изменений сторонним редактором.

При успехе `changed` перечисляет записанные пути. Пустой список означает, что
файлы не переписывались. После apply повтори inspect. Для отсутствующих полей,
которые пользователь решил наследовать, повторное решение — `set: null`.

Поддерживаемые параметры среды: model/effort определений. Неизвестные верхние
поля settings сохраняются; неизвестные поля внутри subagents отклоняет общий
контракт `sdd-spec`. Версия схемы фиксирована, миграции других версий не выполняются.
