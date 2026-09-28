[CmdletBinding()]
param(
    [string[]]$Path,
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

$runnerPath = Join-Path $RepoRoot 'scripts\verify\runtime_neutral\release_notes_quality.py'
if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "release notes quality runner missing: $runnerPath"
}

. (Join-Path $RepoRoot 'scripts\common\vibe-governance-helpers.ps1')
$pythonInvocation = Get-VgoPythonCommand

$args = @(
    $runnerPath
    '--repo-root', $RepoRoot
    '--write-artifacts'
)
foreach ($item in @($Path)) {
    if ([string]::IsNullOrWhiteSpace([string]$item)) {
        continue
    }
    $args += @('--path', (Resolve-Path $item).Path)
}
if ($OutputDirectory) {
    $args += @('--output-directory', $OutputDirectory)
}

& $pythonInvocation.host_path @($pythonInvocation.prefix_arguments) @args
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "vibe-release-notes-quality-gate failed with exit code $exitCode"
}

Write-Host '[PASS] vibe-release-notes-quality-gate passed' -ForegroundColor Green
