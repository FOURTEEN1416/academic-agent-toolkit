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

function Add-Warning {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [System.Collections.Generic.List[string]]$Warnings,
        [Parameter(Mandatory)] [string]$Message
    )

    [void]$Warnings.Add([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
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

    $jsonPath = Join-Path $dir 'vibe-cross-host-route-parity-gate.json'
    $mdPath = Join-Path $dir 'vibe-cross-host-route-parity-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Cross-Host Route Parity Gate (Contract-Only)',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Fixture: `{0}`' -f $Artifact.fixture_path),
        ('- Hosts: {0}' -f $Artifact.summary.host_count),
        ('- Platform lanes: {0}' -f $Artifact.summary.platform_lane_count),
        ('- Failure count: {0}' -f $Artifact.summary.failure_count),
        ('- Warning count: {0}' -f $Artifact.summary.warning_count),
        '',
        '## Notes',
        '',
        '- Offline contract gate: validates adapter/platform truth + no-overclaim rules.',
        '- Does NOT execute the router or claim replay-backed cross-host parity.',
        '',
        '## Assertions',
        ''
    )

    foreach ($a in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($a.pass) { 'PASS' } else { 'FAIL' }), $a.message)
    }

    if (@($Artifact.warnings).Count -gt 0) {
        $lines += ''
        $lines += '## Warnings'
        $lines += ''
        foreach ($w in @($Artifact.warnings)) {
            $lines += ('- {0}' -f $w)
        }
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = [string]$context.repoRoot

$fixtureRel = if ([string]::IsNullOrWhiteSpace($FixturePath)) { 'tests/replay/fixtures/host-capability-matrix.json' } else { $FixturePath }
$fixtureFull = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $fixtureRel

$assertions = [System.Collections.Generic.List[object]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

foreach ($rel in @(
    'docs/universalization/no-regression-proof-standard.md',
    'docs/universalization/platform-support-matrix.md',
    'docs/universalization/platform-parity-contract.md',
    'docs/universalization/router-model-neutrality.md',
    'docs/universalization/host-capability-matrix.md',
    $fixtureRel
)) {
    $full = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $rel
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $full) -Message ("required file exists: {0}" -f $rel) -Details $rel
}

$fixture = $null
if (Test-Path -LiteralPath $fixtureFull) {
    try {
        $fixture = Read-JsonFile -Path $fixtureFull
        Add-Assertion -Assertions $assertions -Pass $true -Message 'fixture parses as JSON' -Details $fixtureRel
    } catch {
        Add-Assertion -Assertions $assertions -Pass $false -Message 'fixture JSON parse failed' -Details $_.Exception.Message
    }
} else {
    Add-Assertion -Assertions $assertions -Pass $false -Message 'fixture exists' -Details $fixtureRel
}

if ($null -ne $fixture) {
    Add-Assertion -Assertions $assertions -Pass ([string]$fixture.policy -eq 'replay-host-capability-matrix') -Message 'fixture policy is replay-host-capability-matrix' -Details ([string]$fixture.policy)
    Add-Assertion -Assertions $assertions -Pass ([int]$fixture.version -ge 1) -Message 'fixture version >= 1' -Details ([int]$fixture.version)

    $allowedFull = @()
    if ($fixture.hard_no_overclaim_rules -and $fixture.hard_no_overclaim_rules.only_allowed_full_authoritative_lanes) {
        $allowedFull = @($fixture.hard_no_overclaim_rules.only_allowed_full_authoritative_lanes | ForEach-Object { [string]$_ })
    }
    if ($allowedFull.Count -eq 0) { $allowedFull = @('codex/windows') }

    Add-Assertion -Assertions $assertions -Pass ($allowedFull -contains 'codex/windows') -Message 'no-overclaim allows codex/windows as full-authoritative lane' -Details ($allowedFull -join ',')

    foreach ($hostEntry in @($fixture.hosts)) {
        if (-not $hostEntry) { continue }

        $adapterId = [string]$hostEntry.adapter_id
        $profileRel = [string]$hostEntry.host_profile

        Add-Assertion -Assertions $assertions -Pass (-not [string]::IsNullOrWhiteSpace($adapterId)) -Message 'host.adapter_id is present' -Details $profileRel
        Add-Assertion -Assertions $assertions -Pass (-not [string]::IsNullOrWhiteSpace($profileRel)) -Message ("host_profile declared for {0}" -f $adapterId) -Details $profileRel

        if (-not [string]::IsNullOrWhiteSpace($profileRel)) {
            $profilePath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $profileRel
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $profilePath) -Message ("adapter host-profile exists: {0}" -f $profileRel) -Details $profileRel

            if (Test-Path -LiteralPath $profilePath) {
                try {
                    $profile = Read-JsonFile -Path $profilePath
                    Add-Assertion -Assertions $assertions -Pass ([string]$profile.adapter_id -eq $adapterId) -Message ("{0} adapter_id matches host-profile" -f $adapterId) -Details ([string]$profile.adapter_id)

                    $expectedStatus = [string]$hostEntry.expected_status
                    if (-not [string]::IsNullOrWhiteSpace($expectedStatus)) {
                        Add-Assertion -Assertions $assertions -Pass ([string]$profile.status -eq $expectedStatus) -Message ("{0} status matches expected" -f $adapterId) -Details ([string]$profile.status)
                    }

                    $expectedRole = [string]$hostEntry.expected_runtime_role
                    if (-not [string]::IsNullOrWhiteSpace($expectedRole)) {
                        Add-Assertion -Assertions $assertions -Pass ([string]$profile.runtime_role -eq $expectedRole) -Message ("{0} runtime_role matches expected" -f $adapterId) -Details ([string]$profile.runtime_role)
                    }
                } catch {
                    Add-Assertion -Assertions $assertions -Pass $false -Message ("failed to parse host-profile: {0}" -f $profileRel) -Details $_.Exception.Message
                }
            }
        }

        foreach ($contractRel in @($hostEntry.platform_contracts)) {
            $c = [string]$contractRel
            if ([string]::IsNullOrWhiteSpace($c)) { continue }
            $cp = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $c
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $cp) -Message ("platform contract exists: {0}" -f $c) -Details $c
        }
    }

    foreach ($lane in @($fixture.platform_lanes)) {
        if (-not $lane) { continue }
        $laneId = [string]$lane.lane_id
        $expectedStatus = [string]$lane.expected_platform_status
        $contractRel = [string]$lane.platform_contract

        if ($expectedStatus -eq 'full-authoritative' -and ($allowedFull -notcontains $laneId)) {
            Add-Assertion -Assertions $assertions -Pass $false -Message ("no-overclaim violation: {0} marked full-authoritative" -f $laneId) -Details $expectedStatus
        } else {
            Add-Assertion -Assertions $assertions -Pass $true -Message ("no-overclaim ok: {0}" -f $laneId) -Details $expectedStatus
        }

        if ([string]::IsNullOrWhiteSpace($contractRel)) {
            Add-Assertion -Assertions $assertions -Pass $false -Message ("lane missing platform_contract: {0}" -f $laneId) -Details ($lane | ConvertTo-Json -Depth 6)
            continue
        }

        $contractPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $contractRel
        Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $contractPath) -Message ("lane platform contract exists: {0}" -f $contractRel) -Details $laneId

        if (Test-Path -LiteralPath $contractPath) {
            try {
                $contract = Read-JsonFile -Path $contractPath
                if (-not [string]::IsNullOrWhiteSpace($expectedStatus)) {
                    Add-Assertion -Assertions $assertions -Pass ([string]$contract.status -eq $expectedStatus) -Message ("lane contract status matches expected: {0}" -f $laneId) -Details ([string]$contract.status)
                }

                if ($laneId -eq 'codex/linux') {
                    $degrade = $null
                    if ($contract.degrade_cases -and ($contract.degrade_cases.PSObject.Properties.Name -contains 'without_pwsh')) {
                        $degrade = [string]$contract.degrade_cases.without_pwsh
                    }
                    Add-Assertion -Assertions $assertions -Pass ($degrade -eq 'degraded-but-supported') -Message 'codex/linux declares without_pwsh degraded-but-supported' -Details $degrade
                }
            } catch {
                Add-Assertion -Assertions $assertions -Pass $false -Message ("failed to parse platform contract: {0}" -f $contractRel) -Details $_.Exception.Message
            }
        }
    }

    $platformDoc = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath 'docs/universalization/platform-support-matrix.md'
    if (Test-Path -LiteralPath $platformDoc) {
        foreach ($needle in @(
            'Windows is the clearest official runtime path',
            'Linux without `pwsh` is an honest degraded path'
        )) {
            $present = [bool](Select-String -LiteralPath $platformDoc -SimpleMatch -Pattern $needle -Quiet)
            Add-Assertion -Assertions $assertions -Pass $present -Message ("platform support doc states truth: {0}" -f $needle) -Details $needle
        }
    } else {
        Add-Warning -Warnings $warnings -Message 'platform-support-matrix.md not found; skipping truth wording checks.'
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-cross-host-route-parity-gate'
    mode = 'contract-only'
    repo_root = $repoRoot
    fixture_path = $fixtureRel
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    assertions = @($assertions.ToArray())
    warnings = @($warnings.ToArray())
    summary = [pscustomobject]@{
        host_count = @($fixture.hosts).Count
        platform_lane_count = @($fixture.platform_lanes).Count
        failure_count = $failureCount
        warning_count = $warnings.Count
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($gateResult -ne 'PASS') {
    exit 1
}
