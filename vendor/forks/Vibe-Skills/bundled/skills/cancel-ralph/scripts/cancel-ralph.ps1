[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($null -eq $CliArgs) {
  $CliArgs = @()
}

function Resolve-AbsolutePath {
  param([Parameter(Mandatory = $true)][string]$PathText)

  if ([System.IO.Path]::IsPathRooted($PathText)) {
    return [System.IO.Path]::GetFullPath($PathText)
  }

  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathText))
}

function Show-Help {
  @(
    'cancel-ralph (Codex compatibility mode)',
    '',
    'Usage:',
    '  cancel-ralph.ps1 [--state-file PATH]',
    '',
    'Options:',
    '  --state-file PATH   Override state path (default: .claude/ralph-loop.local.md)',
    '  -h, --help          Show this help'
  ) | ForEach-Object { Write-Host $_ }
}

$stateFile = '.claude/ralph-loop.local.md'
$stateFileFromCli = $false

for ($i = 0; $i -lt $CliArgs.Count; $i++) {
  $arg = $CliArgs[$i]
  switch ($arg.ToLowerInvariant()) {
    '--help' { Show-Help; exit 0 }
    '-h' { Show-Help; exit 0 }
    '--state-file' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--state-file requires a path'
      }

      $i += 1
      $stateFile = $CliArgs[$i]
      $stateFileFromCli = $true
      continue
    }
    default {
      throw "Unknown argument: $arg"
    }
  }
}

$resolvedStatePath = Resolve-AbsolutePath -PathText $stateFile
if (-not $stateFileFromCli) {
  $fallbackPath = Resolve-AbsolutePath -PathText '.codex/ralph-loop.local.md'
  if (-not (Test-Path -LiteralPath $resolvedStatePath) -and (Test-Path -LiteralPath $fallbackPath)) {
    $resolvedStatePath = $fallbackPath
  }
}

if (-not (Test-Path -LiteralPath $resolvedStatePath)) {
  Write-Host 'No active Ralph loop found.'
  exit 0
}

$raw = Get-Content -LiteralPath $resolvedStatePath -Raw
$iteration = if ($raw -match '(?m)^iteration:\s*([0-9]+)\s*$') { $Matches[1] } else { 'unknown' }

Remove-Item -LiteralPath $resolvedStatePath -Force
Write-Host "Cancelled Ralph loop (was at iteration $iteration)"
