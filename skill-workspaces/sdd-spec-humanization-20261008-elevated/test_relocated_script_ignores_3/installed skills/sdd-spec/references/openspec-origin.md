# Происхождение и адаптация OpenSpec

Пакет переносит поведение локальных `openspec-explore`, `openspec-propose`, `openspec-update-change` (metadata version 1.0, generatedBy 1.12.0, MIT) и инструкций/шаблонов `spec-driven` установленного `@fission-ai/openspec`. Источники изучены при реализации 2026-09-29. Upstream: [OpenSpec](https://github.com/Fission-AI/OpenSpec). Локальные исходники включают уточнения проекта; ссылаться только на upstream как на идентичный текст было бы неточно.

| Локальный источник | SHA-256 исходного SKILL.md |
|---|---|
| `.agents/skills/openspec-explore/SKILL.md` | `28dba6d130b984c28ae3a3b9fa054e4e38b54cf6000c04bbceee6483529c8ba6` |
| `.agents/skills/openspec-propose/SKILL.md` | `5a1997695e482429e2f2a23301cd18cc028b9f5bdbab77d8ed262912316e3e81` |
| `.agents/skills/openspec-update-change/SKILL.md` | `30181d7c0957c55420503c82f01e39a51cabba86bc1c266a191106b913087b76` |

Это сведения происхождения, не runtime-зависимости. Пакет содержит собственные адаптированные инструкции и шаблоны; установка OpenSpec и выполнение его команд не нужны. Обновление исходных скиллов не меняет sdd автоматически. Schema/template `spec-driven` прочитаны из установленного npm-пакета; они определяют роли артефактов, но не исполняемый workflow sdd-spec.

| Исходное поведение | Сохранено в пакете | Замена и основание |
|---|---|---|
| Explore: Stance, Planning a Change | [explore](../flows/explore.md): свободное обсуждение, исследование до фактических вопросов, последовательность выборов, рекомендации, схемы, достаточная ясность | Один внутренний флоу вместо отдельного скилла; без обязательной анкеты |
| Explore: conversational record, Don't auto-capture | Различение фактов, предложений и пользовательских решений | [resume](../flows/resume.md) сохраняет черновики и checkpoint без отдельного подтверждения записи вместо хранения только в разговоре; требуется межсессионная устойчивость |
| Explore: context, existing artifacts, scaffold | Выбор изменения и чтение реальных источников/ограничений | Чтение `sdd/` напрямую и собственные шаблоны заменяют CLI list/status/new change, store/config; пакет самостоятельный |
| Propose: discovery, dependencies, creation | [draft](../flows/draft.md): существенные вопросы, актуальные зависимости с диска, инструкции как ограничения, проверка записанного результата | Фиксированные артефакты sdd заменяют универсальный schema DAG и создание всего apply-набора |
| Spec-driven proposal | Причина, изменения, capabilities и impact; краткость | Явные границы и исключения; нет skip_specs/merge OpenSpec |
| Spec-driven specs | Контракт наблюдаемого поведения, входы/выходы/ошибки, разделение capabilities, полное содержание затронутого требования | YAML operation/source и AC заменяют обязательные Scenario-заголовки; SCN не нужен, критерии удаления остаются проверяемыми; переименование заголовка при стабильном ID — modify |
| Spec-driven design | Подход, контекст, альтернативы, риски, применимая миграция и действительно отложенные вопросы | Design обязателен всегда, включая простое изменение; модули/термины описательные, DEC имеют связи |
| Spec-driven tasks | Specs/design как основания, вопросы до планирования, зависимости, соразмерность и проверяемый результат | [plan](../flows/plan.md): отдельная команда; TASK-ID и номер вместо checkbox-идентичности; однократное покрытие AC и тесты внутри задач. Исходное исключение для отдельной интеграционной проверки не переносится |
| Update: reconcile in any direction | [revise](../flows/revise.md): проверка всех существующих документов в обоих направлениях, сохранение незатронутого, без записи если правка не нужна | Содержательная область согласуется, но не требуется повторное подтверждение каждого файла уже порученной работы; checkpoints и однозначная структура исправляются напрямую |
| Update: frontier/intent | Отсутствующие документы не создаются при пересмотре, смена цели отделяется | Выбор дальнейшего флоу локальный, без обязательных openspec-команд |
| Propose/Update: planning boundary | Подготовка не разрешает реализацию | Пакет заканчивается согласованным планом, без apply/sync/archive |

Независимые линзы, разбор находок, версионные согласования, постоянные checkpoint и детерминированная трассировка — дополнения sdd, не приписываемые OpenSpec. Чистый baseline без скилла при подготовке этого пакета использовал числовые REQ/AC/DES, отдельно назначил дублирующий AC интеграционной задаче и не создал YAML-записи. Это наблюдение объясняет необходимость явного формата и проверок; оно не означает, что любые числовые обозначения или любая интеграционная работа плохи. Требования sdd отдельно задают смысловые ID и однократное владение AC.

## MIT attribution

Применимое уведомление из LICENSE установленного OpenSpec сохранено полностью:

```text
MIT License

Copyright (c) 2024 OpenSpec Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
