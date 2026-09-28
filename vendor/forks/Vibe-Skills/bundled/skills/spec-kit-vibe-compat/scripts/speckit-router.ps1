[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsIn
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($null -eq $ArgsIn) { $ArgsIn = @() }

$mapPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\command-map.json'))
if (-not (Test-Path -LiteralPath $mapPath)) {
  throw "command-map.json not found: $mapPath"
}

$map = Get-Content -LiteralPath $mapPath -Raw -Encoding UTF8 | ConvertFrom-Json
$index = @{}
foreach ($item in @($map)) {
  $index[$item.slash_command.ToLowerInvariant()] = $item
  $index[$item.name.ToLowerInvariant()] = $item
}

function Normalize-CommandToken {
  param([string]$Token)
  if ([string]::IsNullOrWhiteSpace($Token)) { return '' }
  $t = $Token.Trim()
  if ($t.StartsWith('/speckit.')) { return $t.ToLowerInvariant() }
  if ($t.StartsWith('speckit.')) { return ('/' + $t.ToLowerInvariant()) }
  if ($t.StartsWith('speckit-')) {
    $s = $t.Substring(8).ToLowerInvariant()
    return '/speckit.' + $s
  }
  return '/speckit.' + $t.ToLowerInvariant()
}

if ($ArgsIn.Count -eq 0 -or $ArgsIn[0] -in @('--help','-h','help')) {
  Write-Host 'Spec-Kit Vibe Router'
  Write-Host 'Usage:'
  Write-Host '  speckit-router.ps1 --list'
  Write-Host '  speckit-router.ps1 --show /speckit.implement'
  Write-Host '  speckit-router.ps1 /speckit.implement [extra text]'
  exit 0
}

if ($ArgsIn[0] -eq '--list') {
  @($map | Sort-Object slash_command | Select-Object slash_command,status,codex_flow) | Format-Table -AutoSize
  exit 0
}

if ($ArgsIn[0] -eq '--show') {
  if ($ArgsIn.Count -lt 2) { throw '--show requires one command token' }
  $cmd = Normalize-CommandToken -Token $ArgsIn[1]
  if (-not $index.ContainsKey($cmd.ToLowerInvariant())) { throw "Unknown command: $($ArgsIn[1])" }
  $index[$cmd.ToLowerInvariant()] | ConvertTo-Json -Depth 8
  exit 0
}

$cmdNorm = Normalize-CommandToken -Token $ArgsIn[0]
if (-not $index.ContainsKey($cmdNorm.ToLowerInvariant())) {
  Write-Host "Unknown command token: $($ArgsIn[0])"
  Write-Host 'Run --list for supported commands.'
  exit 1
}

$spec = $index[$cmdNorm.ToLowerInvariant()]
$extra = if ($ArgsIn.Count -gt 1) { ($ArgsIn[1..($ArgsIn.Count-1)] -join ' ').Trim() } else { '' }
$skills = @($spec.codex_skills) -join ', '

Write-Host ('Spec-kit command: ' + $spec.slash_command)
Write-Host ('Compatibility status: ' + $spec.status)
Write-Host ('Codex flow: ' + $spec.codex_flow)
Write-Host ('Mapped skills: ' + $skills)
Write-Host ('Notes: ' + $spec.notes)
Write-Host ''
Write-Host 'Recommended Codex prompt:'
if ($extra) {
  Write-Host ('/vibe ' + $extra)
} else {
  Write-Host ('/vibe execute the goal of ' + $spec.slash_command + ' and prioritize mapped skills.')
}
