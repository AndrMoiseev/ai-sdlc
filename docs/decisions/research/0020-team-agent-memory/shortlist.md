# Командная память для агентов. Итоговая пятёрка

**Первым я бы проверил GBrain.** Он даёт агентам общий поиск по репозиториям, показывает происхождение записей и умеет помечать споры между числовыми утверждениями внутри одного подключённого источника. Обычную правку агент может внести самостоятельно с объяснением, а команда может посмотреть предыдущую редакцию. **WeKnora** занимает второе место. Она сильнее в сборе материалов из GitLab и Confluence и тоже позволяет исправлять общие знания с сохранением истории. [Доверие к фактам в GBrain](https://github.com/garrytan/gbrain/blob/master/docs/guides/memory-trust.md) · [Wiki в WeKnora](https://github.com/Tencent/WeKnora/blob/main/website-docs/03-features/14-wiki.md) · [коннекторы WeKnora](https://github.com/Tencent/WeKnora/blob/main/website-docs/03-features/10-datasource.md)

## Пять инструментов

| Место и проект | Что получает команда | Что учесть |
| --- | --- | --- |
| **1. GBrain** · 33 355 звёзд | Агент ищет по нескольким Git-репозиториям, видит источник результата и может записать причину правки страницы. Сохраняется предыдущий текст. Если включить проверку числовых утверждений, агент видит пометку `contested` у спорных фактов и ссылку на вторую запись. Принятую замену можно отменить. [Межпроектный поиск](https://github.com/garrytan/gbrain/blob/master/docs/guides/multi-source-brains.md) · [доверие и разбор спора](https://github.com/garrytan/gbrain/blob/master/docs/guides/memory-trust.md#old-and-conflicting-facts) · [история правок](https://github.com/garrytan/gbrain/blob/master/docs/guides/page-history.md) | Автопроверка сравнивает числа внутри одного источника GBrain и одной области видимости. Должны совпасть сущность, метрика, единица и период. Расхождение между отдельно подключёнными GitLab и Confluence агенту придётся проверить по обеим ссылкам. GitLab можно читать через локальную копию репозитория, для Confluence стоит закладывать импорт. [Код сравнения](https://github.com/garrytan/gbrain/blob/f3aecde8d8b43598b3f57b94f363c2b6c0ab97e3/src/core/facts/claim-conflicts.ts#L80-L90) · [код отметки в выдаче](https://github.com/garrytan/gbrain/blob/f3aecde8d8b43598b3f57b94f363c2b6c0ab97e3/src/core/facts/contested-claims.ts#L35-L60) · [импорт](https://github.com/garrytan/gbrain/blob/master/docs/guides/data-ingestion.md) |
| **2. WeKnora** · 37 926 звёзд | Принимает локальные Markdown-файлы, синхронизирует GitLab и Confluence. Wiki связывает страницы с исходными фрагментами. Агент с правом записи может исправить текст или пометить его как противоречивый либо устаревший. В истории видны автор, время и различия версий. Откат создаёт новую редакцию текста. [Источники](https://github.com/Tencent/WeKnora/blob/main/website-docs/03-features/10-datasource.md) · [ссылки, правки и откат](https://github.com/Tencent/WeKnora/blob/main/website-docs/03-features/14-wiki.md) | При откате сохраняются **текущие** ссылки на источники. Для разбора старого решения важна отдельная история его оснований. Согласование настраивается по типу операции. Решение передать человеку содержательный спор остаётся за агентом. Для записи нужен доступ редактора, опубликованный общий агент работает только на чтение. [Код отката](https://github.com/Tencent/WeKnora/blob/1ef55d4a8dd2f6d464532d4da750b870416b5bae/internal/application/service/wiki_page.go#L413-L440) · [разбор случая с утратой ссылок](https://github.com/Tencent/WeKnora/pull/5186) · [политика действий](https://github.com/Tencent/WeKnora/blob/main/website-docs/03-features/07-agent.md) |
| **3. Hindsight** · 62 300 звёзд | Агенты могут пополнять общий банк. Для каждого сводного наблюдения поиск может вернуть исходные факты и дословные фрагменты. При исправлении основания система пересматривает зависимые наблюдения. Есть история текста наблюдения, а исключённый из выдачи факт можно вернуть. [Поиск с основаниями](https://hindsight.vectorize.io/developer/api/recall) · [пересмотр наблюдений](https://hindsight.vectorize.io/developer/observations) · [исправление факта](https://hindsight.vectorize.io/developer/api/memories) | Система умеет сама изложить противоположные сведения как изменение во времени. Если два источника описывают один и тот же момент, команде потребуется проверка перед объединением. [Обработка расхождений](https://hindsight.vectorize.io/developer/observations#handling-contradictory-evidence) |
| **4. Mnemosyne** · 162 звезды | В стабильной версии 2.0.0 выдача `compile` содержит ссылки, конфликты, причины исключения и признак отказа от ответа. Когда владелец исправляет запись, сохраняются предыдущий текст и основание правки. Записи с явно указанной зависимостью от прежней версии выходят из обращения. [API памяти](https://github.com/28naem-del/mnemosyne/blob/main/docs/api.md) · [стабильный выпуск](https://github.com/28naem-del/mnemosyne/releases) | Подходит как ядро общей базы. Для нескольких агентов нужно общее рабочее пространство и явно опубликованные в нём записи. Ссылку на источник передаёт вызывающая сторона. Ей же нужно проверять содержимое источника и указывать зависимости. [Развёртывание](https://github.com/28naem-del/mnemosyne/blob/main/docs/deployment.md) · [контракт записи](https://github.com/28naem-del/mnemosyne/blob/main/docs/api.md) |
| **5. LongMemory** · 4 585 звёзд | При поиске умеет заново сверять утверждение с внешним фактом и возвращать вид источника, его свежесть и причину включения в ответ. Для независимых утверждений можно сохранить обе версии с предупреждением о споре. Доступны история и разные режимы поиска для планирования и кода. [Проверка при чтении](https://github.com/CaviraOSS/LongMemory/blob/main/docs/world-grounded-recall.md) · [режимы и история](https://github.com/CaviraOSS/LongMemory/blob/main/docs/project-memory.md) | Штатный запрос ограничен одним проектом. Для командного контекста потребуется завести общий проект в LongMemory и собирать туда межпроектные сведения. Интеграция должна обновлять внешние факты и подавать независимые свидетельства с `replace_current: false`, иначе новая запись на ту же тему может заместить прежнюю. [Границы поиска и правила записи](https://github.com/CaviraOSS/LongMemory/blob/main/docs/project-memory.md) |

## Как граница автономности повлияла на выбор

Для оценки обоих главных рисков — слабого обоснования и устаревших знаний — я использовал один пример с тайм-аутом. У рассмотренных инструментов есть отдельные механизмы для такого случая. Готовый процесс, который сам меняет порог обращения к человеку между спецификацией и реализацией, по открытым материалам подтвердить не удалось.

- **Обычное обновление.** Старая заметка указывает 30 секунд, а код и тест в новой ревизии показывают 60. Агент сам обновляет запись о текущей реализации. В журнале остаются прежнее и новое значения, ссылки на версии, автор, время и причина. Если спецификация по-прежнему требует 30 секунд, агент сохраняет это как отдельное требование.
- **Прямое противоречие.** Два действующих источника требуют 30 и 60 секунд для одного вызова в одном окружении. Агент сохраняет обе ссылки, помечает вопрос как спорный и передаёт его человеку. При подготовке спецификации поводом спросить служит уже неоднозначность требования. При реализации по утверждённой спецификации агент останавливает зависящий от ответа шаг, а независимые задачи может продолжать.

## Основания отбора

В исходном обзоре **103 проекта**. Единственным жёстким фильтром были **100 звёзд GitHub**. Порог прошли **72 проекта**, у 30 было меньше 100 звёзд, у Recoll официальный репозиторий находится на Framagit. Из 72 проектов 11 сравнили подробнее. Места в пятёрке определили по качеству свидетельств, пересмотру устаревших выводов и возможности проверить самостоятельную правку агента. Общий поиск, начальная загрузка и повседневная запись также влияли на выбор. Готовые коннекторы учитывались как преимущество. Оценка опирается на документацию и исходный код, без испытаний на данных команды. [Исходный обзор](research.md) · [репозиторий Recoll](https://recoll.org/pages/download.html)

Из ближайших альтернатив **Graphiti** может закрыть период действия прежнего факта при появлении противоречащего эпизода. Для двух одновременно действующих оснований пришлось бы добавить правило разбора спора. **AWS Labs GraphRAG Toolkit**, **LightRAG** и **Quivr** хорошо связывают результаты с документами, но для исправлений отдельных командных выводов с историей потребуется больше собственной логики. **Haft** и **MEX** сильны в работе с решениями и кодом конкретного проекта. [Graphiti](https://github.com/getzep/graphiti) · [AWS Labs GraphRAG Toolkit](https://awslabs.github.io/graphrag-toolkit/lexical-graph/versioned-updates/) · [LightRAG](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md) · [Quivr](https://github.com/The-Vibe-Company/quivr) · [Haft](https://haft.tools/docs/cross-project/) · [MEX](https://github.com/mex-memory/mex/blob/v0.8.5/README.md)

Число звёзд зафиксировано **21 ноября 2026 года в 10:47 МСК** по полю `stargazers_count` GitHub REST API. Для Onyx учтена открытая редакция `onyx-foss`. Для BookStack и Datafari взяты репозитории авторов на GitHub, хотя разработка переехала на другие площадки. [GitHub REST API](https://docs.github.com/en/rest/repos/repos#get-a-repository) · [BookStack](https://www.bookstackapp.com/blog/project-migrated-to-codeberg/) · [Datafari](https://gitlab.datafari.com/datafari-community/datafari)

<details>
<summary>Прошли порог · 72 проекта в порядке убывания числа звёзд</summary>

| Проект из исходного обзора | Звёзды GitHub |
| --- | ---: |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 94 494 |
| [Mem0](https://github.com/mem0ai/mem0) | 69 292 |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | 68 475 |
| [Hindsight](https://github.com/vectorize-io/hindsight) | 62 300 |
| [LlamaIndex Framework](https://github.com/run-llama/llama_index) | 52 973 |
| [OpenViking](https://github.com/volcengine/OpenViking) | 42 549 |
| [Open Notebook](https://github.com/lfnovo/open-notebook) | 42 107 |
| [LightRAG](https://github.com/HKUDS/LightRAG) | 40 795 |
| [Quivr](https://github.com/The-Vibe-Company/quivr) | 39 655 |
| [LangExtract](https://github.com/google/langextract) | 39 348 |
| [Khoj](https://github.com/khoj-ai/khoj) | 38 191 |
| [WeKnora](https://github.com/Tencent/WeKnora) | 37 926 |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | 36 708 |
| [Backstage](https://github.com/backstage/backstage) | 34 894 |
| [Cognee](https://github.com/topoteretes/cognee) | 33 442 |
| [GBrain](https://github.com/garrytan/gbrain) | 33 355 |
| [Graphiti](https://github.com/getzep/graphiti) | 32 972 |
| [QMD](https://github.com/tobi/qmd) | 31 310 |
| [Wiki.js](https://github.com/requarks/wiki) | 29 344 |
| [Haystack](https://github.com/deepset-ai/haystack) | 27 067 |
| [kotaemon](https://github.com/Cinnamon/kotaemon) | 25 925 |
| [BookStack](https://github.com/BookStackApp/BookStack) | 19 149 |
| [DocsGPT](https://github.com/arc53/DocsGPT) | 18 374 |
| [Memvid](https://github.com/memvid/memvid) | 17 434 |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | 16 207 |
| [Zotero](https://github.com/zotero/zotero) | 16 004 |
| [OpenMetadata](https://github.com/open-metadata/OpenMetadata) | 15 827 |
| [memU](https://github.com/NevaMind-AI/memU) | 14 630 |
| [EverOS](https://github.com/EverMind-AI/EverOS) | 13 959 |
| [DataHub Core](https://github.com/datahub-project/datahub) | 13 007 |
| [MemOS](https://github.com/MemTensor/MemOS) | 12 468 |
| [PaperQA](https://github.com/Future-House/paper-qa) | 9 632 |
| [KAG / OpenSPG](https://github.com/OpenSPG/KAG) | 9 183 |
| [Engram](https://github.com/Gentleman-Programming/engram) | 8 250 |
| [Honcho](https://github.com/plastic-labs/honcho) | 8 213 |
| [R2R](https://github.com/SciPhi-AI/R2R) | 8 103 |
| [Airweave](https://github.com/airweave-ai/airweave) | 6 542 |
| [OpenGrok](https://github.com/oracle/opengrok) | 5 033 |
| [OpenRAG](https://github.com/langflow-ai/openrag) | 4 692 |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | 4 651 |
| [LongMemory](https://github.com/CaviraOSS/LongMemory) | 4 585 |
| [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | 4 445 |
| [HippoRAG 2](https://github.com/OSU-NLP-Group/HippoRAG) | 4 137 |
| [Fast GraphRAG](https://github.com/circlemind-ai/fast-graphrag) | 3 972 |
| [Letta Code](https://github.com/letta-ai/letta-code) | 3 887 |
| [ReMe](https://github.com/agentscope-ai/ReMe) | 3 827 |
| [Hypothesis](https://github.com/hypothesis/h) | 3 189 |
| [TrustGraph](https://github.com/trustgraph-ai/trustgraph) | 3 131 |
| [MemMachine](https://github.com/MemMachine/MemMachine) | 3 089 |
| [SWIRL Community](https://github.com/swirlai/swirl-search) | 3 048 |
| [Memobase](https://github.com/memodb-io/memobase) | 2 962 |
| [mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) | 2 138 |
| [Zoekt](https://github.com/sourcegraph/zoekt) | 2 087 |
| [MEX](https://github.com/mex-memory/mex) | 1 797 |
| [LangMem](https://github.com/langchain-ai/langmem) | 1 780 |
| [OpenLore](https://github.com/aakarim/openlore) | 1 713 |
| [GUAC](https://github.com/guacsec/guac) | 1 579 |
| [Haft](https://github.com/m0n0x41d/haft) | 1 400 |
| [XWiki](https://github.com/xwiki/xwiki-platform) | 1 336 |
| [Neo4j GraphRAG for Python](https://github.com/neo4j/neo4j-graphrag-python) | 1 335 |
| [KGGen](https://github.com/stair-lab/kg-gen) | 1 297 |
| [Open Semantic Search](https://github.com/opensemanticsearch/open-semantic-search) | 1 235 |
| [Fess](https://github.com/codelibs/fess) | 1 151 |
| [iText2KG / ATOM](https://github.com/AuvaLab/itext2kg) | 980 |
| [Docling Graph](https://github.com/docling-project/docling-graph) | 947 |
| [GrimoireLab](https://github.com/chaoss/grimoirelab) | 642 |
| [AWS Labs GraphRAG Toolkit](https://github.com/awslabs/graphrag-toolkit) | 467 |
| [Onyx Community Edition](https://github.com/onyx-dot-app/onyx-foss) | 322 |
| [OpenAleph](https://github.com/openaleph/openaleph) | 165 |
| [Mnemosyne](https://github.com/28naem-del/mnemosyne) | 162 |
| [Wikibase](https://github.com/wikimedia/mediawiki-extensions-Wikibase) | 145 |
| [OpenDocuments](https://github.com/joungminsung/OpenDocuments) | 126 |

</details>

<details>
<summary>30 проектов ниже порога</summary>

| Проект из исходного обзора | Звёзды GitHub |
| --- | ---: |
| [Datafari Community](https://github.com/francelabs/datafari) | 96 |
| [Open Knowledge](https://github.com/openknowledge-sh/openknowledge) | 78 |
| [Palinode](https://github.com/phasespace-labs/palinode) | 46 |
| [Nanodash / Nanopublications](https://github.com/knowledgepixels/nanodash) | 43 |
| [Kage](https://github.com/kage-core/Kage) | 41 |
| [Dense-Mem](https://github.com/markhuangai/dense-mem) | 40 |
| [Evidence Lab](https://github.com/dividor/evidencelab) | 39 |
| [pghacker-mcp](https://github.com/Azure-Samples/pghacker-mcp) | 27 |
| [ContextMine](https://github.com/mayflower/contextmine) | 24 |
| [ContextNest](https://github.com/PromptOwl/ContextNest) | 22 |
| [DocIngest](https://github.com/Amal-David/docingest) | 22 |
| [TeamBrain](https://github.com/donatienmigue/TeamBrain) | 14 |
| [llm-wiki-go](https://github.com/olegiv/llm-wiki-go) | 13 |
| [memex](https://github.com/STiFLeR7/memex) | 12 |
| [Mem++](https://github.com/AIDAChip-Inc/mem-plus-plus) | 10 |
| [Infinity Context](https://github.com/777genius/infinity-context) | 8 |
| [Epistemedia](https://github.com/yoheinakajima/epistemedia) | 5 |
| [stalebrain](https://github.com/stalebrainlabs/stalebrain) | 5 |
| [Agora KB](https://github.com/handochan/agora-kb) | 4 |
| [MemoryGuard](https://github.com/MerakOsiris/memoryguard) | 4 |
| [GraphRAGProv](https://github.com/wadie999/graphragprov) | 4 |
| [Qarinah](https://github.com/AjnasNB/qarinah) | 3 |
| [OpenShelf](https://github.com/vecbase-labs/OpenShelf) | 3 |
| [Woxpas Memory](https://github.com/woxpas/memory) | 2 |
| [DocSanctum](https://github.com/DocSanctum/doc-sanctum) | 2 |
| [Git2KG](https://github.com/lennart-h/git2kg) | 1 |
| [ClaimTrace](https://github.com/hasibagen/claimtrace) | 0 |
| [Evidence Tracer](https://github.com/QI-Data-Lab/Evidence-Tracer) | 0 |
| [MainRag](https://github.com/silentspike/mainrag) | 0 |
| [git-wik](https://github.com/suhaani-agarwal/git-wik) | 0 |

</details>
