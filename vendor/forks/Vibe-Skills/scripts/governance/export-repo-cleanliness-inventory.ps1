param(
    [switch]$WriteArtifacts,
    [string]$OutputRoot = "outputs/governance",
    [string]$BaseName = "repo-cleanliness-inventory"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Get-GitStatusEntries {
    param([Parameter(Mandatory)] [string]$RepoRoot)
    $lines = & git -C $RepoRoot -c core.quotePath=false status --porcelain=v1 --untracked-files=all
    if ($LASTEXITCODE -ne 0) { throw "git status failed while exporting repo cleanliness inventory." }
    $entries = @()
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $status = $line.Substring(0, 2).Trim()
        $pathText = $line.Substring(3).Trim()
        if ($pathText.Contains(" -> ")) { $pathText = ($pathText -split " -> ")[-1] }
        $entries += [pscustomobject]@{
            status = $status
            path = $pathText.Replace("\", "/")
        }
    }
    return @($entries)
}

function Test-PathMatchesPolicy {
    param([string]$RelativePath, [string[]]$Patterns)
    $normalized = ($RelativePath.Replace("\", "/")).TrimStart("./")
    foreach ($pattern in $Patterns) {
        if ([string]::IsNullOrWhiteSpace($pattern)) { continue }
        $candidate = ($pattern.Replace("\", "/")).TrimStart("./")
        if ($candidate.EndsWith("/")) {
            if ($normalized.StartsWith($candidate, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        } elseif ($normalized.Equals($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-PlaneId {
    param([string]$RelativePath)
    $normalized = $RelativePath.Replace("\", "/")
    if ($normalized.StartsWith("bundled/skills/vibe/bundled/skills/vibe/", [System.StringComparison]::OrdinalIgnoreCase)) { return "mirror:nested" }
    if ($normalized.StartsWith("bundled/skills/vibe/", [System.StringComparison]::OrdinalIgnoreCase)) { return "mirror:bundled" }
    return "canonical"
}

function Get-RootPrefix {
    param([string]$RelativePath)
    $normalized = $RelativePath.Replace("\", "/")
    if ([string]::IsNullOrWhiteSpace($normalized)) { return "<root>" }
    $first = ($normalized -split "/")[0]
    if ([string]::IsNullOrWhiteSpace($first)) { return "<root>" }
    return $first
}

function Add-BucketEntry {
    param([hashtable]$Bucket, [string]$Key, [psobject]$Entry)
    $Bucket[$Key] += [pscustomobject]@{ status = $Entry.status; path = $Entry.path; plane = $Entry.plane }
}

function Convert-GroupSummary {
    param([object[]]$Items, [scriptblock]$Selector, [int]$Top = 20)
    return @(
        $Items | Group-Object $Selector | Sort-Object Count -Descending | Select-Object -First $Top | ForEach-Object {
            [pscustomobject]@{ key = [string]$_.Name; count = [int]$_.Count }
        }
    )
}

function Write-InventoryArtifacts {
    param([string]$RepoRoot, [string]$OutputRootPath, [string]$BaseNameValue, [psobject]$Artifact)
    $dir = Join-Path $RepoRoot $OutputRootPath
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir ($BaseNameValue + ".json")
    $mdPath = Join-Path $dir ($BaseNameValue + ".md")
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)
    $lines = @(
        '# Repo Cleanliness Inventory',
        '',
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Generated At: `{0}`' -f $Artifact.generated_at),
        ('- Total Dirty Paths: {0}' -f $Artifact.summary.total_dirty_paths),
        ('- Modified Tracked: {0}' -f $Artifact.summary.modified_tracked),
        ('- Untracked: {0}' -f $Artifact.summary.untracked),
        '',
        '## Plane Split',
        ''
    )
    foreach ($plane in $Artifact.plane_split) {
        $lines += ('- `{0}`: total={1}, modified={2}, untracked={3}' -f $plane.plane, $plane.total, $plane.modified, $plane.untracked)
    }
    $lines += @('', '## Bucket Summary', '')
    foreach ($bucket in $Artifact.bucket_summary) {
        $lines += ('- `{0}`: {1}' -f $bucket.bucket, $bucket.count)
    }
    $lines += @('', '## Top Dirty Prefixes', '')
    foreach ($item in $Artifact.top_dirty_prefixes) {
        $lines += ('- `{0}`: {1}' -f $item.key, $item.count)
    }
    $lines += @('', '## Canonical Untracked Prefixes', '')
    foreach ($item in $Artifact.top_canonical_untracked_prefixes) {
        $lines += ('- `{0}`: {1}' -f $item.key, $item.count)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$policyPath = Join-Path $context.repoRoot "config\repo-cleanliness-policy.json"
if (-not (Test-Path -LiteralPath $policyPath)) { throw "repo-cleanliness policy not found: $policyPath" }
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json
$entries = @(Get-GitStatusEntries -RepoRoot $context.repoRoot)
$classified = @{ local_noise = @(); runtime_generated = @(); managed_workset = @(); high_risk_managed = @(); other_dirty = @() }
$annotated = @()
foreach ($entry in $entries) {
    $plane = Get-PlaneId -RelativePath $entry.path
    $row = [pscustomobject]@{ status = $entry.status; path = $entry.path; plane = $plane }
    $annotated += $row
    if (Test-PathMatchesPolicy -RelativePath $entry.path -Patterns @($policy.local_noise_paths)) { Add-BucketEntry -Bucket $classified -Key "local_noise" -Entry $row; continue }
    if (Test-PathMatchesPolicy -RelativePath $entry.path -Patterns @($policy.runtime_generated_roots)) { Add-BucketEntry -Bucket $classified -Key "runtime_generated" -Entry $row; continue }
    if (Test-PathMatchesPolicy -RelativePath $entry.path -Patterns @($policy.high_risk_managed_roots)) { Add-BucketEntry -Bucket $classified -Key "high_risk_managed" -Entry $row; continue }
    if (Test-PathMatchesPolicy -RelativePath $entry.path -Patterns @($policy.managed_workset_roots)) { Add-BucketEntry -Bucket $classified -Key "managed_workset" -Entry $row; continue }
    $isRootPath = -not $entry.path.Contains("/")
    if ($isRootPath -and $policy.PSObject.Properties.Name -contains "managed_root_files" -and (Test-PathMatchesPolicy -RelativePath $entry.path -Patterns @($policy.managed_root_files))) {
        Add-BucketEntry -Bucket $classified -Key "managed_workset" -Entry $row; continue
    }
    Add-BucketEntry -Bucket $classified -Key "other_dirty" -Entry $row
}

$planeSplit = @(
    $annotated | Group-Object plane | Sort-Object Name | ForEach-Object {
        $modified = @($_.Group | Where-Object { $_.status -ne "??" }).Count
        $untracked = @($_.Group | Where-Object { $_.status -eq "??" }).Count
        [pscustomobject]@{ plane = [string]$_.Name; total = [int]$_.Count; modified = [int]$modified; untracked = [int]$untracked }
    }
)

$artifact = [ordered]@{
    operator = "export-repo-cleanliness-inventory"
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString("s")
    policy_path = $policyPath
    summary = [ordered]@{
        total_dirty_paths = $entries.Count
        modified_tracked = @($annotated | Where-Object { $_.status -ne "??" }).Count
        untracked = @($annotated | Where-Object { $_.status -eq "??" }).Count
    }
    plane_split = $planeSplit
    bucket_summary = @(
        [pscustomobject]@{ bucket = "local_noise"; count = $classified.local_noise.Count },
        [pscustomobject]@{ bucket = "runtime_generated"; count = $classified.runtime_generated.Count },
        [pscustomobject]@{ bucket = "managed_workset"; count = $classified.managed_workset.Count },
        [pscustomobject]@{ bucket = "high_risk_managed"; count = $classified.high_risk_managed.Count },
        [pscustomobject]@{ bucket = "other_dirty"; count = $classified.other_dirty.Count }
    )
    top_dirty_prefixes = Convert-GroupSummary -Items $annotated -Selector { Get-RootPrefix -RelativePath $_.path } -Top 20
    top_canonical_untracked_prefixes = Convert-GroupSummary -Items @($annotated | Where-Object { $_.plane -eq "canonical" -and $_.status -eq "??" }) -Selector { Get-RootPrefix -RelativePath $_.path } -Top 20
    entries = $annotated
}

Write-Host "=== Export Repo Cleanliness Inventory ===" -ForegroundColor Cyan
Write-Host ("Repo root : {0}" -f $context.repoRoot)
Write-Host ("Dirty     : {0}" -f $artifact.summary.total_dirty_paths)
Write-Host ("Modified  : {0}" -f $artifact.summary.modified_tracked)
Write-Host ("Untracked : {0}" -f $artifact.summary.untracked)

if ($WriteArtifacts) {
    Write-InventoryArtifacts -RepoRoot $context.repoRoot -OutputRootPath $OutputRoot -BaseNameValue $BaseName -Artifact ([pscustomobject]$artifact)
    Write-Host ("Artifacts written under {0}/{1}.*" -f $OutputRoot, $BaseName) -ForegroundColor Yellow
}

$artifact | ConvertTo-Json -Depth 100 | Write-Output
