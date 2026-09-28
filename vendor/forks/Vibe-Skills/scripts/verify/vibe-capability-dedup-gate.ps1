param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [System.Collections.Generic.List[object]]$Assertions,
        [bool]$Pass,
        [string]$Message,
        [object]$Details = $null
    )
    $Assertions.Add([pscustomobject]@{ pass = [bool]$Pass; message = $Message; details = $Details }) | Out-Null
    Write-Host ('[{0}] {1}' -f $(if ($Pass) { 'PASS' } else { 'FAIL' }), $Message) -ForegroundColor $(if ($Pass) { 'Green' } else { 'Red' })
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-capability-dedup-gate.json'
    $mdPath = Join-Path $dir 'vibe-capability-dedup-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Capability Dedup Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Cluster Count: {0}' -f $Artifact.summary.cluster_count),
        ('- Failure Count: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Clusters',
        ''
    )
    foreach ($cluster in $Artifact.clusters) {
        $lines += ('- `{0}` owner=`{1}` sources={2} anchor_exists={3}' -f $cluster.cluster_id, $cluster.canonical_owner, $cluster.source_count, $cluster.anchor_exists)
    }
    $lines += ''
    $lines += '## Assertions'
    $lines += ''
    foreach ($assertion in $Artifact.assertions) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$configPath = Join-Path $context.repoRoot 'config\capability-dedup-governance.json'
$docPath = Join-Path $context.repoRoot 'docs\capability-dedup-graph-governance.md'
$matrixPath = Join-Path $context.repoRoot 'references\capability-dedup-matrix.md'
$rolePackPolicy = Join-Path $context.repoRoot 'config\role-pack-policy.json'
$rolePackDoc = Join-Path $context.repoRoot 'docs\role-pack-governance.md'
$rolePackDistillationDoc = Join-Path $context.repoRoot 'docs\role-pack-distillation-governance.md'
$assertions = [System.Collections.Generic.List[object]]::new()

Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $configPath) -Message 'capability dedup config exists' -Details $configPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $docPath) -Message 'capability dedup governance doc exists' -Details $docPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $matrixPath) -Message 'capability dedup matrix exists' -Details $matrixPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $rolePackPolicy) -Message 'role-pack policy exists for overlap closure' -Details $rolePackPolicy
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $rolePackDoc) -Message 'role-pack governance doc exists for overlap closure' -Details $rolePackDoc
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $rolePackDistillationDoc) -Message 'role-pack distillation governance doc exists' -Details $rolePackDistillationDoc
if (-not (Test-Path -LiteralPath $configPath)) { exit 1 }

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$clusters = @($config.clusters)
$requiredClusterIds = @($config.required_clusters)
$clusterIds = @($clusters | ForEach-Object { [string]$_.cluster_id })
$owners = @($clusters | ForEach-Object { [string]$_.canonical_owner })
$duplicateOwners = @($owners | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { [string]$_.Name })
$missingRequiredClusters = @($requiredClusterIds | Where-Object { $clusterIds -notcontains $_ })

Add-Assertion -Assertions $assertions -Pass ($clusters.Count -ge $requiredClusterIds.Count) -Message 'cluster count covers required cluster ids' -Details @{ cluster_count = $clusters.Count; required_count = $requiredClusterIds.Count }
Add-Assertion -Assertions $assertions -Pass ($missingRequiredClusters.Count -eq 0) -Message 'all required clusters exist' -Details $missingRequiredClusters
Add-Assertion -Assertions $assertions -Pass ($duplicateOwners.Count -eq 0) -Message 'canonical owners are unique across clusters' -Details $duplicateOwners

$matrixText = if (Test-Path -LiteralPath $matrixPath) { Get-Content -LiteralPath $matrixPath -Raw -Encoding UTF8 } else { '' }
$clusterRecords = @()
foreach ($cluster in $clusters) {
    $clusterId = [string]$cluster.cluster_id
    $anchor = [string]$cluster.verification_anchor
    $anchorPath = Join-Path $context.repoRoot $anchor
    $sources = @($cluster.upstream_sources)
    $absorbed = @($cluster.absorbed_value)
    $nonGoals = @($cluster.explicit_non_goals)

    Add-Assertion -Assertions $assertions -Pass (-not [string]::IsNullOrWhiteSpace([string]$cluster.canonical_owner)) -Message ("cluster {0} has canonical owner" -f $clusterId)
    Add-Assertion -Assertions $assertions -Pass ($sources.Count -gt 0) -Message ("cluster {0} has upstream sources" -f $clusterId) -Details $sources
    Add-Assertion -Assertions $assertions -Pass ($absorbed.Count -gt 0) -Message ("cluster {0} has absorbed value slices" -f $clusterId) -Details $absorbed
    Add-Assertion -Assertions $assertions -Pass ($nonGoals.Count -gt 0) -Message ("cluster {0} has explicit non-goals" -f $clusterId) -Details $nonGoals
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $anchorPath) -Message ("cluster {0} verification anchor exists" -f $clusterId) -Details $anchor
    Add-Assertion -Assertions $assertions -Pass ($matrixText -match [regex]::Escape($clusterId)) -Message ("cluster {0} is mentioned in dedup matrix" -f $clusterId)

    $clusterRecords += [pscustomobject]@{
        cluster_id = $clusterId
        canonical_owner = [string]$cluster.canonical_owner
        source_count = $sources.Count
        anchor_exists = [bool](Test-Path -LiteralPath $anchorPath)
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-capability-dedup-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    clusters = $clusterRecords
    assertions = @($assertions)
    summary = [ordered]@{
        cluster_count = $clusters.Count
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $context.repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) { exit 1 }
exit 0
