[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ScenarioPath,
    [string]$RepoRoot,
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$runnerPath = Join-Path $RepoRoot 'scripts\verify\runtime_neutral\workflow_acceptance_runner.py'
if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "workflow acceptance runner missing: $runnerPath"
}

$resolvedScenario = (Resolve-Path $ScenarioPath).Path

. (Join-Path $RepoRoot 'scripts\common\vibe-governance-helpers.ps1')
$pythonInvocation = Get-VgoPythonCommand

$args = @(
    $runnerPath
    '--repo-root', $RepoRoot
    '--scenario', $resolvedScenario
    '--write-artifacts'
)
if ($OutputDirectory) {
    $args += @('--output-directory', $OutputDirectory)
}

& $pythonInvocation.host_path @($pythonInvocation.prefix_arguments) @args
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "vibe-workflow-acceptance-gate failed with exit code $exitCode"
}

Write-Host '[PASS] vibe-workflow-acceptance-gate passed' -ForegroundColor Green
