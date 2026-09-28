param()

$ErrorActionPreference = "Stop"

$replacementGate = Join-Path $PSScriptRoot "vibe-orchestration-core-hard-removal-gate.ps1"
if (-not (Test-Path -LiteralPath $replacementGate)) {
    throw "Replacement hard-removal gate not found: $replacementGate"
}

Write-Host "orchestration-core consolidation gate is superseded by hard-removal gate."
& $replacementGate
exit $LASTEXITCODE
