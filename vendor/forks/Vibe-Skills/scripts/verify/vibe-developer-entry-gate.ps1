param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        Write-Host "[PASS] $Message" -ForegroundColor Green
        return $true
    }

    Write-Host "[FAIL] $Message" -ForegroundColor Red
    return $false
}

function Get-DeveloperEntryContract {
    param(
        [Parameter(Mandatory)] [string]$Path
    )

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $match = [regex]::Match(
        $raw,
        '(?s)<!--\s*developer-entry-contract:start\s*-->.*?```json\s*(.*?)\s*```.*?<!--\s*developer-entry-contract:end\s*-->'
    )

    if (-not $match.Success) {
        throw "Unable to locate machine-readable developer-entry contract block in: $Path"
    }

    return ($match.Groups[1].Value | ConvertFrom-Json)
}

function Get-InternalMarkdownLinks {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [string]$MarkdownPath
    )

    if (-not (Test-Path -LiteralPath $MarkdownPath -PathType Leaf)) {
        return @()
    }

    $content = Get-Content -LiteralPath $MarkdownPath -Raw -Encoding UTF8
    $linkTargets = @(
        [regex]::Matches($content, '\[[^\]]+\]\(([^)]+)\)') | ForEach-Object {
            [string]$_.Groups[1].Value
        }
    )
    $linkTargets += @(
        [regex]::Matches($content, 'href=["'']([^"'']+)["'']', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase) | ForEach-Object {
            [string]$_.Groups[1].Value
        }
    )
    $resolved = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $baseDir = Split-Path -Parent $MarkdownPath

    foreach ($rawTarget in $linkTargets) {
        if ([string]::IsNullOrWhiteSpace($rawTarget)) {
            continue
        }

        $candidate = $rawTarget.Trim()
        if ($candidate.StartsWith('#')) {
            continue
        }
        if ($candidate -match '^[a-zA-Z][a-zA-Z0-9+.-]*:') {
            continue
        }

        $candidate = $candidate.Split('#')[0]
        $candidate = $candidate.Split('?')[0]
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $fullPath = ConvertTo-VgoFullPath -BasePath $baseDir -RelativePath $candidate
        $relative = Get-VgoRelativePathPortable -BasePath $RepoRoot -TargetPath $fullPath
        [void]$resolved.Add($relative)
    }

    return @($resolved | Sort-Object)
}

