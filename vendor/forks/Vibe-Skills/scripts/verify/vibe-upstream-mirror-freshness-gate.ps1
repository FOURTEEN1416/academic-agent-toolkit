param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [System.Collections.Generic.List[object]]$Collection,
        [bool]$Condition,
        [string]$Message,
        [object]$Details = $null
    )

    if ($Condition) {
        Write-Host ('[PASS] ' + $Message) -ForegroundColor Green
    } else {
        Write-Host ('[FAIL] ' + $Message) -ForegroundColor Red
    }

    [void]$Collection.Add([pscustomobject]@{
        pass = [bool]$Condition
        message = $Message
        details = $Details
    })
}

function Get-HeadSha {
    param([string]$RepoDir)

    try {
        $head = git -C $RepoDir rev-parse HEAD 2>$null | Select-Object -First 1
        return [string]$head
    } catch {
        return ''
    }
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact
    )

    $outDir = Join-Path $RepoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null

    $jsonPath = Join-Path $outDir 'vibe-upstream-mirror-freshness-gate.json'
    $mdPath = Join-Path $outDir 'vibe-upstream-mirror-freshness-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = New-Object System.Collections.Generic.List[string]
    $null = $lines.Add('# VCO Upstream Mirror Freshness Gate')
    $null = $lines.Add('')
    $null = $lines.Add('- Gate Result: **' + $Artifact.gate_result + '**')
    $null = $lines.Add('- Assertions: total=' + $Artifact.summary.total_assertions + ', passed=' + $Artifact.summary.passed_assertions + ', failed=' + $Artifact.summary.failed_assertions)
    $null = $lines.Add('')
    $null = $lines.Add('## Root Results')
    $null = $lines.Add('')

    foreach ($root in @($Artifact.root_results)) {
        $null = $lines.Add(('- root={0}; required={1}; exists={2}; expected={3}; present={4}; matched={5}; missing={6}; non_git={7}; drift={8}; full_coverage={9}' -f $root.id, $root.required_for_freshness_gate, $root.exists, $root.expected_entry_count, $root.present_count, $root.matched_count, @($root.missing).Count, @($root.non_git).Count, @($root.drift).Count, $root.full_coverage_and_match))
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$manifestPath = Join-Path $repoRoot 'config\upstream-corpus-manifest.json'

$results = [System.Collections.Generic.List[object]]::new()
Add-Assertion -Collection $results -Condition (Test-Path -LiteralPath $manifestPath) -Message 'manifest exists' -Details $manifestPath

if (@($results | Where-Object { -not $_.pass }).Count -gt 0) {
    $artifact = [pscustomobject]@{
        gate = 'vibe-upstream-mirror-freshness-gate'
        repo_root = $repoRoot
        generated_at = [DateTime]::UtcNow.ToString('o')
        gate_result = 'FAIL'
        summary = [pscustomobject]@{
            total_assertions = @($results).Count
            passed_assertions = @($results | Where-Object { $_.pass }).Count
            failed_assertions = @($results | Where-Object { -not $_.pass }).Count
        }
        manifest_path = $manifestPath
        root_results = @()
        results = @($results)
    }

    if ($WriteArtifacts) {
        Write-GateArtifacts -RepoRoot $repoRoot -Artifact $artifact
    }

    exit 1
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$entryLookup = @{}
foreach ($entry in @($manifest.entries)) {
    $entryLookup[[string]$entry.slug] = $entry
}
$scopeSlugs = @($manifest.freshness_policy.scope_slugs | ForEach-Object { [string]$_ })
$scopeEntries = foreach ($slug in $scopeSlugs) {
    if ($entryLookup.ContainsKey($slug)) {
        $entryLookup[$slug]
    }
}
$entries = @($scopeEntries)
$roots = @($manifest.mirror_roots)
$expectedEntries = $scopeSlugs.Count

Add-Assertion -Collection $results -Condition ($scopeSlugs.Count -eq 15) -Message 'manifest freshness scope contains 15 mirror-managed slugs' -Details $scopeSlugs
Add-Assertion -Collection $results -Condition ($entries.Count -eq $expectedEntries) -Message 'manifest freshness scope resolves to expected entries' -Details ([ordered]@{ actual = $entries.Count; expected = $expectedEntries })
Add-Assertion -Collection $results -Condition ($roots.Count -ge 1) -Message 'manifest declares at least one mirror root' -Details $roots.Count

$requiredRoots = @($roots | Where-Object { [bool]$_.required_for_freshness_gate })
Add-Assertion -Collection $results -Condition ($requiredRoots.Count -ge 1) -Message 'manifest declares at least one required freshness root' -Details $requiredRoots.Count

$resolvedRoots = @(
    foreach ($root in $roots) {
        $resolvedPath = Resolve-VgoPathSpec -PathSpec ([string]$root.path) -RepoRoot $repoRoot
        [pscustomobject]@{
            root = $root
            id = [string]$root.id
            resolved_path = $resolvedPath
            required = [bool]$root.required_for_freshness_gate
            exists = (Test-Path -LiteralPath $resolvedPath)
        }
    }
)
$materializedRequiredRoots = @($resolvedRoots | Where-Object { $_.required -and $_.exists })
$materializedRequiredRootCount = @($materializedRequiredRoots).Count

$rootResults = New-Object System.Collections.Generic.List[object]
$requiredRootPassCount = 0

foreach ($resolvedRoot in $resolvedRoots) {
    $root = $resolvedRoot.root
    $rootId = $resolvedRoot.id
    $resolvedPath = $resolvedRoot.resolved_path
    $rootExists = [bool]$resolvedRoot.exists
    $required = [bool]$resolvedRoot.required

    $missing = New-Object System.Collections.Generic.List[string]
    $nonGit = New-Object System.Collections.Generic.List[string]
    $drift = New-Object System.Collections.Generic.List[object]
    $presentCount = 0
    $matchedCount = 0

    if ($rootExists) {
        foreach ($entry in $entries) {
            $slug = [string]$entry.slug
            $expectedHead = [string]$entry.observed_head_sha
            $repoDir = Join-Path $resolvedPath $slug

            if (-not (Test-Path -LiteralPath $repoDir)) {
                [void]$missing.Add($slug)
                continue
            }

            $presentCount++

            if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
                [void]$nonGit.Add($slug)
                continue
            }

            $actualHead = Get-HeadSha -RepoDir $repoDir
            if ([string]::IsNullOrWhiteSpace($actualHead)) {
                [void]$nonGit.Add($slug)
                continue
            }

            if ($actualHead -eq $expectedHead) {
                $matchedCount++
            } else {
                [void]$drift.Add([pscustomobject]@{
                    slug = $slug
                    expected = $expectedHead
                    actual = $actualHead
                })
            }
        }
    }

    $expectedCountForRoot = if ($root.PSObject.Properties.Name -contains 'expected_entry_count') { [int]$root.expected_entry_count } else { $expectedEntries }
    Add-Assertion -Collection $results -Condition ($expectedCountForRoot -eq $expectedEntries) -Message ('root expected_entry_count matches freshness scope: ' + $rootId) -Details ([ordered]@{ expected_entry_count = $expectedCountForRoot; scope_count = $expectedEntries })
    $fullCoverage = $rootExists -and ($presentCount -eq $entries.Count) -and ($missing.Count -eq 0) -and ($nonGit.Count -eq 0) -and ($drift.Count -eq 0) -and ($matchedCount -eq $entries.Count)

    if ($required -and $fullCoverage) {
        $requiredRootPassCount++
    }

    $rootResult = [pscustomobject]@{
        id = $rootId
        role = [string]$root.role
        path = $resolvedPath
        required_for_freshness_gate = $required
        exists = [bool]$rootExists
        expected_entry_count = $expectedCountForRoot
        present_count = [int]$presentCount
        matched_count = [int]$matchedCount
        missing = [string[]]$missing.ToArray()
        non_git = [string[]]$nonGit.ToArray()
        drift = [object[]]$drift.ToArray()
        full_coverage_and_match = [bool]$fullCoverage
    }

    [void]$rootResults.Add($rootResult)

    if ($required) {
        if ($materializedRequiredRootCount -eq 0) {
            Add-Assertion -Collection $results -Condition $true -Message ('required root not materialized locally; recorded for advisory freshness only: ' + $rootId) -Details $resolvedPath
        } else {
            Add-Assertion -Collection $results -Condition $rootExists -Message ('required root exists: ' + $rootId) -Details $resolvedPath
            Add-Assertion -Collection $results -Condition $fullCoverage -Message ('required root has full coverage and matching HEADs: ' + $rootId) -Details $rootResult
        }
    } else {
        Add-Assertion -Collection $results -Condition $true -Message ('non-required root recorded for information: ' + $rootId) -Details $rootResult
    }
}

if ($materializedRequiredRootCount -eq 0) {
    Add-Assertion -Collection $results -Condition $true -Message 'no required freshness root is materialized locally; mirror freshness is advisory in this environment' -Details ([ordered]@{ required_root_count = $requiredRoots.Count; materialized_required_root_count = $materializedRequiredRootCount })
} else {
    Add-Assertion -Collection $results -Condition ($requiredRootPassCount -ge 1) -Message 'at least one required freshness root passes full coverage and HEAD alignment' -Details $requiredRootPassCount
}

$totalAssertions = @($results).Count
$passedAssertions = @($results | Where-Object { $_.pass }).Count
$failedAssertions = @($results | Where-Object { -not $_.pass }).Count
$gateResult = if ($failedAssertions -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-upstream-mirror-freshness-gate'
    repo_root = $repoRoot
    generated_at = [DateTime]::UtcNow.ToString('o')
    gate_result = $gateResult
    summary = [pscustomobject]@{
        total_assertions = $totalAssertions
        passed_assertions = $passedAssertions
        failed_assertions = $failedAssertions
        manifest_entry_count = $entries.Count
        required_root_count = $requiredRoots.Count
        required_root_pass_count = $requiredRootPassCount
    }
    manifest_path = $manifestPath
    root_results = [object[]]$rootResults.ToArray()
    results = @($results)
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -Artifact $artifact
}

if ($failedAssertions -gt 0) {
    exit 1
}
