param()

$ErrorActionPreference = 'Stop'

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )

  if ($Condition) {
    Write-Host "[PASS] $Message"
    return $true
  }

  Write-Host "[FAIL] $Message" -ForegroundColor Red
  return $false
}

function Test-ContainsAll {
  param(
    [object[]]$Actual,
    [string[]]$Expected
  )

  foreach ($item in $Expected) {
    if ($Actual -notcontains $item) {
      return $false
    }
  }

  return $true
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$policyPath = Join-Path $repoRoot 'config\cross-plane-conflict-policy.json'
$policy = Get-Content -Raw $policyPath -Encoding UTF8 | ConvertFrom-Json

$checks = @()
$arbitrationIds = @($policy.arbitration_order | ForEach-Object { [string]$_.plane_id })
$arbitrationRanks = @($policy.arbitration_order | ForEach-Object { [int]$_.rank })
$expectedOrder = @(
  'user_explicit',
  'vco_route',
  'verification_gate',
  'memory-runtime-v2',
  'prompt-intelligence',
  'browserops-provider',
  'desktopops-shadow'
)

$checks += Assert-True (($arbitrationIds -join '|') -eq ($expectedOrder -join '|')) 'cross-plane arbitration order is stable'
$checks += Assert-True (($arbitrationRanks -join '|') -eq '1|2|3|4|5|6|7') 'arbitration ranks are sequential and complete'
$checks += Assert-True ($policy.control_plane.owner -eq 'vco_route') 'VCO remains the control-plane owner'
$checks += Assert-True ($policy.control_plane.forbid_second_orchestrator -eq $true) 'policy forbids second orchestrator'
$checks += Assert-True ($policy.control_plane.forbid_second_default_execution_owner -eq $true) 'policy forbids second default execution owner'
$checks += Assert-True ($policy.control_plane.forbid_second_canonical_truth_source -eq $true) 'policy forbids second canonical truth-source'

$ruleNames = @($policy.plane_rules.PSObject.Properties.Name)
$checks += Assert-True (Test-ContainsAll -Actual $ruleNames -Expected @('memory-runtime-v2', 'prompt-intelligence', 'browserops-provider', 'desktopops-shadow')) 'all four plane rules exist'

$memoryRule = $policy.plane_rules.'memory-runtime-v2'
$promptRule = $policy.plane_rules.'prompt-intelligence'
$browserRule = $policy.plane_rules.'browserops-provider'
$desktopRule = $policy.plane_rules.'desktopops-shadow'

$checks += Assert-True (Test-ContainsAll -Actual @($memoryRule.forbid_override) -Expected @('route_selection', 'execution_owner', 'canonical_truth_source')) 'memory plane cannot override route, owner, or truth-source'
$checks += Assert-True (Test-ContainsAll -Actual @($promptRule.forbid_override) -Expected @('selected_pack', 'selected_skill', 'router_decision')) 'prompt plane cannot become a second router'
$checks += Assert-True (Test-ContainsAll -Actual @($browserRule.forbid_override) -Expected @('route_selection', 'execution_owner', 'second_orchestrator')) 'browser plane cannot take over orchestration'
$checks += Assert-True (Test-ContainsAll -Actual @($desktopRule.forbid_override) -Expected @('default_execution_owner', 'route_selection', 'second_orchestrator')) 'desktop plane cannot become default execution owner'

$checks += Assert-True ($policy.conflict_resolution.authority_overlap.action -eq 'freeze_to_shadow') 'authority overlap falls back to shadow'
$checks += Assert-True ($policy.conflict_resolution.confirmation_mismatch.action -eq 'confirm_required_wins') 'confirm_required wins on mismatch'
$checks += Assert-True ($policy.conflict_resolution.promotion_mismatch.action -eq 'block_promotion_and_revert_to_candidate_state') 'promotion mismatch blocks promotion'
$checks += Assert-True ($policy.rollout_guards.freeze_promotion_on_conflict -eq $true) 'promotion freezes when conflict exists'
$checks += Assert-True ($policy.rollout_guards.fallback_stage -eq 'shadow') 'fallback stage remains shadow'

if ($checks -contains $false) {
  throw 'cross-plane conflict gate failed'
}

Write-Host '[PASS] cross-plane conflict gate succeeded' -ForegroundColor Green
