# Локальные источники для показателей качества

Снимки первоисточников для [предложения интегральных показателей](../quality-indicators-proposal.md). Для повторного чтения и поиска использовать эти файлы; обращаться к сайту нужно при намеренном обновлении источника или поиске новых сведений.

Оригиналы PDF, HTML и Kotlin сохранены без правок. Текстовые копии предназначены для поиска и могут терять порядок колонок, таблицы и математическую разметку: формулы проверяются по оригинальным PDF. HTML-копии содержат документ, но внешние изображения, стили и скрипты отдельно не скачивались.

| Источник | Локальный оригинал | Текст для поиска | Исходный адрес |
| --- | --- | --- | --- |
| Mo и соавторы, Decoupling Level, ICSE 2016 | [PDF](decoupling-level-icse2016.pdf) | [TXT](decoupling-level-icse2016.txt) | [Сайт автора](https://ranmo.github.io/papers/icse2016-DL.pdf) |
| Cai и соавторы, Leveraging design rules to improve software architecture recovery, QoSA 2013 | [PDF](archdrh-qosa2013.pdf) | [TXT](archdrh-qosa2013.txt) | [Drexel University](https://www.cs.drexel.edu/~yc349/papers/2013/QoSA2013.pdf) |
| G. Ann Campbell, Cognitive Complexity, версия 1.7 от 29 августа 2023 | [PDF](cognitive-complexity-sonarsource-2023.pdf) | [TXT](cognitive-complexity-sonarsource-2023.txt) | [SonarSource](https://www.sonarsource.com/docs/CognitiveComplexity.pdf) |
| Heitlager, Kuipers, Visser, A Practical Model for Measuring Maintainability, 2007 | [PDF](sig-maintainability-model-2007.pdf) | [TXT](sig-maintainability-model-2007.txt) | [SIG](https://softwareimprovementgroup.com/wp-content/uploads/APracticalModelForMeasuringMaintainability.pdf) |
| JaCoCo Coverage Counters, снимок trunk | [HTML](jacoco-coverage-counters.html) | [TXT](jacoco-coverage-counters.txt) | [JaCoCo](https://www.jacoco.org/jacoco/trunk/doc/counters.html) |
| Alberto Savoia, This Code is CRAP, 22 февраля 2011 | [HTML](crap-alberto-savoia-2011.html) | [TXT](crap-alberto-savoia-2011.txt) | [Google Testing Blog](https://testing.googleblog.com/2011/02/this-code-is-crap.html) |
| detekt Complexity Rule Set, версия 1.23.8 | [HTML](detekt-1.23.8-complexity.html) | [TXT](detekt-1.23.8-complexity.txt) | [detekt](https://detekt.dev/docs/1.23.8/rules/complexity/) |
| detekt CognitiveComplexMethod, tag v1.23.8 | [Kotlin](detekt-1.23.8-CognitiveComplexMethod.kt) | Тот же файл | [Исходник правила](https://raw.githubusercontent.com/detekt/detekt/v1.23.8/detekt-rules-complexity/src/main/kotlin/io/gitlab/arturbosch/detekt/rules/complexity/CognitiveComplexMethod.kt) |
| detekt CognitiveComplexity, tag v1.23.8 | [Kotlin](detekt-1.23.8-CognitiveComplexity.kt) | Тот же файл | [Исходник вычислителя](https://raw.githubusercontent.com/detekt/detekt/v1.23.8/detekt-metrics/src/main/kotlin/io/github/detekt/metrics/CognitiveComplexity.kt) |
| NIST, Modified condition decision coverage | [HTML](nist-modified-condition-decision-coverage.html) | [TXT](nist-modified-condition-decision-coverage.txt) | [NIST CSRC](https://csrc.nist.gov/glossary/term/modified_condition_decision_coverage) |

[manifest.json](manifest.json) содержит для каждого оригинала URL, редакцию, время получения UTC, размер и SHA-256; для извлечений — имя, SHA-256 и средство извлечения. Дата получения не заменяет дату публикации. Для изменяемых страниц, включая JaCoCo trunk, первичным свидетельством является сохранённый снимок с указанным hash.

PDF извлечены с помощью pypdf 7.0.0 и fonttools 4.68.0. HTML преобразованы стандартным `html.parser` Python 3.14 с удалением содержимого script/style/noscript и нормированием whitespace. Извлечения не заменяют оригиналы и не являются новыми редакциями авторских работ.

Сохраняются авторство и уведомления внутри оригинальных документов. Локальные копии и извлечения не переводят материалы третьих лиц под лицензию этого репозитория. Загруженные исходники detekt служат свидетельством определения метрики и не подключены к исполняемому коду проекта.
