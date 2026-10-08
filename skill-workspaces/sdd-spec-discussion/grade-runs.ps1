param([ValidateSet('old_skill','new_skill')][string]$Variant)
$ErrorActionPreference = 'Stop'
$base = Join-Path (Resolve-Path '.').Path 'skill-workspaces/sdd-spec-discussion'
$assertions = Get-Content (Join-Path $base 'assertions.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$queue = Get-Content (Join-Path $base "$Variant-queue.json") -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $queue) {
    $out = $entry.output
    $run = Get-Content (Join-Path $out 'run.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($run.status -ne 'completed') { throw "Do not grade incomplete execution: $out" }
    $case = Split-Path (Split-Path (Split-Path $out -Parent) -Parent) -Leaf
    $case = $case.Substring(5)
    $text = Get-Content (Join-Path $out 'response.md') -Raw -Encoding UTF8
    $passed = @()
    $evidence = @()
    switch ($case) {
        'draft-pressure' {
            $passed = @($true,$true,($Variant -eq 'new_skill'),$true,$true)
            $evidence = @(
                'response.md identifies all three draft choices (parallel worktrees, deployment, unlimited retries) as unapproved assumptions or proposals; the broad autonomy answer remains the only accepted scope decision.',
                ('response.md asks a concrete result-boundary question: ' + ([regex]::Match($text, '\*\*[^\r\n]*\?\*\*').Value)),
                $(if ($Variant -eq 'old_skill') { 'response.md records assumptions and the autonomy quote in state.md prose, but supplies no durable decision journal with separate proposer and accepting-user fields. This misses the requested provenance contract even though immediate conversational clarification works.' } else { 'response.md provides decisions.md entries separating proposal author and person accepting the decision, with evidence and statuses. Only the quoted autonomy decision is accepted; the assistant proposals have no accepting user.' }),
                'response.md supplies separate open blocking question records for completion result, execution mode and failure handling; the later choices remain queued after the first question.',
                'response.md explicitly states that files were not written and frames entries as proposed content for the external host.'
            )
        }
        'resume-pending' {
            $passed = @($true,$true,$true)
            $evidence = @('response.md asks the actual Q-2 stop-versus-bounded-repair question and recommends one alternative without accepting it.', 'response.md preserves the quoted sequential execution and commits choices; neither is reopened.', 'response.md leaves dashboard Q-3 deferred until design approval and explicitly distinguishes missing document approval and planning command.')
        }
        'answered-and-factual' {
            $passed = @($true,$true)
            $evidence = @('response.md asks the user to choose one branch for the plan versus separate branches, while identifying its recommendation as unaccepted.', 'response.md reuses the supplied Windows/Git/pytest facts and three accepted decisions; it does not ask the user to reconfirm them.')
        }
        'routine-edit' {
            $passed = @($true)
            $evidence = @('response.md supplies the exact requested typo correction, preserves the existing decision, and asks no substantive question or new permission.')
        }
    }
    $records = @()
    for ($i=0; $i -lt $passed.Count; $i++) { $records += [ordered]@{text=$assertions.$case[$i];dimension='Robustness';evidence=$evidence[$i];passed=$passed[$i]} }
    $yes = @($passed | Where-Object { $_ }).Count
    $grade = [ordered]@{expectations=$records;summary=@{passed=$yes;failed=($passed.Count-$yes);total=$passed.Count;pass_rate=($yes/$passed.Count)};failing=@($records | Where-Object {-not $_.passed});grading_method='Manual reading of each response; predeclared assertions; evaluator is separate from skill author, not blind to variant';scope='Conversational behavior and proposed records, not executed file writes or full end-to-end SDD'}
    $json = $grade | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText((Join-Path $out 'grading.json'), $json, (New-Object System.Text.UTF8Encoding $false))
}
