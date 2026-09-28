param()

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.ps1")
. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.Suites.ps1")

$summary = Invoke-VibeRouteNoLocalCandidateAudit -RepoRoot (Resolve-VibeRouteAuditRepoRoot -ScriptRoot $PSScriptRoot)
if (-not $summary.gate_passed) {
    exit 1
}

Write-Host "Vibe routing no-local-candidate audit passed." -ForegroundColor Green
exit 0
