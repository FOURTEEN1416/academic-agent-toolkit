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

    $jsonPath = Join-Path $dir 'vibe-wave40-63-board-gate.json'
    $mdPath = Join-Path $dir 'vibe-wave40-63-board-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Wave40-63 Board Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Board Path: `{0}`' -f $Artifact.board_path),
        ('- Waves Checked: {0}' -f $Artifact.summary.wave_count),
        ('- Failures: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Waves',
        ''
    )

    foreach ($wave in $Artifact.waves) {
        $lines += ('- Wave {0}: `{1}` / status=`{2}` / gate=`{3}` / assets_ok={4}' -f $wave.wave, $wave.title, $wave.status, $wave.verify_gate, $wave.assets_ok)
    }

    $lines += ''
    $lines += '## Assertions'
    $lines += ''
    foreach ($assertion in $Artifact.assertions) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$boardPath = Join-Path $context.repoRoot 'config\wave40-63-execution-board.json'
$planPath = Join-Path $context.repoRoot 'docs\plans\2026-03-07-vco-wave40-63-execution-plan.md'
$assertions = [System.Collections.Generic.List[object]]::new()

Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $boardPath) -Message 'wave40-63 execution board exists' -Details $boardPath
Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $planPath) -Message 'wave40-63 formal execution plan exists' -Details $planPath
if (-not (Test-Path -LiteralPath $boardPath)) {
    if ($WriteArtifacts) {
        Write-GateArtifacts -RepoRoot $context.repoRoot -OutputDirectory $OutputDirectory -Artifact ([pscustomobject]@{
            gate = 'vibe-wave40-63-board-gate'
            repo_root = $context.repoRoot
            board_path = $boardPath
            plan_path = $planPath
            gate_result = 'FAIL'
            generated_at = (Get-Date).ToString('s')
            waves = @()
            assertions = @($assertions)
            summary = [ordered]@{ wave_count = 0; failure_count = 1 }
        })
    }
    exit 1
}

$board = Get-Content -LiteralPath $boardPath -Raw -Encoding UTF8 | ConvertFrom-Json
$waves = @($board.waves)
$waveNumbers = @($waves | ForEach-Object { [int]$_.wave })
$expectedWaves = 40..63
$missingWaves = @($expectedWaves | Where-Object { $waveNumbers -notcontains $_ })
$duplicateWaves = @($waveNumbers | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { [int]$_.Name })
$unknownStatuses = @($waves | Where-Object { $board.allowed_statuses -notcontains [string]$_.status } | ForEach-Object { [int]$_.wave })

Add-Assertion -Assertions $assertions -Pass ($waves.Count -eq 24) -Message 'board contains 24 waves (40-63)' -Details $waves.Count
Add-Assertion -Assertions $assertions -Pass ($missingWaves.Count -eq 0) -Message 'board has continuous waves 40-63' -Details $missingWaves
Add-Assertion -Assertions $assertions -Pass ($duplicateWaves.Count -eq 0) -Message 'board has no duplicate wave ids' -Details $duplicateWaves
Add-Assertion -Assertions $assertions -Pass ($unknownStatuses.Count -eq 0) -Message 'all wave statuses are allowed by board policy' -Details $unknownStatuses

$waveRecords = @()
foreach ($wave in $waves) {
    $assetFailures = @()
    foreach ($asset in @($wave.required_assets)) {
        $assetPath = Join-Path $context.repoRoot $asset
        if (-not (Test-Path -LiteralPath $assetPath)) {
            $assetFailures += $asset
        }
    }

    $gateScriptPath = Join-Path $context.repoRoot ('scripts\verify\{0}.ps1' -f [string]$wave.verify_gate)
    $gateExists = Test-Path -LiteralPath $gateScriptPath
    Add-Assertion -Assertions $assertions -Pass $gateExists -Message ('wave {0} verify gate exists' -f $wave.wave) -Details $gateScriptPath
    Add-Assertion -Assertions $assertions -Pass ($assetFailures.Count -eq 0) -Message ('wave {0} required assets exist' -f $wave.wave) -Details $assetFailures

    $waveRecords += [pscustomobject]@{
        wave = [int]$wave.wave
        title = [string]$wave.title
        status = [string]$wave.status
        verify_gate = [string]$wave.verify_gate
        gate_exists = [bool]$gateExists
        assets_ok = [bool]($assetFailures.Count -eq 0)
        missing_assets = @($assetFailures)
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-wave40-63-board-gate'
    repo_root = $context.repoRoot
    board_path = $boardPath
    plan_path = $planPath
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    waves = $waveRecords
    assertions = @($assertions)
    summary = [ordered]@{
        wave_count = $waves.Count
        failure_count = $failureCount
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $context.repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) { exit 1 }
exit 0
