$ErrorActionPreference = 'Stop'
$env:GOTOOLCHAIN = 'local'
$env:GOTELEMETRY = 'off'
$env:GOCACHE = Join-Path $env:TEMP 'code-that-fits-go-cache'
$env:GOMODCACHE = Join-Path $env:TEMP 'code-that-fits-go-modcache'
$root = $PSScriptRoot
$skill = Join-Path $root '../../../skills/code-that-fits-in-your-head/references/outside-in-tdd/examples'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Blocks($name) {
    $content = [IO.File]::ReadAllText((Join-Path $skill $name))
    return @([regex]::Matches($content, '(?s)```go\r?\n(.*?)\r?\n```') | ForEach-Object { $_.Groups[1].Value })
}
function WriteFixture($folder, $files) {
    $dir = Join-Path $root $folder
    New-Item -ItemType Directory -Force $dir | Out-Null
    [IO.File]::WriteAllText((Join-Path $dir 'go.mod'), "module example.com/$folder`n`ngo 1.22`n", $utf8)
    foreach ($entry in $files.GetEnumerator()) {
        [IO.File]::WriteAllText((Join-Path $dir $entry.Key), $entry.Value + "`n", $utf8)
    }
}
$unit = Blocks 'go-testing.md'
$http = Blocks 'go-net-http-testing.md'
WriteFixture 'unit' @{'reservation_test.go'=$unit[0]; 'countercase_test.go'=$unit[1]}
WriteFixture 'spy-before' @{'spy_test.go'=$unit[2]}
WriteFixture 'spy-after' @{'spy_test.go'=$unit[3]}
$middle = [regex]::Replace($unit[3], '(?m)^\s*ReservationDeleted\(Reservation\) error\r?\n', '')
$middle = [regex]::Replace($middle, '(?s)func \(s \*SpyPostOffice\) ReservationDeleted\(r Reservation\) error \{.*?\n\}', '')
$middle = [regex]::Replace($middle, '(?s)\s*if err := spy.ReservationDeleted\(r\); err != nil \{.*?\n\s*\}', '')
$middle = $middle.Replace('[]Observation{{Created, r}, {Deleted, r}}', '[]Observation{{Created, r}}')
WriteFixture 'spy-middle' @{'spy_test.go'=$middle}
WriteFixture 'http-before' @{'home_test.go'=$http[0]; 'reservation_test.go'=$http[1]; 'capacity_test.go'=$http[2]}
WriteFixture 'http-after' @{'home_test.go'=$http[0]; 'reservation_test.go'=$http[1]; 'capacity_test.go'=$http[3]}
foreach ($folder in @('unit','spy-before','spy-middle','spy-after','http-before','http-after')) {
    Push-Location (Join-Path $root $folder)
    try {
        & go test -count=1 ./...
        if ($LASTEXITCODE -ne 0) { throw "go test failed: $folder" }
    } finally { Pop-Location }
}

