param([string]$ReportPath)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$source = Join-Path $repo 'skills/sdd-kb'
$taskRoot = Join-Path ([IO.Path]::GetTempPath()) ('sdd-kb-runtime-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskRoot | Out-Null
$cache = Join-Path $taskRoot 'cache'
$installed = Join-Path $taskRoot 'installed/.agents/skills/sdd-kb'
New-Item -ItemType Directory -Force -Path (Split-Path $installed) | Out-Null
Copy-Item -LiteralPath $source -Destination $installed -Recurse
$bare = Join-Path $taskRoot 'bare'
$conflict = Join-Path $taskRoot 'conflict'
New-Item -ItemType Directory -Path $bare,$conflict | Out-Null
[IO.File]::WriteAllText((Join-Path $conflict 'pyproject.toml'), @'
[project]
name = "conflicting-consumer"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = ["sdd-kb-nonexistent-dependency==0.0.0"]
'@)
$projectHash = (Get-FileHash (Join-Path $conflict 'pyproject.toml')).Hash
$lock = Join-Path $source 'scripts/gitmark.py.lock'
$lockHash = (Get-FileHash $lock).Hash
$checks = [Collections.Generic.List[object]]::new()

function Invoke-Check([string]$Name, [string]$Directory, [string[]]$Arguments, [bool]$ExpectSuccess) {
    Push-Location $Directory
    try {
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $output = & uv @Arguments 2>&1 | Out-String
        $code = $LASTEXITCODE
        $ErrorActionPreference = $previous
    } finally { Pop-Location }
    $passed = ($code -eq 0) -eq $ExpectSuccess
    $checks.Add(@{name=$Name; passed=$passed; exit_code=$code; output=$output})
    if (-not $passed) { throw "${Name}: unexpected exit ${code}: $output" }
    Write-Output "PASS $Name"
}

$script = Join-Path $source 'scripts/gitmark.py'
Invoke-Check 'empty-cache-offline' $bare @('run','--cache-dir',(Join-Path $taskRoot 'offline-cache'),'--offline','--locked','--script',$script,'version') $false
Invoke-Check 'empty-cache-install' $bare @('run','--cache-dir',$cache,'--locked','--script',$script,'version') $true
Invoke-Check 'cached-source' $bare @('run','--cache-dir',$cache,'--offline','--locked','--script',$script,'version') $true
$installedScript = Join-Path $installed 'scripts/gitmark.py'
Invoke-Check 'installed-without-python-project' $bare @('run','--cache-dir',$cache,'--offline','--locked','--script',$installedScript,'version') $true
Invoke-Check 'installed-conflicting-project' $conflict @('run','--cache-dir',$cache,'--offline','--locked','--script',$installedScript,'version') $true

# Alter only a disposable installed copy. A locked run must fail without rewriting it.
$installedLock = "$installedScript.lock"
$installedLockHash = (Get-FileHash $installedLock).Hash
$code = [IO.File]::ReadAllText($installedScript).Replace('PyYAML==6.0.3','PyYAML==6.0.2')
[IO.File]::WriteAllText($installedScript,$code)
Invoke-Check 'stale-lock-rejected' $bare @('run','--cache-dir',$cache,'--locked','--script',$installedScript,'version') $false
if ((Get-FileHash $installedLock).Hash -ne $installedLockHash) { throw 'Stale lock was rewritten' }
if ($checks[-1].output -notmatch 'lockfile.*needs to be updated') { throw 'Failure did not identify a stale lockfile' }
if ((Get-FileHash $lock).Hash -ne $lockHash) { throw 'Source lock was changed' }
if ((Get-FileHash (Join-Path $conflict 'pyproject.toml')).Hash -ne $projectHash) { throw 'Consumer project was changed' }
if (@(Get-ChildItem -Force $bare).Count -ne 0) { throw 'Bare project acquired generated files' }
if (@(Get-ChildItem -Force $conflict).Count -ne 1) { throw 'Conflicting project acquired generated files' }

$bad = @(Get-ChildItem -LiteralPath $source,$installed -Force -Recurse | Where-Object {
    $_.Name -in @('__pycache__','.venv','.gitmark','.pytest_cache') -or $_.Extension -in @('.pyc','.db','.html')
})
if ($bad.Count) { throw "Package contains generated runtime files: $($bad.FullName)" }
$checks.Add(@{name='lock-project-and-package-cleanliness';passed=$true})
$report = @{runtime_root=$taskRoot;source=$source;installed=$installed;cache=$cache;checks=@($checks.ToArray())}
if ($ReportPath) {
    $resolvedReport = [IO.Path]::GetFullPath($ReportPath)
    New-Item -ItemType Directory -Force -Path (Split-Path $resolvedReport) | Out-Null
    [IO.File]::WriteAllText($resolvedReport,($report | ConvertTo-Json -Depth 6))
}
Write-Output "Runtime workspace retained at $taskRoot"
