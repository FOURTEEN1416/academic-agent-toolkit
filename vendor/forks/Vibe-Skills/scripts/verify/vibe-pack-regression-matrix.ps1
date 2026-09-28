param()

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.ps1")
. (Join-Path $PSScriptRoot "lib\VibeRouteAudit.Suites.ps1")

$repoRoot = Resolve-VibeRouteAuditRepoRoot -ScriptRoot $PSScriptRoot
$summaries = @(
    Invoke-VibeRouteNoLocalCandidateAudit -RepoRoot $repoRoot
    Invoke-VibeRouteLocalOwnerAudit -RepoRoot $repoRoot
    Invoke-VibeRouteRequestedSkillAudit -RepoRoot $repoRoot
)

$totalAssertions = (@($summaries | Measure-Object -Property total -Sum).Sum)
$passedAssertions = (@($summaries | Measure-Object -Property passed -Sum).Sum)
$failedAssertions = (@($summaries | Measure-Object -Property failed -Sum).Sum)

Write-Host ""
Write-Host "=== VCO Pack Regression Matrix (Compatibility Wrapper) ==="
Write-Host ("Suites: {0}" -f $summaries.Count)
Write-Host ("Total assertions: {0}" -f $totalAssertions)
Write-Host ("Passed: {0}" -f $passedAssertions)
Write-Host ("Failed: {0}" -f $failedAssertions)

if ($failedAssertions -gt 0) {
    exit 1
}

Write-Host "Pack regression audit wrapper passed." -ForegroundColor Green
exit 0
