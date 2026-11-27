# sdd

`sdd` — CLI на Go для рабочих команд SDD. Скиллы по-прежнему вызывают свои Python-скрипты. CLI можно вызывать напрямую из каталога проекта или передать ему путь к проекту.

## Установка через mise

Для установки последнего опубликованного CLI выполните эти команды из каталога проекта. Проверено с mise 2026.11.8.

```sh
mise use 'github:AndrMoiseev/ai-sdlc[version_prefix=sdd-v]@latest'
mise exec -- sdd --help
```

Для фиксации версии и проверки SHA-256 скачайте `sdd.mise.toml` из выбранного релиза. Сохраните его как `mise.toml` в новом проекте или перенесите таблицу `[tools."github:AndrMoiseev/ai-sdlc"]` в существующую конфигурацию. Затем выполните `mise install`. При обновлении замените таблицу целиком, чтобы обновить версию и контрольные суммы вместе. [Релизы CLI](https://github.com/AndrMoiseev/ai-sdlc/releases) · [GitHub-бэкенд mise](https://mise.jdx.dev/dev-tools/backends/github.html)

Оба способа устанавливают бинарник для выбранной платформы вместе с нужным ему каталогом `sdd-shared`. Скиллы для агентов по-прежнему устанавливаются через APM.

## Сборка

Из каталога `cli` выполните `go build ./cmd/sdd` с Go 1.22 или новее. Имя бинарника в Windows — `sdd.exe`, в Linux и macOS — `sdd`. Для команд, которые работают с репозиторием или запускают проверки проекта, нужны Git и инструменты, указанные в настройках проекта.

## CI и релизы

GitHub Actions собирает CLI при изменениях в `cli/`, `skills/sdd-shared/`, `.gitattributes`, лицензии или самом workflow. Сборки запускаются для pull request и при push в `main`. Сборку выбранной ветки можно также запустить вручную через **Actions → SDD CLI → Run workflow**. [Workflow](../.github/workflows/sdd-cli.yml)

| Платформа | Архив релиза |
|---|---|
| Windows x64 | `sdd-windows-amd64.zip` |
| Windows ARM64 | `sdd-windows-arm64.zip` |
| macOS Intel | `sdd-darwin-amd64.tar.gz` |
| macOS Apple Silicon | `sdd-darwin-arm64.tar.gz` |

Каждая сборка запускает `go test ./...`, упаковывает бинарник с каталогом `sdd-shared` и лицензией, устанавливает полученный архив через mise и выполняет `sdd setup inspect`. Готовые архивы доступны в артефактах запуска. При ручной распаковке оставьте `sdd-shared` рядом с бинарником.

Чтобы выпустить CLI через интерфейс GitHub, в разделе **Releases** создайте релиз с новым тегом вида `sdd-vX.Y.Z`, выберите коммит выпуска и нажмите **Publish release**. Создание тега запустит сборку. Когда пройдут все четыре задания, workflow добавит в этот релиз четыре архива, `sdd.mise.toml` и `SHA256SUMS`.

Можно также отправить тег через Git, например `git push origin sdd-v0.1.0`. Если релиза для тега ещё нет, workflow создаст черновик, загрузит файлы и опубликует его.

## Команды

| Вызов Go | Точка входа Python | Назначение |
|---|---|---|
| `sdd setup <команда>` | `sdd-setup/scripts/setup.py` | Маршрут настройки, инструменты проекта, настройка ролей через `inspect`, `plan` и `apply` |
| `sdd architect metrics <команда>` | `sdd-architect/scripts/metrics.py` | Сбор метрик, свидетельства, ранжирование и статус аудита |
| `sdd architect audit-state <команда>` | `sdd-architect/scripts/audit_state.py` | Чтение, запись и проверка состояния аудита |
| `sdd check` | `sdd-spec/scripts/check.py` | Документы, граф задач и согласование изменения или рефакторинга |
| `sdd resolve-agent` | `sdd-spec/scripts/resolve_agent.py` | Выбор исполнителя и параметров модели |
| `sdd simplicity` | `sdd-spec/scripts/simplicity.py` | Профиль проверки простоты для указанной модели |
| `sdd checkpoint <команда>` | `sdd-shared/scripts/checkpoint.py` | Операции Git `inspect`, `initialize`, `accept` и `create` |
| `sdd apply --request <файл>` | `sdd-apply/scripts/execute.py` | 13 операций исполнения, включая `event` с 29 типами событий |

Для `setup inspect` каталог `sdd-shared` должен лежать рядом с бинарником либо быть указан через `--sdd-shared`. Инспекция записывает фактический путь и хэш контракта. При запуске из исходного репозитория можно передать `--sdd-shared ../skills/sdd-shared` из каталога `cli`.

Примеры для PowerShell

```powershell
.\sdd.exe setup --help
.\sdd.exe check --project-root C:\work\example --change sample-change --stage plan
.\sdd.exe checkpoint inspect --project-root C:\work\example --change sample-change --work-kind change
.\sdd.exe apply --help-operation
.\sdd.exe apply --help-event transfer
.\sdd.exe apply --request C:\work\requests\read.json
```

Файл запроса для чтения состояния имеет вид `{"operation":"read","args":{"directory":"C:/work/example/sdd/changes/sample-change/execution"}}`. Для `check` код 0 означает успешную структурную проверку, 1 — ошибку структуры, 2 — ошибку входных данных. Состояние согласования команда возвращает отдельно в `approval_status`.

## Сравнение с Python

Из корня репозитория, настроив uv по правилам проекта, запустите наборы последовательно. Нужны системный Python 3.11 или новее, uv, Go и Git. Для сравнения используется зафиксированный коммит Python. Каждый запуск извлекает его во внешний временный каталог и собирает текущую версию Go. [Правила окружения](../AGENTS.md) · [Реестр сценариев и эталонный коммит](../sdd/changes/sdd-cli/scenarios.md)

```powershell
$python = uv python find --system --no-managed-python '>=3.11'
$tmp = [IO.Path]::GetTempPath()
& $python -B (Resolve-Path cli/tests/spec.py) spec --basetemp $tmp
& $python -B (Resolve-Path cli/tests/spec.py) checkpoint --basetemp $tmp
& $python -B (Resolve-Path cli/tests/setup.py) --basetemp $tmp
& $python -B (Resolve-Path cli/tests/architect.py) --basetemp $tmp
& $python -B (Resolve-Path cli/tests/apply.py) --basetemp $tmp
```

Запускатели сверяют код выхода, потоки вывода и эффекты команды. Проверки Git читают реальные refs, деревья, индекс и патчи. Проверки исполнения дополнительно читают объекты по сохранённым SHA-256, запускают команды фикстуры и обращаются к локальному HTTP-серверу. Номера портов, UUID и время сопоставляются по формату и связям с другими результатами. Входы о действиях ролей моделируются записями протокола. Путь к рабочему каталогу печатается для разбора расхождений.
