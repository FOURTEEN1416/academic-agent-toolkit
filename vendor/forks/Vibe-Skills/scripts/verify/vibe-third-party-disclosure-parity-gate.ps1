param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [System.Collections.Generic.List[object]]$Collection,
        [bool]$Condition,
        [string]$Message,
        [object]$Details = $null
    )

    [void]$Collection.Add([pscustomobject]@{
        pass = [bool]$Condition
        message = $Message
        details = $Details
    })
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-third-party-disclosure-parity-gate.json'
    $mdPath = Join-Path $dir 'vibe-third-party-disclosure-parity-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)
    $lines = @(
        '# VCO Third-Party Disclosure Parity Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Missing disclosures: `{0}`' -f $Artifact.summary.missing_disclosures),
        ('- Undeclared disclosed sources: `{0}`' -f $Artifact.summary.undeclared_disclosed_sources),
        '',
        '## Details',
        '',
        ('- Missing disclosures: `{0}`' -f (($Artifact.results.missing_disclosures) -join ', ')),
        ('- Undeclared disclosed sources: `{0}`' -f (($Artifact.results.undeclared_disclosed_sources) -join ', '))
    )
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$lockPath = Join-Path $repoRoot 'config\upstream-lock.json'
$manifestPath = Join-Path $repoRoot 'config\upstream-corpus-manifest.json'
$disclosurePath = Join-Path $repoRoot 'THIRD_PARTY_LICENSES.md'

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$disclosure = Get-Content -LiteralPath $disclosurePath -Raw -Encoding UTF8

$lockIds = @($lock.dependencies | ForEach-Object { [string]$_.id } | Sort-Object -Unique)
$canonicalRepos = New-Object System.Collections.Generic.HashSet[string]
foreach ($id in $lockIds) { [void]$canonicalRepos.Add($id) }
foreach ($entry in @($manifest.entries)) {
    $repoUrl = [string]$entry.repo_url
    if ($repoUrl -match '^https://github\.com/([^/]+)/([^/]+)$') {
        [void]$canonicalRepos.Add(('{0}/{1}' -f $Matches[1], $Matches[2]))
    }
}

$disclosedRepos = @([regex]::Matches($disclosure, '`([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
$missingDisclosures = @($lockIds | Where-Object { $disclosedRepos -notcontains $_ })
$undeclaredDisclosedSources = @($disclosedRepos | Where-Object { -not $canonicalRepos.Contains($_) })

$results = [System.Collections.Generic.List[object]]::new()
Add-Assertion -Collection $results -Condition ($missingDisclosures.Count -eq 0) -Message 'all upstream-lock dependencies are disclosed' -Details $missingDisclosures
Add-Assertion -Collection $results -Condition ($undeclaredDisclosedSources.Count -eq 0) -Message 'all disclosed upstreams are canonicalized' -Details $undeclaredDisclosedSources

$failures = @($results | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-third-party-disclosure-parity-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failures -eq 0) { 'PASS' } else { 'FAIL' }
    summary = [ordered]@{
        lock_dependency_count = $lockIds.Count
        disclosed_source_count = $disclosedRepos.Count
        canonical_source_count = $canonicalRepos.Count
        missing_disclosures = $missingDisclosures.Count
        undeclared_disclosed_sources = $undeclaredDisclosedSources.Count
        failure_count = $failures
    }
    results = [ordered]@{
        assertions = @($results)
        missing_disclosures = $missingDisclosures
        undeclared_disclosed_sources = $undeclaredDisclosedSources
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failures -gt 0) { exit 1 }
