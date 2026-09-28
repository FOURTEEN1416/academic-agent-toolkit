param()

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.ps1")
. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.Suites.ps1")

$summary = Invoke-VibeRouteRequestedSkillAudit -RepoRoot (Resolve-VibeRouteAuditRepoRoot -ScriptRoot $PSScriptRoot)
if (-not $summary.gate_passed) {
    exit 1
}

Write-Host "Vibe routing requested-skill audit passed." -ForegroundColor Green
exit 0
