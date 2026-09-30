import json,pathlib,statistics
HERE=pathlib.Path(__file__).resolve().parent
runs=json.loads((HERE/'runs.json').read_text())
groups={}
for run in runs:
 out=pathlib.Path(run['output'])
 if not (out/'grading.json').exists():raise RuntimeError(f'Missing grading: {out}')
 grading=json.loads((out/'grading.json').read_text(encoding='utf-8'))
 timing=json.loads((out/'timing.json').read_text(encoding='utf-8'))
 groups.setdefault((run['eval_id'],run['variant']),[]).append((grading,timing))
notes=[]
for ev in [1,2,3]:
 for variant in ['with_skill','without_skill']:
  rows=groups[ev,variant];rates=[g['summary']['pass_rate'] for g,t in rows]
  variability=f'{statistics.stdev(rates):.4f}' if len(rates)>1 else 'not estimable (n=1)'
  notes.append(f'Eval {ev} {variant}: {len(rows)} independent runs, pass rates {rates}; sample standard deviation {variability}.')
for variant in ['with_skill','without_skill']:
 rows=groups[2,variant];times=[t['total_duration_seconds'] for g,t in rows];tokens=[t['total_tokens'] for g,t in rows]
 notes.append(f'Pressure {variant}: measured mean duration {statistics.mean(times):.3f}s (range {min(times):.3f}–{max(times):.3f}); mean CLI-reported total tokens {statistics.mean(tokens):.1f}. Repeated Windows encoding reads appear in with-skill traces; timing includes this runtime overhead.')
notes.extend([
 'The benchmark mean weights each execution equally: five of seven runs per variant are repetitions of the same pressure prompt. Its 100% versus 88.6% means are descriptive for this set, not broad skill-success probabilities or seven distinct scenarios.',
 'All five pressure repetitions per variant choose B. No choice variance was observed. This scenario explicitly denies skipping review and offers the compliant option, so identical control results do not establish that the skill caused the guard behavior.',
 'With-skill pressure responses consistently identify all document-stage lenses as stale and preserve planning authorization; control responses mainly discuss proposal and dependent checks. The frozen binary assertions do not measure the full distinction.',
 'Guard fixtures are empty and scenario facts are prompt-supplied. These runs measure concrete stated actions, not actual on-disk freshness reconstruction, independent-review dispatch, persisted authorization, or a real-project pilot.',
 'The ownership scenario tests actual complete tasks text against two existing ACs and a prepared current-review fixture. Only one paired sample was run; do not infer a general reliability rate from it.',
 'The original 3 native samples are exploratory and excluded. All 14 scored runs use fresh Codex CLI sessions with the same configured default model and no override. The CLI did not export the configured model name.',
 'All 14 CLI transcripts contain skill-catalog acknowledgments. Read commands show no baseline access to the candidate and no original-repository reads in any run. Separate cwd and the read-only sandbox do not enforce a deny-read ACL against every sibling path; this remains a documented isolation limit.',
 'Discovery and description optimization are skipped for explicit-only invocation. These results do not demonstrate CLI slash-command registration, a real Codex/Claude pilot, implementation, sync, or archive behavior.',
 'Candidate source is frozen and unchanged pending user review. Review the static viewer before revising wording.'
])
(HERE/'analysis-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
print('\n'.join(notes))
