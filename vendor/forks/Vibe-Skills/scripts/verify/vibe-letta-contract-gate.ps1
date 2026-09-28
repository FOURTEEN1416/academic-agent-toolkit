param()

$ErrorActionPreference = "Stop"
function Assert-True { param([bool]$Condition,[string]$Message) if ($Condition) { Write-Host "[PASS] $Message"; return $true } Write-Host "[FAIL] $Message" -ForegroundColor Red; return $false }
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$path = Join-Path $repoRoot "config\letta-governance-contract.json"
$contract = Get-Content -Raw $path -Encoding UTF8 | ConvertFrom-Json
$checks = @()
$checks += Assert-True ($contract.role -eq 'contract_source_only') "letta role is contract source only"
$checks += Assert-True ($contract.contracts.memory_block_mapping -eq $true) "memory block mapping enabled"
$checks += Assert-True ($contract.forbid_runtime_takeover -eq $true) "runtime takeover forbidden"
$checks += Assert-True ($contract.forbid_second_orchestrator -eq $true) "second orchestrator forbidden"
$checks += Assert-True ($contract.forbid_route_mutation -eq $true) "route mutation forbidden"
if ($checks -contains $false) { throw 'letta contract gate failed' }
Write-Host "[PASS] letta contract gate succeeded" -ForegroundColor Green
