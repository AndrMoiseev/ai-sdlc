# Локальная проверка пакета, 2026-10-02

Проверены переносимая копия, структура, чистота пакетов и механика сохранения
согласования. Внешние LLM, поведенческие прогоны и браузер не запускались.
Полные команды, exit codes, длительности, хеши и результаты находятся
в [package-validation.json](package-validation.json). Сценарий воспроизводится
скриптом [validate-local-package.py](validate-local-package.py).

## Переносимость и регрессия

Полный пакет скопирован в
`C:/Users/Andrew/AppData/Local/Temp/sdd-spec-portability-mcsi5ylx/installed/sdd-spec`.
Рабочий каталог всех проверок:
`C:/Users/Andrew/AppData/Local/Temp/sdd-spec-portability-mcsi5ylx/external-cwd`.

Команда `python <copy>/scripts/run.py test`: **131 passed, 1 skipped**, exit 0,
pytest сообщил 8.12 секунды. Вывод сохранён в
[package-copy-tests.stdout.txt](package-copy-tests.stdout.txt).
После окончательной редактуры синхронизированы references/explanation.md,
templates/preview-handoff.md, flows/revise.md и evals/manual.md. После freeze
от 2026-10-02 окончательная проверка завершилась в 16:38:48 UTC:
`python <copy>/scripts/run.py test -k package_contract` дал **5 passed,
127 deselected** за 0.16 секунды; результаты
в [package-copy-contract-final.stdout.txt](package-copy-contract-final.stdout.txt).
На момент завершения хеши всех файлов исходного и перенесённого пакетов совпали.

Штатный launcher сам выбрал внешний runtime-каталог
`C:/Users/Andrew/AppData/Local/ai-sdlc/sdd-spec/e8434f067026c784`;
ручная настройка окружения внутри пакета не применялась. Первая попытка
создать внешний cwd была ограничена sandbox. Локальный повтор с разрешённой
эскалацией выполнен успешно; отказа автоматической проверки разрешений не было.

Новые flow, reference и оба template прочитаны именно из перенесённой копии.
Ссылки на необходимые ресурсы разрешаются внутри неё; авторских абсолютных
путей в этих файлах нет. Три ссылки `archify/...` в шаблоне explanation.md
находятся в примерах будущего вывода: эти PNG/HTML не должны входить в пакет.
Проверка подтверждает независимость путей ресурсов, а не изоляцию ОС
от исходного каталога.

## Структура и чистота

Выполнено `uv run <conductor>/scripts/eval_skill.py <copy> --json` с внешними
UV_CACHE_DIR/PYTHONPYCACHEPREFIX. Первая попытка завершилась UnicodeDecodeError
из-за cp1251; повтор с PYTHONUTF8=1 завершился и сохранил
[package-structural-utf8.stdout.txt](package-structural-utf8.stdout.txt).
Получено 17 записей: 14 положительных, 3 отрицательных, все критические
проверки положительны. Отрицательные записи оставлены без подмены результата:

- README.md намеренно входит в существующий пакет и изменяется по tasks.md.
- Положительные и отрицательные discovery triggers отсутствуют у скилла
  с явным вызовом; это сохранённая политика, автоматическое обнаружение
  не проверялось.

Рекурсивный осмотр файловой системы включал скрытые и игнорируемые пути,
независимо от git status. В обоих пакетах по 68 элементов; единственный
dotfile — .gitignore. Окружений, bytecode, кэшей, логов, PNG и результатов
прогонов не найдено. До заключительной синхронизации полный прогон не изменил
ни одного байта проверочной копии. Отчёты хранятся в данном workspace,
внешние runtime-данные — в temp и пользовательском cache.

## Согласование при изменении производных файлов

Синтетическая валидная фикстура построена по tests/conftest.py. В ней находятся
proposal, design, spec, завершённый consistency-review и document_approval,
привязанный к фактическому documents snapshot. Это тестовые записи, они
не выражают реальное согласие пользователя.

До и после замены заглушки в explanation.md на Markdown-превью и добавления
производных файлов archify выполнены штатные команды:

```text
python <copy>/scripts/run.py snapshot --project-root <fixture> --change demo --stage documents
python <copy>/scripts/run.py check --project-root <fixture> --change demo --stage documents
```

Оба check вернули 0. Нормативные байты, запись согласования и documents-манифест
совпали; approval_status до/после одинаков: approved=true, ready=true,
применимость USER-doc-approval=true. Исходные JSON-выводы сохранены
в approval-snapshot-before/after.stdout.txt и approval-check-before/after.stdout.txt.

Это проверка исключения производных файлов из манифеста и применимости
согласования. HTML и PNG здесь синтетические; выполнение explain/handoff,
достоверность превью и браузерные проверки этим прогоном не подтверждаются.
