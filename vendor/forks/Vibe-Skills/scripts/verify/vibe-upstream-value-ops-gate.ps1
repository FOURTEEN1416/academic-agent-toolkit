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

    $jsonPath = Join-Path $dir 'vibe-upstream-value-ops-gate.json'
    $mdPath = Join-Path $dir 'vibe-upstream-value-ops-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Upstream Value Ops Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Workstreams: {0}' -f $Artifact.summary.workstream_count),
        ('- Unique Source Projects: {0}' -f $Artifact.summary.unique_source_count),
        ('- Failures: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Workstreams',
        ''
    )
    foreach ($ws in $Artifact.workstreams) {
        $lines += ('- `{0}` target=`{1}` sources={2} quality_bar=`{3}`' -f $ws.id, $ws.target_plane, $ws.source_count, $ws.quality_bar)
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
$configPath = Join-Path $context.repoRoot 'config\upstream-value-ops-board.json'
$docPath = Join-Path $context.repoRoot 'docs\continuous-value-extraction-operations.md'
$qualityBarPath = Join-Path $context.repoRoot 'references\upstream-distillation-quality-bar.md'
$ledgerPath = Join-Path $context.repoRoot 'references\upstream-value-ledger.md'
$manifestPath = Join-Path $context.repoRoot 'config\upstream-corpus-manifest.json'
$auditScriptPath = Join-Path $context.repoRoot 'scripts\governance\audit-upstream.ps1'
$releaseReadmePath = Join-Path $context.repoRoot 'docs\releases\README.md'
$releaseLedgerPath = Join-Path $context.repoRoot 'references\release-ledger.jsonl'
$releaseCutPath = Join-Path $context.repoRoot 'scripts\governance\release-cut.ps1'
$assertions = [System.Collections.Generic.List[object]]::new()

foreach ($requiredPath in @($configPath, $docPath, $qualityBarPath, $ledgerPath, $manifestPath, $auditScriptPath, $releaseReadmePath, $releaseLedgerPath, $releaseCutPath)) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $requiredPath) -Message ('required value-ops asset exists: {0}' -f (Get-VgoRelativePathPortable -BasePath $context.repoRoot -TargetPath $requiredPath)) -Details $requiredPath
}
if (-not (Test-Path -LiteralPath $configPath)) { exit 1 }

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$workstreams = @($config.workstreams)
$uniqueSources = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
$workstreamRecords = @()

Add-Assertion -Assertions $assertions -Pass ([string]$config.policy.mode -eq 'continuous_intake') -Message 'value ops mode is continuous_intake' -Details $config.policy.mode
Add-Assertion -Assertions $assertions -Pass ([bool]$config.policy.forbid_unmapped_absorption) -Message 'value ops forbids unmapped absorption'
Add-Assertion -Assertions $assertions -Pass ([bool]$config.policy.require_quality_bar) -Message 'value ops requires quality bar'
Add-Assertion -Assertions $assertions -Pass ($workstreams.Count -ge 6) -Message 'at least six value-op workstreams are declared' -Details $workstreams.Count

foreach ($workstream in $workstreams) {
    $sources = @($workstream.source_projects)
    foreach ($source in $sources) {
        if (-not [string]::IsNullOrWhiteSpace([string]$source)) {
            [void]$uniqueSources.Add([string]$source)
        }
    }

    Add-Assertion -Assertions $assertions -Pass (-not [string]::IsNullOrWhiteSpace([string]$workstream.target_plane)) -Message ("workstream {0} has target plane" -f $workstream.id)
    Add-Assertion -Assertions $assertions -Pass ($sources.Count -gt 0) -Message ("workstream {0} has source projects" -f $workstream.id) -Details $sources
    Add-Assertion -Assertions $assertions -Pass (-not [string]::IsNullOrWhiteSpace([string]$workstream.next_action)) -Message ("workstream {0} has next action" -f $workstream.id)

    $qualityBarRel = [string]$workstream.quality_bar
    $qualityBarExists = $false
    if (-not [string]::IsNullOrWhiteSpace($qualityBarRel)) {
        $qualityBarExists = Test-Path -LiteralPath (Join-Path $context.repoRoot $qualityBarRel)
    }
    Add-Assertion -Assertions $assertions -Pass $qualityBarExists -Message ("workstream {0} quality bar exists" -f $workstream.id) -Details $qualityBarRel

    $workstreamRecords += [pscustomobject]@{
        id = [string]$workstream.id
        target_plane = [string]$workstream.target_plane
        source_count = $sources.Count
        quality_bar = $qualityBarRel
    }
}

Add-Assertion -Assertions $assertions -Pass ($uniqueSources.Count -ge 15) -Message 'value-ops board covers at least 15 distinct source projects' -Details $uniqueSources.Count

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-upstream-value-ops-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    workstreams = $workstreamRecords
    assertions = @($assertions)
    summary = [ordered]@{
        workstream_count = $workstreams.Count
        unique_source_count = $uniqueSources.Count
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $context.repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) { exit 1 }
exit 0
