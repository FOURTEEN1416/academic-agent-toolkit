param(
    [string]$TargetRoot = '',
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'

function Add-Assertion {
    param(
        [System.Collections.Generic.List[object]]$Collection,
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
    }

    [void]$Collection.Add([pscustomobject]@{
        ok = $Condition
        message = $Message
    })
}

function Write-Artifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact
    )

    $outputDir = Join-Path $RepoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    $jsonPath = Join-Path $outputDir 'vibe-uninstall-coherence-gate.json'
    $mdPath = Join-Path $outputDir 'vibe-uninstall-coherence-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Uninstall Coherence Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Removal Documentation: `{0}`' -f $Artifact.contract.docs),
        ('- Assertion Failures: {0}' -f $Artifact.summary.failures),
        ('- Warnings: {0}' -f $Artifact.summary.warnings),
        ''
    )

    if ($Artifact.assertions.Count -gt 0) {
        $lines += '## Assertions'
        $lines += ''
        foreach ($item in $Artifact.assertions) {
            $lines += ('- [{0}] {1}' -f $(if ($item.ok) { 'PASS' } else { 'FAIL' }), $item.message)
        }
        $lines += ''
    }

    if ($Artifact.warnings.Count -gt 0) {
        $lines += '## Warnings'
        $lines += ''
        foreach ($item in $Artifact.warnings) {
            $lines += ('- {0}' -f $item)
        }
        $lines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

$TargetRoot = Resolve-VgoTargetRoot -TargetRoot $TargetRoot

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$assertions = New-Object System.Collections.Generic.List[object]
$warnings = New-Object System.Collections.Generic.List[string]

$repoRoot = [string]$context.repoRoot
$uninstallPs1 = [System.IO.Path]::Combine($repoRoot, 'uninstall.ps1')
$uninstallSh = [System.IO.Path]::Combine($repoRoot, 'uninstall.sh')
$docPath = [System.IO.Path]::Combine($repoRoot, 'docs', 'uninstall-governance.md')
$installGuideEn = [System.IO.Path]::Combine($repoRoot, 'docs', 'install', 'README.en.md')
$installGuideZh = [System.IO.Path]::Combine($repoRoot, 'docs', 'install', 'README.md')
$troubleshootingPath = [System.IO.Path]::Combine($repoRoot, 'docs', 'troubleshooting.md')

$results = [ordered]@{
    gate = 'vibe-uninstall-coherence-gate'
    repo_root = $context.repoRoot
    target_root = [System.IO.Path]::GetFullPath($TargetRoot)
    generated_at = (Get-Date).ToString('s')
    gate_result = 'FAIL'
    assertions = @()
    warnings = @()
    contract = [ordered]@{
        uninstall_ps1 = $uninstallPs1
        uninstall_sh = $uninstallSh
        docs = $docPath
        install_guide_en = $installGuideEn
        install_guide_zh = $installGuideZh
        troubleshooting = $troubleshootingPath
    }
    summary = [ordered]@{
        failures = 0
        warnings = 0
    }
}

Write-Host '=== VCO Uninstall Coherence Gate ==='
Write-Host ("Repo root  : {0}" -f $context.repoRoot)
Write-Host ("Target root: {0}" -f $TargetRoot)
Write-Host ''

Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $uninstallPs1) -Message '[repo] uninstall.ps1 entrypoint exists'
Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $uninstallSh) -Message '[repo] uninstall.sh entrypoint exists'
Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $docPath) -Message '[docs] removal doc exists'
Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $installGuideEn) -Message '[docs] English install guide exists'
Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $installGuideZh) -Message '[docs] Chinese install guide exists'
Add-Assertion -Collection $assertions -Condition (Test-Path -LiteralPath $troubleshootingPath) -Message '[docs] troubleshooting guide exists'

$publicDocs = @($docPath, $installGuideEn, $installGuideZh, $troubleshootingPath)
foreach ($path in $publicDocs) {
    if (-not (Test-Path -LiteralPath $path)) {
        continue
    }

    Add-Assertion -Collection $assertions -Condition (Select-String -LiteralPath $path -Pattern '<SkillsDir>/vibe' -SimpleMatch -Quiet) -Message ("[docs] {0} points to the installed vibe folder" -f ([System.IO.Path]::GetFileName($path)))
    foreach ($retiredTerm in @('uninstall.ps1', 'uninstall.sh', '-HostId', '-Profile', '-StrictOffline', '-Deep', 'install-ledger.json', 'host-closure.json')) {
        Add-Assertion -Collection $assertions -Condition (-not (Select-String -LiteralPath $path -Pattern $retiredTerm -SimpleMatch -Quiet)) -Message ("[docs] {0} omits retired term {1}" -f ([System.IO.Path]::GetFileName($path)), $retiredTerm)
    }
}

$failed = @($assertions | Where-Object { -not $_.ok }).Count
$results.summary.failures = $failed
$results.summary.warnings = $warnings.Count
$results.assertions = $assertions
$results.warnings = $warnings
$results.gate_result = if ($failed -eq 0) { 'PASS' } else { 'FAIL' }

if ($WriteArtifacts) {
    Write-Artifacts -RepoRoot $context.repoRoot -Artifact $results
}

if ($failed -ne 0) {
    exit 1
}
