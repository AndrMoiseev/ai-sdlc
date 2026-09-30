import json,pathlib,hashlib
HERE=pathlib.Path(__file__).resolve().parent
rows=[]
for run in json.loads((HERE/'runs.json').read_text()):
 out=pathlib.Path(run['output']);trace=out/'stdout.jsonl'
 if not trace.exists():continue
 events=[json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines() if line.strip()]
 items=[e['item'] for e in events if e.get('type')=='item.completed' and 'item' in e]
 commands=[i for i in items if i.get('type')=='command_execution']
 messages=[i.get('text','') for i in items if i.get('type')=='agent_message']
 candidate_reads=[i['command'] for i in commands if 'candidate' in i.get('command','')]
 repository_reads=[i['command'] for i in commands if 'repos' in i.get('command','').lower() and 'ai-sdlc' in i.get('command','').lower()]
 rows.append(dict(eval_id=run['eval_id'],rep=run['rep'],variant=run['variant'],tool_calls=len(commands),nonzero_commands=sum(i.get('exit_code',0)!=0 for i in commands),candidate_path_commands=candidate_reads,original_repository_path_commands=repository_reads,catalog_messages=[m for m in messages if 'каталог' in m.lower() or 'catalog' in m.lower()]))
 metrics={'total_tool_calls':len(commands),'errors_encountered':None,'nonzero_command_exits':sum(i.get('exit_code',0)!=0 for i in commands),'output_chars':len((out/'response.md').read_text(encoding='utf-8')),'transcript_chars':len(trace.read_text(encoding='utf-8'))}
 (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
(HERE/'trace-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Audited {len(rows)} traces; baseline candidate reads: {sum(bool(r["candidate_path_commands"]) for r in rows if r["variant"]=="without_skill")}; original repository command references: {sum(bool(r["original_repository_path_commands"]) for r in rows)}')
