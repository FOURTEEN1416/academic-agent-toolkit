param()

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.ps1")
. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.Suites.ps1")

$summary = Invoke-VibeRouteLocalOwnerAudit -RepoRoot (Resolve-VibeRouteAuditRepoRoot -ScriptRoot $PSScriptRoot)
if (-not $summary.gate_passed) {
    exit 1
}

Write-Host "Vibe routing local-owner audit passed." -ForegroundColor Green
exit 0
