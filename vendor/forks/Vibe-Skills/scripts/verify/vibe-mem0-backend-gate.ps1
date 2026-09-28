param()

$ErrorActionPreference = "Stop"
function Assert-True { param([bool]$Condition,[string]$Message) if ($Condition) { Write-Host "[PASS] $Message"; return $true } Write-Host "[FAIL] $Message" -ForegroundColor Red; return $false }
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$policyPath = Join-Path $repoRoot "config\mem0-backend-policy.json"
$policy = Get-Content -Raw $policyPath -Encoding UTF8 | ConvertFrom-Json
$checks = @()
$checks += Assert-True ($policy.role -eq 'optional_external_preference_backend') "mem0 role is optional backend"
$checks += Assert-True (@($policy.allowed_payload_types) -contains 'preference') "preference payload allowed"
$checks += Assert-True (@($policy.forbidden_payload_types) -contains 'route_assignment') "route_assignment payload forbidden"
$checks += Assert-True (@($policy.forbidden_payload_types) -contains 'canonical_project_decision') "canonical project decision forbidden"
$checks += Assert-True ($policy.fallback_behavior.on_missing_backend -eq 'keep_core_memory_owners') "fallback preserves core owners"
if ($checks -contains $false) { throw 'mem0 backend gate failed' }
Write-Host "[PASS] mem0 backend gate succeeded" -ForegroundColor Green
