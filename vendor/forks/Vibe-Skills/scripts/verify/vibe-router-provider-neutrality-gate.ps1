param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-router-provider-neutrality-gate.json'
    $mdPath = Join-Path $dir 'vibe-router-provider-neutrality-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Router Provider Neutrality Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Providers declared: `{0}`' -f $Artifact.summary.provider_count),
        ('- Missing required files: `{0}`' -f $Artifact.summary.missing_required_files),
        ('- Boundary violations: `{0}`' -f $Artifact.summary.boundary_violations),
        ('- Failure count: `{0}`' -f $Artifact.summary.failure_count),
        '',
        '## Boundary Contract',
        '',
        ('- canonical_authority_script: `{0}`' -f $Artifact.results.canonical_authority_script),
        ('- provider_layer_advice_only: `{0}`' -f $Artifact.results.provider_layer_advice_only),
        '',
        '## Providers',
        ''
    )

    foreach ($p in @($Artifact.results.providers)) {
        $lines += ('- `{0}` kind=`{1}` module=`{2}` abstain_reason=`{3}`' -f $p.id, $p.kind, $p.module_relpath, $p.abstain_reason)
    }

    if (@($Artifact.results.failures).Count -gt 0) {
        $lines += ''
        $lines += '## Failures'
        $lines += ''
        foreach ($f in @($Artifact.results.failures)) {
            $lines += ('- {0}' -f $f)
        }
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Require-File {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [System.Collections.Generic.List[string]]$Failures
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        [void]$Failures.Add("missing_required_file:$Path")
        return $false
    }
    return $true
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot

$govPath = Join-Path $repoRoot 'config\router-model-governance.json'
$registryPath = Join-Path $repoRoot 'config\router-provider-registry.json'
$defaultsPath = Join-Path $repoRoot 'config\router-provider-defaults.json'
$schemaPath = Join-Path $repoRoot 'schemas\router-provider.schema.json'
$docPath = Join-Path $repoRoot 'docs\universalization\router-provider-layer.md'

$failures = New-Object System.Collections.Generic.List[string]
$requiredOk = $true
$requiredOk = (Require-File -Path $govPath -Failures $failures) -and $requiredOk
$requiredOk = (Require-File -Path $registryPath -Failures $failures) -and $requiredOk
$requiredOk = (Require-File -Path $defaultsPath -Failures $failures) -and $requiredOk
$requiredOk = (Require-File -Path $schemaPath -Failures $failures) -and $requiredOk
$requiredOk = (Require-File -Path $docPath -Failures $failures) -and $requiredOk

$gov = $null
$registry = $null
$defaults = $null
if ($requiredOk) {
    try { $gov = Get-Content -LiteralPath $govPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { [void]$failures.Add("invalid_json:$govPath") }
    try { $registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { [void]$failures.Add("invalid_json:$registryPath") }
    try { $defaults = Get-Content -LiteralPath $defaultsPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { [void]$failures.Add("invalid_json:$defaultsPath") }
}

if ($gov) {
    if ([string]$gov.control_plane_owner -ne 'canonical-pack-router') { [void]$failures.Add('control_plane_owner_mismatch') }
    if (-not $gov.provider_layer) { [void]$failures.Add('missing_provider_layer_section') }
    if ($gov.provider_layer -and [bool]$gov.provider_layer.authoritative) { [void]$failures.Add('provider_layer_must_not_be_authoritative') }
    if ($gov.provider_layer -and -not [bool]$gov.provider_layer.provider_neutral_contract_required) { [void]$failures.Add('provider_neutral_contract_required_false') }
    if (-not $gov.provider_neutral_contract) { [void]$failures.Add('missing_provider_neutral_contract_block') }
}

$providersOut = @()
$boundaryViolations = 0
if ($registry) {
    if ([string]$registry.policy -ne 'router-provider-registry') { [void]$failures.Add('registry_policy_mismatch') }
    $authorityScript = if ($registry.canonical_router_authority -and $registry.canonical_router_authority.script_relpath) { [string]$registry.canonical_router_authority.script_relpath } else { '' }
    if ($authorityScript -ne 'scripts/router/resolve-pack-route.ps1') { [void]$failures.Add('canonical_authority_script_mismatch') }
    if (-not [bool]($registry.canonical_router_authority.provider_layer_advice_only)) { [void]$failures.Add('provider_layer_must_be_advice_only') }

    $ids = @()
    foreach ($p in @($registry.providers)) {
        if (-not $p) { continue }
        $id = [string]$p.id
        if ([string]::IsNullOrWhiteSpace($id)) {
            [void]$failures.Add('provider_missing_id')
            continue
        }
        $ids += $id

        $moduleRel = [string]$p.module_relpath
        if ([string]::IsNullOrWhiteSpace($moduleRel)) {
            [void]$failures.Add(("provider_missing_module_relpath:{0}" -f $id))
            $boundaryViolations++
        } else {
            $moduleFull = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $moduleRel
            $routerModuleRoot = Join-Path $repoRoot 'scripts\router\modules'
            if (-not (Test-Path -LiteralPath $moduleFull)) {
                [void]$failures.Add(("provider_module_missing:{0}:{1}" -f $id, $moduleRel))
                $boundaryViolations++
            } elseif (-not (Test-VgoPathWithin -ParentPath $routerModuleRoot -ChildPath $moduleFull)) {
                [void]$failures.Add(("provider_module_outside_router_modules:{0}:{1}" -f $id, $moduleRel))
                $boundaryViolations++
            }
        }

        $abstainReason = if ($p.offline_contract -and $p.offline_contract.abstain_reason) { [string]$p.offline_contract.abstain_reason } else { '' }
        if ([string]::IsNullOrWhiteSpace($abstainReason)) {
            [void]$failures.Add(("provider_missing_abstain_reason:{0}" -f $id))
            $boundaryViolations++
        }

        $providersOut += [pscustomobject]@{
            id = $id
            kind = if ($p.kind) { [string]$p.kind } else { 'unknown' }
            module_relpath = $moduleRel
            abstain_reason = $abstainReason
        }
    }

    $dup = @($ids | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { [string]$_.Name })
    foreach ($d in $dup) { [void]$failures.Add(("duplicate_provider_id:{0}" -f $d)) }
}

if ($defaults) {
    if ([string]$defaults.policy -ne 'router-provider-layer-defaults') { [void]$failures.Add('defaults_policy_mismatch') }
    $states = @($defaults.runtime_states)
    foreach ($s in @('provider-assisted', 'heuristic-only', 'offline-frozen')) {
        if (-not ($states -contains $s)) { [void]$failures.Add(("missing_runtime_state:{0}" -f $s)) }
    }
    if ([string]$defaults.default_runtime_state -ne 'heuristic-only') { [void]$failures.Add('default_runtime_state_must_be_heuristic_only') }
}

if (Test-Path -LiteralPath $docPath) {
    $doc = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
    foreach ($needle in @(
        'scripts/router/resolve-pack-route.ps1',
        'config/router-provider-registry.json',
        'config/router-provider-defaults.json',
        'scripts/verify/vibe-router-provider-neutrality-gate.ps1',
        'scripts/verify/vibe-router-offline-degrade-contract-gate.ps1'
    )) {
        if ($doc -notmatch [Regex]::Escape($needle)) {
            [void]$failures.Add(("doc_missing_reference:{0}" -f $needle))
        }
    }
}

$gateResult = if ($failures.Count -eq 0) { 'PASS' } else { 'FAIL' }
$summary = [pscustomobject]@{
    provider_count = [int]@($providersOut).Count
    missing_required_files = [int](@($failures | Where-Object { $_ -like 'missing_required_file:*' }).Count)
    boundary_violations = [int]$boundaryViolations
    failure_count = [int]$failures.Count
}

$artifact = [pscustomobject]@{
    gate = 'vibe-router-provider-neutrality-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    summary = $summary
    results = [pscustomobject]@{
        canonical_authority_script = if ($registry -and $registry.canonical_router_authority) { [string]$registry.canonical_router_authority.script_relpath } else { '' }
        provider_layer_advice_only = if ($registry -and $registry.canonical_router_authority) { [bool]$registry.canonical_router_authority.provider_layer_advice_only } else { $false }
        providers = @($providersOut)
        failures = @($failures)
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failures.Count -gt 0) { exit 1 }
