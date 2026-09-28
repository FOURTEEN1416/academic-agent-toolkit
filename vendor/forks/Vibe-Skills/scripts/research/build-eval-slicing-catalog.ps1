param(
    [switch]$WriteArtifacts,
    [string]$PolicyPath,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function New-MarkdownReport {
    param([object]$Catalog)
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# Eval Slicing Catalog')
    $lines.Add('')
    $lines.Add(('- Generated: {0}' -f $Catalog.generated_at))
    $lines.Add(('- Source policy: `{0}`' -f $Catalog.policy_path))
    $lines.Add('')
    $lines.Add('## Summary')
    $lines.Add('')
    $lines.Add(('- Slice count: `{0}`' -f $Catalog.summary.slice_count))
    $lines.Add(('- Planes: `{0}`' -f ($Catalog.summary.planes -join ', ')))
    $lines.Add(('- Decision horizons: `{0}`' -f ($Catalog.summary.horizons -join ', ')))
    $lines.Add('')
    $lines.Add('## Slices')
    $lines.Add('')
    $lines.Add('| Slice | Plane | Evidence mode | Horizon | Default surface change |')
    $lines.Add('| --- | --- | --- | --- | --- |')
    foreach ($slice in @($Catalog.slices)) {
        $lines.Add(('| `{0}` | `{1}` | `{2}` | `{3}` | `{4}` |' -f $slice.id, $slice.plane, $slice.evidence_mode, $slice.decision_horizon, $slice.default_surface_change))
    }
    return ($lines -join [Environment]::NewLine)
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not $PolicyPath) { $PolicyPath = Join-Path $repoRoot 'config\eval-slicing-policy.json' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'outputs\governance\eval-slicing' }

$policy = Read-JsonFile -Path $PolicyPath
$slices = @($policy.slices)
$catalog = [pscustomobject]@{
    generated_at = (Get-Date).ToString('s')
    policy_path = $PolicyPath
    summary = [pscustomobject]@{
        slice_count = $slices.Count
        planes = @($slices | Group-Object plane | ForEach-Object { $_.Name })
        horizons = @($slices | Group-Object decision_horizon | ForEach-Object { $_.Name })
    }
    slices = $slices
}

$catalog | ConvertTo-Json -Depth 8

if ($WriteArtifacts) {
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $jsonPath = Join-Path $OutputDirectory 'eval-slicing-catalog.json'
    $mdPath = Join-Path $OutputDirectory 'eval-slicing-catalog.md'
    ($catalog | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    (New-MarkdownReport -Catalog $catalog) | Set-Content -LiteralPath $mdPath -Encoding UTF8
    Write-Host ('Wrote {0}' -f $jsonPath) -ForegroundColor Green
    Write-Host ('Wrote {0}' -f $mdPath) -ForegroundColor Green
}
