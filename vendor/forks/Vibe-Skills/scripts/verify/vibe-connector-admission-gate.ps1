param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Assert-Collect {
    param(
        [bool]$Condition,
        [string]$Message,
        [object]$Details = $null
    )
    if ($Condition) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
    }
    return [pscustomobject]@{ pass = $Condition; message = $Message; details = $Details }
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$docPath = Join-Path $repoRoot 'docs\connector-admission-governance.md'
$matrixPath = Join-Path $repoRoot 'references\connector-admission-matrix.md'
$policyPath = Join-Path $repoRoot 'config\connector-provider-policy.json'
$results = New-Object System.Collections.Generic.List[object]

$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $docPath) -Message '存在 connector governance 文档')) | Out-Null
$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $matrixPath) -Message '存在 connector admission matrix')) | Out-Null
$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $policyPath) -Message '存在 connector provider policy')) | Out-Null
if (@($results | Where-Object { -not $_.pass }).Count -gt 0) {
    exit 1
}

$docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
$matrixText = Get-Content -LiteralPath $matrixPath -Raw -Encoding UTF8
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json

$results.Add((Assert-Collect -Condition ($policy.plane -eq 'connector_admission') -Message 'policy.plane = connector_admission')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.control_plane_owner -eq 'vco') -Message 'policy.control_plane_owner = vco')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.allow_second_orchestrator -eq $false) -Message '禁止 second orchestrator')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.allow_provider_takeover -eq $false) -Message '禁止 provider takeover')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.allow_auto_install_from_catalog -eq $false) -Message '禁止 catalog auto-install')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.require_allowlist_entry -eq $true) -Message 'require_allowlist_entry = true')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.require_confirm_for_write -eq $true) -Message 'require_confirm_for_write = true')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.allowlist.Count -eq 3) -Message 'allowlist 共 3 项')) | Out-Null

$results.Add((Assert-Collect -Condition ($policy.sources.'awesome-mcp-servers'.position -eq 'catalog_reference_only') -Message 'awesome-mcp-servers 固定为 catalog_reference_only')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.'awesome-mcp-servers'.status -eq 'catalog_governed') -Message 'awesome-mcp-servers status = catalog_governed')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.composio.position -eq 'provider_candidate') -Message 'composio 固定为 provider_candidate')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.composio.status -eq 'shadow_governed') -Message 'composio status = shadow_governed')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.composio.confirm_required -eq $true) -Message 'composio 默认 confirm_required')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.composio.takeover_forbidden -eq $true) -Message 'composio takeover_forbidden = true')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.activepieces.position -eq 'provider_candidate') -Message 'activepieces 固定为 provider_candidate')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.activepieces.status -eq 'shadow_governed') -Message 'activepieces status = shadow_governed')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.activepieces.confirm_required -eq $true) -Message 'activepieces 默认 confirm_required')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.sources.activepieces.takeover_forbidden -eq $true) -Message 'activepieces takeover_forbidden = true')) | Out-Null

$denylistExpected = @('second_orchestrator', 'route_override', 'auto_install_from_catalog', 'unconfirmed_production_write', 'credential_exfiltration', 'connector_defined_memory_truth_source')
foreach ($item in $denylistExpected) {
    $results.Add((Assert-Collect -Condition (@($policy.denylist) -contains $item) -Message ('denylist 包含 {0}' -f $item))) | Out-Null
}

$docKeywords = @('allowlist', 'denylist', 'catalog_reference_only', 'provider_candidate', 'second orchestrator')
foreach ($keyword in $docKeywords) {
    $results.Add((Assert-Collect -Condition ($docText.Contains($keyword)) -Message ('governance 文档包含关键词 {0}' -f $keyword))) | Out-Null
}
$matrixKeywords = @('awesome-mcp-servers', 'composio', 'activepieces', 'catalog_governed', 'shadow_governed')
foreach ($keyword in $matrixKeywords) {
    $results.Add((Assert-Collect -Condition ($matrixText.Contains($keyword)) -Message ('matrix 包含关键词 {0}' -f $keyword))) | Out-Null
}

$total = $results.Count
$passed = @($results | Where-Object { $_.pass }).Count
$failed = $total - $passed
$gatePass = ($failed -eq 0)
$gateResultText = if ($gatePass) { 'PASS' } else { 'FAIL' }

Write-Host ''
Write-Host '=== Summary ==='
Write-Host ('Total assertions: ' + $total)
Write-Host ('Passed: ' + $passed)
Write-Host ('Failed: ' + $failed)
Write-Host ('Gate Result: ' + $gateResultText)

if ($WriteArtifacts) {
    $outDir = Join-Path $repoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonPath = Join-Path $outDir 'vibe-connector-admission-gate.json'
    $mdPath = Join-Path $outDir 'vibe-connector-admission-gate.md'
    $assertionSummary = @{ total = $total; passed = $passed; failed = $failed }
    $artifact = @{
        generated_at = [DateTime]::UtcNow.ToString('o')
        gate_result = $gateResultText
        assertions = $assertionSummary
        policy_path = $policyPath
        results = [object[]]$results
    }
    $artifact | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    $md = @(
        '# VCO Connector Admission Gate',
        '',
        ('- Gate Result: **' + $artifact.gate_result + '**'),
        ('- Assertions: total=' + $total + ', passed=' + $passed + ', failed=' + $failed),
        ('- Policy: `' + $policyPath + '`')
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $mdPath -Value $md -Encoding UTF8
}

if (-not $gatePass) {
    exit 1
}
