"""Normalize legacy native-executor artifacts only; never overwrite CLI telemetry."""
import json,pathlib
HERE=pathlib.Path(__file__).resolve().parent
for run in json.loads((HERE/'runs.json').read_text()):
 out=pathlib.Path(run['output'])
 if (out/'stdout.jsonl').exists():continue
 if not (out/'response.md').exists():continue
 timing=json.loads((out/'timing.json').read_text(encoding='utf-8-sig')) if (out/'timing.json').exists() else {}
 timing['total_duration_seconds']=timing.get('total_duration_seconds',timing.get('wall_elapsed_seconds'))
 timing['total_tokens']=None
 (out/'timing.json').write_text(json.dumps(timing,indent=2),encoding='utf-8')
 meta=dict(run,harness='native Codex subagent',model='inherited parent default; no override',fresh_context=True,status='completed',token_usage=None,transcript_available=False,isolation='Separate fixture outside repository ancestry; read scope enforced by executor prompt, not filesystem ACL. Inherited developer skill catalog present, candidate sdd absent per executor reports. Original repository still technically readable; no audit-grade filesystem isolation.')
 (out/'run.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 (out/'transcript.md').write_text('# Trace limitation\n\nThe native harness did not export a full tool-call transcript. response.md preserves the executor final answer; prompt.txt preserves exact task input. Reported tool execution and file reads cannot all be independently audited from these artifacts. This file is a limitation record, not a reconstructed transcript.\n',encoding='utf-8')
