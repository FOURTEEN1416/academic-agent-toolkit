param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-upstream-lock-coverage-gate.json'
    $mdPath = Join-Path $dir 'vibe-upstream-lock-coverage-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Upstream Lock Coverage Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Dependencies: `{0}`' -f $Artifact.summary.dependency_count),
        ('- Missing governance fields: `{0}`' -f $Artifact.summary.missing_governance_fields),
        ('- Moving branch refs: `{0}`' -f $Artifact.summary.moving_branch_refs),
        '',
        '## Missing Field Report',
        ''
    )
    foreach ($item in @($Artifact.results.missing_field_report)) {
        $lines += ('- `{0}` missing: {1}' -f $item.id, (($item.missing_fields) -join ', '))
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$lockPath = Join-Path $repoRoot 'config\upstream-lock.json'
$tiersPath = Join-Path $repoRoot 'config\distribution-tiers.json'

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$tiers = Get-Content -LiteralPath $tiersPath -Raw -Encoding UTF8 | ConvertFrom-Json
$allowedTiers = @($tiers.tiers | ForEach-Object { [string]$_.id })

$requiredFields = @(
    'canonical_slug',
    'license_spdx',
    'distribution_tier',
    'redistribution_posture',
    'disclosure_required',
    'local_retention_allowed',
    'shipped_by_default'
)

$missingFieldReport = New-Object System.Collections.Generic.List[object]
$invalidTierIds = New-Object System.Collections.Generic.List[string]
$duplicateIds = @($lock.dependencies | Group-Object -Property id | Where-Object { $_.Count -gt 1 } | ForEach-Object { [string]$_.Name })
$movingBranchRefs = 0

foreach ($dep in @($lock.dependencies)) {
    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($field in $requiredFields) {
        if (-not ($dep.PSObject.Properties.Name -contains $field)) {
            [void]$missing.Add($field)
            continue
        }

        $value = $dep.$field
        if ($value -is [string] -and [string]::IsNullOrWhiteSpace([string]$value)) {
            [void]$missing.Add($field)
        }
        if ($null -eq $value) {
            [void]$missing.Add($field)
        }
    }

    if (-not ($allowedTiers -contains [string]$dep.distribution_tier)) {
        [void]$invalidTierIds.Add([string]$dep.id)
    }

    if ([string]$dep.upstream_ref -notmatch '^[0-9a-f]{7,40}$') {
        $movingBranchRefs++
    }

    if ($missing.Count -gt 0) {
        [void]$missingFieldReport.Add([pscustomobject]@{
            id = [string]$dep.id
            missing_fields = @($missing)
        })
    }
}

$failures = 0
if ($missingFieldReport.Count -gt 0) { $failures++ }
if ($duplicateIds.Count -gt 0) { $failures++ }
if ($invalidTierIds.Count -gt 0) { $failures++ }
$gateResult = if ($failures -eq 0) { 'PASS' } else { 'FAIL' }

$summary = [pscustomobject]@{
    dependency_count = [int]@($lock.dependencies).Count
    required_field_count = [int]$requiredFields.Count
    missing_governance_fields = [int]$missingFieldReport.Count
    duplicate_ids = [int]$duplicateIds.Count
    invalid_tier_ids = [int]$invalidTierIds.Count
    moving_branch_refs = [int]$movingBranchRefs
    failure_count = [int]$failures
}

$resultPayload = [pscustomobject]@{
    missing_field_report = [object[]]$missingFieldReport.ToArray()
    duplicate_ids = [string[]]$duplicateIds
    invalid_tier_ids = [string[]](@($invalidTierIds | Sort-Object -Unique))
    allowed_tiers = [string[]]$allowedTiers
}

$artifact = [pscustomobject]@{
    gate = 'vibe-upstream-lock-coverage-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    summary = $summary
    results = $resultPayload
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failures -gt 0) { exit 1 }
