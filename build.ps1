param(
    [switch]$SmokeOnline
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[workspace] backend quality gate..."
Push-Location (Join-Path $root "apps\backend")
try {
    $backendArgs = @("scripts/build.py")
    if ($SmokeOnline) { $backendArgs += "--smoke-online" }
    & python @backendArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally { Pop-Location }

Write-Host "[workspace] frontend production build..."
Push-Location (Join-Path $root "apps\frontend")
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally { Pop-Location }

Write-Host "[workspace] all checks passed"
