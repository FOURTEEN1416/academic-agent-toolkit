[CmdletBinding()]
param(
  [string]$SkillsDir = '',
  [Alias('?')]
  [switch]$Help
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Show-WrapperUsage {
  Write-Output 'Usage: update.ps1 [-SkillsDir <path>] [-Help|-?]'
  Write-Output 'Run this from a newer extracted public release copy to update the installed Vibe package under <SkillsDir>\vibe when the receipt is clean.'
}

function Get-PreferredPythonInvocation {
  foreach ($candidate in @(
    [pscustomobject]@{ name = 'py'; prefix_arguments = @('-3') },
    [pscustomobject]@{ name = 'python3'; prefix_arguments = @() },
    [pscustomobject]@{ name = 'python'; prefix_arguments = @() }
  )) {
    $command = Get-Command ([string]$candidate.name) -ErrorAction SilentlyContinue
    if ($command) {
      return [pscustomobject]@{ host_path = $command.Source; prefix_arguments = @($candidate.prefix_arguments) }
    }
  }
  throw 'Python 3.10+ is required to launch vgo-cli.'
}

if ($Help) {
  Show-WrapperUsage
  exit 0
}

$pythonInvocation = Get-PreferredPythonInvocation
$pythonPathEntries = @((Join-Path $RepoRoot 'apps\vgo-cli\src'))
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $pythonPathEntries += $env:PYTHONPATH
}
$env:PYTHONPATH = ($pythonPathEntries -join [System.IO.Path]::PathSeparator)

$argsList = @($pythonInvocation.prefix_arguments)
$argsList += @('-m', 'vgo_cli.main', 'update', '--repo-root', $RepoRoot)
if (-not [string]::IsNullOrWhiteSpace($SkillsDir)) {
  $argsList += @('--skills-dir', $SkillsDir)
}

& $pythonInvocation.host_path @argsList
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
