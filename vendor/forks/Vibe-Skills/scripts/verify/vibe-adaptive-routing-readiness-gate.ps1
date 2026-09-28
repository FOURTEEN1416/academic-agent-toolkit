param(
    [switch]$Strict,
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

    $jsonPath = Join-Path $dir 'vibe-adaptive-routing-readiness-gate.json'
    $mdPath = Join-Path $dir 'vibe-adaptive-routing-readiness-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Adaptive Routing Readiness Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Stage: `{0}`' -f $Artifact.stage),
        ('- Strict: `{0}`' -f $Artifact.strict),
        ('- Failure Count: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )
    foreach ($assertion in $Artifact.assertions) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Get-RouteEventFiles {
    param([string]$RepoRoot)

    $telemetryDir = Join-Path $RepoRoot 'outputs\telemetry'
    if (-not (Test-Path -LiteralPath $telemetryDir)) {
        return @()
    }

    return @(Get-ChildItem -LiteralPath $telemetryDir -Filter 'route-events-*.jsonl' -File -ErrorAction SilentlyContinue)
}

function Ensure-RouteEventTelemetry {
    param([string]$RepoRoot)

    $existing = @(Get-RouteEventFiles -RepoRoot $RepoRoot)
    if ($existing.Count -gt 0) {
        return $existing
    }

    $observabilityGate = Join-Path $RepoRoot 'scripts\verify\vibe-observability-gate.ps1'
    if (-not (Test-Path -LiteralPath $observabilityGate)) {
        return @()
    }

    & $observabilityGate -TelemetryOutputRel 'outputs/telemetry' -KeepTelemetry
    if ($LASTEXITCODE -ne 0) {
        throw 'failed to seed route event telemetry via vibe-observability-gate.ps1'
    }

    return @(Get-RouteEventFiles -RepoRoot $RepoRoot)
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$configPath = Join-Path $context.repoRoot 'config\adaptive-routing-eval-governance.json'
$docPath = Join-Path $context.repoRoot 'docs\governance\adaptive-routing-eval-governance.md'
$replayContract = Join-Path $context.repoRoot 'references\eval-replay-ledger-contract.md'
$promotionBoardPath = Join-Path $context.repoRoot 'config\promotion-board.json'
$requiredScripts = @(
    'scripts/verify/vibe-routing-stability-gate.ps1',
    'scripts/verify/vibe-pack-regression-matrix.ps1',
    'scripts/verify/vibe-keyword-precision-audit.ps1',
    'scripts/verify/vibe-observability-gate.ps1',
    'scripts/verify/vibe-pilot-scenarios.ps1',
    'scripts/research/vibe-adaptive-train.ps1'
)
$assertions = [System.Collections.Generic.List[object]]::new()

Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $configPath) -Message 'adaptive routing governance config exists' -Details $configPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $docPath) -Message 'adaptive routing governance doc exists' -Details $docPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $replayContract) -Message 'eval replay ledger contract exists' -Details $replayContract
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $promotionBoardPath) -Message 'promotion board exists for adaptive rollout linkage' -Details $promotionBoardPath
foreach ($scriptRel in $requiredScripts) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath (Join-Path $context.repoRoot $scriptRel)) -Message ("required adaptive routing asset exists: {0}" -f $scriptRel) -Details $scriptRel
}
if (-not (Test-Path -LiteralPath $configPath)) { exit 1 }

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$allowedStages = @('off', 'shadow_ready', 'soft_candidate', 'strict_candidate')
$routeEvents = @(Ensure-RouteEventTelemetry -RepoRoot $context.repoRoot)
$routeEventCount = @($routeEvents).Count

Add-Assertion -Assertions $assertions -Pass ($allowedStages -contains [string]$config.stage) -Message 'adaptive routing stage is in allowed readiness set' -Details $config.stage
Add-Assertion -Assertions $assertions -Pass ([bool]$config.guardrails.advice_first) -Message 'guardrail advice_first enabled'
Add-Assertion -Assertions $assertions -Pass ([bool]$config.guardrails.shadow_first) -Message 'guardrail shadow_first enabled'
Add-Assertion -Assertions $assertions -Pass ([bool]$config.guardrails.auto_promote_forbidden) -Message 'guardrail auto_promote_forbidden enabled'
Add-Assertion -Assertions $assertions -Pass ([bool]$config.guardrails.no_second_router) -Message 'guardrail no_second_router enabled'
Add-Assertion -Assertions $assertions -Pass (@($config.baseline_heuristics).Count -ge 3) -Message 'at least three baseline heuristics are defined' -Details @($config.baseline_heuristics).Count
Add-Assertion -Assertions $assertions -Pass (@($config.evaluation_scenarios).Count -ge 3) -Message 'at least three evaluation scenarios are defined' -Details @($config.evaluation_scenarios).Count
Add-Assertion -Assertions $assertions -Pass ($routeEventCount -gt 0) -Message 'route event telemetry exists for replay/audit' -Details $routeEventCount

if ($Strict) {
    Add-Assertion -Assertions $assertions -Pass ([string]$config.stage -eq 'shadow_ready') -Message 'strict mode requires stage shadow_ready' -Details $config.stage
    Add-Assertion -Assertions $assertions -Pass ([string]$config.replay_contract -eq 'references/eval-replay-ledger-contract.md') -Message 'strict mode requires canonical replay contract path' -Details $config.replay_contract
    Add-Assertion -Assertions $assertions -Pass (@($config.promotion_heuristics.shadow_to_soft_requires).Count -ge 3) -Message 'strict mode requires explicit shadow_to_soft heuristics' -Details @($config.promotion_heuristics.shadow_to_soft_requires).Count
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-adaptive-routing-readiness-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    strict = [bool]$Strict
    stage = [string]$config.stage
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    assertions = @($assertions)
    summary = [ordered]@{
        failure_count = $failureCount
        telemetry_files = $routeEventCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $context.repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) { exit 1 }
exit 0
