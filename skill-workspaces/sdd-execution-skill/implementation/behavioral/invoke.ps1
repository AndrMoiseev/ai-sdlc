param([string]$Operation='read', [string]$Kind='', [string]$Payload='{}', [string]$TaskId='TASK-add', [string]$Tag='')
$ErrorActionPreference='Stop'
$env:UV_CACHE_DIR=Join-Path $env:TEMP 'uv-runtime/cache'
$env:UV_TOOL_DIR=Join-Path $env:TEMP 'uv-runtime/tools'
$fixture=Get-Content -Raw (Join-Path $PSScriptRoot 'fixture.json') | ConvertFrom-Json
$scriptPath='C:/Users/Andrew/repos/ai-sdlc/skills/sdd-apply/scripts/execute.py'
$stamp=[guid]::NewGuid().ToString('N')
if (!$Tag) {$Tag="$Operation-$Kind"}
$prefix=Join-Path $PSScriptRoot "$Tag-$stamp"
if($Operation -eq 'event') {
  $readPath="$prefix-read-request.json"
  @{operation='read';args=@{directory=$fixture.directory}} | ConvertTo-Json -Depth 60 | Set-Content -Encoding UTF8 $readPath
  $raw=& uv run --locked --script $scriptPath --request $readPath
  $raw | Set-Content -Encoding UTF8 "$prefix-read-response.json"
  if($LASTEXITCODE -ne 0){throw "Read failed: $raw"}
  $state=($raw | ConvertFrom-Json).result
  $tid=$TaskId
  if($TaskId -eq 'null') {$tid=$null}
  $request=@{operation='event';args=@{directory=$fixture.directory;event=@{event_id=$stamp;run_id=$state.run_id;expected_revision=$state.revision;owner=$state.owner;type=$Kind;task_id=$tid;payload=($Payload|ConvertFrom-Json)}}}
} elseif($Operation -eq 'initialize') {
  $request=@{operation='initialize';args=@{project_root=$fixture.project_root;change='add';instruction=@{text='Explicitly invoke sdd-apply to implement this approved numeric-add behavioral fixture sequentially; local task commits included.';source='parent-native-behavioral-evaluation-assignment'};sdd_spec='C:/Users/Andrew/repos/ai-sdlc/skills/sdd-spec';owner='/root/behavioral_eval'}}
} else {$request=@{operation=$Operation;args=@{directory=$fixture.directory}}}
$request | ConvertTo-Json -Depth 80 | Set-Content -Encoding UTF8 "$prefix-request.json"
$started=Get-Date
$raw=& uv run --locked --script $scriptPath --request "$prefix-request.json" 2> "$prefix-stderr.txt"
$code=$LASTEXITCODE
$raw | Set-Content -Encoding UTF8 "$prefix-response.json"
@{duration_seconds=((Get-Date)-$started).TotalSeconds;exit_code=$code;total_tokens=$null} | ConvertTo-Json | Set-Content -Encoding UTF8 "$prefix-timing.json"
$raw
if($code -ne 0){exit $code}
