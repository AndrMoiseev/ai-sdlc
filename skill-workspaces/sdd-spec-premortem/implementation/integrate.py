"""Apply the planned documentation change after baseline capture."""
from pathlib import Path
import re
import sys

work = Path(__file__).resolve().parent
root = work.parents[2]
skill = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'skills/sdd-spec'

def edit(path, old, new):
    file = skill / path
    text = file.read_text(encoding='utf-8')
    assert text.count(old) == 1, (path, old)
    file.write_text(text.replace(old, new), encoding='utf-8')

def step(path, number, text):
    file = skill / path
    source = file.read_text(encoding='utf-8')
    source = re.sub(r'^(\d+)\. ', lambda m: f'{int(m[1])+1}. ' if int(m[1]) >= number else m[0], source, flags=re.M)
    anchor = f'{number+1}. '
    offset = source.index(anchor)
    source = source[:offset] + f'{number}. {text}\n' + source[offset:]
    file.write_text(source, encoding='utf-8')

(skill/'references/premortem.md').write_text((work/'premortem-reference.md').read_text(encoding='utf-8'), encoding='utf-8')
(skill/'templates/premortem.md').write_text((work/'premortem-template.md').read_text(encoding='utf-8'), encoding='utf-8')
step('flows/explore.md', 2, 'После установления цели и контекста выполни короткий [премортем](../references/premortem.md) или используй актуальный сохранённый разбор. Сохрани итог до перехода к подробной спецификации; возникающие вопросы обработай по следующим шагам.')
edit('flows/explore.md', '4. Задай один сфокусированный вопрос,', '4. При конкретной существенной неопределённости задай один сфокусированный вопрос,')
step('flows/draft.md', 3, 'Установив цель и контекст, прочитай [премортем](../references/premortem.md): используй актуальный разбор либо выполни короткую проверку и сохрани итог до подробной спецификации. Прямой draft и малое изменение проходят ту же проверку. Выбранные по находкам цель, поведение и подход перенеси в proposal, specs с AC и design по их назначению; предложения сохраняй отдельно.')
step('flows/resume.md', 3, 'Проверь сохранённый [премортем](../references/premortem.md): прочитай краткий итог и документ по ссылке, сопоставь основания с текущими источниками. При актуальном разборе используй прежние ответы; при изменениях пересмотри затронутую часть. Отсутствующую запись, недоступный документ или источник обработай по правилам восстановления справочника.')
step('flows/revise.md', 3, 'При изменении цели, существенной предпосылки или противоречащих данных пересмотри затронутую часть [премортема](../references/premortem.md), сохраняя остальные выводы. Выбранное пользователем изменение поведения отрази в specs с AC и связанных proposal/design. Правка только premortem.md не меняет нормативный манифест; проверь, не требует ли её смысл нормативной правки.')
edit('templates/state.md', '## Проверки', '''## Премортем

После проверки оставьте один краткий итог: «Премортем: находок нет» либо
«Есть находки: [premortem.md](premortem.md)». Во втором случае добавьте
существующий документ в document_links. Сценарии и основания храните в нём;
Q-записи остаются в state. После закрытия всех находок сохраните ссылку:
«Открытых находок нет; история: [premortem.md](premortem.md)».
До выполнения проверки не отмечайте её завершённой.

## Проверки''')
edit('references/document-format.md', '## Идентичность и трассировка', '''## Премортем

`premortem.md` в каталоге изменения хранит исследование по
[контракту премортема](premortem.md); создавай его только при находках по
[шаблону](../templates/premortem.md). Это обычный Markdown без frontmatter,
нового document_type, sdd_record или вида USER. Заголовки находок служат
якорями; вопросы используют существующие Q-ID в state, а не FIND ревью.

Раздел «Премортем» в state содержит краткий итог: отсутствие находок либо
наличие находок со ссылкой на документ. Закрытые находки и ссылка сохраняются.
Разбор не входит в манифест documents или plan. Выбранные изменения цели,
поведения и подхода переноси в proposal, specs с AC и design; после нормативной
правки действуют обычные правила актуальности ревью и согласований.
Завершение проверки не заменяет условия перехода к плану.

## Идентичность и трассировка''')
edit('references/document-format.md', 'State, review, внешние источники и инструкции линз исключены.', 'State, review, premortem.md, внешние источники и инструкции линз исключены.')
edit('references/editorial-pass.md', '   и производных сводках, explanation.md, документах explanation/, авторской', '   и производных сводках, premortem.md, explanation.md, документах explanation/, авторской')
(skill/'evals/evals.json').write_text((work/'planned-evals.json').read_text(encoding='utf-8'), encoding='utf-8')
manual = skill/'evals/manual.md'
manual.write_text(manual.read_text(encoding='utf-8') + '\n' + (work/'manual-premortem.md').read_text(encoding='utf-8'), encoding='utf-8')
print('Applied premortem documentation and evals; scripts and schema unchanged')
