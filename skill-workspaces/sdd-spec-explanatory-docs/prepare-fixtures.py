"""Prepare local inputs only. Does not invoke an LLM or change installed skills."""
import hashlib
import json
import shutil
from pathlib import Path

workspace = Path(__file__).parent
repo = workspace.parents[1]
base = workspace / 'fixtures/base/sdd/changes/sample-change'

def write(name, kind, body, extra=''):
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\nschema_version: 1\ndocument_type: {kind}\nchange_id: sample-change\nlanguage: ru\n{extra}---\n{body}\n', encoding='utf-8')

write('proposal.md','proposal','# Заказы и возвраты\nИзменение предотвращает повторное создание заказа и убирает опасный повтор возврата. Область: [заказы](specs/orders/spec.md), [возвраты](specs/refunds/spec.md). Публичный API сохраняется; новый worker обрабатывает сообщения. Область пояснения: оба процесса. Исходное поведение внешнего обработчика неизвестно.')
write('design.md','design','# Дизайн\nСуществуют Client, API, Orders DB и Payment Service. Связь API -> Orders DB для чтения заказа остается без изменений. При повторе ключа API возвращает прежний заказ. Новый worker получает асинхронное сообщение OrderCreated. Отказ платежного сервиса завершает создание без нового заказа.\nДля возврата прежний Payment Service получает измененное сообщение RefundRequested с ключом; возвращает подтверждение API. Устаревший retry endpoint прежде повторял возврат, теперь отвечает 410 без вызова Payment Service. Поведение внешнего обработчика неизвестно и не реконструируется. Отдельный сценарий меняет только пользовательский текст подтверждения; компонентов или связей он не меняет.')
for capability, description, criteria in [
    ('orders','API возвращает прежний заказ при повторе ключа; новый worker принимает асинхронное сообщение создания; отказ оплаты завершает процесс.', [('repeat','Повтор использованного ключа','Прежний заказ без второй записи'),('async','Заказ создан','Worker получает асинхронное OrderCreated'),('decline','Платеж отклонен','Процесс завершается без нового заказа')]),
    ('refunds','Прежний Payment Service принимает RefundRequested с ключом и подтверждает возврат; retry endpoint отвечает 410; текст подтверждения меняется.', [('refund','Запрошен возврат','Payment Service подтверждает возврат с ключом'),('retired','Вызван retry endpoint','HTTP 410 без вызова Payment Service'),('wording','Возврат подтвержден','Текст: Возврат принят')])]:
    body=f'# {capability}\n```yaml\nsdd_record: requirement\nid: REQ-{capability}\noperation: add\n```\n{description}\n'
    for ident,condition,expected in criteria:
        body+=f'```yaml\nsdd_record: acceptance\nid: AC-{ident}\nrequirement: REQ-{capability}\nconditions: {condition}\nexpected: {expected}\n```\n'
    write(f'specs/{capability}/spec.md','spec',body,f'capability: {capability}\n')
write('state.md','state','# Точка продолжения\n## Поручение\nЯвный запрос пользователя: подготовить пояснение обоих процессов по существующим документам. Основной комплект не менять, код не реализовывать; ревью и планирование не поручены. Частично готовых пояснений пока нет.',"phase: drafting\nawaiting: none\nupdated_at: '2026-10-02T00:00:00Z'\ndocument_links: [proposal.md, design.md, specs/orders/spec.md, specs/refunds/spec.md]\nreview_links: []\napproval_refs: []\n")
manifest={str(p.relative_to(base)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.md')}
(workspace/'fixtures/base-inputs.sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
evals=json.loads((repo/'skills/sdd-spec/evals/evals.json').read_text(encoding='utf-8-sig'))['evals']
for case in evals:
    if not case['name'].startswith('explanation-'):
        continue
    target=workspace/'fixtures'/case['name']
    if not target.exists():
        shutil.copytree(workspace/'fixtures/base',target)
    (target/'prompt.txt').write_text(case['prompt'],encoding='utf-8')
    metadata=workspace/'prepared'/case['name']/'eval_metadata.json'
    if metadata.exists():
        meta=json.loads(metadata.read_text(encoding='utf-8-sig'))
        meta['execution_status']='skipped-per-user-local-only'
        meta['fixture_status']='base-prepared; variants-require-manual-setup'
        meta['notes']='No LLM run authorized. Base fixtures exist; real/mocked browser variants must be configured explicitly.'
        metadata.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared base + 9 scenario inputs; browser receipts and multi-turn variants require manual setup; no LLM executed.')
