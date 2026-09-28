param(
  [switch]$WriteArtifacts,
  [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Assert-True {
  param([bool]$Condition,[string]$Message)
  if ($Condition) {
    Write-Host "[PASS] $Message"
    return $true
  }
  Write-Host "[FAIL] $Message" -ForegroundColor Red
  return $false
}

function Test-ContainsAll {
  param([object[]]$Actual,[string[]]$Expected)
  foreach ($item in $Expected) {
    if ($Actual -notcontains $item) {
      return $false
    }
  }
  return $true
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$boardPath = Join-Path $repoRoot 'config\promotion-board.json'
$board = Get-Content -Raw $boardPath -Encoding UTF8 | ConvertFrom-Json

$executionPlanes = @('memory-runtime-v2', 'prompt-intelligence', 'browserops-provider', 'desktopops-shadow')
$waveTracks = @('mirror-topology-governance', 'upstream-corpus-governance', 'docling-document-plane', 'connector-admission-layer', 'role-pack-distillation', 'capability-catalog-corpus')
$requiredItems = @($executionPlanes + $waveTracks)
$requiredGateMap = @{
  'memory-runtime-v2' = @('vibe-memory-tier-gate','vibe-mem0-backend-gate','vibe-letta-contract-gate','vibe-cross-plane-conflict-gate','vibe-pilot-scenarios')
  'prompt-intelligence' = @('vibe-prompt-intelligence-assets-gate','vibe-cross-plane-conflict-gate','vibe-pilot-scenarios')
  'browserops-provider' = @('vibe-browserops-gate','vibe-cross-plane-conflict-gate','vibe-pilot-scenarios')
  'desktopops-shadow' = @('vibe-desktopops-shadow-gate','vibe-cross-plane-conflict-gate','vibe-pilot-scenarios')
  'mirror-topology-governance' = @('vibe-version-packaging-gate','vibe-nested-bundled-parity-gate','vibe-mirror-edit-hygiene-gate','vibe-release-install-runtime-coherence-gate')
  'upstream-corpus-governance' = @('vibe-upstream-corpus-manifest-gate','vibe-upstream-mirror-freshness-gate','vibe-deep-extraction-pilot-gate')
  'docling-document-plane' = @('vibe-docling-contract-gate','vibe-deep-extraction-pilot-gate')
  'connector-admission-layer' = @('vibe-connector-admission-gate','vibe-deep-extraction-pilot-gate')
  'role-pack-distillation' = @('vibe-role-pack-governance-gate','vibe-deep-extraction-pilot-gate')
  'capability-catalog-corpus' = @('vibe-capability-catalog-gate','vibe-deep-extraction-pilot-gate')
}
$pilotMap = @{
  'memory-runtime-v2' = 'scripts/verify/fixtures/pilot-memory.json'
  'prompt-intelligence' = 'scripts/verify/fixtures/pilot-prompt.json'
  'browserops-provider' = 'scripts/verify/fixtures/pilot-browserops.json'
  'desktopops-shadow' = 'scripts/verify/fixtures/pilot-desktopops.json'
  'mirror-topology-governance' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
  'upstream-corpus-governance' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
  'docling-document-plane' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
  'connector-admission-layer' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
  'role-pack-distillation' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
  'capability-catalog-corpus' = 'scripts/verify/fixtures/pilot-deep-extraction.json'
}

$checks = @()
$checks += Assert-True ($board.board_policy.mode -eq 'advice_first') 'promotion board is advice-first'
$checks += Assert-True ($board.board_policy.forbid_unsafe_auto_promote -eq $true) 'promotion board forbids unsafe auto-promote'
$checks += Assert-True ($board.board_policy.promote_stage_is_board_decision_only -eq $true) 'promote stage is board-decision only'
$checks += Assert-True (Test-ContainsAll -Actual @($board.allowed_stages) -Expected @('shadow', 'soft', 'strict', 'promote')) 'allowed stages cover shadow -> soft -> strict -> promote'
$checks += Assert-True (Test-ContainsAll -Actual @($board.stage_requirements.PSObject.Properties.Name) -Expected @('shadow', 'soft', 'strict', 'promote')) 'stage requirements exist for all rollout stages'
$checks += Assert-True ((@($board.planes).Count) -ge $requiredItems.Count) 'promotion board tracks Wave19-39 execution planes and governance tracks'

$releasePlane = @($board.planes | Where-Object { [string]$_.plane_id -eq 'operator-release-train' }) | Select-Object -First 1
$checks += Assert-True ($null -ne $releasePlane) 'operator-release-train plane exists'
if ($releasePlane) {
  $checks += Assert-True (@($releasePlane.required_gates) -contains 'vibe-release-truth-consistency-gate') 'operator-release-train requires release-truth consistency gate'
}

$actualPlanes = @($board.planes | ForEach-Object { [string]$_.plane_id })
$checks += Assert-True (Test-ContainsAll -Actual $actualPlanes -Expected $requiredItems) 'promotion board covers all required execution planes and Wave31-39 governance tracks'

foreach ($plane in @($board.planes)) {
  $planeId = [string]$plane.plane_id
  if ($requiredItems -notcontains $planeId) {
    continue
  }
  $pilotFixturePath = Join-Path $repoRoot (([string]$pilotMap[$planeId]).Replace('/', '\'))
  $checks += Assert-True (-not [string]::IsNullOrWhiteSpace([string]$plane.current_stage)) "current_stage exists for $planeId"
  $checks += Assert-True (-not [string]::IsNullOrWhiteSpace([string]$plane.next_stage)) "next_stage exists for $planeId"
  $checks += Assert-True ((@($board.allowed_stages) -contains [string]$plane.current_stage)) "current_stage is valid for $planeId"
  $checks += Assert-True ((@($plane.required_gates).Count) -ge 2) "required_gates defined for $planeId"
  foreach ($gate in @($requiredGateMap[$planeId])) {
    $checks += Assert-True (@($plane.required_gates) -contains $gate) ("required gate {0} bound to {1}" -f $gate, $planeId)
  }
  $checks += Assert-True (([string]$plane.pilot_fixture) -eq [string]$pilotMap[$planeId]) "pilot fixture path is canonical for $planeId"
  $checks += Assert-True (Test-Path -LiteralPath $pilotFixturePath) "pilot fixture exists for $planeId"
  $checks += Assert-True (-not [string]::IsNullOrWhiteSpace([string]$plane.rollback.command)) "rollback.command exists for $planeId"
  $checks += Assert-True (-not [string]::IsNullOrWhiteSpace([string]$plane.rollback.owner)) "rollback.owner exists for $planeId"
  $checks += Assert-True ($plane.rollback.max_safe_auto_write_stage -eq 'soft') "max_safe_auto_write_stage is soft for $planeId"
  $checks += Assert-True ($plane.evidence.soft_candidate_ready -eq $true) "soft candidate evidence exists for $planeId"
  $checks += Assert-True (-not [string]::IsNullOrWhiteSpace([string]$plane.evidence_summary)) "evidence summary exists for $planeId"
}

$gatePassed = ($checks -notcontains $false)
if ($WriteArtifacts) {
  if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repoRoot 'outputs\verify'
  }
  New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
  ([ordered]@{
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($gatePassed) { 'PASS' } else { 'FAIL' }
    tracked_items = $requiredItems
  } | ConvertTo-Json -Depth 20) | Set-Content -LiteralPath (Join-Path $OutputDirectory 'vibe-promotion-board-gate.json') -Encoding UTF8
}

if (-not $gatePassed) {
  throw 'promotion board gate failed'
}

Write-Host '[PASS] promotion board gate succeeded' -ForegroundColor Green
