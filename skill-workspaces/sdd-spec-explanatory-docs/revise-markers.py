import json
from pathlib import Path
root=Path(__file__).parent/'markers/sdd/changes/sample-change/archify'
for kind in ['architecture','workflow','sequence']:
    path=root/kind/'candidate.json'
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    obj['cards'][0]['items']=['[=] existing / unchanged; [+] added; [~] changed; [-] removed', 'Node and relationship statuses are independent.', 'BEFORE retains the removed retry write; AFTER returns 410 without a write.']
    nodes=obj.get('components',obj.get('nodes',obj.get('participants')))
    for node in nodes:
        sub=node['sublabel']
        mark='[-]' if sub.startswith('REMOVED') else '[+]' if sub.startswith('NEW') else '[=]'
        role=sub.split(' / ',1)[1]
        if kind=='sequence': node['sublabel']=mark+' '+role
        else:
            node['tag']=mark
            node['sublabel']=role
    edges=obj.get('connections',obj.get('edges',obj.get('messages')))
    for edge in edges:
        for old,new in [('OLD:','[=]'),('NEW:','[+]'),('CHG:','[~]'),('REMOVED:','[-]')]:
            edge['label']=edge['label'].replace(old,new)
    if kind=='architecture':
        payment=obj['components'][-1]
        payment.update(type='backend',label='Payment Service',sublabel='refund handler',tag='[=]')
        obj['connections'][1]['label']='[+] keyed refund'
    if kind=='sequence':
        obj['meta']['viewBox']=[900,540]
        obj['meta']['column_fit']='spread'
        obj['participants'][2].update(type='backend',label='Worker',sublabel='[+] async processor')
        obj['messages'][1].update(label='[+] async OrderCreated',variant='dashed',note='New asynchronous event; caller does not wait for worker completion.')
        obj['messages'][2].update(label='[+] async receipt',variant='return',note='Receipt follows asynchronous processing; not a blocking request return.')
        obj['messages'][3]['note']='[~] Changed response from the existing API participant; returns the previously stored order.'
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
