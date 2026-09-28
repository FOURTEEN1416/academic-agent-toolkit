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

    $Assertions.Add([pscustomobject]@{
        pass = [bool]$Pass
        message = $Message
        details = $Details
    }) | Out-Null

    $color = if ($Pass) { 'Green' } else { 'Red' }
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ('[{0}] {1}' -f $status, $Message) -ForegroundColor $color
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-ops-cockpit-gate.json'
    $mdPath = Join-Path $dir 'vibe-ops-cockpit-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Ops Cockpit Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Failures: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )
    foreach ($assertion in $Artifact.assertions) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$assertions = [System.Collections.Generic.List[object]]::new()

$requiredPaths = @(
    'docs/ops-cockpit-governance.md',
    'config/ops-cockpit-panel-contract.json',
    'references/ops-cockpit-gap-matrix.md',
    'outputs/dashboard/ops-dashboard.json',
    'outputs/dashboard/ops-dashboard.md'
)
foreach ($relPath in $requiredPaths) {
    $fullPath = Join-Path $repoRoot $relPath
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $fullPath) -Message ('required asset exists: ' + $relPath) -Details $fullPath
}

$keywordChecks = @(
    [pscustomobject]@{ path = 'docs/ops-cockpit-governance.md'; keywords = @(
        'actionable panels',
        'Every panel must produce',
        'ops-dashboard.json',
        'gap matrix'
    ) },
    [pscustomobject]@{ path = 'config/ops-cockpit-panel-contract.json'; keywords = @(
        'freshness',
        'promotion',
        'replay',
        'rollback',
        'release'
    ) },
    [pscustomobject]@{ path = 'references/ops-cockpit-gap-matrix.md'; keywords = @(
        'plane_id',
        'blocker',
        'evidence_ref',
        'next_action'
    ) },
    [pscustomobject]@{ path = 'outputs/dashboard/ops-dashboard.md'; keywords = @(
        'Actionable Panels',
        'Blockers',
        'Evidence',
        'Next Action'
    ) }
)
foreach ($check in $keywordChecks) {
    $targetPath = Join-Path $repoRoot $check.path
    if (-not (Test-Path -LiteralPath $targetPath)) {
        continue
    }
    $raw = Get-Content -LiteralPath $targetPath -Raw -Encoding UTF8
    foreach ($keyword in @($check.keywords)) {
        Add-Assertion -Assertions $assertions -Pass ($raw.Contains($keyword)) -Message ('keyword present in ' + $check.path + ': ' + $keyword) -Details $keyword
    }
}

$contractPath = Join-Path $repoRoot 'config\ops-cockpit-panel-contract.json'
$dashboardJsonPath = Join-Path $repoRoot 'outputs\dashboard\ops-dashboard.json'
if ((Test-Path -LiteralPath $contractPath) -and (Test-Path -LiteralPath $dashboardJsonPath)) {
    $contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $dashboard = Get-Content -LiteralPath $dashboardJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $hasActionablePanels = $dashboard.PSObject.Properties.Name -contains 'actionable_panels'
    Add-Assertion -Assertions $assertions -Pass $hasActionablePanels -Message 'dashboard declares actionable_panels'
    $panels = if ($hasActionablePanels) { @($dashboard.actionable_panels) } else { @() }
    foreach ($panelDef in @($contract.panels)) {
        $panelId = [string]$panelDef.panel_id
        $matchedPanels = @($panels | Where-Object { $_.panel_id -eq $panelId } | Select-Object -First 1)
        $panel = if ($matchedPanels.Count -gt 0) { $matchedPanels[0] } else { $null }
        Add-Assertion -Assertions $assertions -Pass ($null -ne $panel) -Message ('dashboard contains panel: ' + $panelId) -Details $panelId
        if ($null -eq $panel) {
            continue
        }
        foreach ($field in @($panelDef.required_fields)) {
            $hasField = $panel.PSObject.Properties.Name -contains $field
            $value = if ($hasField) { $panel.$field } else { $null }
            $nonEmpty = $false
            if ($hasField) {
                if ($value -is [System.Array]) {
                    $nonEmpty = @($value).Count -gt 0
                } else {
                    $nonEmpty = -not [string]::IsNullOrWhiteSpace([string]$value)
                }
            }
            Add-Assertion -Assertions $assertions -Pass ($hasField -and $nonEmpty) -Message ('panel {0} provides field {1}' -f $panelId, $field) -Details $value
        }
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
$artifact = [pscustomobject]@{
    gate = 'vibe-ops-cockpit-gate'
    repo_root = $repoRoot
    gate_result = $gateResult
    generated_at = (Get-Date).ToString('s')
    assertions = @($assertions)
    summary = [ordered]@{
        total = $assertions.Count
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) {
    exit 1
}
