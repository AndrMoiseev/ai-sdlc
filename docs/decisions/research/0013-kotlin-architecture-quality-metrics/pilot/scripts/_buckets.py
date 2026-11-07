"""Общая классификация путей по корзинам (контексты AGENTS.md / плоские пакеты).

Используется report.py и coverage.py. Изменение списка контекстов — здесь.
"""

CONTEXTS = {
    'brand', 'catalog', 'categorization', 'matching', 'offline',
    'orchestration', 'settings', 'groupidReconcile', 'deduplication',
}


def classify(path: str) -> str:
    """Путь -> корзина: ctx:<name> | flat:<pkg> | test-ctx:<n> | test-flat:<p> | res | lib | infra."""
    p = path.replace('file://', '')
    for side, tag in (('app/src/main/kotlin/ru/tbank/gp/matcher/', ''),
                      ('app/src/test/kotlin/ru/tbank/gp/matcher/', 'test-')):
        if p.startswith(side):
            seg = p[len(side):].split('/')
            if seg[0] in CONTEXTS:
                prefix = f'{tag}ctx:' if not tag else f'{tag}-ctx:'
                return prefix + seg[0]
            if len(seg) == 1:  # файл в корне пакета matcher/
                return f'{tag}flat:_root'
            return f'{tag}flat:{seg[0]}'
    if p.startswith('app/src/main/resources/'):
        return 'res'
    if p.startswith('lib/'):
        return 'lib'
    return 'infra'
