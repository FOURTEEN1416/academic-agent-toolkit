param(
    [switch]$WriteArtifacts,
    [switch]$Strict
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

function Test-PolicyMatch {
    param(
        [Parameter(Mandatory)] [string]$RelativePath,
        [Parameter(Mandatory)] [string[]]$Patterns
    )

    $normalized = $RelativePath.Replace('\\', '/')
    foreach ($pattern in $Patterns) {
        $candidate = $pattern.Replace('\\', '/')
        if ($candidate.EndsWith('/')) {
            if ($normalized.StartsWith($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        } elseif ($normalized.Equals($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

function Get-RelativeFileHash {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [string]$RelativePath
    )

    $resolvedPath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        return $null
    }

    return (Get-FileHash -LiteralPath $resolvedPath -Algorithm SHA256).Hash
}

function Write-Artifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact
    )

    $outDir = Join-Path $RepoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonPath = Join-Path $outDir 'vibe-output-artifact-boundary-gate.json'
    $mdPath = Join-Path $outDir 'vibe-output-artifact-boundary-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Output Artifact Boundary Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Migration stage: `{0}`' -f $Artifact.policy_migration_stage),
        ('- Tracked outputs: {0}' -f $Artifact.summary.tracked_outputs_count),
        ('- Allowlisted tracked outputs: {0}' -f $Artifact.summary.allowlisted_tracked_outputs),
        ('- Unallowlisted tracked outputs: {0}' -f $Artifact.summary.unallowlisted_tracked_outputs),
        ('- Disallowed-root tracked outputs: {0}' -f $Artifact.summary.disallowed_root_tracked_outputs),
        ('- Expected count: {0}' -f $Artifact.summary.expected_tracked_output_count),
        ('- Fixture roots: {0}' -f $Artifact.summary.fixture_roots_count),
        ('- Mirrored sources: {0}' -f $Artifact.summary.stage2_mirrored_sources),
        ('- Missing mirror mappings: {0}' -f $Artifact.summary.missing_mirror_mappings),
        ('- Missing fixture files: {0}' -f $Artifact.summary.missing_fixture_files),
        ('- Hash mismatches: {0}' -f $Artifact.summary.fixture_hash_mismatches),
        '',
        '## Allowlisted Sets',
        ''
    )

    foreach ($set in $Artifact.allowlisted_sets) {
        $lines += ('- `{0}`: {1} files, class=`{2}`, migrate-> `{3}`' -f $set.id, $set.count, $set.classification, $set.migration_target)
    }
    $lines += ''

    if ($Artifact.fixture_roots.Count -gt 0) {
        $lines += '## Fixture Roots'
        $lines += ''
        foreach ($root in $Artifact.fixture_roots) {
            $lines += ('- `{0}`' -f $root)
        }
        $lines += ''
    }

    if ($Artifact.unallowlisted_tracked_outputs.Count -gt 0) {
        $lines += '## Unallowlisted Tracked Outputs'
        $lines += ''
        foreach ($item in $Artifact.unallowlisted_tracked_outputs) {
            $lines += ('- `{0}`' -f $item)
        }
        $lines += ''
    }

    if ($Artifact.disallowed_root_tracked_outputs.Count -gt 0) {
        $lines += '## Disallowed-Root Tracked Outputs'
        $lines += ''
        foreach ($item in $Artifact.disallowed_root_tracked_outputs) {
            $lines += ('- `{0}`' -f $item)
        }
        $lines += ''
    }

    if ($Artifact.missing_mirror_mappings.Count -gt 0) {
        $lines += '## Missing Mirror Mappings'
        $lines += ''
        foreach ($item in $Artifact.missing_mirror_mappings) {
            $lines += ('- `{0}`' -f $item)
        }
        $lines += ''
    }

    if ($Artifact.missing_fixture_files.Count -gt 0) {
        $lines += '## Missing Fixture Files'
        $lines += ''
        foreach ($item in $Artifact.missing_fixture_files) {
            $lines += ('- `{0}`' -f $item)
        }
        $lines += ''
    }

    if ($Artifact.fixture_hash_mismatches.Count -gt 0) {
        $lines += '## Fixture Hash Mismatches'
        $lines += ''
        foreach ($item in $Artifact.fixture_hash_mismatches) {
            $lines += ('- `{0}` -> `{1}`' -f $item.source, $item.destination)
        }
        $lines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`r`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$policyPath = Join-Path $context.repoRoot 'config\outputs-boundary-policy.json'
if (-not (Test-Path -LiteralPath $policyPath)) {
    throw "outputs-boundary policy not found: $policyPath"
}

$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
$tracked = @(& git -C $context.repoRoot ls-files outputs)
if ($LASTEXITCODE -ne 0) {
    throw 'git ls-files outputs failed while computing output artifact boundary.'
}
$tracked = @($tracked | ForEach-Object { $_.Replace('\\', '/') })

$allowlistedSets = @()
$allowlistedPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
foreach ($set in @($policy.allowlisted_sets)) {
    $matched = @($tracked | Where-Object { Test-PolicyMatch -RelativePath $_ -Patterns @($set.patterns) })
    foreach ($path in $matched) {
        [void]$allowlistedPaths.Add($path)
    }
    $allowlistedSets += [pscustomobject]@{
        id = $set.id
        classification = $set.classification
        migration_target = $set.migration_target
        count = $matched.Count
        paths = @($matched)
    }
}

$unallowlisted = @($tracked | Where-Object { -not $allowlistedPaths.Contains($_) })
$disallowed = @($tracked | Where-Object { Test-PolicyMatch -RelativePath $_ -Patterns @($policy.disallowed_generated_output_roots) })
$allowlistedTracked = @($tracked | Where-Object { $allowlistedPaths.Contains($_) })

$fixtureRoots = @($policy.fixture_roots | ForEach-Object { $_.Replace('\\', '/') })
$invalidFixtureRoots = @()
foreach ($root in $fixtureRoots) {
    $resolvedRoot = Join-Path $context.repoRoot $root
    if ((-not $root.StartsWith('references/fixtures/', [System.StringComparison]::OrdinalIgnoreCase)) -or (-not (Test-Path -LiteralPath $resolvedRoot -PathType Container))) {
        $invalidFixtureRoots += $root
    }
}

$migrationTargetsOutsideRoots = @()
foreach ($set in @($policy.allowlisted_sets)) {
    $migrationTarget = $set.migration_target.Replace('\\', '/')
    if (-not (Test-PolicyMatch -RelativePath $migrationTarget -Patterns $fixtureRoots)) {
        $migrationTargetsOutsideRoots += ('{0} -> {1}' -f $set.id, $migrationTarget)
    }
}

$migrationMapPath = Join-Path $context.repoRoot 'references\fixtures\migration-map.json'
$migrationMapExists = Test-Path -LiteralPath $migrationMapPath -PathType Leaf
$migrationMap = $null
$migrationMappings = @()
if ($migrationMapExists) {
    $migrationMap = Get-Content -LiteralPath $migrationMapPath -Raw | ConvertFrom-Json
    $migrationMappings = @($migrationMap.mappings)
}

$mappingsBySource = @{}
foreach ($mapping in $migrationMappings) {
    $source = $mapping.source.Replace('\\', '/')
    if (-not $mappingsBySource.ContainsKey($source)) {
        $mappingsBySource[$source] = @()
    }
    $mappingsBySource[$source] += $mapping
}

$missingMirrorMappings = @()
$invalidMirrorDestinations = @()
$missingFixtureFiles = @()
$fixtureHashMismatches = @()
$mirroredPairs = @()
foreach ($source in $allowlistedTracked) {
    $sourceMappings = if ($mappingsBySource.ContainsKey($source)) { @($mappingsBySource[$source]) } else { @() }
    $stage2Mappings = @($sourceMappings | Where-Object { $_.stage2_mirrored -eq $true })

    if ($stage2Mappings.Count -eq 0) {
        $missingMirrorMappings += $source
        continue
    }

    $mapping = $stage2Mappings[0]
    $destination = $mapping.destination.Replace('\\', '/')
    if (-not (Test-PolicyMatch -RelativePath $destination -Patterns $fixtureRoots)) {
        $invalidMirrorDestinations += ('{0} -> {1}' -f $source, $destination)
        continue
    }

    $fixturePath = Join-Path $context.repoRoot $destination
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        $missingFixtureFiles += $destination
        continue
    }

    $sourceHash = Get-RelativeFileHash -RepoRoot $context.repoRoot -RelativePath $source
    $destinationHash = Get-RelativeFileHash -RepoRoot $context.repoRoot -RelativePath $destination
    $matches = ($sourceHash -and $destinationHash -and ($sourceHash -eq $destinationHash))
    if (-not $matches) {
        $fixtureHashMismatches += [pscustomobject]@{
            source = $source
            destination = $destination
            source_hash = $sourceHash
            destination_hash = $destinationHash
        }
    }

    $mirroredPairs += [pscustomobject]@{
        source = $source
        destination = $destination
        source_hash = $sourceHash
        destination_hash = $destinationHash
        matches = [bool]$matches
    }
}

$results = [ordered]@{
    gate = 'vibe-output-artifact-boundary-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    strict = [bool]$Strict
    gate_result = 'FAIL'
    policy_migration_stage = [string]$policy.migration_stage
    tracked_outputs = @($tracked)
    allowlisted_sets = @($allowlistedSets)
    fixture_roots = @($fixtureRoots)
    migration_targets_outside_fixture_roots = @($migrationTargetsOutsideRoots)
    missing_mirror_mappings = @($missingMirrorMappings)
    invalid_mirror_destinations = @($invalidMirrorDestinations)
    missing_fixture_files = @($missingFixtureFiles)
    fixture_hash_mismatches = @($fixtureHashMismatches)
    mirrored_pairs = @($mirroredPairs)
    unallowlisted_tracked_outputs = @($unallowlisted)
    disallowed_root_tracked_outputs = @($disallowed)
    summary = [ordered]@{
        tracked_outputs_count = $tracked.Count
        allowlisted_tracked_outputs = $allowlistedPaths.Count
        unallowlisted_tracked_outputs = $unallowlisted.Count
        disallowed_root_tracked_outputs = $disallowed.Count
        expected_tracked_output_count = [int]$policy.expected_tracked_output_count
        fixture_roots_count = $fixtureRoots.Count
        invalid_fixture_roots = $invalidFixtureRoots.Count
        stage2_mirrored_sources = $mirroredPairs.Count
        missing_mirror_mappings = $missingMirrorMappings.Count
        invalid_mirror_destinations = $invalidMirrorDestinations.Count
        missing_fixture_files = $missingFixtureFiles.Count
        fixture_hash_mismatches = $fixtureHashMismatches.Count
        failures = 0
    }
}

Write-Host '=== VCO Output Artifact Boundary Gate ===' -ForegroundColor Cyan
Write-Host ("Repo root       : {0}" -f $context.repoRoot)
Write-Host ("Tracked outputs : {0}" -f $tracked.Count)
Write-Host ("Migration stage : {0}" -f $policy.migration_stage)
Write-Host ''

$assertions = @()
$assertions += Assert-True -Condition ($unallowlisted.Count -eq 0) -Message '[outputs] all tracked outputs are explicitly allowlisted'
$assertions += Assert-True -Condition ($disallowed.Count -eq 0) -Message '[outputs] no tracked outputs exist under disallowed generated-output roots'
if ($policy.enforcement.check_expected_count) {
    $assertions += Assert-True -Condition ($tracked.Count -eq [int]$policy.expected_tracked_output_count) -Message '[outputs] tracked output count matches policy registry'
}
$assertions += Assert-True -Condition ([string]$policy.migration_stage -eq 'stage2_mirrored') -Message '[fixtures] policy migration_stage is stage2_mirrored'
$assertions += Assert-True -Condition ($fixtureRoots.Count -gt 0) -Message '[fixtures] policy declares fixture_roots for mirrored baselines'
$assertions += Assert-True -Condition ($invalidFixtureRoots.Count -eq 0) -Message '[fixtures] declared fixture_roots exist and stay under references/fixtures/'
if ($policy.enforcement.document_migration_target) {
    $assertions += Assert-True -Condition ($migrationTargetsOutsideRoots.Count -eq 0) -Message '[fixtures] allowlisted migration_target paths stay within declared fixture_roots'
}
$assertions += Assert-True -Condition $migrationMapExists -Message '[fixtures] migration-map.json exists for stage2 mirrored enforcement'
if ($migrationMapExists) {
    $assertions += Assert-True -Condition ([string]$migrationMap.migration_stage -eq [string]$policy.migration_stage) -Message '[fixtures] migration map stage matches policy migration_stage'
}
$assertions += Assert-True -Condition ($missingMirrorMappings.Count -eq 0) -Message '[fixtures] every allowlisted tracked output has a stage2 mirror mapping'
$assertions += Assert-True -Condition ($invalidMirrorDestinations.Count -eq 0) -Message '[fixtures] mirrored destinations stay within declared fixture_roots'
$assertions += Assert-True -Condition ($missingFixtureFiles.Count -eq 0) -Message '[fixtures] mirrored fixture files exist under references/fixtures/**'
$assertions += Assert-True -Condition ($fixtureHashMismatches.Count -eq 0) -Message '[fixtures] mirrored fixture files match their tracked output sources'
if ($Strict -and $policy.enforcement.strict_requires_zero_tracked_outputs) {
    $assertions += Assert-True -Condition ($tracked.Count -eq 0) -Message '[outputs:strict] no tracked outputs remain in repository'
}

$results.summary.failures = @($assertions | Where-Object { -not $_ }).Count
$results.gate_result = if ($results.summary.failures -eq 0) { 'PASS' } else { 'FAIL' }

if ($WriteArtifacts) {
    Write-Artifacts -RepoRoot $context.repoRoot -Artifact ([pscustomobject]$results)
}

if ($results.summary.failures -gt 0) {
    exit 1
}
exit 0
