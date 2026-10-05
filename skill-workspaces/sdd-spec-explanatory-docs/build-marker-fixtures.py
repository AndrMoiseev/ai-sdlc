import json
from pathlib import Path

root = Path(__file__).parent / 'markers/sdd/changes/sample-change/archify'
cards = [{'dot':'cyan','title':'Change markers','items':['OLD = existing; NEW = added; CHG = changed interaction','Nodes and relationships carry independent change markers.','Retired retry write exists only in BEFORE; AFTER returns 410 without a write.']}]
def save(kind, body):
    folder = root / kind
    folder.mkdir(parents=True, exist_ok=True)
    doc = {'schema_version': 2 if kind == 'workflow' else 1, 'diagram_type':kind,
           'meta':{'title':'Order retry — independent markers', 'output':'diagram.html','quality_profile':'showcase'}, **body, 'cards':cards}
    (folder/'candidate.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
save('architecture', {'components':[
 {'id':'client','type':'external','label':'Client','sublabel':'OLD / HTTP caller','pos':[40,70],'size':[170,70]},
 {'id':'api','type':'backend','label':'Orders API','sublabel':'OLD / request handler','pos':[430,70],'size':[170,70]},
 {'id':'orders','type':'database','label':'Orders','sublabel':'OLD / stored orders','pos':[430,340],'size':[170,70]},
 {'id':'keys','type':'database','label':'Key index','sublabel':'NEW / deduplication','pos':[820,70],'size':[180,70]}],
 'connections':[
 {'id':'request','from':'client','to':'api','label':'OLD: POST order'},
 {'id':'lookup','from':'api','to':'keys','label':'NEW: lookup key'},
 {'id':'insert','from':'api','to':'orders','label':'CHG: insert if new key'}]})
save('workflow', {'lanes':[{'id':'flow','label':'AFTER: create order'},{'id':'before','label':'BEFORE: retired retry'}],
 'nodes':[
 {'id':'request','lane':'flow','col':0,'type':'external','label':'Request','sublabel':'OLD / HTTP POST','width':170},
 {'id':'lookup','lane':'flow','col':1,'type':'backend','label':'Check key','sublabel':'NEW / deduplicate','width':170},
 {'id':'reply','lane':'flow','col':2,'type':'backend','label':'Reply','sublabel':'OLD / HTTP response','width':170},
 {'id':'retry','lane':'before','col':0,'type':'backend','label':'Retry endpoint','sublabel':'REMOVED / old insert','width':170},
 {'id':'duplicate','lane':'before','col':1,'type':'database','label':'Second order','sublabel':'REMOVED / duplicate','width':170}],
 'edges':[
 {'id':'check','from':'request','to':'lookup','label':'NEW: key lookup'},
 {'id':'same','from':'lookup','to':'reply','label':'CHG: existing key -> 200'},
 {'id':'retired','from':'retry','to':'duplicate','label':'REMOVED: write again','variant':'dashed'}]})
save('sequence', {'participants':[
 {'id':'client','type':'external','label':'Client','sublabel':'OLD / caller'},
 {'id':'api','type':'backend','label':'API','sublabel':'OLD / handler'},
 {'id':'keys','type':'database','label':'Key index','sublabel':'NEW / keys'}],
 'messages':[
 {'id':'request','from':'client','to':'api','y':160,'label':'OLD: POST order','variant':'default'},
 {'id':'lookup','from':'api','to':'keys','y':200,'label':'NEW: lookup key','variant':'default'},
 {'id':'found','from':'keys','to':'api','y':245,'label':'NEW: saved order','variant':'return'},
 {'id':'reply','from':'api','to':'client','y':295,'label':'CHG: 200 same order','variant':'return'}]})
print(root)

