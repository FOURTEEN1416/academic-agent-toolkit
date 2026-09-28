param(
  [string]$CodexRoot = '',
  [ValidateSet("IntentAdvice", "VectorDiff", "All")]
  [string]$Target = "All",
  [ValidateSet("User", "Process")]
  [string]$Scope = "User",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

$CodexRoot = Resolve-VgoTargetRoot -TargetRoot $CodexRoot

function Get-NonEmptyOrNull {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
  return [string]$Value
}

function Set-EnvSafe {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Value,
    [Parameter(Mandatory = $true)][string]$Scope,
    [switch]$DryRun
  )

  if ($DryRun) {
    Write-Host ("- would set {0} ({1})" -f $Name, $Scope) -ForegroundColor DarkGray
    return
  }

  if ($Scope -eq "Process") {
    Set-Item -Path ("env:{0}" -f $Name) -Value $Value
    return
  }

  # Persist to Windows user environment (registry) without printing the secret value.
  [Environment]::SetEnvironmentVariable($Name, $Value, "User")
}

$settingsPath = Join-Path $CodexRoot "settings.json"
if (-not (Test-Path -LiteralPath $settingsPath)) {
  throw "Codex settings.json not found: $settingsPath"
}

try {
  $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
  throw "Failed to parse settings.json as JSON: $settingsPath"
}

if (-not $settings.env) {
  throw "settings.json missing .env object: $settingsPath"
}

Write-Host "Sync Codex settings.json -> Windows env" -ForegroundColor Cyan
Write-Host ("- target: {0}" -f $Target)
Write-Host ("- scope:  {0}" -f $Scope)
if ($DryRun) { Write-Host "- dry_run: true" -ForegroundColor Yellow }

function Sync-One {
  param([string]$Name)
  $value = $null
  try { $value = $settings.env.$Name } catch { $value = $null }
  $resolved = Get-NonEmptyOrNull -Value ([string]$value)
  if (-not $resolved) {
    Write-Host ("- {0}: missing in settings.json (skip)" -f $Name) -ForegroundColor DarkGray
    return
  }
  Set-EnvSafe -Name $Name -Value $resolved -Scope $Scope -DryRun:$DryRun
  Write-Host ("- {0}: synced" -f $Name) -ForegroundColor Green
}

if ($Target -eq "IntentAdvice" -or $Target -eq "All") {
  Sync-One -Name "VCO_INTENT_ADVICE_BASE_URL"
  Sync-One -Name "VCO_INTENT_ADVICE_API_KEY"
  Sync-One -Name "VCO_INTENT_ADVICE_MODEL"
}

if ($Target -eq "VectorDiff" -or $Target -eq "All") {
  Sync-One -Name "VCO_VECTOR_DIFF_BASE_URL"
  Sync-One -Name "VCO_VECTOR_DIFF_API_KEY"
  Sync-One -Name "VCO_VECTOR_DIFF_MODEL"
}

Write-Host "Done. Note: a new shell may be required to pick up User-scope variables." -ForegroundColor Cyan
