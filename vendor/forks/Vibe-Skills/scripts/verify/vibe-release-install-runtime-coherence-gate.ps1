param(
    [string]$TargetRoot = '',
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')
if ([string]::IsNullOrWhiteSpace($TargetRoot)) {
    $TargetRoot = Resolve-VgoTargetRoot
}

$runnerPath = Join-Path $PSScriptRoot 'runtime_neutral\coherence_gate.py'
if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "runtime-neutral coherence gate missing: $runnerPath"
}

$pythonInvocation = Get-VgoPythonCommand

$args = @(
    $runnerPath,
    '--target-root', $TargetRoot
)
if ($WriteArtifacts) {
    $args += '--write-artifacts'
}

& $pythonInvocation.host_path @($pythonInvocation.prefix_arguments) @args
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "vibe-release-install-runtime-coherence-gate failed with exit code $exitCode"
}

Write-Host '[PASS] vibe-release-install-runtime-coherence-gate passed' -ForegroundColor Green
