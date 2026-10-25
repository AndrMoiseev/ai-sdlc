# Связь с OpenSpec

Проверено 2026-10-22 по первичным инструкциям проекта:

- [openspec-sync-specs](https://github.com/Fission-AI/OpenSpec/blob/main/skills/openspec-sync-specs/SKILL.md): слияние delta specs с сохранением незатронутого содержания и проверкой результата.
- [openspec-archive-change](https://github.com/Fission-AI/OpenSpec/blob/main/skills/openspec-archive-change/SKILL.md): проверка завершения, перенос всего изменения в датированный архив, отказ от перезаписи существующей цели.

В OpenSpec sync оставляет изменение активным; archive может предварительно
синхронизировать spec. По запросу пользователя обычный вызов sdd-sync объединяет
оба результата. Явное «без архива» ограничивает операцию синхронизацией.

SDD использует собственные пути и YAML operation/source, REQ/AC-ID вместо
ADDED/MODIFIED/REMOVED/RENAMED и Scenario-заголовков. Переименование сохраняет ID
и выражается через modify. Проверка принятого исполнения sdd-apply, формат
текущей baseline и отчёт возобновления относятся к SDD, а не к API OpenSpec.
Вариант OpenSpec «архив без синхронизации незавершённой дельты» сюда не перенесён:
назначение этого скилла состоит в переносе завершённого поведения в baseline.

OpenSpec CLI для этого скилла не требуется. Инструкции адаптированы по смыслу;
уведомление MIT сохранено в [LICENSE](../LICENSE).
