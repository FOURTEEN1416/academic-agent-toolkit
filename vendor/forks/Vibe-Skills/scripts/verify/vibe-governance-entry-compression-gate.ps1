param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Write-GateArtifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [string]$OutputDirectory,
        [Parameter(Mandatory)] [object]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        Join-Path $RepoRoot 'outputs\verify'
    } elseif ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
        [System.IO.Path]::GetFullPath($OutputDirectory)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $OutputDirectory))
    }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-VgoUtf8NoBomText -Path (Join-Path $dir 'vibe-governance-entry-compression-gate.json') -Content ($Artifact | ConvertTo-Json -Depth 100)
    $lines = @(
        '# VCO Governance Entry Compression Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Registered documents: `{0}`' -f $Artifact.summary.registered_documents),
        ('- Missing registered documents: `{0}`' -f $Artifact.summary.missing_registered_documents),
        ('- Historical navigation references: `{0}`' -f $Artifact.summary.historical_navigation_references),
        ('- Failure count: `{0}`' -f $Artifact.summary.failure_count)
    )
    Write-VgoUtf8NoBomText -Path (Join-Path $dir 'vibe-governance-entry-compression-gate.md') -Content ($lines -join "`n")
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [string]$Path
    )
    return ([System.IO.Path]::GetRelativePath($RepoRoot, $Path)).Replace('\', '/')
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$contractPath = Join-Path $repoRoot 'config\live-document-contract.json'
$contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json

$requiredEntryPaths = @(
    'README.md',
    'README.zh.md',
    'CONTRIBUTING.md',
    'SKILL.md',
    'docs/README.md',
    'docs/governance/README.md',
    'references/index.md',
    'config/live-document-contract.json',
    'scripts/verify/gate-family-index.md'
)

$failures = @()
$missingEntries = @()
foreach ($relative in $requiredEntryPaths) {
    $full = Join-Path $repoRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        $missingEntries += $relative
        $failures += "missing_entry:$relative"
    }
}

$documents = @($contract.documents)
if ($documents.Count -gt [int]$contract.max_live_documents) {
    $failures += ('document_budget_exceeded:{0}>{1}' -f $documents.Count, [int]$contract.max_live_documents)
}

$missingRegistered = @()
foreach ($document in $documents) {
    $relative = [string]$document.path
    $full = Join-Path $repoRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        $missingRegistered += $relative
        $failures += "missing_registered_document:$relative"
    }
    if ([string]::IsNullOrWhiteSpace([string]$document.owner) -or [string]::IsNullOrWhiteSpace([string]$document.lifecycle)) {
        $failures += "incomplete_registry_entry:$relative"
    }
}

$navigationFiles = @(
    'README.md',
    'README.zh.md',
    'CONTRIBUTING.md',
    'docs/README.md',
    'docs/governance/README.md',
    'references/index.md',
    'scripts/README.md',
    'scripts/verify/README.md',
    'scripts/verify/gate-family-index.md'
)
$historicalPatterns = @(
    'docs/archive',
    'docs/requirements',
    'docs/plans',
    'docs/status',
    'docs/releases',
    'docs/superpowers',
    'archive-first',
    'archive/governance-history'
)
$historicalReferences = @()
foreach ($relative in $navigationFiles) {
    $full = Join-Path $repoRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
    $lines = @(Get-Content -LiteralPath $full -Encoding UTF8)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        foreach ($pattern in $historicalPatterns) {
            if ([string]$lines[$index] -match [Regex]::Escape($pattern)) {
                $historicalReferences += [pscustomobject]@{
                        path = $relative
                        line = $index + 1
                        pattern = $pattern
                    }
                $failures += ('historical_navigation:{0}:{1}:{2}' -f $relative, ($index + 1), $pattern)
            }
        }
    }
}

$requiredEntryResults = @()
foreach ($relative in $requiredEntryPaths) {
    $requiredEntryResults += [pscustomobject]@{
        path = $relative
        exists = [bool](Test-Path -LiteralPath (Join-Path $repoRoot ($relative.Replace('/', '\'))) -PathType Leaf)
    }
}

$gateResult = if ($failures.Count -eq 0) { 'PASS' } else { 'FAIL' }
$artifact = [pscustomobject]@{
    gate = 'vibe-governance-entry-compression-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    summary = [ordered]@{
        registered_documents = $documents.Count
        missing_registered_documents = $missingRegistered.Count
        missing_required_entries = $missingEntries.Count
        historical_navigation_references = $historicalReferences.Count
        failure_count = $failures.Count
    }
    results = [ordered]@{
        required_entries = @($requiredEntryResults)
        missing_registered_documents = @($missingRegistered)
        historical_navigation_references = @($historicalReferences)
        failures = @($failures)
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failures.Count -gt 0) {
    $artifact | ConvertTo-Json -Depth 100
    exit 1
}

$artifact | ConvertTo-Json -Depth 100
exit 0
