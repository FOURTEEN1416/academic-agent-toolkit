[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Topic,
  [string]$BaseDir = "D:\table\luo2.20\outputs\agent-runs"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$date = Get-Date -Format "yyyyMMdd"
$dir = Join-Path $BaseDir ("$date-" + $Topic)
New-Item -ItemType Directory -Path $dir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dir 'role-outputs') -Force | Out-Null

"# Input" | Set-Content -LiteralPath (Join-Path $dir 'input.md') -Encoding UTF8
"# Task Board`nUse docs/agent-workflow/vco-dialectic-review/task-board.md as template." | Set-Content -LiteralPath (Join-Path $dir 'task-board.md') -Encoding UTF8
"# Final Summary" | Set-Content -LiteralPath (Join-Path $dir 'final-summary.md') -Encoding UTF8
"# Verification" | Set-Content -LiteralPath (Join-Path $dir 'verification.md') -Encoding UTF8

Write-Host "Created run folder: $dir"
