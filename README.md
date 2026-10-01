# ai-sdlc
Поддержка AI Assisted Software Engineering

## Пакеты APM

Исходники скиллов хранятся в `skills/`. Пакеты описывают подборки через
зависимости и не дублируют исходники:

| Пакет | Состав |
|---|---|
| [aisdlc-core](packages/aisdlc-core/apm.yml) | `sdd-spec`, `sdd-doc`, пакет `common-dependencies` |
| [aisdlc-skills](packages/aisdlc-skills/apm.yml) | `sdd-skill-conductor`, пакет `common-dependencies` |
| [common-dependencies](packages/common-dependencies/apm.yml) | [humanizer-ru](https://github.com/smixs/humanizer-ru) |

`aisdlc-core` и `aisdlc-skills` можно подключать по отдельности или вместе.
Оба автоматически устанавливают `common-dependencies`; при совместной
установке общая зависимость используется один раз. `humanizer-ru` загружается
из внешнего репозитория; его версия закреплена полным Git SHA в манифесте
`common-dependencies`. Для обновления измените этот SHA и выполните
`apm install --update`, затем проверьте изменения скилла и lock-файла.

OpenSpec CLI и установленные
в этом проекте OpenSpec-скиллы в эти наборы не входят.

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

### Окружение и кэши проверок

Для `sdd-spec` используйте запускатель, который автоматически размещает
окружение uv, байткод Python и кэш pytest вне `skills/`:

```text
python skills/sdd-spec/scripts/run.py test
python skills/sdd-spec/scripts/run.py cache-dir
```

Вторая команда показывает каталог кэша этой копии скилла. На Windows он
находится в `%LOCALAPPDATA%/ai-sdlc/sdd-spec/`; расположение для других ОС
и команды `check`/`snapshot` описаны в
[runtime-setup](skills/sdd-spec/references/runtime-setup.md).
Запускатель также входит в установленные копии пакета. Он создаёт отдельное
окружение для каждой копии и восстанавливает зависимости по `uv.lock`.

APM 0.32.0 копирует локальные зависимости целиком, без учёта `.gitignore`.
Поэтому запускайте проверки через `run.py`, а результаты ручных прогонов
храните вне `skills/`. Старый прямой вызов `uv run --project skills/sdd-spec`
снова создаст `.venv` в исходниках. Режим APM `--root` не решает эту проблему
для вложенных локальных зависимостей.

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
