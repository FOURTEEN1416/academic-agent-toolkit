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

    $jsonPath = Join-Path $dir 'vibe-proof-bundle-tracked-files-gate.json'
    $mdPath = Join-Path $dir 'vibe-proof-bundle-tracked-files-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Proof Bundle Tracked Files Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Failure count: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )

    foreach ($assertion in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Normalize-RepoRelativePath {
    param(
        [Parameter(Mandatory)] [string]$Path
    )

    return $Path.Replace('\', '/')
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = [string]$context.repoRoot
$assertions = [System.Collections.Generic.List[object]]::new()

$manifestRel = 'references/proof-bundles/linux-full-authoritative-candidate/manifest.json'
$manifestPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $manifestRel

Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $manifestPath) -Message "proof-bundle manifest exists: $manifestRel" -Details $null

$manifest = $null
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

$trackedProofPaths = @()
$trackedProofSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$lsFilesOutput = @(& git -C $repoRoot ls-files)
if ($LASTEXITCODE -ne 0) {
    throw 'git ls-files failed while computing proof-bundle tracked paths.'
}

foreach ($item in $lsFilesOutput) {
    $normalized = Normalize-RepoRelativePath -Path ([string]$item)
    if (-not [string]::IsNullOrWhiteSpace($normalized)) {
        $trackedProofPaths += $normalized
        [void]$trackedProofSet.Add($normalized)
    }
}

Add-Assertion -Assertions $assertions -Pass ($trackedProofSet.Contains($manifestRel)) -Message 'proof-bundle manifest itself is tracked by git' -Details $manifestRel

if ($null -ne $manifest) {
    foreach ($reportRel in @($manifest.required_fresh_machine_reports)) {
        $normalizedReport = Normalize-RepoRelativePath -Path ([string]$reportRel)
        $reportPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $normalizedReport
        Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $reportPath) -Message ("manifest-declared report exists: {0}" -f $normalizedReport) -Details $normalizedReport
        Add-Assertion -Assertions $assertions -Pass ($trackedProofSet.Contains($normalizedReport)) -Message ("manifest-declared report is tracked: {0}" -f $normalizedReport) -Details $normalizedReport
    }

    foreach ($run in @($manifest.frozen_runs)) {
        $runId = [string]$run.id
        $bundleDirRel = Normalize-RepoRelativePath -Path ([string]$run.bundle_dir)
        $operationRecordRel = Normalize-RepoRelativePath -Path ([string]$run.operation_record)

        if (-not [string]::IsNullOrWhiteSpace($operationRecordRel)) {
            $operationRecordPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $operationRecordRel
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $operationRecordPath) -Message ("[{0}] operation record exists" -f $runId) -Details $operationRecordRel
            Add-Assertion -Assertions $assertions -Pass ($trackedProofSet.Contains($operationRecordRel)) -Message ("[{0}] operation record is tracked" -f $runId) -Details $operationRecordRel
        }

        foreach ($requiredFile in @($run.required_files)) {
            $artifactRel = Normalize-RepoRelativePath -Path (Join-Path $bundleDirRel ([string]$requiredFile))
            $artifactPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $artifactRel
            Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $artifactPath) -Message ("[{0}] manifest-declared proof artifact exists: {1}" -f $runId, $requiredFile) -Details $artifactRel
            Add-Assertion -Assertions $assertions -Pass ($trackedProofSet.Contains($artifactRel)) -Message ("[{0}] manifest-declared proof artifact is tracked: {1}" -f $runId, $requiredFile) -Details $artifactRel
        }
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-proof-bundle-tracked-files-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    manifest = $manifestRel
    tracked_path_count = $trackedProofPaths.Count
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
