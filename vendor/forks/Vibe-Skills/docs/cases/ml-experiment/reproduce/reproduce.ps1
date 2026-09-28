[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$caseRoot = Join-Path $PSScriptRoot 'generated'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Create the case environment and install requirements before running this script: $python"
}

$dataAuditDir = Join-Path $caseRoot 'deliverables\01-data-audit'
$baselineDir = Join-Path $caseRoot 'deliverables\02-baseline'
$statisticsDir = Join-Path $caseRoot 'deliverables\03-statistical-review\statistics'
$figuresDir = Join-Path $caseRoot 'deliverables\04-figures'

foreach ($directory in @($dataAuditDir, $baselineDir, $statisticsDir, $figuresDir)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'create_data_audit.py') -Destination $dataAuditDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run_experiment.py') -Destination $baselineDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'compute_uncertainty.py') -Destination $statisticsDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'make_figures.py') -Destination $figuresDir -Force

$steps = @(
    (Join-Path $dataAuditDir 'create_data_audit.py'),
    (Join-Path $baselineDir 'run_experiment.py'),
    (Join-Path $baselineDir 'run_experiment.py'),
    (Join-Path $statisticsDir 'compute_uncertainty.py'),
    (Join-Path $figuresDir 'make_figures.py')
)

foreach ($step in $steps) {
    & $python $step
    if ($LASTEXITCODE -ne 0) {
        throw "Reproduction step failed with exit code ${LASTEXITCODE}: $step"
    }
}

$actualMetrics = Join-Path $baselineDir 'metrics.json'
$acceptedMetrics = Join-Path (Split-Path -Parent $PSScriptRoot) 'evidence\metrics.json'
$actualHash = (Get-FileHash -LiteralPath $actualMetrics -Algorithm SHA256).Hash
$acceptedHash = (Get-FileHash -LiteralPath $acceptedMetrics -Algorithm SHA256).Hash
if ($actualHash -ne $acceptedHash) {
    throw 'Generated metrics do not match the accepted case metrics.'
}

$reproduction = Get-Content -LiteralPath (Join-Path $baselineDir 'reproduction-check.json') -Raw | ConvertFrom-Json
if ($reproduction.exact_match_previous_run -ne $true) {
    throw 'The two baseline runs did not produce an exact match.'
}

Write-Host 'Reproduction passed: metrics match the accepted case and the second baseline run matched the first.'
