param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = "Stop"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        Write-Host "[PASS] $Message"
        return $true
    }

    Write-Host "[FAIL] $Message" -ForegroundColor Red
    return $false
}

function Get-JsonFileStatus {
    param([string]$Path)

    $exists = Test-Path -LiteralPath $Path
    $parsed = $false
    $value = $null

    if ($exists) {
        try {
            $value = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
            $parsed = $true
        } catch {
            $parsed = $false
        }
    }

    return [pscustomobject]@{
        exists = $exists
        parsed = $parsed
        value = $value
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$paths = [ordered]@{
    tool_registry = Join-Path $repoRoot 'config\tool-registry.json'
    risk_tiers = Join-Path $repoRoot 'config\tool-risk-tiers.json'
    egress_allowlist = Join-Path $repoRoot 'config\egress-allowlist.json'
    secrets_policy = Join-Path $repoRoot 'config\secrets-policy.json'
}

Write-Host '=== VCO Tool Governance Gate ==='

$statuses = [ordered]@{}
$assertions = @()
foreach ($pair in $paths.GetEnumerator()) {
    $status = Get-JsonFileStatus -Path $pair.Value
    $statuses[$pair.Key] = [ordered]@{
        path = $pair.Value
        exists = $status.exists
        parsed = $status.parsed
    }
    $assertions += Assert-True -Condition $status.exists -Message "[$($pair.Key)] file exists"
    $assertions += Assert-True -Condition $status.parsed -Message "[$($pair.Key)] valid JSON"
}

$registry = $null
$riskConfig = $null
$egressConfig = $null
$secretsConfig = $null
if ($statuses.tool_registry.parsed) { $registry = (Get-JsonFileStatus -Path $paths.tool_registry).value }
if ($statuses.risk_tiers.parsed) { $riskConfig = (Get-JsonFileStatus -Path $paths.risk_tiers).value }
if ($statuses.egress_allowlist.parsed) { $egressConfig = (Get-JsonFileStatus -Path $paths.egress_allowlist).value }
if ($statuses.secrets_policy.parsed) { $secretsConfig = (Get-JsonFileStatus -Path $paths.secrets_policy).value }

$riskRank = @{}
$riskGuardMap = @{}
if ($null -ne $riskConfig) {
    foreach ($tier in @($riskConfig.tiers)) {
        $riskRank[[string]$tier.id] = [int]$tier.rank
        $riskGuardMap[[string]$tier.id] = $tier.default_guards
    }
}

$defaultUnattendedAllowedTiers = @()
if ($null -ne $registry) {
    $defaultUnattendedAllowedTiers = @($registry.default_runtime_policy.default_unattended_allowed_tiers)
}
foreach ($tierId in $defaultUnattendedAllowedTiers) {
    $assertions += Assert-True -Condition $riskRank.ContainsKey([string]$tierId) -Message "[default_runtime_policy] unattended tier '$tierId' exists"
}

$minimumTierForAction = @{}
if ($null -ne $riskConfig) {
    $riskConfig.action_type_minimum_tier.PSObject.Properties | ForEach-Object {
        $minimumTierForAction[$_.Name] = [string]$_.Value
    }
}

$allowedSecrets = @{}
if ($null -ne $secretsConfig) {
    foreach ($secret in @($secretsConfig.allowed_secret_refs)) {
        $allowedSecrets[[string]$secret.name] = $secret
    }
}

$egressProfiles = @{}
if ($null -ne $egressConfig) {
    foreach ($profile in @($egressConfig.profiles)) {
        $egressProfiles[[string]$profile.id] = $profile
    }
}

$tools = @()
if ($null -ne $registry) {
    $tools = @($registry.tools)
}

$toolIdCounts = @{}
foreach ($tool in $tools) {
    $id = [string]$tool.tool_id
    if (-not $toolIdCounts.ContainsKey($id)) {
        $toolIdCounts[$id] = 0
    }
    $toolIdCounts[$id] += 1
}

$results = [ordered]@{
    files = $statuses
    tools = @()
}

foreach ($tool in $tools) {
    $toolId = [string]$tool.tool_id
    $tierId = [string]$tool.risk_tier
    $toolRank = if ($riskRank.ContainsKey($tierId)) { [int]$riskRank[$tierId] } else { -1 }

    $duplicateFree = ($toolIdCounts[$toolId] -eq 1)
    $tierExists = $riskRank.ContainsKey($tierId)
    $egressExists = $egressProfiles.ContainsKey([string]$tool.egress_profile)

    $secretChecks = @()
    foreach ($secretRef in @($tool.secret_refs)) {
        $secretChecks += [pscustomobject]@{
            secret_ref = [string]$secretRef
            exists = $allowedSecrets.ContainsKey([string]$secretRef)
        }
    }
    $allSecretsValid = (@($secretChecks | Where-Object { -not $_.exists }).Count -eq 0)

    $actionChecks = @()
    foreach ($actionType in @($tool.action_types)) {
        $requiredTierId = if ($minimumTierForAction.ContainsKey([string]$actionType)) { [string]$minimumTierForAction[[string]$actionType] } else { $null }
        $requiredRank = if ($null -ne $requiredTierId -and $riskRank.ContainsKey($requiredTierId)) { [int]$riskRank[$requiredTierId] } else { -1 }
        $satisfied = ($null -ne $requiredTierId -and $tierExists -and $toolRank -ge $requiredRank)
        $actionChecks += [pscustomobject]@{
            action_type = [string]$actionType
            minimum_tier = $requiredTierId
            satisfied = $satisfied
        }
    }
    $allActionsValid = (@($actionChecks | Where-Object { -not $_.satisfied }).Count -eq 0)

    $perActionRequired = [bool]$tool.human_confirmation.per_action_required
    $unattendedAllowed = [bool]$tool.human_confirmation.unattended_allowed
    $tier2OrTier3GuardOk = ($toolRank -lt 2) -or $perActionRequired
    $tier3UnattendedOk = ($toolRank -lt 3) -or (-not $unattendedAllowed)

    $contractReference = [string]$tool.contract_reference
    $contractPath = $null
    $contractExists = $true
    if (-not [string]::IsNullOrWhiteSpace($contractReference)) {
        $contractPath = Join-Path $repoRoot $contractReference
        $contractExists = Test-Path -LiteralPath $contractPath
    }

    $assertions += Assert-True -Condition $duplicateFree -Message "[tool:$toolId] unique tool_id"
    $assertions += Assert-True -Condition $tierExists -Message "[tool:$toolId] risk tier exists"
    $assertions += Assert-True -Condition $egressExists -Message "[tool:$toolId] egress profile exists"
    $assertions += Assert-True -Condition $allSecretsValid -Message "[tool:$toolId] secret refs registered"
    $assertions += Assert-True -Condition $allActionsValid -Message "[tool:$toolId] action types meet minimum tier"
    $assertions += Assert-True -Condition $tier2OrTier3GuardOk -Message "[tool:$toolId] tier2+ requires per_action confirmation"
    $assertions += Assert-True -Condition $tier3UnattendedOk -Message "[tool:$toolId] tier3 disallows unattended"
    $assertions += Assert-True -Condition $contractExists -Message "[tool:$toolId] contract reference exists when declared"

    $results.tools += [pscustomobject]@{
        tool_id = $toolId
        risk_tier = $tierId
        egress_profile = [string]$tool.egress_profile
        unique_tool_id = $duplicateFree
        risk_tier_exists = $tierExists
        egress_profile_exists = $egressExists
        secrets = @($secretChecks)
        actions = @($actionChecks)
        per_action_required = $perActionRequired
        unattended_allowed = $unattendedAllowed
        contract_reference = if ([string]::IsNullOrWhiteSpace($contractReference)) { $null } else { $contractReference }
        contract_exists = $contractExists
    }
}

$total = $assertions.Count
$passed = @($assertions | Where-Object { $_ }).Count
$failed = $total - $passed
$gatePass = ($failed -eq 0)

Write-Host ''
Write-Host '=== Summary ==='
Write-Host ("Total assertions: {0}" -f $total)
Write-Host ("Passed: {0}" -f $passed)
Write-Host ("Failed: {0}" -f $failed)
Write-Host ("Gate Result: {0}" -f $(if ($gatePass) { 'PASS' } else { 'FAIL' }))

if ($WriteArtifacts) {
    $outDir = Join-Path $repoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonPath = Join-Path $outDir 'tool-governance-gate.json'
    $mdPath = Join-Path $outDir 'tool-governance-gate.md'

    $artifact = [ordered]@{
        generated_at = [DateTime]::UtcNow.ToString('o')
        gate_result = if ($gatePass) { 'PASS' } else { 'FAIL' }
        assertions = [ordered]@{
            total = $total
            passed = $passed
            failed = $failed
        }
        results = $results
    }

    $artifact | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $md = @(
        '# VCO Tool Governance Gate',
        '',
        ("- Generated: {0}" -f $artifact.generated_at),
        ("- Gate Result: **{0}**" -f $artifact.gate_result),
        ("- Assertions: total={0}, passed={1}, failed={2}" -f $total, $passed, $failed),
        '',
        '## Tool Summary'
    )
    foreach ($toolResult in @($results.tools)) {
        $missingSecrets = @($toolResult.secrets | Where-Object { -not $_.exists }).secret_ref
        $badActions = @($toolResult.actions | Where-Object { -not $_.satisfied }).action_type
        $md += ("- {0}: tier={1}, egress={2}, secrets_missing={3}, bad_actions={4}, contract_ok={5}" -f `
            $toolResult.tool_id,
            $toolResult.risk_tier,
            $toolResult.egress_profile,
            $(if (@($missingSecrets).Count -gt 0) { (@($missingSecrets) -join ', ') } else { 'none' }),
            $(if (@($badActions).Count -gt 0) { (@($badActions) -join ', ') } else { 'none' }),
            $toolResult.contract_exists)
    }
    $md -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8

    Write-Host ''
    Write-Host 'Artifacts written:'
    Write-Host ("- {0}" -f $jsonPath)
    Write-Host ("- {0}" -f $mdPath)
}

if (-not $gatePass) { exit 1 }
