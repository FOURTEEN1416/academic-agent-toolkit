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

    $jsonPath = Join-Path $dir 'vibe-letta-policy-conformance-gate.json'
    $mdPath = Join-Path $dir 'vibe-letta-policy-conformance-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Letta Policy Conformance Gate',
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

$lettaPath = Join-Path $repoRoot 'config/letta-governance-contract.json'
$runtimePath = Join-Path $repoRoot 'config/memory-runtime-v3-policy.json'
$docPath = Join-Path $repoRoot 'docs/letta-policy-conformance.md'
$memoryBlockPath = Join-Path $repoRoot 'references/memory-block-contract.md'
$toolRulePath = Join-Path $repoRoot 'references/tool-rule-contract.md'

foreach ($path in @($lettaPath, $runtimePath, $docPath, $memoryBlockPath, $toolRulePath)) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $path) -Message ('required asset exists: ' + [System.IO.Path]::GetFileName($path)) -Details $path
}

if ((@($assertions | Where-Object { -not $_.pass }).Count) -eq 0) {
    $letta = Get-Content -LiteralPath $lettaPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
    $memoryBlockText = Get-Content -LiteralPath $memoryBlockPath -Raw -Encoding UTF8
    $toolRuleText = Get-Content -LiteralPath $toolRulePath -Raw -Encoding UTF8
    $docLower = $docText.ToLowerInvariant()
    $memoryBlockLower = $memoryBlockText.ToLowerInvariant()
    $toolRuleLower = $toolRuleText.ToLowerInvariant()

    Add-Assertion -Assertions $assertions -Pass ($letta.role -eq 'contract_source_only') -Message 'letta role stays contract_source_only'
    Add-Assertion -Assertions $assertions -Pass ($letta.contracts.memory_block_mapping -eq $true) -Message 'letta contract enables memory_block_mapping'
    Add-Assertion -Assertions $assertions -Pass ($letta.contracts.archival_search_contract -eq $true) -Message 'letta contract enables archival_search_contract'
    Add-Assertion -Assertions $assertions -Pass ($letta.contracts.tool_rule_contract -eq $true) -Message 'letta contract enables tool_rule_contract'
    Add-Assertion -Assertions $assertions -Pass ($letta.contracts.token_pressure_policy -eq $true) -Message 'letta contract enables token_pressure_policy'
    Add-Assertion -Assertions $assertions -Pass ($letta.forbid_runtime_takeover -eq $true) -Message 'letta contract forbids runtime takeover'
    Add-Assertion -Assertions $assertions -Pass ($letta.forbid_second_orchestrator -eq $true) -Message 'letta contract forbids second orchestrator'
    Add-Assertion -Assertions $assertions -Pass ($letta.forbid_route_mutation -eq $true) -Message 'letta contract forbids route mutation'

    Add-Assertion -Assertions $assertions -Pass ($runtime.extension_planes.letta.role -eq 'policy_contract_source') -Message 'runtime v3 registers letta as policy_contract_source'
    Add-Assertion -Assertions $assertions -Pass ($runtime.extension_planes.letta.token_pressure_contract_key -eq 'token_pressure_policy') -Message 'runtime v3 sets token_pressure_policy contract key'
    Add-Assertion -Assertions $assertions -Pass ($runtime.extension_planes.letta.cannot_take_runtime_ownership -eq $true) -Message 'runtime v3 prevents letta runtime ownership'

    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('memory block mapping')) -Message 'conformance doc covers memory block mapping'
    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('archival search contract')) -Message 'conformance doc covers archival search contract'
    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('tool-rule contract')) -Message 'conformance doc covers tool-rule contract'
    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('token-pressure policy')) -Message 'conformance doc covers token-pressure policy'
    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('compaction')) -Message 'conformance doc covers compaction discipline'
    Add-Assertion -Assertions $assertions -Pass ($docText.Contains('No second workflow surface')) -Message 'conformance doc forbids second workflow surface'
    Add-Assertion -Assertions $assertions -Pass ($docLower.Contains('shadow')) -Message 'conformance doc preserves shadow fallback'

    Add-Assertion -Assertions $assertions -Pass ($memoryBlockLower.Contains('state_store')) -Message 'memory block contract maps to state_store'
    Add-Assertion -Assertions $assertions -Pass ($memoryBlockText.Contains('Serena')) -Message 'memory block contract maps to Serena'
    Add-Assertion -Assertions $assertions -Pass ($memoryBlockText.Contains('Cognee')) -Message 'memory block contract maps to Cognee'
    Add-Assertion -Assertions $assertions -Pass ($memoryBlockLower.Contains('organization, not ownership transfer')) -Message 'memory block contract preserves ownership'

    Add-Assertion -Assertions $assertions -Pass ($toolRuleLower.Contains('require confirmation')) -Message 'tool-rule contract includes require confirmation'
    Add-Assertion -Assertions $assertions -Pass ($toolRuleLower.Contains('forbid unsafe escalation')) -Message 'tool-rule contract includes forbid unsafe escalation'
    Add-Assertion -Assertions $assertions -Pass ($toolRuleLower.Contains('budget-aware tool use')) -Message 'tool-rule contract includes budget-aware tool use'
    Add-Assertion -Assertions $assertions -Pass ($toolRuleText.Contains('cannot replace VCO routing')) -Message 'tool-rule contract preserves VCO routing authority'
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
$artifact = [pscustomobject]@{
    gate = 'vibe-letta-policy-conformance-gate'
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
