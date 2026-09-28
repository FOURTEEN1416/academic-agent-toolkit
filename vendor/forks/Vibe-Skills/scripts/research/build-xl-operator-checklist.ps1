param(
    [switch]$WriteArtifacts,
    [string]$PriorityPath,
    [string]$CheckpointPath,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function New-MarkdownReport {
    param([object]$Checklist)
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# XL Operator Checklist')
    $lines.Add('')
    $lines.Add(('- Generated: {0}' -f $Checklist.generated_at))
    $lines.Add('')
    $lines.Add('## Intake Bands')
    $lines.Add('')
    foreach ($band in @($Checklist.intake_bands)) {
        $lines.Add(('- `{0}` → action=`{1}`, label=`{2}`' -f $band.id, $band.intake_action, $band.decision_label))
    }
    $lines.Add('')
    $lines.Add('## XL Checkpoints')
    $lines.Add('')
    foreach ($checkpoint in @($Checklist.checkpoints)) {
        $lines.Add(('- `{0}` (order `{1}`) — required=`{2}`' -f $checkpoint.id, $checkpoint.stage_order, $checkpoint.required))
    }
    return ($lines -join [Environment]::NewLine)
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not $PriorityPath) { $PriorityPath = Join-Path $repoRoot 'config\skill-intake-priority.json' }
if (-not $CheckpointPath) { $CheckpointPath = Join-Path $repoRoot 'config\xl-operator-checkpoints.json' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'outputs\governance\xl-operator' }

$priority = Read-JsonFile -Path $PriorityPath
$checkpoint = Read-JsonFile -Path $CheckpointPath
$checklist = [pscustomobject]@{
    generated_at = (Get-Date).ToString('s')
    intake_bands = @($priority.bands)
    checkpoints = @($checkpoint.checkpoints)
}

$checklist | ConvertTo-Json -Depth 8

if ($WriteArtifacts) {
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $jsonPath = Join-Path $OutputDirectory 'xl-operator-checklist.json'
    $mdPath = Join-Path $OutputDirectory 'xl-operator-checklist.md'
    ($checklist | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    (New-MarkdownReport -Checklist $checklist) | Set-Content -LiteralPath $mdPath -Encoding UTF8
    Write-Host ('Wrote {0}' -f $jsonPath) -ForegroundColor Green
    Write-Host ('Wrote {0}' -f $mdPath) -ForegroundColor Green
}
