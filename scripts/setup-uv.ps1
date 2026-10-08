# Run once in a user PowerShell terminal; no agent or project configuration is needed.
$ErrorActionPreference = 'Stop'

$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'uv-runtime'
$settings = @{
    UV_CACHE_DIR = Join-Path $runtimeRoot 'cache'
    UV_TOOL_DIR = Join-Path $runtimeRoot 'tools'
}

foreach ($name in $settings.Keys) {
    $value = [System.IO.Path]::GetFullPath($settings[$name])
    New-Item -ItemType Directory -Path $value -Force | Out-Null
    [Environment]::SetEnvironmentVariable($name, $value, 'User')
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    Write-Output "$name=$value"
}

Write-Output 'Restart your agent application and other terminals to inherit these variables.'
Write-Output 'Temporary storage is disposable; dependencies may need downloading again after cleanup.'
