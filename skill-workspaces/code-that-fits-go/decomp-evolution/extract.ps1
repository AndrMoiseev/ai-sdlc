$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $taskRoot '../../..')).Path
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Write-Module($name, $source, $tests) {
    $directory = Join-Path $taskRoot $name
    New-Item -ItemType Directory -Force $directory | Out-Null
    [IO.File]::WriteAllText((Join-Path $directory 'go.mod'), "module example.com/$name`n`ngo 1.22`n", $utf8)
    [IO.File]::WriteAllText((Join-Path $directory 'example.go'), $source, $utf8)
    if ($tests) { [IO.File]::WriteAllText((Join-Path $directory 'example_test.go'), $tests, $utf8) }
}
$decomp = Get-Content -Raw -Encoding utf8 (Join-Path $repoRoot 'skills/code-that-fits-in-your-head/references/decomposition/examples/go.md')
$blocks = [regex]::Matches($decomp, '(?s)```go\r?\n(.*?)```')
Write-Module 'decomposition' (($blocks | ForEach-Object { $_.Groups[1].Value }) -join "`n") ''
$evolution = Get-Content -Raw -Encoding utf8 (Join-Path $repoRoot 'skills/code-that-fits-in-your-head/references/evolution/examples/go.md')
$sections = [regex]::Split($evolution, '(?m)^## Example \d+:')
$names = @('calendar', 'repository', 'scheduling')
for ($i = 1; $i -le 3; $i++) {
    $code = @()
    $tests = ''
    foreach ($block in [regex]::Matches($sections[$i], '(?s)```go\r?\n(.*?)```')) {
        $body = $block.Groups[1].Value
        if ($body -match 'func TestCalendarFlag') { $tests = $body } else { $code += $body }
    }
    Write-Module $names[$i - 1] ($code -join "`n") $tests
}
