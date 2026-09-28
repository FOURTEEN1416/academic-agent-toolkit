param(
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

function Write-GateArtifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [AllowEmptyString()] [string]$OutputDirectory,
        [Parameter(Mandatory)] [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-universalization-no-regression-gate.json'
    $mdPath = Join-Path $dir 'vibe-universalization-no-regression-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Universalization No-Regression Gate (Batch C)',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Failure count: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Subgates',
        ''
    )

    foreach ($g in @($Artifact.subgates)) {
        $lines += ('- `{0}` :: {1} (exit={2})' -f $g.gate, $g.result, $g.exit_code)
    }

    $lines += ''
    $lines += '## Assertions'
    $lines += ''
    foreach ($a in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($a.pass) { 'PASS' } else { 'FAIL' }), $a.message)
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Invoke-SubGate {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [string]$GateScriptRel,
        [Parameter(Mandatory)] [bool]$SupportsArtifacts,
        [switch]$WriteArtifacts,
        [string]$OutputDirectory
    )

    $gateFull = ConvertTo-VgoFullPath -BasePath $RepoRoot -RelativePath $GateScriptRel
    if (-not (Test-Path -LiteralPath $gateFull)) {
        return [pscustomobject]@{
            gate = $GateScriptRel
            result = 'MISSING'
            exit_code = 1
            path = $gateFull
        }
    }

    $args = @()

    if ($WriteArtifacts -and $SupportsArtifacts) {
        $args += '-WriteArtifacts'
        if (-not [string]::IsNullOrWhiteSpace($OutputDirectory)) {
            $args += @('-OutputDirectory', $OutputDirectory)
        }
    }

    $result = Invoke-VgoPowerShellFile -ScriptPath $gateFull -ArgumentList $args -NoProfile
    $code = [int]$result.exit_code

    return [pscustomobject]@{
        gate = $GateScriptRel
        result = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
        exit_code = $code
        path = $gateFull
        host_path = $result.host_path
    }
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = [string]$context.repoRoot

$assertions = [System.Collections.Generic.List[object]]::new()
$subgates = [System.Collections.Generic.List[object]]::new()

$proofDocRel = 'docs/universalization/no-regression-proof-standard.md'
$proofDocPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $proofDocRel
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $proofDocPath) -Message 'no-regression proof standard doc exists' -Details $proofDocRel

$gateSpecs = @(
    @{ Gate = 'scripts/verify/vibe-platform-support-contract-gate.ps1'; SupportsArtifacts = $false },
    @{ Gate = 'scripts/verify/vibe-host-adapter-contract-gate.ps1'; SupportsArtifacts = $false },
    @{ Gate = 'scripts/verify/vibe-router-provider-neutrality-gate.ps1'; SupportsArtifacts = $true },
    @{ Gate = 'scripts/verify/vibe-router-offline-degrade-contract-gate.ps1'; SupportsArtifacts = $true },
    @{ Gate = 'scripts/verify/vibe-cross-host-route-parity-gate.ps1'; SupportsArtifacts = $true },
    @{ Gate = 'scripts/verify/vibe-cross-host-degrade-contract-gate.ps1'; SupportsArtifacts = $true },
    @{ Gate = 'scripts/verify/vibe-cross-host-install-isolation-gate.ps1'; SupportsArtifacts = $true },
    @{ Gate = 'scripts/verify/vibe-governed-runtime-contract-gate.ps1'; SupportsArtifacts = $true }
)

foreach ($spec in $gateSpecs) {
    $rel = [string]$spec.Gate
    $supports = [bool]$spec.SupportsArtifacts
    $subgate = Invoke-SubGate -RepoRoot $repoRoot -GateScriptRel $rel -SupportsArtifacts:$supports -WriteArtifacts:$WriteArtifacts -OutputDirectory $OutputDirectory
    [void]$subgates.Add($subgate)
}

$failureCount = @($subgates | Where-Object { [int]$_.exit_code -ne 0 }).Count + @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-universalization-no-regression-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    subgates = @($subgates)
    assertions = @($assertions)
    summary = [pscustomobject]@{
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($gateResult -ne 'PASS') {
    exit 1
}
