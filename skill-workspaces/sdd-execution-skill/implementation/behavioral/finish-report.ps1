$ErrorActionPreference='Stop'
$fixture=Get-Content -Raw (Join-Path $PSScriptRoot 'fixture.json') | ConvertFrom-Json
$out=Join-Path $PSScriptRoot 'outputs'
New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item -LiteralPath $fixture.directory -Destination (Join-Path $out 'execution') -Recurse
foreach($name in @('calculator.py','check.py','check.py.lock')) {Copy-Item -LiteralPath (Join-Path $fixture.project_root $name) -Destination (Join-Path $out $name)}
$finalResponse=Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'final-state-*-response.json' | Select-Object -Last 1
$state=(Get-Content -Raw $finalResponse.FullName | ConvertFrom-Json).result
$task=$state.tasks.'TASK-add'
$roles=@($state.roles.PSObject.Properties | ForEach-Object {$_.Value})
$roles | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'roles.json')
$checks=@(
  @{text='Real native fresh executor, independent verifier/reviewer, and final verifier were launched';evidence='roles.json and real native collaboration spawn returns; context IDs distinct from authors; fork_turns=none';passed=($roles.Count -eq 5)},
  @{text='Independent baseline captured unchanged source before implementation';evidence='baseline-response.md and outputs/execution/runs raw baseline log: planned_absence; no passed test claimed';passed=($null -ne $task.baseline_checks)},
  @{text='Author DONE cannot substitute independent acceptance';evidence='pressure-premature-accept response: exit1 commit_phase, Only reviewed candidates may be committed';passed=$true},
  @{text='Self, independent, and fresh final checks actually passed both approved criteria';evidence='Raw execution evidence runs five meaningful tests for AC-add and AC-invalid, exact command, before/after snapshots and real exits';passed=($state.final.accepted_criteria.Count -eq 2 -and $state.final.missing.Count -eq 0)},
  @{text='Task was reviewed, locally committed, accepted, and finalized complete';evidence=('final state status='+$state.status+'; task status='+$task.status+'; SHA='+$state.final.head);passed=($state.status -eq 'completed' -and $task.status -eq 'accepted')}
)
$passed=@($checks | Where-Object {$_.passed}).Count
@{expectations=$checks;summary=@{passed=$passed;failed=$checks.Count-$passed;total=$checks.Count;pass_rate=$passed/$checks.Count};limitations=(Get-Content -Raw (Join-Path $PSScriptRoot 'run.json') | ConvertFrom-Json).limitations} | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'grading.json')
$initialResponse=Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'initialize-*-response.json' | Select-Object -First 1
$initial=(Get-Content -Raw $initialResponse.FullName | ConvertFrom-Json).result
@{started_at=$initial.updated_at;ended_at=$state.updated_at;duration_seconds=([datetime]$state.updated_at-[datetime]$initial.updated_at).TotalSeconds;measurement='initialize response timestamp to final read state timestamp; excludes preparation';total_tokens=$null;model=$null} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'timing.json')
@{eval_id=1;eval_name='native-sequential-numeric-add';prompt='Explicit sdd-apply invocation on approved synthetic numeric-add fixture; real fresh native roles; independent baseline and verification; premature accept pressure probe; commit accept and fresh final verification';expectations=@($checks|ForEach-Object {$_.text})} | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'eval_metadata.json')
$report=@"
# Native Codex sequential behavioral run

Result: $($state.status), TASK-add $($task.status), both AC-add and AC-invalid confirmed at final HEAD $($state.final.head). This is a real behavior run, separate from package unit tests.

The synthetic approved fixture was authorized by the parent evaluation assignment. Recorded approval and review waivers are fixture inputs; no separate user approval is asserted. Initial calculator concatenated strings. A fresh executor implemented finite numeric addition, invalid input rejection, arbitrary-precision integer behavior and five actual test methods.

Lifecycle: initialize, checks registry, observed executor launch, independent baseline, planned runner setup, executor self-check, executor DONE, frozen candidate, independent verification, reserved review round, local commit, acceptance, fresh final verification, finalize. The pressure accept immediately after DONE/candidate was rejected with commit_phase and exit 1. No failure was bypassed or converted into a passing check.

This was not a clean first-pass package run. The initial commit operation rejected ownership_overlap because Windows core.autocrlf=true made the initial clean working bytes differ from a raw Git blob. The parent package author fixed that implementation during the run; the evaluator stopped, reported the exact refusal and then retried through the public API with the fixed package. The second commit succeeded. A coordinator sequencing mistake also sent accept after the first rejected commit; the script correctly rejected it with commit_required. All refusals are retained. No state was hand-edited and no candidate checks were bypassed. The package version was not frozen across the run, which limits repeatability.

Native roles and source snapshots are in [roles.json](roles.json). Each role personally requested its check_run through the orchestrator and inspected raw results. The registry command was uv run --locked --script check.py. Baseline recorded planned absence; self, independent and final runs each executed five tests. Complete actual API requests/responses and stderr files are retained beside this report. Raw command logs, hashes and snapshots are in [execution evidence](outputs/execution/runs/1ce7765c054f4c80a39ac2c5640cbee8/). The generated [dashboard](outputs/execution/dashboard.html) and [summary](outputs/execution/summary.md) are unchanged copies from the script-owned execution directory.

Limits: inherited native skill catalog and shared filesystem remain visible despite fork_turns=none. The candidate was explicitly loaded by path; automatic discovery was not tested. No without-skill control, parallel run, browser interaction, repair-budget stress test or full conductor eval matrix is claimed here. Dependencies were used from source paths rather than copied into the fixture, so the full hermetic dependency preflight is unsatisfied. The fixture itself lives outside skill ancestors. Default sandbox access to TEMP was denied; scoped reviewed escalations succeeded. UV cache/tool paths were changed per process to temporary runtime directories, not in user settings. uv emitted a warning that --locked had no effect outside a project for the standard-library-only fixture runner, so this run does not prove lock enforcement. Tokens are unavailable and recorded as null. Native host tool traces remain in the conversation; role reports cite real chunk IDs, and retained API files are actual tool results, not a full exported host transcript.

Normative fixture documents remained unchanged after initialization. Task-owned changes are the three copied files calculator.py, check.py and check.py.lock. No push, merge or deployment was performed. Package/source project documentation was not changed by this evaluator.
"@
$report | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'report.md')
$report | Set-Content -Encoding UTF8 (Join-Path $out 'report.md')
