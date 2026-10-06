"""Serialize the independent static review; excludes behavior-run information."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BANK = REPO / 'skills/sdd-skill-conductor/references/quality-questions.md'
explanations = {
'Q-DISCOVERY-1': ('SKILL.md describes preparation and approval of specifications, design and a change plan. This states the work product, rather than merely an invocation keyword.', 1),
'Q-DISCOVERY-2': ('The description supplies only explicit sdd invocation, with no 4-5 natural phrasings or broadened-trigger clause. This is intentional for disable-model-invocation: true, but the fixed bank question is not satisfied; automatic discovery is outside the declared invocation policy.', 0),
'Q-CLARITY-1': ('references/premortem.md explains that a report schedule does not establish usefulness and that a matching manifest does not prove changed behavior reached the specification. resume.md explains that state and task presence do not establish permission. These explanations ground the critical evidence and authorization instructions.', 1),
'Q-CLARITY-2': ('The new reference and template consistently distinguish premortem findings, Q records, review FIND records, and USER decisions. document-format.md preserves the same document and manifest terminology; no alternate identifier system is introduced.', 1),
'Q-CLARITY-3': ('flows/resume.md ends with an instruction to save periodically when metrics are absent, while flows/draft.md says to investigate proportionally to the change. The former has no observable cadence. Many other thresholds are concrete, including greater than 70%, but the fixed question asks for freedom from vague modifiers.', 0),
'Q-CLARITY-4': ('references/premortem.md separates no-findings, findings, closed history, changed evidence and missing evidence into distinct paragraphs and branches. Planning prerequisites are explicitly enumerated in flows/plan.md, with permission and version agreement distinguished rather than expressed through nested negation.', 1),
'Q-CLARITY-5': ('The executable instructions use direct imperatives such as Прочитай, Сохрани, Проверь and Пересчитай throughout explore/draft/revise/resume. Descriptive paragraphs define artifact semantics; they do not weaken the procedural steps into suggestions.', 1),
'Q-CLARITY-6': ('Premortem branches use observable predicates: first check with no findings, existing closed findings, changed source, missing referenced file, and a selected normative behavior change. Editorial exclusions likewise enumerate document languages and protected fragments rather than permitting broad discretionary exceptions.', 1),
'Q-STRUCT-1': ('SKILL.md is a short entry and flow map. Premortem detail resides in references/premortem.md and templates/premortem.md; document format, runtime, editorial and review procedures are separated into named references and flows.', 1),
'Q-STRUCT-2': ('The flow table and startup paragraph say when to open runtime, document format and a host adapter, but do not explicitly tell readers what references not to load for a task. OpenSpec provenance, README and manual are a flat purpose list. The bank specifically requires selective-loading exclusions when multiple references exist.', 0),
'Q-ROBUST-1': ('references/runtime-setup.md requires package files, readable sources, writable change directory, uv and Python 3.11+. Missing tools or dependencies produce a concrete limitation and recovery path, with no fabricated checks or bypassed gate; drafts remain allowed.', 1),
'Q-ROBUST-2': ('references/premortem.md covers missing prior state, missing linked document, unavailable source, stale premise, a trivial typo, and closed findings. It specifies narrow reconstruction and targeted questions rather than assuming completion or restarting an interview.', 1),
'Q-ROBUST-3': ('scripts/check.py catches InputError, ValidationError, OSError and UnicodeError, emits structured code/path/message errors, and distinguishes exits 1 and 2. scripts/run.py reports missing uv and keeps runtime caches external. snapshot code raises descriptive missing/unreadable input errors.', 1),
'Q-ROBUST-4': ('The reviewed current path relies on explicit schema versions, runtime requirements and relative artifact state, not calendar cutovers or claims about a new API. Timestamps in templates are examples for records, not dated branches in operational instructions.', 1),
'Q-COMPLETE-1': ('The description promises specification, design and plan preparation/approval. SKILL.md maps these to draft, review, user-review and plan, while explore, revise and resume cover clarification and continuation. Each promised work product has a template and flow.', 1),
'Q-COMPLETE-2': ('The reference uses concrete schedule-without-purpose and typo-diff cases, and explicitly handles missing sources, closed history, deferred nonblocking questions and scope growth. The workflow also addresses stale hashes and cancelled commands rather than limiting itself to idealized happy-path prose.', 1),
'Q-COMPLETE-3': ('The plan entry enumerates readiness conditions before tasks creation. Explore ends with a local completion check; review ends with reports/manifests/coverage/checkpoint checks. The premortem completion condition sits immediately after the four checking steps, before storage instructions.', 1),
'Q-COMPLETE-4': ('The reviewed files define package-specific SDD fields, permissions, manifests and premortem storage. They do not teach generic Markdown, JSON, Python or basic project-management concepts; templates are operational artifacts rather than tutorials.', 1),
}

raw = (HERE / 'candidate-structure.json').read_bytes()
det = json.loads(raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'))
questions = list(det if isinstance(det, list) else det['questions'])
pattern = r'- `(Q-[A-Z]+-\d+)` — (non-critical|critical).*?\n  - text: "(.*?)"\n  - violation_example: "(.*?)"'
for match in re.finditer(pattern, BANK.read_text(encoding='utf-8'), re.S):
    ident, critical, text, violation = match.groups()
    category = ident.split('-')[1]
    dimension = {'DISCOVERY':'Discovery','CLARITY':'Clarity','STRUCT':'Structure','ROBUST':'Robustness','COMPLETE':'Completeness'}[category]
    evidence, answer = explanations[ident]
    questions.append(dict(id=ident, dimension=dimension, requirement_id=None, text=text.replace('\\"','"'), violation_example=violation.replace('\\"','"'), source='llm', critical=critical=='critical', explanation=evidence, answer=answer))
assert sum(q['source']=='llm' for q in questions) == len(explanations)
dimensions = {}
for dimension in ('Discovery','Clarity','Structure','Robustness','Completeness'):
    group = [q for q in questions if q['dimension']==dimension]
    passed = sum(q['answer'] for q in group)
    dimensions[dimension] = dict(score=passed/len(group), passed=passed, total=len(group))
result = dict(target='skill-artifact', skill_name='sdd-spec', skill_path='skill-workspaces/sdd-spec-premortem/implementation/candidate', eval_id=None, question_source='hybrid', requirements=[], questions=questions, dimension_scores=dimensions, failing=[{k:q[k] for k in ('id','dimension','text','explanation','critical')} for q in questions if not q['answer']])
(HERE / 'candidate-bineval.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
coverage = {
'entry': ('references/premortem.md opening and numbered steps; flows/explore.md step 2; flows/draft.md step 3', ['explore','direct-draft','small-change']),
'evidence': ('references/premortem.md steps 1-4 distinguish fact/hypothesis, read sources first and avoid question quotas', ['known-answer','unknown-assumption','no-quota']),
'storage': ('references/premortem.md storage section; templates/state.md and templates/premortem.md', ['empty-result','findings-document','closed-history']),
'disposition': ('references/premortem.md question/disposition bullets require blocking dependent choices, matching reason/return_at and real risk/scope choices', ['block-dependent','defer','no-scope-growth']),
'resume': ('references/premortem.md continuation section; flows/resume.md step 3; flows/revise.md step 3', ['resume-current','revisit','restore']),
'authority': ('references/premortem.md normative-boundary section; flows/plan.md entry; scripts/lib/snapshots.py fixed normative input list', ['normative-change','no-gate-bypass'])}
static = dict(scope='Static instruction coverage only; this does not establish observed behavior or substitute for execution evaluations.', criteria=[])
for evidence, ids in coverage.values():
    for ident in ids:
        static['criteria'].append(dict(id='AC-premortem-'+ident,evidence=evidence,covered=True))
(HERE / 'candidate-static-ac-review.json').write_text(json.dumps(static,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Wrote static fixed-bank and AC coverage reviews; no behavior results included.')
