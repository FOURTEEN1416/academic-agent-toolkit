param()

$ErrorActionPreference = "Stop"
function Assert-True { param([bool]$Condition,[string]$Message) if ($Condition) { Write-Host "[PASS] $Message"; return $true } Write-Host "[FAIL] $Message" -ForegroundColor Red; return $false }
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$cardsPath = Join-Path $repoRoot "references\prompt-pattern-cards.md"
$checklistPath = Join-Path $repoRoot "references\prompt-risk-checklist.md"
$policyPath = Join-Path $repoRoot "config\prompt-intelligence-policy.json"
$indexPath = Join-Path $repoRoot "references\index.md"
$cards = Get-Content -Raw $cardsPath -Encoding UTF8
$checklist = Get-Content -Raw $checklistPath -Encoding UTF8
$policy = Get-Content -Raw $policyPath -Encoding UTF8 | ConvertFrom-Json
$index = Get-Content -Raw $indexPath -Encoding UTF8
$checks = @()
$checks += Assert-True (Test-Path $cardsPath) "prompt pattern cards exist"
$checks += Assert-True (Test-Path $checklistPath) "prompt risk checklist exists"
$checks += Assert-True (($cards -split "`n").Count -ge 26) "prompt pattern cards have minimum content"
$checks += Assert-True (($checklist -split "`n").Count -ge 40) "prompt risk checklist has minimum content"
$checks += Assert-True ($index.Contains('references/prompt-pattern-cards.md') -or $index.Contains('prompt-pattern-cards.md')) "references index includes prompt pattern cards"
$checks += Assert-True ($index.Contains('references/prompt-risk-checklist.md') -or $index.Contains('prompt-risk-checklist.md')) "references index includes prompt risk checklist"
$checks += Assert-True ($policy.allow_route_override -eq $false) "prompt intelligence cannot override route"
if ($checks -contains $false) { throw 'prompt intelligence assets gate failed' }
Write-Host "[PASS] prompt intelligence assets gate succeeded" -ForegroundColor Green
