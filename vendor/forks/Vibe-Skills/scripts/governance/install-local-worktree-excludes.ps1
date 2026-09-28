param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$policyPath = Join-Path $context.repoRoot 'config\repo-cleanliness-policy.json'
if (-not (Test-Path -LiteralPath $policyPath)) {
    throw "repo-cleanliness policy not found: $policyPath"
}

$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
$patterns = @($policy.local_worktree_excludes)
$excludePath = Join-Path $context.repoRoot '.git\info\exclude'
$startMarker = '# >>> vco-local-cleanliness >>>'
$endMarker = '# <<< vco-local-cleanliness <<<'

$current = if (Test-Path -LiteralPath $excludePath) {
    Get-Content -LiteralPath $excludePath -Raw
} else {
    ''
}

$blockLines = @($startMarker) + $patterns + @($endMarker)
$block = ($blockLines -join "`r`n")

if ($current -match [regex]::Escape($startMarker)) {
    $updated = [regex]::Replace(
        $current,
        [regex]::Escape($startMarker) + '.*?' + [regex]::Escape($endMarker),
        [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block },
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
} else {
    $normalized = $current
    if (-not [string]::IsNullOrEmpty($normalized) -and -not $normalized.EndsWith("`n")) {
        $normalized += "`r`n"
    }
    if (-not [string]::IsNullOrEmpty($normalized)) {
        $normalized += "`r`n"
    }
    $updated = $normalized + $block + "`r`n"
}

Write-Host '=== Install Local Worktree Excludes ===' -ForegroundColor Cyan
Write-Host ("Repo root   : {0}" -f $context.repoRoot)
Write-Host ("Exclude path: {0}" -f $excludePath)
foreach ($pattern in $patterns) {
    Write-Host ("[PATTERN] {0}" -f $pattern)
}

if ($DryRun) {
    Write-Host ''
    Write-Host '[DRY-RUN] Computed block:' -ForegroundColor Yellow
    Write-Host $block
    exit 0
}

Write-VgoUtf8NoBomText -Path $excludePath -Content $updated
Write-Host 'Local worktree exclude block installed.' -ForegroundColor Green
