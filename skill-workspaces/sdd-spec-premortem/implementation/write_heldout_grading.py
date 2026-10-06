"""Independent heldout assessments; do not expose to the skill author before gate."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {x['id']: x for x in json.loads((HERE/'planned-evals.json').read_text(encoding='utf-8'))['evals']}


def save(iteration, variant, number, evidence_and_verdict):
    case = CASES[number]
    root = HERE / iteration / case['name'] / variant
    run = json.loads((root/'run.json').read_text(encoding='utf-8'))
    assert run['status']=='completed' and run['returncode']==0
    assert len(evidence_and_verdict)==len(case['expectations'])
    questions = [dict(text=text,dimension='Robustness',evidence=evidence,passed=passed) for text,(evidence,passed) in zip(case['expectations'],evidence_and_verdict)]
    passed = sum(q['passed'] for q in questions)
    result = dict(status='graded',expectations=questions,summary=dict(passed=passed,failed=len(questions)-passed,total=len(questions),pass_rate=passed/len(questions)),dimension_scores={'Robustness':dict(score=passed/len(questions),passed=passed,total=len(questions))},failing=[q for q in questions if not q['passed']],timing=json.loads((root/'timing.json').read_text(encoding='utf-8')),limitations=['Executor records missing humanizer-ru; retained draft status is separate from these behavior assertions.'],eval_feedback={'suggestions':[],'overall':'Evidence cites written artifacts and trace actions; a saved input alone is not treated as completed work.'})
    (root/'grading.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    save('iteration-1-corrected','old_skill',20,[
      ('state.md retains Q-bulk-capacity blocking:false/status:open with reason limiting the current pilot to confirmed 10 rows and return_at before expansion to mass rollout. The agent edits proposal/spec/design to express that pilot boundary, so this is considered use of the inherited question in the continued task, not merely unattended fixture data.',True),
      ('premortem.md adds a Pilot boundary section: current work is 10 rows, unknown mass capacity does not block it, Q-bulk-capacity stays open until expansion. This matches state reason and return_at semantically. Trace item_10 edits the premortem and normative scope together; no different trigger is introduced.',True),
      ('Design says the pilot does not establish readiness for mass load and mass rollout remains out of scope. State and the final response keep capacity open/nonblocking; neither claims the remaining risk was accepted or creates a USER risk decision.',True)])
    save('iteration-1','old_skill',23,[
      ('premortem.md preserves the old 09:00/08:30 failure and 08:00 answer as history, then narrowly revisits assignment at07:30. Q-report-time alone is reopened. Proposed07:00 is explicitly an agent proposal, not silently selected as a new requirement.',True),
      ('The saved premortem CSV section retains all three column names, recipient, goal and manual assignment. Proposal/spec/design retain those same commitments and exclusion of automatic assignment; the final response explicitly preserves CSV and other premises.',True),
      ('Proposal and spec replace the stale08:00 commitment with before07:30 and an unresolved exact deadline. AC-report-delivered and design refer to Q-report-time, whose state record is blocking/open. Trace writes and subsequent readback confirm these changes exist, not just a suggested next step.',True)])
    save('iteration-1','old_skill',24,[
      ('Trace item_3 reads current docs/report.md; item_4 reads historical docs/decision.md and prior premortem. Item_5 explicitly reports the08:30-to07:30 change. Saved premortem contrasts both sources and explains why08:00 now arrives30 minutes late.',True),
      ('Only premortem/state are rewritten; premortem What remains retains recipient, purpose, three columns and manual assignment. Q-report-time is reopened and07:00 is labelled an unaccepted proposal. The old normative deadline remains pending the user answer and state clearly flags that limitation rather than reopening unrelated decisions.',True)])
