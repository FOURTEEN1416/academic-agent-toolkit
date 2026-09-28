param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Get-LocalGovernanceExecutionHint {
    param(
        [Parameter(Mandatory)] [string]$ScriptPath
    )

    try {
        $localRoot = Resolve-VgoRepoRoot -StartPath $ScriptPath
    } catch {
        return $null
    }

    $hint = [ordered]@{
        local_root = [System.IO.Path]::GetFullPath($localRoot)
        has_outer_git_root = [bool](Test-Path -LiteralPath (Join-Path $localRoot '.git'))
        release_version = $null
        release_updated = $null
    }

    $governancePath = Join-Path $localRoot 'config\version-governance.json'
    if (Test-Path -LiteralPath $governancePath) {
        try {
            $governance = Get-Content -LiteralPath $governancePath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($null -ne $governance -and $governance.PSObject.Properties.Name -contains 'release' -and $null -ne $governance.release) {
                if ($governance.release.PSObject.Properties.Name -contains 'version') {
                    $hint.release_version = [string]$governance.release.version
                }
                if ($governance.release.PSObject.Properties.Name -contains 'updated') {
                    $hint.release_updated = [string]$governance.release.updated
                }
            }
        } catch {
        }
    }

    return [pscustomobject]$hint
}

function Write-ExecutionContextFailureAndExit {
    param(
        [Parameter(Mandatory)] [string]$ScriptPath,
        [Parameter(Mandatory)] [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    $hint = Get-LocalGovernanceExecutionHint -ScriptPath $ScriptPath
    $message = ''
    if ($null -ne $ErrorRecord -and $null -ne $ErrorRecord.Exception) {
        $message = $ErrorRecord.Exception.Message
    }

    Write-Host "[FAIL] linux proof gate execution-context lock" -ForegroundColor Red
    Write-Host ("[INFO] {0}" -f $message) -ForegroundColor Yellow

    if ($null -ne $hint) {
        Write-Host ("[INFO] detected local root: {0}" -f $hint.local_root) -ForegroundColor Yellow
        if (-not $hint.has_outer_git_root) {
            Write-Host "[INFO] detected root does not contain an outer .git directory." -ForegroundColor Yellow
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$hint.release_version)) {
            Write-Host ("[INFO] detected local release: {0} / {1}" -f $hint.release_version, $hint.release_updated) -ForegroundColor Yellow
        }
    }

    Write-Host "[INFO] Linux proof gates are canonical repo-root governance gates. Run them from the git checkout root, not from an installed runtime copy such as ~/.codex/skills/vibe." -ForegroundColor Yellow
    Write-Host "[INFO] If your installed runtime is older than the repo, refresh it first with install.sh or scripts/bootstrap/one-shot-setup.sh before treating proof failures as live Linux regressions." -ForegroundColor Yellow
    exit 1
}

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

function Add-WarningNote {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [System.Collections.Generic.List[string]]$Warnings,
        [Parameter(Mandatory)] [string]$Message
    )

    [void]$Warnings.Add([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-GateArtifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [AllowEmptyString()] [string]$OutputDirectory,
        [Parameter(Mandatory)] [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-linux-pwsh-proof-gate.json'
    $mdPath = Join-Path $dir 'vibe-linux-pwsh-proof-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Linux + pwsh Proof Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Linux Status: `{0}`' -f $Artifact.platform_linux.status),
        ('- Evidence State: `{0}`' -f $Artifact.proof_bundle.evidence_state),
        ('- Failure count: {0}' -f $Artifact.summary.failure_count),
        ('- Warning count: {0}' -f $Artifact.summary.warning_count),
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

function Test-FileContainsLiteral {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Needle
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    return [bool](Select-String -LiteralPath $Path -SimpleMatch -Pattern $Needle -Quiet)
}

function Get-ManifestFrozenRuns {
    param(
        [AllowNull()] [object]$Manifest
    )

    if ($null -eq $Manifest) {
        return @()
    }

    if ($Manifest.PSObject.Properties.Name -contains 'frozen_runs' -and $null -ne $Manifest.frozen_runs) {
        return @($Manifest.frozen_runs)
    }

    return @()
}

$context = $null
try {
    $context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
} catch {
    Write-ExecutionContextFailureAndExit -ScriptPath $PSCommandPath -ErrorRecord $_
}
$repoRoot = [string]$context.repoRoot

$assertions = [System.Collections.Generic.List[object]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

$linuxContractRel = 'adapters/codex/platform-linux.json'
$fixtureRel = 'tests/replay/fixtures/host-capability-matrix.json'
$manifestRel = 'references/proof-bundles/linux-full-authoritative-candidate/manifest.json'
$criteriaRel = 'docs/universalization/platform-promotion-criteria.md'
$baselineRel = 'docs/status/platform-promotion-baseline-2026-03-13.md'
$ledgerRel = 'docs/status/linux-pwsh-fresh-machine-evidence-ledger-2026-03-13.md'

$linuxContractPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $linuxContractRel
$fixturePath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $fixtureRel
$manifestPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $manifestRel
$criteriaPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $criteriaRel
$baselinePath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $baselineRel
$ledgerPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $ledgerRel

foreach ($path in @($linuxContractPath, $fixturePath, $manifestPath, $criteriaPath, $baselinePath, $ledgerPath)) {
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $path) -Message ("required file exists: {0}" -f (Get-VgoRelativePathPortable -BasePath $repoRoot -TargetPath $path)) -Details $null
}

$linux = if (Test-Path -LiteralPath $linuxContractPath) { Get-Content -LiteralPath $linuxContractPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$fixture = if (Test-Path -LiteralPath $fixturePath) { Get-Content -LiteralPath $fixturePath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$manifest = if (Test-Path -LiteralPath $manifestPath) { Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$frozenRuns = @(Get-ManifestFrozenRuns -Manifest $manifest)
$proofPendingState = 'pending-fresh-machine-proof'
$proofCompletePendingPromotionState = 'fresh-machine-proof-complete-pending-promotion-sync'
$promotedCompleteState = 'complete'

if ($null -ne $linux) {
    Add-Assertion -Assertions $assertions -Pass ([string]$linux.status -in @('supported-with-constraints', 'full-authoritative')) -Message 'platform-linux status is promotion-eligible or promoted' -Details $linux.status
    Add-Assertion -Assertions $assertions -Pass ([string]$linux.degrade_cases.without_pwsh -eq 'degraded-but-supported') -Message 'platform-linux keeps without_pwsh degraded-but-supported' -Details $linux.degrade_cases.without_pwsh
    Add-Assertion -Assertions $assertions -Pass ([string]$linux.promotion_target -eq 'full-authoritative') -Message 'platform-linux promotion_target is full-authoritative' -Details $linux.promotion_target
    Add-Assertion -Assertions $assertions -Pass ([string]$linux.proof_bundle.manifest -eq $manifestRel) -Message 'platform-linux references the Linux proof-bundle manifest' -Details $linux.proof_bundle.manifest
    Add-Assertion -Assertions $assertions -Pass ([string]$linux.proof_bundle.current_evidence_state -eq [string]$manifest.evidence_state) -Message 'platform-linux current_evidence_state matches proof-bundle manifest' -Details $linux.proof_bundle.current_evidence_state
}

if ($null -ne $manifest) {
    Add-Assertion -Assertions $assertions -Pass ([int]$manifest.schema_version -eq 1) -Message 'Linux proof-bundle manifest schema_version == 1' -Details $manifest.schema_version
    Add-Assertion -Assertions $assertions -Pass ([string]$manifest.lane_id -eq 'codex/linux') -Message 'Linux proof-bundle manifest lane_id is codex/linux' -Details $manifest.lane_id
    Add-Assertion -Assertions $assertions -Pass ([string]$manifest.target_status -eq 'full-authoritative') -Message 'Linux proof-bundle target_status is full-authoritative' -Details $manifest.target_status
    Add-Assertion -Assertions $assertions -Pass ([string]$manifest.current_status -eq [string]$linux.status) -Message 'Linux proof-bundle current_status matches platform-linux contract' -Details $manifest.current_status
}

$linuxLane = $null
if ($null -ne $fixture) {
    $linuxLane = @($fixture.platform_lanes | Where-Object { $_.lane_id -eq 'codex/linux' }) | Select-Object -First 1
    Add-Assertion -Assertions $assertions -Pass ($null -ne $linuxLane) -Message 'host-capability fixture contains codex/linux lane' -Details $null
    if ($null -ne $linuxLane) {
        Add-Assertion -Assertions $assertions -Pass ([string]$linuxLane.expected_platform_status -eq [string]$linux.status) -Message 'fixture Linux expected status matches platform-linux contract' -Details $linuxLane.expected_platform_status
        Add-Assertion -Assertions $assertions -Pass ([string]$linuxLane.promotion_bundle.manifest -eq $manifestRel) -Message 'fixture Linux lane references the Linux proof-bundle manifest' -Details $linuxLane.promotion_bundle.manifest
        Add-Assertion -Assertions $assertions -Pass ([string]$linuxLane.promotion_bundle.current_evidence_state -eq [string]$manifest.evidence_state) -Message 'fixture Linux current_evidence_state matches proof-bundle manifest' -Details $linuxLane.promotion_bundle.current_evidence_state
        Add-Assertion -Assertions $assertions -Pass ([string]$linuxLane.closure_truth.degrade_cases.without_pwsh -eq 'degraded-but-supported') -Message 'fixture Linux lane keeps without_pwsh degraded-but-supported' -Details $linuxLane.closure_truth.degrade_cases.without_pwsh
    }
}

$fullAuthoritativeLanes = @()
if ($null -ne $fixture) {
    $fullAuthoritativeLanes = @($fixture.hard_no_overclaim_rules.only_allowed_full_authoritative_lanes)
}

$linuxPromoted = ($null -ne $linux -and [string]$linux.status -eq 'full-authoritative')

if ($linuxPromoted) {
    Add-Assertion -Assertions $assertions -Pass ($fullAuthoritativeLanes -contains 'codex/linux') -Message 'Linux promotion is reflected in the replay no-overclaim allowlist' -Details ($fullAuthoritativeLanes -join ',')

    $reportFailures = @()
    foreach ($reportRel in @($manifest.required_fresh_machine_reports)) {
        $reportPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath ([string]$reportRel)
        if (-not (Test-Path -LiteralPath $reportPath)) {
            $reportFailures += [string]$reportRel
        }
    }
    Add-Assertion -Assertions $assertions -Pass ($reportFailures.Count -eq 0) -Message 'promoted Linux lane has all required fresh-machine reports' -Details ($reportFailures -join ',')
    Add-Assertion -Assertions $assertions -Pass ([string]$manifest.evidence_state -eq $promotedCompleteState) -Message 'promoted Linux lane has complete proof-bundle evidence state' -Details $manifest.evidence_state
} else {
    Add-Assertion -Assertions $assertions -Pass (-not ($fullAuthoritativeLanes -contains 'codex/linux')) -Message 'unpromoted Linux lane is not listed as full-authoritative in replay rules' -Details ($fullAuthoritativeLanes -join ',')
    Add-Assertion -Assertions $assertions -Pass ([string]$manifest.evidence_state -in @($proofPendingState, $proofCompletePendingPromotionState)) -Message 'unpromoted Linux lane uses an allowed pre-promotion evidence state' -Details $manifest.evidence_state
    if ([string]$manifest.evidence_state -eq $proofPendingState) {
        Add-WarningNote -Warnings $warnings -Message 'Linux remains a promotion candidate only; fresh-machine proof is still pending.'
    }
}

$proofFrozenOrPromoted = [string]$manifest.evidence_state -in @($proofCompletePendingPromotionState, $promotedCompleteState)
if ($proofFrozenOrPromoted) {
    Add-Assertion -Assertions $assertions -Pass ($frozenRuns.Count -ge 2) -Message 'proof-complete Linux bundle records at least two frozen fresh-machine runs' -Details $frozenRuns.Count

    foreach ($run in $frozenRuns) {
        $runId = [string]$run.id
        $bundleDirRel = [string]$run.bundle_dir
        $bundleDirPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $bundleDirRel
        Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $bundleDirPath) -Message ("[{0}] bundle_dir exists" -f $runId) -Details $bundleDirRel

        $operationRecordRel = [string]$run.operation_record
        if (-not [string]::IsNullOrWhiteSpace($operationRecordRel)) {
            $operationRecordPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $operationRecordRel
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $operationRecordPath) -Message ("[{0}] operation record is frozen" -f $runId) -Details $operationRecordRel
        }

        foreach ($requiredFile in @($run.required_files)) {
            $rel = [string]$requiredFile
            $full = Join-Path $bundleDirPath $rel
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $full) -Message ("[{0}] required proof artifact exists: {1}" -f $runId, $rel) -Details $rel
        }

        $checkLogPath = Join-Path $bundleDirPath 'check.log'
        $expectedCheckSummary = if ($run.PSObject.Properties.Name -contains 'expected_check_summary') { [string]$run.expected_check_summary } else { '' }
        if (-not [string]::IsNullOrWhiteSpace($expectedCheckSummary)) {
            Add-Assertion -Assertions $assertions -Pass (Test-FileContainsLiteral -Path $checkLogPath -Needle $expectedCheckSummary) -Message ("[{0}] check.log contains expected pass summary" -f $runId) -Details $expectedCheckSummary
        }

        $doctorLogPath = Join-Path $bundleDirPath 'bootstrap-doctor.log'
        $expectedReadinessState = if ($run.PSObject.Properties.Name -contains 'expected_readiness_state') { [string]$run.expected_readiness_state } else { '' }
        if (-not [string]::IsNullOrWhiteSpace($expectedReadinessState)) {
            Add-Assertion -Assertions $assertions -Pass (Test-FileContainsLiteral -Path $doctorLogPath -Needle $expectedReadinessState) -Message ("[{0}] bootstrap-doctor.log contains expected readiness_state" -f $runId) -Details $expectedReadinessState
        }
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-linux-pwsh-proof-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    platform_linux = [pscustomobject]@{
        status = if ($null -ne $linux) { [string]$linux.status } else { $null }
        promotion_target = if ($null -ne $linux) { [string]$linux.promotion_target } else { $null }
    }
    proof_bundle = [pscustomobject]@{
        manifest = $manifestRel
        evidence_state = if ($null -ne $manifest) { [string]$manifest.evidence_state } else { $null }
    }
    assertions = @($assertions)
    warnings = @($warnings)
    summary = [pscustomobject]@{
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
