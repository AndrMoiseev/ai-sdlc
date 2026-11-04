# Проверка сохранения исследования

Поручения `save-check-01` и `save-check-02` выполнил `sdd-spec.explorer`, context_id `/root/save_discussion_check`. Профиль выбран resolver: `sdd-explorer`, `gpt-6.1-terra`, `high`. Первый запуск использовал свежий контекст, повтор продолжил его с теми же областью и профилем. Фактические effective model/effort не наблюдались. Поле developer_instructions определения не импортировалось; инструкция роли передана явно. Запись разрешалась только во внешние outputs.

## Область и результат

Проверены `state.yaml`/`state.md`, `questions.md`, `review/decisions.md`, наличие файлов по ссылкам и точность копирования `research.md`. Временный скрипт вызывает существующие `sdd_shared.documents.read_checkpoint` и `sdd_shared.reviews.review_status`, затем сверяет исходный SHA-256 отчёта и сохранность входов. Это проверка записей обсуждения; proposal/design/specs/tasks не создавались и полный documents/plan-check не выполнялся. Машинный `checks.structure` поэтому остаётся `not_run` для нормативного комплекта.

- Первый запуск: 0,8339006 секунды, stdout без структурных ошибок; PowerShell потерял код завершения. Фактический статус `unknown`, успешным запуск не объявлялся.
- Повтор по новому поручению: прямой вызов uv с немедленным захватом кода завершения. Код 0, время 0,7807336 секунды; `errors: []`, `warnings: []`, хэши входов до и после совпадают.
- Суммарное время двух команд: 1,6146342 секунды. Тесты и эвалы скиллов не запускались; неизвестные счётчики не подменялись нулём.
- Сохранены ровно три открытых блокирующих вопроса; document approval отсутствует. Исследование не объявлено согласованным или готовым к реализации.
- stderr второго запуска содержит штатное сообщение uv об установке трёх пакетов, отображённое PowerShell как NativeCommandError; фактический код uv равен 0. Содержимое исходных журналов не редактировалось.

Команда успешного запуска, cwd `C:/Users/Andrew/repos/ai-sdlc`:

```text
uv run --python "C:/Program Files/Python314/python.exe" --locked --script "C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/validate-discussion.py"
```

В каждом shell использованы общий UV_CACHE_DIR/UV_TOOL_DIR и PYTHONDONTWRITEBYTECODE=1 из state.md. Скрипт и lock находятся вне проекта и коллекций скиллов; зависимости совпадают со штатным shared check.py. Доступ к Temp выполнен через штатное расширение после ранее подтверждённого ограничения песочницы. Протоколы роли, raw stdout/stderr и обе версии результата сохранены отдельно.

Журнал в этом файле заполнен после получения результата; он не входит в проверяемые входы. Проверенные документы после запуска не менялись. Оркестратор отдельно сверил происхождение решений, точные ответы пользователя, область изменений и этот журнал. Проверка не заменяет независимое содержательное ревью.

## Проверенные входы

Исходный Git commit: `4b65ee0daa408696fdef25f2131de2dd6d4a769e`.

| Файл | SHA-256 |
|---|---|
| `state.yaml` | `c520d5c12bb8e694fd0d89a09ee3c512e0822f8ee58cdcf4be063d49c3b1c421` |
| `state.md` | `19780557396f3841a8d09ad564a462e2c7a591ac10b6fc860b287e0baba51fb3` |
| `questions.md` | `d9e65cb4a4aad4330bf5e68e8943efc0b0d7dcd5c108313e692ce5c687864515` |
| `review/decisions.md` | `f5a097c6e923bd4fa2160eb2fa903e6a5a7fc75e08109be6c661bcf5a471702d` |
| `research.md` | `5ddda6a840747409408429622ce94c04750ff392450afcfb77bc8572a31b7136` |

## Внешние свидетельства

| Абсолютный путь | SHA-256 |
|---|---|
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/launch.json` | `0494c2fbf030100ee5342704d38209c3ff1ae6e7b35f35a7d64d8a4b4a1b9519` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/request.json` | `c8e2f1e68dbd3f0317ad4481b1a14bea5e936c7ef06cc60c1cc0ef2f49fd8ea4` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/result.json` | `af6fe4a7cfe8cc558ab6c82bc9fbd81bfc6571c547587fd101b239bfebd45f41` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/selection.json` | `3644faebbc9109d2c3dc726c38051a7768c7894e8be078b6683a6537b4016b90` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/stderr.txt` | `9dd033554f26ee764c974fbf9e7a025fa0f7ee27618c0331c985a58e992a33ef` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/stdout.txt` | `d9c06a552474ea8fd4787ab163313fab86e5fda2ad4b3ba6b1fd687882c043b7` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/validate-discussion.py` | `b7808ba2f43c1c6c94e5f1c51b87e92915d6d5d77842679081f2b0acc43a9de3` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-01/validate-discussion.py.lock` | `8422fa7a6eccab5207463b53515e33bb333eea1b70e3fe9e9e383949977ad984` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/launch.json` | `81d6383cc35bb3085bc85e53d2f1497744b1384833d49ae2b9598cc0124ec9f7` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/request.json` | `601278b49f1e0fa2b38e6e767c20c7f32412f8a2051ba7862cbf26e01cdb6471` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/result.json` | `451b68227460631bbc8189081a57e5506c10e1d31fea0c2246377891d25518bc` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/stderr.txt` | `cfed02d87665dfb0fc85f7503798c4e8f848afa2e3e9c753608fa1d9b1720b52` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/stdout.txt` | `148f4f248b2d5a4b43f773c675136f50ba1a01cd97afcd927f6cdb6fdb769bce` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/validate-discussion.py` | `b7808ba2f43c1c6c94e5f1c51b87e92915d6d5d77842679081f2b0acc43a9de3` |
| `C:/Users/Andrew/AppData/Local/Temp/sdd-simple-task-8cn5g_00/save-check-02/validate-discussion.py.lock` | `8422fa7a6eccab5207463b53515e33bb333eea1b70e3fe9e9e383949977ad984` |
