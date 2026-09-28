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

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$governance = $context.governance
$metrics = $governance.metrics
$manifest = Get-Content -LiteralPath (Join-Path $context.repoRoot 'config/upstream-corpus-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$board = Get-Content -LiteralPath (Join-Path $context.repoRoot 'config/promotion-board.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$fixturePath = Join-Path $context.repoRoot 'scripts/verify/fixtures/pilot-deep-extraction.json'
$fixture = if (Test-Path -LiteralPath $fixturePath) { Get-Content -LiteralPath $fixturePath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$runtimeOnlyTracked = @('references/docling-output-spec.md')
$runtimeRoot = Resolve-VgoPathSpec -PathSpec ([string]$manifest.runtime_mirror_root) -RepoRoot $context.repoRoot
$runtimeOnlyArtifactCount = 0
foreach ($rel in $runtimeOnlyTracked) {
  if (-not [string]::IsNullOrWhiteSpace($runtimeRoot)) {
    $runtimePath = Join-Path (Join-Path $runtimeRoot 'bundled/skills/vibe') $rel
    $canonicalPath = Join-Path $context.repoRoot $rel
    if ((Test-Path -LiteralPath $runtimePath) -and (-not (Test-Path -LiteralPath $canonicalPath))) {
      $runtimeOnlyArtifactCount++
    }
  }
}
$productized = @($manifest.entries | Where-Object { @($_.canonical_assets).Count -ge 1 }).Count
$productizationRatio = if (@($manifest.entries).Count -gt 0) { [math]::Round(($productized / @($manifest.entries).Count), 4) } else { 0 }
$requiredMirrorIds = @('canonical','bundled','nested_bundled')
$mirrorIds = @($governance.mirror_topology.targets | ForEach-Object { [string]$_.id })
$governedMirrorCoverage = [math]::Round((@($requiredMirrorIds | Where-Object { $mirrorIds -contains $_ }).Count / $requiredMirrorIds.Count), 4)
$requiredBoardItems = @('mirror-topology-governance','upstream-corpus-governance','docling-document-plane','connector-admission-layer','role-pack-distillation','capability-catalog-corpus')
$actualBoardItems = @($board.planes | ForEach-Object { [string]$_.plane_id })
$checks = @()
$checks += Assert-True (Test-Path -LiteralPath $fixturePath) 'deep extraction pilot fixture exists'
$checks += Assert-True ($null -ne $fixture -and $fixture.expected.governed_mirror_coverage -eq 1.0) 'deep extraction fixture encodes mirror coverage target'
$checks += Assert-True ($governedMirrorCoverage -ge [double]$metrics.governed_mirror_coverage_target) 'governed mirror coverage meets target'
$checks += Assert-True ($runtimeOnlyArtifactCount -le [int]$metrics.runtime_only_artifact_count_target) 'runtime-only artifact count meets target'
$checks += Assert-True (@($manifest.entries).Count -ge [int]$metrics.upstream_manifest_coverage_target) 'upstream manifest coverage meets target'
$checks += Assert-True ($productizationRatio -ge [double]$metrics.productization_ratio_target) 'productization ratio meets target'
$checks += Assert-True ((@($requiredBoardItems | Where-Object { $actualBoardItems -contains $_ }).Count) -eq $requiredBoardItems.Count) 'promotion board covers Wave31-39 items'
$gatePassed = ($checks -notcontains $false)
if ($WriteArtifacts) {
  if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $context.repoRoot 'outputs\verify'
  }
  New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
  ([ordered]@{
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($gatePassed) { 'PASS' } else { 'FAIL' }
    metrics = [ordered]@{
      governed_mirror_coverage = $governedMirrorCoverage
      runtime_only_artifact_count = $runtimeOnlyArtifactCount
      upstream_manifest_coverage = @($manifest.entries).Count
      productization_ratio = $productizationRatio
    }
  } | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath (Join-Path $OutputDirectory 'vibe-deep-extraction-pilot-gate.json') -Encoding UTF8
}
if (-not $gatePassed) {
  exit 1
}
