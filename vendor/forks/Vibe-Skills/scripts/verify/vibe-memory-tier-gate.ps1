param()

$ErrorActionPreference = "Stop"

function Assert-True {
    param([bool]$Condition,[string]$Message)
    if ($Condition) { Write-Host "[PASS] $Message"; return $true }
    Write-Host "[FAIL] $Message" -ForegroundColor Red; return $false
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$tierPath = Join-Path $repoRoot "config\memory-tier-router.json"
$govPath = Join-Path $repoRoot "config\memory-governance.json"
$tier = Get-Content -Raw $tierPath -Encoding UTF8 | ConvertFrom-Json
$gov = Get-Content -Raw $govPath -Encoding UTF8 | ConvertFrom-Json
$checks = @()
$checks += Assert-True ($tier.tiers.session -eq 'state_store') "session tier maps to state_store"
$checks += Assert-True ($tier.tiers.project_decision -eq 'serena') "project_decision tier maps to serena"
$checks += Assert-True ($tier.tiers.short_term_semantic -eq 'ruflo') "short_term_semantic tier maps to ruflo"
$checks += Assert-True ($tier.tiers.long_term_graph -eq 'cognee') "long_term_graph tier maps to cognee"
$checks += Assert-True ($tier.tiers.external_preference -eq 'mem0') "external_preference tier maps to mem0"
$checks += Assert-True ($tier.tiers.policy_contract -eq 'letta') "policy_contract tier maps to letta"
$checks += Assert-True ($tier.constraints.forbid_mem0_as_primary -eq $true) "mem0 cannot be primary"
$checks += Assert-True ($tier.constraints.forbid_letta_as_runtime_owner -eq $true) "letta cannot own runtime"
$checks += Assert-True ($gov.role_boundaries.episodic_memory.status -eq 'disabled') "episodic memory remains disabled"
if ($checks -contains $false) { throw "memory tier gate failed" }
Write-Host "[PASS] memory tier gate succeeded" -ForegroundColor Green
