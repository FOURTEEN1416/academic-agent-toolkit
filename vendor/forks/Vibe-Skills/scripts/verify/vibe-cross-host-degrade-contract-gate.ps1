param(
    [string]$FixturePath = '',
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [System.Collections.Generic.List[object]]$Assertions,
        [Parameter(Mandatory)] [bool]$Pass,
        [Parameter(Mandatory)] [string]$Message,
        [AllowNull()] [object]$Details = $null
    )

    [void]$Assertions.Add([pscustomobject]@{
        pass = [bool]$Pass
        message = [string]$Message
        details = $Details
    })

    if ($Pass) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
    }
}

function Read-JsonFile {
    param([Parameter(Mandatory)] [string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-GateArtifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [AllowEmptyString()] [string]$OutputDirectory,
        [Parameter(Mandatory)] [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-cross-host-degrade-contract-gate.json'
    $mdPath = Join-Path $dir 'vibe-cross-host-degrade-contract-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Cross-Host Degrade Contract Gate (Contract-Only)',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Fixture: `{0}`' -f $Artifact.fixture_path),
        ('- Providers checked: {0}' -f $Artifact.summary.providers_checked),
        ('- Failure count: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Notes',
        '',
        '- Offline contract gate: compares `tests/replay/fixtures/provider-state-matrix.json` against `config/router-provider-*.json`.',
        '- Does NOT execute any provider modules and does NOT make any network calls.',
        '',
        '## Assertions',
        ''
    )

    foreach ($a in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($a.pass) { 'PASS' } else { 'FAIL' }), $a.message)
    }

    if (@($Artifact.results.providers).Count -gt 0) {
        $lines += ''
        $lines += '## Providers'
        $lines += ''
        foreach ($p in @($Artifact.results.providers)) {
            $lines += ('- `{0}` ok={1} module=`{2}` expected_offline=`{3}` registry_offline=`{4}`' -f $p.id, $p.ok, $p.module_relpath, $p.expected_offline_state, $p.registry_offline_state)
        }
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

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = [string]$context.repoRoot

$fixtureRel = if ([string]::IsNullOrWhiteSpace($FixturePath)) { 'tests/replay/fixtures/provider-state-matrix.json' } else { $FixturePath }
$fixturePath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $fixtureRel

$registryRel = 'config/router-provider-registry.json'
$defaultsRel = 'config/router-provider-defaults.json'
$registryPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $registryRel
$defaultsPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $defaultsRel

$assertions = [System.Collections.Generic.List[object]]::new()
$failureList = [System.Collections.Generic.List[string]]::new()
$providerChecks = [System.Collections.Generic.List[object]]::new()

foreach ($rel in @(
    $fixtureRel,
    $registryRel,
    $defaultsRel,
    'docs/universalization/router-model-neutrality.md'
)) {
    $full = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $rel
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $full) -Message ("required file exists: {0}" -f $rel) -Details $rel
    if (-not (Test-Path -LiteralPath $full)) {
        [void]$failureList.Add(("missing_required_file:{0}" -f $rel))
    }
}

$fixture = $null
$registry = $null
$defaults = $null

if ($failureList.Count -eq 0) {
    try { $fixture = Read-JsonFile -Path $fixturePath } catch { [void]$failureList.Add(("invalid_json:{0}:{1}" -f $fixtureRel, $_.Exception.Message)) }
    try { $registry = Read-JsonFile -Path $registryPath } catch { [void]$failureList.Add(("invalid_json:{0}:{1}" -f $registryRel, $_.Exception.Message)) }
    try { $defaults = Read-JsonFile -Path $defaultsPath } catch { [void]$failureList.Add(("invalid_json:{0}:{1}" -f $defaultsRel, $_.Exception.Message)) }
}

if ($fixture) {
    Add-Assertion -Assertions $assertions -Pass ([string]$fixture.policy -eq 'replay-provider-state-matrix') -Message 'fixture policy is replay-provider-state-matrix' -Details ([string]$fixture.policy)
    Add-Assertion -Assertions $assertions -Pass ([int]$fixture.version -ge 1) -Message 'fixture version >= 1' -Details ([int]$fixture.version)
}

if ($fixture -and $registry -and $defaults) {
    Add-Assertion -Assertions $assertions -Pass ([string]$defaults.default_runtime_state -eq [string]$fixture.defaults_contract.default_runtime_state) -Message 'defaults.default_runtime_state matches fixture' -Details $defaults.default_runtime_state
    Add-Assertion -Assertions $assertions -Pass ([string]$defaults.fallback_provider_mode -eq [string]$fixture.defaults_contract.fallback_provider_mode) -Message 'defaults.fallback_provider_mode matches fixture' -Details $defaults.fallback_provider_mode
    Add-Assertion -Assertions $assertions -Pass ([bool]$defaults.offline_frozen_mode.enabled -eq [bool]$fixture.defaults_contract.offline_frozen_enabled) -Message 'defaults.offline_frozen_mode.enabled matches fixture' -Details $defaults.offline_frozen_mode.enabled
    Add-Assertion -Assertions $assertions -Pass ([string]$defaults.offline_frozen_mode.state -eq [string]$fixture.defaults_contract.offline_frozen_state) -Message 'defaults.offline_frozen_mode.state matches fixture' -Details $defaults.offline_frozen_mode.state

    Add-Assertion -Assertions $assertions -Pass ([string]$defaults.default_runtime_state -ne 'provider-assisted') -Message 'no-silent-degrade: default_runtime_state must not be provider-assisted' -Details $defaults.default_runtime_state
    Add-Assertion -Assertions $assertions -Pass ([string]$defaults.fallback_provider_mode -ne 'provider-assisted') -Message 'no-silent-degrade: fallback_provider_mode must not be provider-assisted' -Details $defaults.fallback_provider_mode

    $registryMap = @{}
    foreach ($rp in @($registry.providers)) {
        if ($rp -and $rp.id) { $registryMap[[string]$rp.id] = $rp }
    }

    foreach ($p in @($fixture.providers)) {
        if (-not $p) { continue }
        $id = [string]$p.id
        $ok = $true

        if (-not $registryMap.ContainsKey($id)) {
            $ok = $false
            Add-Assertion -Assertions $assertions -Pass $false -Message ("provider exists in registry: {0}" -f $id) -Details $id
            [void]$failureList.Add(("provider_missing_in_registry:{0}" -f $id))
            continue
        }

        $reg = $registryMap[$id]

        $expectedModule = [string]$p.module_relpath
        $registryModule = [string]$reg.module_relpath
        Add-Assertion -Assertions $assertions -Pass ($registryModule -eq $expectedModule) -Message ("provider module_relpath matches: {0}" -f $id) -Details @{ expected = $expectedModule; actual = $registryModule }
        if ($registryModule -ne $expectedModule) { $ok = $false; [void]$failureList.Add(("module_mismatch:{0}" -f $id)) }

        $expectedKind = [string]$p.kind
        Add-Assertion -Assertions $assertions -Pass ([string]$reg.kind -eq $expectedKind) -Message ("provider kind matches: {0}" -f $id) -Details @{ expected = $expectedKind; actual = [string]$reg.kind }
        if ([string]$reg.kind -ne $expectedKind) { $ok = $false; [void]$failureList.Add(("kind_mismatch:{0}" -f $id)) }

        $expectedOffline = [string]$p.offline_state_expected
        $registryOffline = [string]$reg.offline_state
        Add-Assertion -Assertions $assertions -Pass ($registryOffline -eq $expectedOffline) -Message ("provider offline_state matches: {0}" -f $id) -Details @{ expected = $expectedOffline; actual = $registryOffline }
        if ($registryOffline -ne $expectedOffline) { $ok = $false; [void]$failureList.Add(("offline_state_mismatch:{0}" -f $id)) }

        $expectedReason = [string]$p.offline_abstain_reason_expected
        $registryReason = if ($reg.offline_contract) { [string]$reg.offline_contract.abstain_reason } else { $null }
        Add-Assertion -Assertions $assertions -Pass ($registryReason -eq $expectedReason) -Message ("provider offline abstain_reason matches: {0}" -f $id) -Details @{ expected = $expectedReason; actual = $registryReason }
        if ($registryReason -ne $expectedReason) { $ok = $false; [void]$failureList.Add(("offline_reason_mismatch:{0}" -f $id)) }

        $expectedNoNetwork = [bool]$p.no_network_without_credentials
        $registryNoNetwork = $true
        if ($reg.offline_contract -and ($reg.offline_contract.PSObject.Properties.Name -contains 'no_network_without_credentials')) {
            $registryNoNetwork = [bool]$reg.offline_contract.no_network_without_credentials
        }
        Add-Assertion -Assertions $assertions -Pass ($registryNoNetwork -eq $expectedNoNetwork) -Message ("provider no_network_without_credentials matches: {0}" -f $id) -Details @{ expected = $expectedNoNetwork; actual = $registryNoNetwork }
        if ($registryNoNetwork -ne $expectedNoNetwork) { $ok = $false; [void]$failureList.Add(("no_network_mismatch:{0}" -f $id)) }

        $expectedEnv = @($p.required_env_any | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        $registryEnv = @()
        if ($reg.offline_contract -and ($reg.offline_contract.PSObject.Properties.Name -contains 'required_env_any')) {
            $registryEnv = @($reg.offline_contract.required_env_any | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        }

        $expectedEnvSorted = @($expectedEnv | Sort-Object)
        $registryEnvSorted = @($registryEnv | Sort-Object)
        $envOk = ($expectedEnvSorted -join ';') -eq ($registryEnvSorted -join ';')
        Add-Assertion -Assertions $assertions -Pass $envOk -Message ("provider required_env_any matches: {0}" -f $id) -Details @{ expected = $expectedEnvSorted; actual = $registryEnvSorted }
        if (-not $envOk) { $ok = $false; [void]$failureList.Add(("env_mismatch:{0}" -f $id)) }

        [void]$providerChecks.Add([pscustomobject]@{
            id = $id
            ok = [bool]$ok
            module_relpath = $expectedModule
            expected_offline_state = $expectedOffline
            registry_offline_state = $registryOffline
        })
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count + $failureList.Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-cross-host-degrade-contract-gate'
    mode = 'contract-only'
    repo_root = $repoRoot
    fixture_path = $fixtureRel
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    assertions = @($assertions.ToArray())
    results = [pscustomobject]@{
        providers = @($providerChecks.ToArray())
        failures = @($failureList.ToArray())
    }
    summary = [pscustomobject]@{
        providers_checked = $providerChecks.Count
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($gateResult -ne 'PASS') {
    exit 1
}
