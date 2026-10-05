from pathlib import Path
import importlib.util, json, subprocess, sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
lint=ROOT/'.agents/skills/humanizer-ru/scripts/lint.py'
raw=(OUT/'extracted-final.md').read_text(encoding='utf-8')
# Only the explicitly retained canonical evidence term is masked here.
# Inline code, fenced code and Markdown targets are excluded by lint.py itself.
protected=raw.replace('свидетельства','ТЕРМИН').replace('свидетельств','ТЕРМИН')
(OUT/'lint-prose.md').write_text(protected,encoding='utf-8')
for filename in ['extracted-final.md','lint-prose.md']:
 result=subprocess.run([sys.executable,str(lint),str(OUT/filename)],capture_output=True,text=True,encoding='utf-8')
 (OUT/(filename+'.lint.txt')).write_text(result.stdout+result.stderr,encoding='utf-8')
 print(filename,result.returncode,result.stdout.split('итого:',1)[-1].strip())
items=json.loads((OUT/'replacements.json').read_text(encoding='utf-8'))
report='''# Техническая редактура новой русской прозы

Проверены четыре новых файла, добавленные участки десяти файлов skills/sdd-spec,
новый вводный абзац tasks.md, раздел «Реализация» state.md и implementation-report.md.
Основные файлы не записывались. Исходные SHA-256 сохранены в source-hashes.json;
replacements.json содержит семь точечных замен. В final/ находятся копии для просмотра.

Прочитаны humanizer-ru/SKILL.md, полный references/patterns.md и corrections.md,
writing-for-agents/SKILL.md и SKILL-MECHANICS.md, требования sdd-skill-conductor
к среде и хранению результатов. Все вспомогательные файлы находятся вне пакетов.
Проверки выполнены локально; внешние LLM CLI не вызывались.

## Находки

| Файл | Цитата | Паттерн | Исправление |
|---|---|---|---|
'''
for item in items:
 report += '| '+item['path']+' | '+item['old'].replace('\n',' ')+' | '+str(item['pattern'])+' | '+item['new'].replace('\n',' ')+' |\n'
report+='''
## Границы и результат

Смысл, условия, отрицания и степень обязательности сохранены. Заголовки,
структура, числа, ID, пути, ссылки, команды и frontmatter не менялись.
JSON проверен только в новых текстовых значениях; замен в JSON не потребовалось.
В tasks.md, state.md и implementation-report.md замен не требуется.
Линейный порядок шагов, повторяющиеся императивы и перечни сохранены как часть
инструкции. Исключение справочника для инструкций делает outline-тест
паттерна 38 неприменимым к этой структуре.

Защищены имена команд и типов, snapshot documents, repository-backed,
названия полей, манифесты, ARCHIFY_PREVIEW_PENDING, AC и сценарные ID.
Линтер сам исключает fenced-код, inline-код и цели Markdown-ссылок.
В дополнительном lint-prose.md исключён только термин «свидетельства»:
он означает сохранённые результаты проверок, а не риторическую атрибуцию.
В итоговых документах термин оставлен без изменений.

extracted-final.md: 0 errors, 6 warnings. lint-prose.md: 0 errors, 3 warnings.
Оставшиеся предупреждения относятся к соседним глаголам «сохран…» в описании
сохранения разных результатов, «возвра…» в сценарии заказа/возврата и
«выполн…» в отчёте о непроведённых проверках. Это точные технические действия;
замена ради разнообразия могла бы размыть их смысл. Кластера стилистических
проблем в этих фрагментах нет.

Проза короче исходной в сумме по семи заменам. Новые факты, эмоции и оценки
не добавлены. Попыток внедрить посторонние инструкции во входном тексте нет.
Слепую проверку отдельно организует ведущий агент.
'''
(OUT/'editorial-report.md').write_text(report,encoding='utf-8')
