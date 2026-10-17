# ai-sdlc
Поддержка AI Assisted Software Engineering

## Рекомендуемые инструменты для анализа кода

Подбирайте инструменты под стек и задачу: сложность функций, зависимости между модулями, дублирование, неиспользуемый код и качество тестов. Команды и ориентиры для проверок приведены в [справочнике скилла](skills/code-that-fits-in-your-head/references/tooling/commands.md). Не обязательно устанавливать весь список: для одного вида проверки обычно достаточно одного подходящего инструмента.

| Инструмент | Краткое описание | Инструкция по установке | Подходящие стеки |
|---|---|---|---|
| Lizard | Цикломатическая сложность функций | [Установка](https://github.com/terryyin/lizard#installation) | C#, JS/TS, Python, Go, Java, C/C++, Rust и другие |
| Radon | Метрики сложности Python-кода | [Установка](https://pypi.org/project/radon/) | Python |
| Ruff (`C901`) | Проверка сложности функций в линтере | [Установка](https://docs.astral.sh/ruff/installation/) | Python |
| ESLint (`complexity`) | Проверка сложности по правилу линтера | [Установка](https://eslint.org/docs/latest/use/getting-started) | JavaScript, TypeScript |
| Анализаторы Roslyn (`CA1502`, `IDE0051`, `IDE0052`) и `dotnet format` | Сложность и неиспользуемые члены; анализаторы и команда входят в современный .NET SDK | [Установка .NET SDK](https://learn.microsoft.com/dotnet/core/install/) | .NET, C# |
| gocyclo | Цикломатическая сложность функций | [Установка](https://github.com/fzipp/gocyclo#installation) | Go |
| Madge | Циклические зависимости модулей | [Установка](https://github.com/pahen/madge#installation) | JavaScript, TypeScript |
| dependency-cruiser | Циклы и правила зависимостей между слоями | [Установка](https://github.com/sverweij/dependency-cruiser#how-do-i-use-it) | JavaScript, TypeScript |
| pydeps | Граф зависимостей и циклы импортов | [Установка](https://pydeps.readthedocs.io/en/latest/#how-to-install) | Python |
| Import Linter | Контракты между слоями и запреты импортов | [Установка](https://import-linter.readthedocs.io/en/latest/get_started/install/) | Python |
| NetArchTest | Архитектурные ограничения как тесты | [Подключение пакета](https://github.com/BenMorris/NetArchTest#getting-started) | .NET, C# |
| ArchUnit | Архитектурные ограничения и циклы как тесты | [Подключение зависимости](https://www.archunit.org/userguide/html/000_Index.html#_installation) | JVM, Java |
| depguard (в golangci-lint) | Ограничения на импорты пакетов | [Установка golangci-lint](https://golangci-lint.run/docs/welcome/install/local/) | Go |
| jscpd | Поиск дублирующихся фрагментов | [Установка](https://jscpd.dev/start/quickstart) | Разные языки |
| ripgrep (`rg`) | Поиск существующих реализаций и употреблений символа | [Установка](https://github.com/BurntSushi/ripgrep#installation) | Любой стек |
| Knip | Неиспользуемые файлы, экспорты и зависимости | [Установка](https://knip.dev/overview/getting-started) | JavaScript, TypeScript |
| ts-prune | Потенциально неиспользуемые экспорты | [Установка](https://github.com/nadeesha/ts-prune#installing) | TypeScript |
| Vulture | Потенциально неиспользуемый код | [Установка](https://github.com/jendrikseipp/vulture#installation) | Python |
| deptry | Неиспользуемые и отсутствующие зависимости проекта | [Установка](https://deptry.com/#installation) | Python |
| `dead_code` | Встроенное предупреждение компилятора о неиспользуемом коде | [Установка Rust](https://www.rust-lang.org/tools/install) | Rust |
| cargo-udeps | Неиспользуемые зависимости Cargo; для запуска нужен nightly | [Установка](https://github.com/est31/cargo-udeps#installation) | Rust |
| Git | История изменений для поиска часто меняющихся файлов и связанных правок | [Установка](https://git-scm.com/install/) | Любой стек |
| Stryker | Мутационное тестирование | [Установка](https://stryker-mutator.io/stryker/quickstart/) | JavaScript, TypeScript |
| Stryker.NET | Мутационное тестирование | [Установка](https://stryker-mutator.io/docs/stryker-net/getting-started/) | .NET, C# |
| mutmut | Мутационное тестирование; на Windows требуется WSL | [Установка](https://github.com/boxed/mutmut#install-and-run) | Python |
| Cosmic Ray | Мутационное тестирование | [Установка](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html#installation) | Python |
| PIT | Мутационное тестирование | [Подключение к Maven](https://pitest.org/quickstart/maven/) | JVM, Java (Maven) |
| cargo-mutants | Мутационное тестирование | [Установка](https://github.com/sourcefrog/cargo-mutants#install) | Rust |
| eslint-plugin-boundaries | Правила границ между модулями | [Установка](https://github.com/javierbrea/eslint-plugin-boundaries#quick-example) | JavaScript, TypeScript |

Для Go циклы импортов пакетов запрещены компилятором, поэтому отдельный инструмент для их поиска не нужен. Примеры анализа истории в справочнике используют Git вместе со стандартными утилитами POSIX (`sort`, `uniq`, `awk` и др.); в Windows их удобно запускать через WSL или Git Bash.

## Пакеты APM

Исходники скиллов хранятся в `skills/`. Пакеты описывают подборки через
зависимости и не дублируют исходники:

| Пакет | Состав |
|---|---|
| [aisdlc-core](packages/aisdlc-core/apm.yml) | `sdd-setup`, `sdd-spec`, `sdd-apply`, `sdd-doc`, `sdd-implement`, пакет `common-dependencies` |
| [aisdlc-skills](packages/aisdlc-skills/apm.yml) | `sdd-skill-conductor`, пакет `common-dependencies` |
| [aisdlc-experimental](packages/aisdlc-experimental/apm.yml) | [ubiquitous-language](https://github.com/CodeAlive-AI/ai-driven-development/tree/79d911b773d83986bee7ac4170d09a972e61fe31/skills/ubiquitous-language) |
| [common-dependencies](packages/common-dependencies/apm.yml) | [humanizer-ru](https://github.com/smixs/humanizer-ru), [Archify 3.0.1](https://github.com/tt-a1i/archify/tree/v3.0.1/archify) |

`aisdlc-core` и `aisdlc-skills` можно подключать по отдельности или вместе.
Оба автоматически устанавливают `common-dependencies`; при совместной
установке общая зависимость используется один раз. `humanizer-ru` и `archify`
загружаются из внешних репозиториев; их версии закреплены полными Git SHA
в манифесте `common-dependencies`. Archify закреплён на коммите тега `v3.0.1`.
`aisdlc-experimental` подключается отдельно; `ubiquitous-language` закреплён
полным Git SHA в манифесте пакета.
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

### Настройка SDD проекта

После установки набора вызовите `$sdd-setup` в Codex или `/sdd-setup` в Claude Code
для настройки ролей и моделей проекта. Мастер показывает текущие значения,
предлагает [пресеты по ролям и средам](skills/sdd-setup/assets/defaults.json),
сохраняет выбор в `.sdd/settings.json` и создаёт недостающие проектные определения
агентов. Имена агентов одинаковы в обеих средах; модели и effort различаются.

### Установка и настройка uv

Установите [uv](https://docs.astral.sh/uv/getting-started/installation/)
(на Windows: `winget install --id=astral-sh.uv -e`). Проверенная версия — uv 0.12.5.
Агент сам запускает служебные скрипты в рамках скиллов. uv автоматически
устанавливает нужные зависимости и при необходимости Python в пользовательское
окружение. Дополнительная настройка Python в каждом проекте не требуется.

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

После очистки временного кэша uv автоматически восстановит зависимости при
следующем использовании скилла. Для первой загрузки и восстановления нужен доступ
к сети. Отдельно установленные CLI, например APM, после очистки каталога
инструментов потребуется установить заново.

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
apm install AndrMoiseev/ai-sdlc/packages/aisdlc-experimental --target codex,claude
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

- [sdd-apply](skills/sdd-apply/SKILL.md) — исполнение согласованного плана
  `sdd-spec` по явному вызову `$sdd-apply` или `/sdd-apply`: независимые
  проверки, коммиты задач, восстановление и локальная панель прогресса.
  Параллельное исполнение включается только по явному запросу.
  [Установка и runtime](skills/sdd-apply/references/runtime-setup.md).

- [sdd-implement](skills/sdd-implement/SKILL.md) — выполнение или продолжение
  готового изменения OpenSpec по явному вызову `$sdd-implement` или `/sdd-implement`.
  Перенесён из пользовательского `openspec-autopilot`; автоматический выбор
  отключён для Codex и Claude Code.
