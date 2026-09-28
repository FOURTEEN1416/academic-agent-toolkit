param(
    [string]$FixturePath,
    [switch]$WriteMarkdown,
    [switch]$PassThru,
    [string]$OutputDirectory,
    [string]$RepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '..\common\ProcessLedger.ps1')

function Resolve-VgoOutputDirectory {
    param(
        [string]$PreferredPath,
        [string]$DefaultPath
    )

    if ([string]::IsNullOrWhiteSpace($PreferredPath)) {
        return $DefaultPath
    }

    if ([System.IO.Path]::IsPathRooted($PreferredPath)) {
        return [System.IO.Path]::GetFullPath($PreferredPath)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Get-VgoProcessHealthContext -RepoRoot $RepoRoot).repoRoot $PreferredPath))
}

$resolvedRepoRoot = if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    Resolve-VgoRepoRoot -StartPath $PSScriptRoot
} else {
    [System.IO.Path]::GetFullPath($RepoRoot)
}

$context = Initialize-VgoProcessHealthRuntime -RepoRoot $resolvedRepoRoot
$auditResult = Get-VgoNodeProcessAuditRows -RepoRoot $context.repoRoot -FixturePath $FixturePath
$targetDir = Resolve-VgoOutputDirectory -PreferredPath $OutputDirectory -DefaultPath $context.auditsDir
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$baseName = if ($auditResult.source -eq 'fixture') {
    "node-process-audit-$($auditResult.case_id)"
} else {
    "node-process-audit-$timestamp"
}

$jsonPath = Join-Path $targetDir ($baseName + '.json')
$payload = [ordered]@{
    generated_at = Get-VgoUtcTimestamp
    source = $auditResult.source
    fixture_path = $auditResult.fixture_path
    case_id = $auditResult.case_id
    summary = $auditResult.summary
    rows = $auditResult.rows
}

Write-VgoUtf8NoBomText -Path $jsonPath -Content ($payload | ConvertTo-Json -Depth 30)

$markdownPath = $null
$shouldWriteMarkdown = $WriteMarkdown -or [bool]$context.healthPolicy.audit.write_markdown_summary
if ($shouldWriteMarkdown) {
    $markdownPath = Join-Path $targetDir ($baseName + '.md')
    $lines = @(
        '# Node Process Audit',
        '',
        ('- Generated: `{0}`' -f $payload.generated_at),
        ('- Source: `{0}`' -f $payload.source),
        ('- Case: `{0}`' -f $payload.case_id),
        ('- Total processes: `{0}`' -f $payload.summary.total_processes),
        ('- Cleanup candidates: `{0}`' -f $payload.summary.cleanup_candidate_count),
        ('- External processes: `{0}`' -f $payload.summary.external_count),
        ('- Unknown processes: `{0}`' -f $payload.summary.unknown_count),
        ('- Total working set MB: `{0}`' -f $payload.summary.total_working_set_mb),
        '',
        '## Classification Counts',
        ''
    )

    foreach ($prop in @($payload.summary.classifications.PSObject.Properties | Sort-Object Name)) {
        $lines += ('- `{0}`: `{1}`' -f $prop.Name, $prop.Value)
    }

    $lines += ''
    $lines += '## Rows'
    $lines += ''

    foreach ($row in @($payload.rows)) {
        $lines += ('- PID `{0}`: `{1}` / ownership `{2}` / cleanup_candidate=`{3}`' -f $row.pid, $row.classification, $row.ownership, $row.cleanup_candidate)
        if ($row.command_line) {
            $lines += ('  command: `{0}`' -f $row.command_line)
        }
        if ($row.reasons) {
            $lines += ('  reasons: `{0}`' -f (([string[]]$row.reasons) -join '; '))
        }
    }

    Write-VgoUtf8NoBomText -Path $markdownPath -Content ($lines -join [Environment]::NewLine)
}

$result = [pscustomobject]@{
    artifact_path = $jsonPath
    markdown_path = $markdownPath
    payload = $payload
}

if ($PassThru) {
    return $result
}

$result | ConvertTo-Json -Depth 20
