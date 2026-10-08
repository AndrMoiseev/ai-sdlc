# ai-sdlc
Поддержка AI Assisted Software Engineering

## Пакеты APM

Исходники скиллов хранятся в `skills/`. Пакеты описывают подборки через
зависимости и не дублируют исходники:

| Пакет | Состав |
|---|---|
| [aisdlc-core](packages/aisdlc-core/apm.yml) | `sdd-spec`, `sdd-doc`, `sdd-implement`, пакет `common-dependencies` |
| [aisdlc-skills](packages/aisdlc-skills/apm.yml) | `sdd-skill-conductor`, пакет `common-dependencies` |
| [common-dependencies](packages/common-dependencies/apm.yml) | [humanizer-ru](https://github.com/smixs/humanizer-ru), [Archify 3.0.1](https://github.com/tt-a1i/archify/tree/v3.0.1/archify) |

`aisdlc-core` и `aisdlc-skills` можно подключать по отдельности или вместе.
Оба автоматически устанавливают `common-dependencies`; при совместной
установке общая зависимость используется один раз. `humanizer-ru` и `archify`
загружаются из внешних репозиториев; их версии закреплены полными Git SHA
в манифесте `common-dependencies`. Archify закреплён на коммите тега `v3.0.1`.
Для обновления измените соответствующий SHA и выполните
`apm install --update`, затем проверьте изменения скилла и lock-файла.
Если APM использует старый граф вложенных зависимостей, выполните
`apm install --update --refresh`.

Для Archify нужен каталог `bin/`. В корневом `apm.yml` разрешена его установка
через `executables.allow` для конкретного SHA Archify. При подключении пакетов
в другом проекте перенесите этот блок в манифест потребителя: настройки доверия
корневого проекта не наследуются через зависимости. При обновлении Archify
обновите SHA и в зависимости, и в разрешении. Для запуска требуется Node.js.
Для неинтерактивной установки используйте `apm install --trust-bin`
(для зафиксированных версий — `apm install --frozen --trust-bin`). Без этого
флага APM может пропустить `bin/`, даже при наличии разрешения в манифесте.
При проверке этого подключения `apm audit --ci` сообщил drift для 14 файлов
Archify в `bin/`: контрольная переустановка пропустила их, хотя файлы присутствуют
в lock-файле и их хэши совпадают. `apm install --frozen --trust-bin` проходит
без изменения lock-файла, а `node .agents/skills/archify/bin/archify.mjs doctor`
подтверждает комплектность установки. Полный audit пока не проходит.

OpenSpec CLI и установленные в этом проекте скиллы `openspec-*` в эти наборы
не входят. Для работы `sdd-implement` требуется отдельно установленный OpenSpec CLI.

### Работа над этим репозиторием

Корневой [apm.yml](apm.yml) подключает оба пакета по локальным путям.
Установка рассчитана на Codex и Claude Code: полные копии скиллов попадают
в `.agents/skills/` и `.claude/skills/` соответственно.

Проверенная версия CLI — **APM 0.32.0**. Установить её можно через `uv`:

```text
uv tool install apm-cli==0.32.0
apm --version
```

В чистой рабочей копии, без окружений и кэшей внутри `skills/`:

```text
apm install --frozen
apm audit --ci
```

После изменения состава пакетов или исходников выполните `apm install`,
проверьте diff исходников, установленных копий и `apm.lock.yaml`.
Если изменились зависимости внутри `packages/*/apm.yml`, используйте
`apm install --update`: в APM 0.32.0 обычная установка может повторно
использовать прежний граф вложенных зависимостей из lock-файла.
Манифесты, lock-файл и установленные копии хранятся в Git;
служебный каталог `apm_modules/` игнорируется. Для локальных зависимостей
версию содержимого задаёт коммит этого репозитория; lock-файл не хранит
отдельный Git SHA каждого локального скилла.
Файл `.gitattributes` фиксирует LF для исходников и установленных скиллов,
чтобы преобразование окончаний строк в Git не нарушало хеши APM.

### Python-скрипты: подготовка и запуск

Установите [uv](https://docs.astral.sh/uv/getting-started/installation/)
(на Windows: `winget install --id=astral-sh.uv -e`). Проверенная версия — uv 0.12.5.
Наши скрипты объявляют зависимости в формате PEP 723 и поставляются с соседними
`.py.lock`-файлами. uv создаёт изолированные окружения в пользовательском кэше.
Проекту, в котором используется скилл, не нужны Python-манифест, lock-файл или `.venv`.

На Windows один раз настройте пользовательские переменные uv в обычном PowerShell:

```powershell
./scripts/setup-uv.ps1
```

Скрипт задаёт `UV_CACHE_DIR` на `uv-runtime/cache`, а `UV_TOOL_DIR` на
`uv-runtime/tools` внутри системной временной папки. Он сохраняет абсолютные пути
в пользовательских переменных Windows и применяет их к текущему PowerShell.
Настройки агента и каждого проекта не меняются. Для установки без клонирования
репозитория можно выполнить тот же код вручную:

```powershell
$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'uv-runtime'
$settings = @{
    UV_CACHE_DIR = Join-Path $runtimeRoot 'cache'
    UV_TOOL_DIR = Join-Path $runtimeRoot 'tools'
}
foreach ($name in $settings.Keys) {
    $value = [System.IO.Path]::GetFullPath($settings[$name])
    New-Item -ItemType Directory -Path $value -Force | Out-Null
    [Environment]::SetEnvironmentVariable($name, $value, 'User')
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
```

Перезапустите приложение агента и другие терминалы, чтобы они получили переменные.
Проверьте `uv cache dir` и `uv tool dir` из нового процесса. Сторонние `uv run`
и `uvx` используют те же переменные; явные параметры команд или переназначение
переменных могут их переопределить. `UV_TOOL_DIR` нужен также для файла блокировки
инструментов. Старые кэши и установленные инструменты не перемещаются и не удаляются;
инструменты из прежнего `UV_TOOL_DIR` при необходимости установите заново.

Системная временная папка должна быть доступна песочнице для записи. Если среда
запрещает запись и туда, настройка uv сама по себе не даёт разрешений.
На других ОС используйте доступный пользовательский кэш uv; при необходимости
задайте те же переменные абсолютными путями к разрешённым каталогам.
Общий `UV_PROJECT_ENVIRONMENT` для разных проектов не задавайте.

В терминале с доступом к сети подготовьте нужные скрипты по их установленным путям:

```text
uv sync --locked --script .agents/skills/sdd-spec/scripts/check.py
uv sync --locked --script .agents/skills/sdd-spec/scripts/snapshot.py
uv sync --locked --script .agents/skills/sdd-skill-conductor/scripts/eval_skill.py
```

`uv sync --script` устанавливает зависимости без выполнения скрипта и при
необходимости скачивает подходящий Python. Для исходников или Claude замените
путь на `skills/...` или `.claude/skills/...`. Остальные скрипты готовятся так же.
Повторите подготовку после обновления зависимостей, переноса копии или очистки
кэша. Временную папку может очистить система: офлайн-запуск тогда потребует
повторной подготовки. Установки `uv tool install` в этом каталоге тоже временные.

Обычный запуск агента использует подготовленные зависимости:

```text
uv run --locked --offline --script .agents/skills/sdd-spec/scripts/check.py --project-root . --change <id> --stage documents
```

Из другой директории укажите абсолютные пути к скрипту и `--project-root`.
`--locked` проверяет lock-файл скрипта, `--offline` запрещает сетевые обращения uv,
а сами точки входа отключают запись байткода. Зависимости проекта пользователя
не участвуют в запуске. При недостающих пакетах повторите подготовку в терминале
с сетью. При изменении зависимостей автор обновляет соответствующий lock-файл
командой `uv lock --script <script.py>` и сохраняет его вместе со скриптом.

Регрессионные тесты также запускаются автономно:

```text
uv sync --locked --script skills/sdd-spec/scripts/test.py
uv run --locked --offline --script skills/sdd-spec/scripts/test.py -q
uv sync --locked --script skills/sdd-skill-conductor/scripts/test_harness.py
uv run --locked --offline --script skills/sdd-skill-conductor/scripts/test_harness.py
uv sync --locked --script skills/sdd-skill-conductor/scripts/test_smoke.py
uv run --locked --offline --script skills/sdd-skill-conductor/scripts/test_smoke.py
```

Корневые `pyproject.toml` и `uv.lock` остаются для разработки этого репозитория;
потребителям скиллов они не нужны. Примеры остальных команд — в
[runtime-setup](skills/sdd-spec/references/runtime-setup.md).
APM копирует каталоги скиллов целиком, поэтому результаты прогонов и окружения
храните вне `skills/`, `.agents/skills/` и `.claude/skills/`.

Правки вносите в `skills/`. Перед установкой сравнивайте существующие
копии с исходниками и сохраняйте локальные изменения по [AGENTS.md](AGENTS.md).
APM не объединяет изменения в управляемых копиях с обновлениями исходников.
Не используйте `--force` как обычный способ обновления.

### Подключение к другому проекту

После публикации этих манифестов в Git установите нужные пакеты из корня
проекта-потребителя:

```text
apm install AndrMoiseev/ai-sdlc/packages/aisdlc-core --target codex,claude
apm install AndrMoiseev/ai-sdlc/packages/aisdlc-skills --target codex,claude
```

Можно выбрать только `--target codex` или `--target claude`. Для фиксации
версии добавьте `#<commit>` к пути пакета. Сохраните созданные `apm.yml`
и `apm.lock.yaml`; повторная установка выполняется через
`apm install --frozen`. Для обновления удалённых зависимостей используйте
`apm update` с проверкой предложенных изменений.

Относительные зависимости пакета разрешаются внутри этого же репозитория.
Корневой манифест рабочего проекта при подключении `packages/aisdlc-core`
или `packages/aisdlc-skills` не наследуется.

Документация APM:
[зависимости](https://github.com/microsoft/apm/blob/v0.32.0/packages/apm-guide/.apm/skills/apm-usage/dependencies.md),
[тип скилла](https://github.com/microsoft/apm/blob/v0.32.0/docs/src/content/docs/reference/package-types.md).

## Скиллы

- [sdd-skill-conductor](skills/sdd-skill-conductor/SKILL.md) — разработка,
  проверка и упаковка скиллов с поддержкой Codex и Claude Code.
  Основан на [smixs/skill-conductor](https://github.com/smixs/skill-conductor).
  Исходники для дальнейших доработок находятся в `skills/sdd-skill-conductor/`.
  Рабочая копия установлена в `.agents/skills/sdd-skill-conductor/`;
  порядок её обновления описан в [AGENTS.md](AGENTS.md).
  [Результаты проверок исходной версии](skill-workspaces/sdd-skill-conductor/validation.md).

- [sdd-spec](skills/sdd-spec/SKILL.md) — исследование, спецификации, дизайн и согласованный
  план изменения по явному вызову `$sdd-spec` или `/sdd-spec`.
  [Подключение](skills/sdd-spec/README.md) ·
  [Проверки](skill-workspaces/sdd-spec/validation.md).

- [sdd-doc](skills/sdd-doc/SKILL.md) — создание и
  обновление глоссария проекта по явному вызову `$sdd-doc`.
  Неоднозначные термины остаются открытыми вопросами.
  [Ручная проверка](skills/sdd-doc/evals/manual.md) ·
  [Состояние проверки](skill-workspaces/sdd-doc/validation.md).

- [sdd-implement](skills/sdd-implement/SKILL.md) — выполнение или продолжение
  готового изменения OpenSpec по явному вызову `$sdd-implement` или `/sdd-implement`.
  Перенесён из пользовательского `openspec-autopilot`; автоматический выбор
  отключён для Codex и Claude Code.
