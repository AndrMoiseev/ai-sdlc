$ErrorActionPreference = 'Stop'
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../skills/code-that-fits-in-your-head')).Path
$baseline = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'baseline-hashes.json') | ConvertFrom-Json
$allowed = @('README.md', 'SKILL.md', 'guidelines.md')
$changed = @($baseline | Where-Object { (Get-FileHash -LiteralPath $_.Path -Algorithm SHA256).Hash -ne $_.Hash })
foreach ($entry in $changed) {
    if ([IO.Path]::GetFileName($entry.Path) -notin $allowed) { throw "Existing material changed: $($entry.Path)" }
}
$files = @(Get-ChildItem -LiteralPath $skillRoot -Recurse -Force -File)
$generated = @($files | Where-Object { $_.Extension -ne '.md' })
if ($generated.Count) { throw "Unexpected non-document package files: $($generated.FullName -join ', ')" }
$goFiles = @($files | Where-Object { $_.Name -like 'go*.md' })
if ($goFiles.Count -lt 7) { throw "Expected at least seven Go documents, got $($goFiles.Count)" }
foreach ($file in $files) {
    $body = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    foreach ($match in [regex]::Matches($body, '\[[^\]]*\]\(([^)]+)\)')) {
        $target = $match.Groups[1].Value
        if ($target -match '^(https?://|mailto:|#)') { continue }
        $target = ($target -split '#')[0]
        if ($target -and -not (Test-Path -LiteralPath (Join-Path $file.DirectoryName $target))) {
            throw "Broken local link in $($file.FullName): $target"
        }
    }
}
$routes = Get-Content -LiteralPath (Join-Path $skillRoot 'guidelines.md') -Raw -Encoding UTF8
foreach ($file in $goFiles) {
    $relative = $file.FullName.Substring($skillRoot.Length + 1).Replace('\', '/')
    if (-not $routes.Contains($relative)) { throw "Unrouted Go file: $relative" }
    $body = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    if ($body -notmatch '(?i)fork') { throw "Missing fork attribution: $relative" }
}
$summary = [ordered]@{
    original_files_checked = $baseline.Count
    intentionally_changed_existing_files = @($changed | ForEach-Object { [IO.Path]::GetFileName($_.Path) })
    go_documents = @($goFiles | ForEach-Object { $_.FullName.Substring($skillRoot.Length + 1).Replace('\', '/') })
    local_links = 'pass'
    example_routes = 'pass'
    existing_examples_preserved = 'pass'
    package_generated_state = 'none'
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'package-checks.json')
$summary | ConvertTo-Json -Depth 5
