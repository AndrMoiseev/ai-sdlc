$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$utf8 = New-Object System.Text.UTF8Encoding($false)
$fragmentPath = Join-Path $PSScriptRoot 'format-fragment.go'
foreach ($topic in @('decomposition','evolution')) {
    $documentPath = Join-Path $repoRoot "skills/code-that-fits-in-your-head/references/$topic/examples/go.md"
    $markdown = [IO.File]::ReadAllText($documentPath)
    $updated = [regex]::Replace($markdown, '(?s)```go\r?\n(.*?)```', {
        param($match)
        $body = $match.Groups[1].Value
        $hasPackage = $body -match '^package '
        if (-not $hasPackage) { $body = "package example`n`n" + $body }
        [IO.File]::WriteAllText($fragmentPath, $body, $utf8)
        gofmt -w $fragmentPath
        if ($LASTEXITCODE -ne 0) { throw 'gofmt failed' }
        $formatted = [IO.File]::ReadAllText($fragmentPath)
        if (-not $hasPackage) { $formatted = $formatted -replace '^package example\r?\n\r?\n', '' }
        return '```go' + "`n" + $formatted + '```'
    })
    [IO.File]::WriteAllText($documentPath, $updated, $utf8)
}
