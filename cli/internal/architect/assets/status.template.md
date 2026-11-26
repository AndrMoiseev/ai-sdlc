# Статус проекта

Сбор: $collected_at. [Материалы аудита]($audit/report.md).
Профиль: `$profile`. Источник этого документа — [status.json](status.json).

[Файлы Kotlin](status-indicators.md#kotlin-files) — $kotlin_files, [прочие production-файлы](status-indicators.md#other-production-files) — $other_production_files.
Связи Kotlin с прочим production-кодом — [входящие](status-indicators.md#incoming-non-kotlin-edges) $incoming_non_kotlin_edges, [исходящие](status-indicators.md#outgoing-non-kotlin-edges) $outgoing_non_kotlin_edges.

Оценки качества относятся к production-коду Kotlin; статистика scc охватывает
файлы репозитория после настроенных исключений.

## Интегральные показатели

| Область Kotlin | [Файлы Kotlin](status-indicators.md#kotlin-files) | [Токены](status-indicators.md#tokens) | [D](status-indicators.md#d) | [L](status-indicators.md#l) | [U](status-indicators.md#u) | [Q](status-indicators.md#q) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
$scores

## Статистика scc

| Область / категория / язык | [Файлы](status-indicators.md#scc-files) | [Строки](status-indicators.md#scc-lines) | [Код](status-indicators.md#scc-code) | [Комментарии](status-indicators.md#scc-comment) | [Пустые](status-indicators.md#scc-blank) |
| --- | ---: | ---: | ---: | ---: | ---: |
$statistics

## Диагностические показатели

$diagnostics

## Границы архитектурных модулей

| Модуль | [Входящие рёбра](status-indicators.md#incoming-edges) | [Исходящие рёбра](status-indicators.md#outgoing-edges) | [Файлы в циклах проекта](status-indicators.md#project-cyclic-files) | [Токены файлов с межмодульными совместными изменениями](status-indicators.md#cross-module-coupled-tokens) | [Токены в межмодульных повторах](status-indicators.md#cross-module-duplicate-tokens) |
| --- | ---: | ---: | ---: | ---: | ---: |
$boundaries

## Область интерпретации

$limitations

Числители, знаменатели, вклад групп DRH, видимость файлов и крупнейшие вклады
сохранены в status.json. Значения показаны с округлением только в Markdown.