function Test-LinkPresent {
    param(
        [string[]]$ResolvedLinks,
        [Parameter(Mandatory)] [string]$ExpectedRelativePath
    )

    $normalized = $ExpectedRelativePath.Replace('\', '/')
    return ($ResolvedLinks -contains $normalized)
}

function Test-MarkerGroup {
    param(
        [string]$Content,
        [object[]]$Alternatives
    )

    $matched = @()
    foreach ($item in $Alternatives) {
        $candidate = [string]$item
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if ($Content.IndexOf($candidate, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $matched += $candidate
        }
    }

    return [pscustomobject]@{
        passed = ($matched.Count -gt 0)
        matched = @($matched)
    }
}

function Write-Artifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [psobject]$Artifact,
        [string]$DestinationRoot
    )

    $outputRoot = if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
        Join-Path $RepoRoot 'outputs\verify'
    } else {
        $DestinationRoot
    }

    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

    $jsonPath = Join-Path $outputRoot 'vibe-developer-entry-gate.json'
    $mdPath = Join-Path $outputRoot 'vibe-developer-entry-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Developer Entry Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Contract Version: `{0}`' -f $Artifact.contract_version),
        ('- Contract Path: `{0}`' -f $Artifact.contract_path),
        ('- Failure Count: `{0}`' -f $Artifact.summary.failures),
        ('- Missing Required Files: `{0}`' -f $Artifact.summary.missing_required_files),
        ('- Missing Required Links: `{0}`' -f $Artifact.summary.missing_required_links),
        ('- Missing Marker Groups: `{0}`' -f $Artifact.summary.missing_marker_groups),
        '',
        '## Key Assertions',
        '',
        ('- `contract_exists`: `{0}`' -f $Artifact.assertions.contract_exists),
        ('- `root_readme_exists`: `{0}`' -f $Artifact.assertions.root_readme_exists),
        ('- `root_link_to_contributing`: `{0}`' -f $Artifact.assertions.root_link_to_contributing),
        ('- `contributing_exists`: `{0}`' -f $Artifact.assertions.contributing_exists),
        ('- `contributing_links_governance`: `{0}`' -f $Artifact.assertions.contributing_links_governance),
        ('- `contributing_links_zone_table`: `{0}`' -f $Artifact.assertions.contributing_links_zone_table),
        ('- `contributing_links_proof_matrix`: `{0}`' -f $Artifact.assertions.contributing_links_proof_matrix),
        ('- `contributing_links_live_contract`: `{0}`' -f $Artifact.assertions.contributing_links_live_contract),
        ''
    )

    if ($Artifact.required_files.Count -gt 0) {
        $lines += '## Required Files'
        $lines += ''
        foreach ($item in $Artifact.required_files) {
            $lines += ('- `{0}`: exists=`{1}`' -f $item.path, $item.exists)
        }
        $lines += ''
    }

    if ($Artifact.required_links.Count -gt 0) {
        $lines += '## Required Links From CONTRIBUTING'
        $lines += ''
        foreach ($item in $Artifact.required_links) {
            $lines += ('- `{0}`: present=`{1}`' -f $item.path, $item.present)
        }
        $lines += ''
    }

    if ($Artifact.marker_groups.Count -gt 0) {
        $lines += '## Required Marker Groups'
        $lines += ''
        foreach ($group in $Artifact.marker_groups) {
            $lines += ('- `{0}`: passed=`{1}` matched=`{2}`' -f $group.label, $group.passed, (($group.matched -join ', ')))
        }
        $lines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`r`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$contractPath = Join-Path $context.repoRoot 'references\developer-entry-contract.md'

$contractExists = Test-Path -LiteralPath $contractPath -PathType Leaf
$assertions = @()
$requiredFiles = @()
$requiredLinks = @()
$markerGroups = @()

$results = [ordered]@{
    gate = 'vibe-developer-entry-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    contract_path = 'references/developer-entry-contract.md'
    contract_version = $null
    gate_result = 'FAIL'
    assertions = [ordered]@{
        contract_exists = $false
        root_readme_exists = $false
        root_link_to_contributing = $false
        contributing_exists = $false
        contributing_links_governance = $false
        contributing_links_zone_table = $false
        contributing_links_proof_matrix = $false
        contributing_links_live_contract = $false
    }
    required_files = @()
    required_links = @()
    marker_groups = @()
    summary = [ordered]@{
        failures = 0
        missing_required_files = 0
        missing_required_links = 0
        missing_marker_groups = 0
    }
}

Write-Host '=== VCO Developer Entry Gate ===' -ForegroundColor Cyan
Write-Host ("Repo root      : {0}" -f $context.repoRoot)
Write-Host ("Contract path  : {0}" -f $results.contract_path)
Write-Host ''

$assertions += Assert-True -Condition $contractExists -Message '[contract] references/developer-entry-contract.md exists'
$results.assertions.contract_exists = [bool]$contractExists

if ($contractExists) {
    $contract = Get-DeveloperEntryContract -Path $contractPath
    $results.contract_version = $contract.contract_version

    $rootReadmeRel = [string]$contract.root_entry.path
    $contributingRel = [string]$contract.developer_entry.path
    $requiredFileRelPaths = @($contract.developer_entry.required_files | ForEach-Object { [string]$_ })
    $requiredLinkRelPaths = @($contract.developer_entry.required_links | ForEach-Object { [string]$_ })
    $requiredMarkerGroups = @($contract.developer_entry.required_marker_groups)

    $rootReadmePath = Join-Path $context.repoRoot $rootReadmeRel
    $contributingPath = Join-Path $context.repoRoot $contributingRel

    $rootReadmeExists = Test-Path -LiteralPath $rootReadmePath -PathType Leaf
    $results.assertions.root_readme_exists = [bool]$rootReadmeExists
    $assertions += Assert-True -Condition $rootReadmeExists -Message '[entry] root README exists'

    $rootLinks = Get-InternalMarkdownLinks -RepoRoot $context.repoRoot -MarkdownPath $rootReadmePath
    $rootHasContributingLink = Test-LinkPresent -ResolvedLinks $rootLinks -ExpectedRelativePath $contributingRel
    $results.assertions.root_link_to_contributing = [bool]$rootHasContributingLink
    $assertions += Assert-True -Condition $rootHasContributingLink -Message '[entry] root README links directly to CONTRIBUTING.md'

    $contributingExists = Test-Path -LiteralPath $contributingPath -PathType Leaf
    $results.assertions.contributing_exists = [bool]$contributingExists
    $assertions += Assert-True -Condition $contributingExists -Message '[entry] CONTRIBUTING.md exists'

    $contributingLinks = Get-InternalMarkdownLinks -RepoRoot $context.repoRoot -MarkdownPath $contributingPath
    $contributingContent = if ($contributingExists) {
        Get-Content -LiteralPath $contributingPath -Raw -Encoding UTF8
    } else {
        ''
    }

    foreach ($path in $requiredFileRelPaths) {
        $exists = Test-Path -LiteralPath (Join-Path $context.repoRoot $path) -PathType Leaf
        $requiredFiles += [pscustomobject]@{
            path = $path
            exists = [bool]$exists
        }
        $assertions += Assert-True -Condition $exists -Message ("[files] required developer-entry file exists: {0}" -f $path)
    }

    foreach ($path in $requiredLinkRelPaths) {
        $present = Test-LinkPresent -ResolvedLinks $contributingLinks -ExpectedRelativePath $path
        $requiredLinks += [pscustomobject]@{
            path = $path
            present = [bool]$present
        }
        $assertions += Assert-True -Condition $present -Message ("[links] CONTRIBUTING.md links to {0}" -f $path)
    }

    foreach ($group in $requiredMarkerGroups) {
        $alternatives = @($group | ForEach-Object { [string]$_ })
        $markerResult = Test-MarkerGroup -Content $contributingContent -Alternatives $alternatives
        $markerGroups += [pscustomobject]@{
            label = ($alternatives -join ' | ')
            passed = [bool]$markerResult.passed
            matched = @($markerResult.matched)
        }
        $assertions += Assert-True -Condition ([bool]$markerResult.passed) -Message ("[content] CONTRIBUTING.md contains one of: {0}" -f ($alternatives -join ' | '))
    }

    $results.assertions.contributing_links_governance = [bool]((@($requiredLinks | Where-Object { $_.path -eq 'docs/developer-change-governance.md' -and $_.present }).Count) -gt 0)
    $results.assertions.contributing_links_zone_table = [bool]((@($requiredLinks | Where-Object { $_.path -eq 'references/contributor-zone-decision-table.md' -and $_.present }).Count) -gt 0)
    $results.assertions.contributing_links_proof_matrix = [bool]((@($requiredLinks | Where-Object { $_.path -eq 'references/change-proof-matrix.md' -and $_.present }).Count) -gt 0)
    $results.assertions.contributing_links_live_contract = [bool]((@($requiredLinks | Where-Object { $_.path -eq 'config/live-document-contract.json' -and $_.present }).Count) -gt 0)
}

$results.required_files = @($requiredFiles)
$results.required_links = @($requiredLinks)
$results.marker_groups = @($markerGroups)
$results.summary.missing_required_files = @($requiredFiles | Where-Object { -not $_.exists }).Count
$results.summary.missing_required_links = @($requiredLinks | Where-Object { -not $_.present }).Count
$results.summary.missing_marker_groups = @($markerGroups | Where-Object { -not $_.passed }).Count
$results.summary.failures = @($assertions | Where-Object { -not $_ }).Count
$results.gate_result = if ($results.summary.failures -eq 0) { 'PASS' } else { 'FAIL' }

if ($WriteArtifacts) {
    Write-Artifacts -RepoRoot $context.repoRoot -Artifact ([pscustomobject]$results) -DestinationRoot $OutputDirectory
}

if ($results.summary.failures -gt 0) {
    exit 1
}

exit 0
