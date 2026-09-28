param(
  [Parameter(Mandatory = $true)]
  [string]$PlaneId,

  [Alias('Apply')]
  [switch]$WriteBoard
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$boardPath = Join-Path $repoRoot 'config\promotion-board.json'
$board = Get-Content -Raw $boardPath -Encoding UTF8 | ConvertFrom-Json
$item = @($board.planes | Where-Object { $_.plane_id -eq $PlaneId }) | Select-Object -First 1

if ($null -eq $item) {
  throw "Unknown plane_id: $PlaneId"
}

$pilotFixturePath = Join-Path $repoRoot ([string]$item.pilot_fixture).Replace('/', '\')
$reasons = [System.Collections.Generic.List[string]]::new()
$eligible = $true

if ($board.board_policy.mode -ne 'advice_first') {
  $eligible = $false
  $null = $reasons.Add('promotion board mode is not advice_first')
}

if ($board.board_policy.forbid_unsafe_auto_promote -ne $true) {
  $eligible = $false
  $null = $reasons.Add('promotion board does not declare forbid_unsafe_auto_promote=true')
}

if ([string]$item.current_stage -ne 'shadow') {
  $eligible = $false
  $null = $reasons.Add("current_stage is $($item.current_stage), not shadow")
}

if ([string]$item.next_stage -ne 'soft') {
  $eligible = $false
  $null = $reasons.Add("next_stage is $($item.next_stage), not soft")
}

if ($item.evidence.soft_candidate_ready -ne $true) {
  $eligible = $false
  $null = $reasons.Add('evidence.soft_candidate_ready is not true')
}

if ($item.evidence.rollback_ready -ne $true) {
  $eligible = $false
  $null = $reasons.Add('evidence.rollback_ready is not true')
}

if ($item.evidence.cross_plane_conflict_ready -ne $true) {
  $eligible = $false
  $null = $reasons.Add('evidence.cross_plane_conflict_ready is not true')
}

if (-not (Test-Path $pilotFixturePath)) {
  $eligible = $false
  $null = $reasons.Add("pilot fixture missing: $($item.pilot_fixture)")
}

if ([string]::IsNullOrWhiteSpace([string]$item.rollback.command)) {
  $eligible = $false
  $null = $reasons.Add('rollback.command is empty')
}

$advice = [pscustomobject]@{
  plane_id = $item.plane_id
  current_stage = $item.current_stage
  recommended_stage = 'soft'
  eligible = $eligible
  reasons = @($reasons)
  required_gates = @($item.required_gates)
  pilot_fixture = $item.pilot_fixture
  pilot_status = $item.pilot_status
  rollback_command = $item.rollback.command
  board_mode = $board.board_policy.mode
  write_scope = $board.board_policy.write_scope
}

Write-Host '[INFO] soft-rollout advice:' -ForegroundColor Cyan
Write-Host ($advice | ConvertTo-Json -Depth 6)

if (-not $WriteBoard) {
  Write-Host '[INFO] Advice-only mode: no board write performed.' -ForegroundColor Yellow
  Write-Host '[INFO] To write the board explicitly, use -WriteBoard. Only shadow -> soft is supported.' -ForegroundColor Yellow
  exit 0
}

if (-not $eligible) {
  throw "Plane $PlaneId is not eligible for shadow -> soft write. Resolve the advice reasons first."
}

$item.current_stage = 'soft'
$item.last_reviewed_at = (Get-Date).ToString('yyyy-MM-dd')
$item.evidence.latest_gate_status = 'manual_soft_rollout_written'

$out = $board | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText($boardPath, $out + "`n", [System.Text.UTF8Encoding]::new($false))

Write-Host "[PASS] $PlaneId was explicitly written to soft stage (shadow -> soft only)." -ForegroundColor Green
