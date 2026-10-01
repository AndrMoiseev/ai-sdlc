# ai-sdlc
Поддержка AI Assisted Software Engineering

## Пакеты APM

Исходники скиллов хранятся в `skills/`. Пакеты описывают подборки через
зависимости и не дублируют исходники:

| Пакет | Состав |
|---|---|
| [aisdlc-core](packages/aisdlc-core/apm.yml) | `sdd-spec`, `sdd-doc` |
| [aisdlc-skills](packages/aisdlc-skills/apm.yml) | `sdd-skill-conductor` |

Пакеты независимы; можно подключить один или оба. OpenSpec CLI и установленные
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
Манифесты, lock-файл и установленные копии хранятся в Git;
служебный каталог `apm_modules/` игнорируется. Для локальных зависимостей
версию содержимого задаёт коммит этого репозитория; lock-файл не хранит
отдельный Git SHA каждого локального скилла.
Файл `.gitattributes` фиксирует LF для исходников и установленных скиллов,
чтобы преобразование окончаний строк в Git не нарушало хеши APM.

**Особенность локальной установки APM 0.32.0:** каталоги зависимостей
копируются целиком, без учёта `.gitignore`. Не запускайте установку из
исходников, содержащих `.venv/`, `__pycache__/`, `.pytest_cache/` или
результаты прогонов. Используйте чистую рабочую копию либо временно вынесите
эти каталоги за пределы `skills/` с сохранением и верните после установки.
Окружения и результаты новых проверок по возможности размещайте вне `skills/`.
Режим `--root` в этой версии не подходит для обхода проблемы: вложенные
локальные зависимости могут разрешаться из рабочего дерева назначения.

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
