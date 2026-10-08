$ErrorActionPreference = 'Stop'
$reportRoot = (Resolve-Path 'skill-workspaces/sdd-spec-discussion').Path
$benchmarkPath = Join-Path $reportRoot 'iteration-1/benchmark.json'
$benchmark = Get-Content -Encoding UTF8 $benchmarkPath -Raw | ConvertFrom-Json
$benchmark.metadata.skill_path = 'new_skill/sdd-spec (frozen snapshot)'
$benchmark.metadata.executor_model = $null
$benchmark.metadata.analyzer_model = $null
$benchmark.metadata.runs_per_configuration = 8
$benchmark.metadata | Add-Member -NotePropertyName repetition_counts_per_variant -NotePropertyValue @{ 'draft-pressure'=5; 'resume-pending'=1; 'answered-and-factual'=1; 'routine-edit'=1 } -Force
$benchmark.metadata | Add-Member -NotePropertyName model_note -NotePropertyValue 'Configured Codex CLI default; model ID not reported by runner. No model override.' -Force
$transitions = @()
foreach ($run in $benchmark.runs) {
    $runDir = Join-Path $reportRoot ('iteration-1/eval-' + $run.eval_id + '/' + $run.configuration + '/run-' + $run.run_number)
    $events = @(Get-Content -Encoding UTF8 (Join-Path $runDir 'stdout.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
    $commands = @($events | Where-Object {$_.type -eq 'item.completed' -and $_.item.type -eq 'command_execution'})
    $run.result.tool_calls = $commands.Count
    $run.result.errors = @($commands | Where-Object {$_.item.exit_code -ne 0}).Count
    if ($run.configuration -eq 'new_skill') {
        $control = $benchmark.runs | Where-Object {$_.configuration -eq 'old_skill' -and $_.eval_id -eq $run.eval_id -and $_.run_number -eq $run.run_number}
        for ($i=0; $i -lt $run.expectations.Count; $i++) {
            $transition = if ($control.expectations[$i].passed -eq $run.expectations[$i].passed) { 'stable-success' } elseif ($run.expectations[$i].passed) { 'improved' } else { 'regressed' }
            $transitions += @{eval_id=$run.eval_id;run=$run.run_number;text=$run.expectations[$i].text;transition=$transition}
        }
    }
}
$benchmark | Add-Member -NotePropertyName transitions -NotePropertyValue $transitions -Force
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($benchmarkPath, ($benchmark | ConvertTo-Json -Depth 25), $utf8)
$markdownPath = Join-Path $reportRoot 'iteration-1/benchmark.md'
$markdown = Get-Content -Encoding UTF8 $markdownPath -Raw
$markdown = $markdown.Replace('**Model**: <model-name>', '**Model**: configured Codex CLI default (ID unavailable)').Replace('(3 runs each per configuration)', '(8 runs per configuration: 5 pressure repetitions + 3 single controls)')
[System.IO.File]::WriteAllText($markdownPath, $markdown, $utf8)
$env:UV_CACHE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) 'uv-runtime/cache'
$env:PYTHONUTF8 = '1'
uv run --locked --script skills/sdd-skill-conductor/eval-viewer/generate_review.py skill-workspaces/sdd-spec-discussion/iteration-1 --skill-name sdd-spec --benchmark $benchmarkPath --static skill-workspaces/sdd-spec-discussion/review.html
