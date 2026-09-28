param(
    [string]$FixturePath,
    [switch]$Apply,
    [switch]$PassThru,
    [string]$OutputDirectory,
    [string]$RepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '..\common\ProcessLedger.ps1')

function Resolve-VgoCleanupOutputDirectory {
    param(
        [string]$PreferredPath,
        [string]$DefaultPath,
        [string]$RepoRoot
    )

    if ([string]::IsNullOrWhiteSpace($PreferredPath)) {
        return $DefaultPath
    }

    if ([System.IO.Path]::IsPathRooted($PreferredPath)) {
        return [System.IO.Path]::GetFullPath($PreferredPath)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PreferredPath))
}

$resolvedRepoRoot = if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    Resolve-VgoRepoRoot -StartPath $PSScriptRoot
} else {
    [System.IO.Path]::GetFullPath($RepoRoot)
}

$context = Initialize-VgoProcessHealthRuntime -RepoRoot $resolvedRepoRoot
$auditResult = Get-VgoNodeProcessAuditRows -RepoRoot $context.repoRoot -FixturePath $FixturePath
$candidates = @(Get-VgoNodeCleanupCandidates -Rows $auditResult.rows -HealthPolicy $context.healthPolicy)
$targetDir = Resolve-VgoCleanupOutputDirectory -PreferredPath $OutputDirectory -DefaultPath $context.cleanupsDir -RepoRoot $context.repoRoot
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$baseName = if ($auditResult.source -eq 'fixture') {
    "node-process-cleanup-$($auditResult.case_id)"
} else {
    "node-process-cleanup-$timestamp"
}

$results = @()
foreach ($candidate in $candidates) {
    $row = [ordered]@{
        pid = [int]$candidate.pid
        entry_id = [string]$candidate.entry_id
        classification = [string]$candidate.classification
        ownership = [string]$candidate.ownership
        cleanup_safe = [bool]$candidate.cleanup_safe
        apply_requested = [bool]$Apply
        simulated = [bool](-not $Apply -or $auditResult.source -eq 'fixture')
        terminated = $false
        skipped = $false
        reason = $null
    }

    if (-not $Apply) {
        $row.reason = 'report_only_mode'
        $results += [pscustomobject]$row
        continue
    }

    if ($auditResult.source -eq 'fixture') {
        $row.reason = 'fixture_mode_simulation'
        $results += [pscustomobject]$row
        continue
    }

    if ($candidate.ownership -ne [string]$context.healthPolicy.ownership_contract.managed) {
        $row.skipped = $true
        $row.reason = 'non_managed_process_protected'
        $results += [pscustomobject]$row
        continue
    }

    try {
        Stop-Process -Id ([int]$candidate.pid) -Force -ErrorAction Stop
        Start-Sleep -Seconds ([int]$context.healthPolicy.cleanup.termination_wait_sec)
        $row.terminated = (-not (Test-VgoProcessAlive -Pid ([int]$candidate.pid)))
        $row.reason = if ($row.terminated) { 'terminated' } else { 'termination_requested_process_still_alive' }
        $results += [pscustomobject]$row
    } catch {
        $row.skipped = $true
        $row.reason = $_.Exception.Message
        $results += [pscustomobject]$row
    }
}

$payload = [ordered]@{
    generated_at = Get-VgoUtcTimestamp
    source = $auditResult.source
    fixture_path = $auditResult.fixture_path
    case_id = $auditResult.case_id
    apply_requested = [bool]$Apply
    cleanup_candidate_count = $candidates.Count
    results = $results
}

$jsonPath = Join-Path $targetDir ($baseName + '.json')
Write-VgoUtf8NoBomText -Path $jsonPath -Content ($payload | ConvertTo-Json -Depth 30)

$result = [pscustomobject]@{
    artifact_path = $jsonPath
    payload = $payload
}

if ($PassThru) {
    return $result
}

$result | ConvertTo-Json -Depth 20
