param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$policyPath = Join-Path $repoRoot 'config/platform-support-policy.json'
$matrixPath = Join-Path $repoRoot 'docs/universalization/platform-support-matrix.md'
$contractPath = Join-Path $repoRoot 'docs/universalization/platform-parity-contract.md'
$ledgerPath = Join-Path $repoRoot 'references/platform-gap-ledger.md'

$failures = @()

foreach ($path in @($policyPath, $matrixPath, $contractPath, $ledgerPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        $failures += "missing required platform contract artifact: $path"
    }
}

if (Test-Path -LiteralPath $policyPath) {
    try {
        $policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        $failures += "invalid platform-support-policy.json: $($_.Exception.Message)"
    }

    if ($null -ne $policy) {
        $levels = @($policy.status_levels)
        foreach ($required in @('full-authoritative', 'supported-with-constraints', 'degraded-but-supported', 'not-yet-proven')) {
            if ($levels -notcontains $required) {
                $failures += "platform-support-policy missing status level: $required"
            }
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Host "[FAIL] $_" -ForegroundColor Red }
    exit 1
}

Write-Host '[PASS] platform support contract gate'
