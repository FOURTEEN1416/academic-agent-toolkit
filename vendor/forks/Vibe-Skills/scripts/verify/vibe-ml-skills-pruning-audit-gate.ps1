[CmdletBinding()]
param(
    [string]$RepoRoot,
    [switch]$WriteArtifacts,
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$runnerPath = Join-Path $RepoRoot 'scripts/verify/runtime_neutral/ml_skills_pruning_audit.py'
if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "ML skills pruning audit runner missing: $runnerPath"
}

. (Join-Path $RepoRoot 'scripts/common/vibe-governance-helpers.ps1')
$pythonInvocation = Get-VgoPythonCommand

$runnerArgs = @(
    $runnerPath,
    '--repo-root', $RepoRoot
)
if ($WriteArtifacts) {
    $runnerArgs += '--write-artifacts'
}
if ($OutputDirectory) {
    $runnerArgs += @('--output-directory', $OutputDirectory)
}

& $pythonInvocation.host_path @($pythonInvocation.prefix_arguments) @runnerArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "vibe-ml-skills-pruning-audit-gate failed with exit code $exitCode"
}

Write-Host '[PASS] vibe-ml-skills-pruning-audit-gate passed' -ForegroundColor Green
