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

    $jsonPath = Join-Path $dir 'vibe-memory-runtime-v3-gate.json'
    $mdPath = Join-Path $dir 'vibe-memory-runtime-v3-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Memory Runtime v3 Gate',
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

$docPath = Join-Path $repoRoot 'docs/memory-runtime-v3-governance.md'
$policyPath = Join-Path $repoRoot 'config/memory-runtime-v3-policy.json'
$contractPath = Join-Path $repoRoot 'references/memory-runtime-v3-contract.md'
$mem0Path = Join-Path $repoRoot 'config/mem0-backend-policy.json'
$lettaPath = Join-Path $repoRoot 'config/letta-governance-contract.json'

foreach ($path in @($docPath, $policyPath, $contractPath, $mem0Path, $lettaPath)) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $path) -Message ('required asset exists: ' + [System.IO.Path]::GetFileName($path)) -Details $path
}

if ((@($assertions | Where-Object { -not $_.pass }).Count) -eq 0) {
    $docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
    $policyText = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8
    $contractText = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8

    Add-Assertion -Assertions $assertions -Pass ($docText.Contains('single control plane')) -Message 'governance doc contains single control plane'
    Add-Assertion -Assertions $assertions -Pass ($docText.Contains('external preference backend lane')) -Message 'governance doc contains mem0 lane wording'
    Add-Assertion -Assertions $assertions -Pass ($contractText.Contains('state_store')) -Message 'contract names state_store as canonical owner'
    Add-Assertion -Assertions $assertions -Pass ($contractText.Contains('Serena')) -Message 'contract names Serena as canonical owner'
    Add-Assertion -Assertions $assertions -Pass ($contractText.Contains('soft_candidate')) -Message 'contract includes soft_candidate stage'

    Add-Assertion -Assertions $assertions -Pass ($policyText.Contains('memory-runtime-v3')) -Message 'policy contains memory-runtime-v3'
    Add-Assertion -Assertions $assertions -Pass ($policyText.Contains('single_control_plane_only')) -Message 'policy contains single_control_plane_only'
    Add-Assertion -Assertions $assertions -Pass ($policyText.Contains('soft_candidate')) -Message 'policy contains soft_candidate'
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
$artifact = [pscustomobject]@{
    gate = 'vibe-memory-runtime-v3-gate'
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
