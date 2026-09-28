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

    Write-Host ("[{0}] {1}" -f $(if ($Pass) { 'PASS' } else { 'FAIL' }), $Message) -ForegroundColor $(if ($Pass) { 'Green' } else { 'Red' })
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-release-truth-consistency-gate.json'
    $mdPath = Join-Path $dir 'vibe-release-truth-consistency-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Release Truth Consistency Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Failure count: `{0}`' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )
    foreach ($assertion in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$assertions = [System.Collections.Generic.List[object]]::new()

$liveContractPath = Join-Path $repoRoot 'config\live-document-contract.json'
$runtimeContractPath = Join-Path $repoRoot 'config\runtime-contract.json'
$previewContractPath = Join-Path $repoRoot 'config\operator-preview-contract.json'
$promotionBoardPath = Join-Path $repoRoot 'config\promotion-board.json'

$requiredContractPaths = @(
    $liveContractPath,
    $runtimeContractPath,
    $previewContractPath,
    $promotionBoardPath
)
foreach ($requiredContractPath in $requiredContractPaths) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $requiredContractPath -PathType Leaf) -Message ('release truth contract exists: {0}' -f (Split-Path -Leaf $requiredContractPath)) -Details $requiredContractPath
}

$liveContract = Get-Content -LiteralPath $liveContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$runtimeContract = Get-Content -LiteralPath $runtimeContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$previewContract = Get-Content -LiteralPath $previewContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$releaseCutOperator = $previewContract.operators.'release-cut'
$promotionBoard = Get-Content -LiteralPath $promotionBoardPath -Raw -Encoding UTF8 | ConvertFrom-Json
$releasePlane = @($promotionBoard.planes | Where-Object { [string]$_.plane_id -eq 'operator-release-train' }) | Select-Object -First 1

Add-Assertion -Assertions $assertions -Pass ([string]$liveContract.artifact_sink.root -eq '.vibeskills/runs') -Message 'release truth uses the canonical run artifact sink'
Add-Assertion -Assertions $assertions -Pass ([string]$liveContract.artifact_sink.primary_document_paths.requirement -eq 'requirement.md') -Message 'release truth stores requirements inside the run sink'
Add-Assertion -Assertions $assertions -Pass ([string]$liveContract.artifact_sink.primary_document_paths.plan -eq 'plan.md') -Message 'release truth stores plans inside the run sink'
Add-Assertion -Assertions $assertions -Pass ([string]$liveContract.artifact_sink.legacy_write_mode -eq 'disabled') -Message 'release truth keeps legacy documentation writes disabled'
Add-Assertion -Assertions $assertions -Pass (@($runtimeContract.stages | Where-Object { [string]$_.receipt -match 'docs/(requirements|plans)' }).Count -eq 0) -Message 'runtime stage receipts do not require historical documentation roots'
Add-Assertion -Assertions $assertions -Pass ([int]$liveContract.proof_retention.pull_request_days -eq 30) -Message 'release truth keeps pull-request proof retention at 30 days'
Add-Assertion -Assertions $assertions -Pass ([int]$liveContract.proof_retention.main_and_scheduled_days -eq 90) -Message 'release truth keeps main and scheduled proof retention at 90 days'
Add-Assertion -Assertions $assertions -Pass (@($releaseCutOperator.apply_gates) -contains 'scripts/verify/vibe-release-truth-consistency-gate.ps1') -Message 'release-cut contract includes release-truth consistency gate'
Add-Assertion -Assertions $assertions -Pass ($null -ne $releasePlane) -Message 'promotion board contains operator-release-train plane'
if ($releasePlane) {
    Add-Assertion -Assertions $assertions -Pass (@($releasePlane.required_gates) -contains 'vibe-release-truth-consistency-gate') -Message 'operator-release-train plane requires release-truth consistency gate'
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-release-truth-consistency-gate'
    repo_root = $repoRoot
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    generated_at = (Get-Date).ToString('s')
    assertions = @($assertions)
    summary = [pscustomobject]@{
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) {
    exit 1
}
