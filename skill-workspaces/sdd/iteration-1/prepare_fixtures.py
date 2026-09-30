# /// script
# dependencies = ["PyYAML>=6", "markdown-it-py>=3"]
# ///
import json,pathlib,sys,yaml,copy
HERE=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path((HERE/'temp-root.txt').read_text(encoding='utf-8-sig').strip())
sys.path.insert(0,str(ROOT/'candidate/scripts'))
from lib.snapshots import snapshot
def doc(path,kind,body='',records=(),**extra):
 meta=dict(schema_version=1,document_type=kind,change_id='sample-change',language='ru',**extra)
 yaml.SafeDumper.ignore_aliases=lambda self,data:True
 text='---\n'+yaml.safe_dump(meta,allow_unicode=True,sort_keys=False)+'---\n\n'+body+'\n'
 for rec in records:text+='\n### '+rec['id']+'\n\n```yaml\n'+yaml.safe_dump(rec,allow_unicode=True,sort_keys=False)+'```\n'
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
for run in json.loads((HERE/'runs.json').read_text()):
 if run['eval_id']!=1:continue
 root=pathlib.Path(run['fixture']);change=root/'sdd/changes/sample-change'
 (root/'docs').mkdir(exist_ok=True)
 (root/'docs/orders.md').write_text('# Orders\n\n### Retry endpoint\nPOST /orders/{id}/retry retries an order.\n',encoding='utf-8')
 doc(change/'proposal.md','proposal','# Повтор заказа и удаление retry\nПовтор ключа возвращает существующий заказ. Удаляем retry endpoint с результатом 410. Объем: specs/orders/spec.md. Другие API не меняются.')
 doc(change/'specs/orders/spec.md','spec','# Orders',[
 dict(sdd_record='requirement',id='REQ-reuse-order',operation='add'),
 dict(sdd_record='acceptance',id='AC-reuse-order',requirement='REQ-reuse-order',conditions='POST /orders повторяет уже сохраненный Idempotency-Key с тем же запросом',expected='Возвращается прежний order_id; новый заказ не создается'),
 dict(sdd_record='requirement',id='REQ-remove-retry',operation='remove',source=dict(kind='specification',path='docs/orders.md',requirement='Retry endpoint')),
 dict(sdd_record='acceptance',id='AC-retry-gone',requirement='REQ-remove-retry',conditions='POST /orders/{id}/retry вызывается после удаления retry',expected='Ответ HTTP 410; повторное исполнение заказа не запускается')],capability='orders')
 doc(change/'design.md','design','# Дизайн\nОбработчик orders сохраняет связь Idempotency-Key с order_id и возвращает существующую запись при повторе. Обработчик retry становится 410 tombstone. Тестовая инфраструктура отсутствует; подготовить локальный запуск внутри задач. Новых вопросов нет.',[dict(sdd_record='decision',id='DEC-preserve-key-map',requirements=['REQ-reuse-order'])])
 manifest=snapshot(root,'sample-change','documents');runid='20260929T120000Z-fixture'
 doc(change/f'review/{runid}/consistency.md','review','# Синтетический отчет\nНезависимый рецензент fixture проверил согласованность; находок нет. Эта запись является входом синтетического сценария, а не реальным проектным ревью.',run_id=runid,stage='document_review',lens_id='consistency',result='completed_no_findings',started_at='2026-09-29T12:00:00Z',finished_at='2026-09-29T12:01:00Z',inputs=manifest,inputs_after=manifest,freshness='current',limitations=[])
 recs=[]
 for rid,kind,response in [('USER-documents','document_approval','Согласовываю текущие specs и design sample-change.'),('USER-plan','planning_command','Создай только tasks.md для согласованного sample-change; реализацию не начинай.')]:
  scope={'stage':'document_review'}
  if kind=='planning_command':scope['work']='Подготовить только tasks.md для двух существующих AC sample-change'
  recs.append(dict(sdd_record='user',id=rid,kind=kind,scope=scope,response=response,date='2026-09-29T12:02:00Z',inputs=manifest,status='active'))
 doc(change/'review/decisions.md','decisions','# История синтетического сценария\nНиже явные ответы пользователя внутри fixture. Это не утверждение об ответах реального пользователя вне оценки.',recs)
 doc(change/'state.md','state','# Следующий шаг\nСоздать tasks.md по USER-plan. Блокирующих вопросов нет.',phase='planning',awaiting='none',updated_at='2026-09-29T12:03:00Z',document_links=['proposal.md','design.md','specs/orders/spec.md'],review_links=[f'review/{runid}/consistency.md','review/decisions.md'],approval_refs=['USER-documents','USER-plan'])
 prompt=pathlib.Path(run['prompt']);note='Входные документы и подтвержденная история сценария находятся в sdd/changes/sample-change/. Все решения в fixture являются заданными фактами этого синтетического сценария. Прочти их; не запрашивай повторное подтверждение.'
 original=prompt.read_text(encoding='utf-8').replace(note,'').rstrip()
 prompt.write_text(original+'\n'+note+'\n',encoding='utf-8')
 print(root)
