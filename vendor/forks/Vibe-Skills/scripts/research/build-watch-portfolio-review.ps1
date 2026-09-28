param(
    [switch]$WriteArtifacts,
    [string]$ConfigPath,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function New-MarkdownReport {
    param([object]$Review)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# Watch Portfolio Review')
    $lines.Add('')
    $lines.Add(('- Generated: {0}' -f $Review.generated_at))
    $lines.Add(('- Source config: `{0}`' -f $Review.config_path))
    $lines.Add('')
    $lines.Add('## Summary')
    $lines.Add('')
    $lines.Add(('- Watch candidates: `{0}`' -f $Review.summary.watch_candidates))
    $lines.Add(('- Review-ready: `{0}`' -f $Review.summary.review_ready_count))
    $lines.Add(('- Pilot: `{0}`' -f $Review.summary.pilot_count))
    $lines.Add(('- Hold: `{0}`' -f $Review.summary.hold_count))
    $lines.Add(('- Default surface changes: `{0}`' -f $Review.summary.default_surface_change_count))
    $lines.Add('')
    $lines.Add('## Decision Table')
    $lines.Add('')
    $lines.Add('| Candidate | Band | Decision | Landing zone | Default surface change |')
    $lines.Add('| --- | --- | --- | --- | --- |')
    foreach ($candidate in @($Review.candidates)) {
        $lines.Add(('| `{0}` | `{1}` | `{2}` | {3} | `{4}` |' -f $candidate.id, $candidate.priority_band, $candidate.decision_label, $candidate.landing_zone, $candidate.default_surface_change))
    }
    $lines.Add('')
    $lines.Add('## Guardrails')
    $lines.Add('')
    foreach ($rule in @($Review.guardrails)) {
        $lines.Add(('- {0}' -f $rule))
    }
    return ($lines -join [Environment]::NewLine)
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $repoRoot 'config\candidate-watch-decisions.json'
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'outputs\governance\watch-portfolio'
}

$config = Read-JsonFile -Path $ConfigPath
$candidates = @($config.candidates)
$reviewReady = @($candidates | Where-Object { $_.decision_label -eq 'review-ready' })
$pilot = @($candidates | Where-Object { $_.decision_label -eq 'pilot' })
$hold = @($candidates | Where-Object { $_.decision_label -eq 'hold' })
$review = [pscustomobject]@{
    generated_at = (Get-Date).ToString('s')
    config_path = $ConfigPath
    summary = [pscustomobject]@{
        watch_candidates = $candidates.Count
        review_ready_count = $reviewReady.Count
        pilot_count = $pilot.Count
        hold_count = $hold.Count
        default_surface_change_count = @($candidates | Where-Object { $_.default_surface_change }).Count
    }
    guardrails = @(
        'All decisions stay reporting-only and board-governed.',
        'No default-surface expansion is approved by this review artifact.',
        'Pilot candidates must preserve rollback-first and project-scoped enablement.'
    )
    candidates = $candidates
}

$review | ConvertTo-Json -Depth 8

if ($WriteArtifacts) {
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $jsonPath = Join-Path $OutputDirectory 'watch-portfolio-review.json'
    $mdPath = Join-Path $OutputDirectory 'watch-portfolio-review.md'
    ($review | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    (New-MarkdownReport -Review $review) | Set-Content -LiteralPath $mdPath -Encoding UTF8
    Write-Host ('Wrote {0}' -f $jsonPath) -ForegroundColor Green
    Write-Host ('Wrote {0}' -f $mdPath) -ForegroundColor Green
}
