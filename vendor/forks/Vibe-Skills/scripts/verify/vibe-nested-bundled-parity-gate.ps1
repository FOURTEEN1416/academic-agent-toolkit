param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        Write-Host "[PASS] $Message"
        return $true
    }

    Write-Host "[FAIL] $Message" -ForegroundColor Red
    return $false
}

function Compare-LatestReleaseRecord {
    param(
        [object]$ReferenceRecord,
        [object]$CandidateRecord
    )

    if ($null -eq $ReferenceRecord -or $null -eq $CandidateRecord) {
        return $false
    }

    $referenceVersion = if ($ReferenceRecord.PSObject.Properties.Name -contains 'version') { [string]$ReferenceRecord.version } else { $null }
    $candidateVersion = if ($CandidateRecord.PSObject.Properties.Name -contains 'version') { [string]$CandidateRecord.version } else { $null }
    $referenceUpdated = if ($ReferenceRecord.PSObject.Properties.Name -contains 'updated') { [string]$ReferenceRecord.updated } else { $null }
    $candidateUpdated = if ($CandidateRecord.PSObject.Properties.Name -contains 'updated') { [string]$CandidateRecord.updated } else { $null }

    return ($referenceVersion -eq $candidateVersion) -and ($referenceUpdated -eq $candidateUpdated)
}

function Write-Artifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact
    )

    $outputDir = Join-Path $RepoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    $jsonPath = Join-Path $outputDir 'vibe-nested-bundled-parity-gate.json'
    $mdPath = Join-Path $outputDir 'vibe-nested-bundled-parity-gate.md'

    $Artifact | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $lines = @(
        '# VCO Nested Bundled Parity Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Bundled Target: `{0}`' -f $Artifact.targets.bundled.path),
        ('- Nested Target: `{0}`' -f $Artifact.targets.nested.path),
        ('- Presence Policy: `{0}`' -f $Artifact.targets.nested.presence_policy),
        ('- Legacy Compatibility: `{0}`' -f $(if ($Artifact.legacy_source_of_truth_compatible) { 'PASS' } else { 'FAIL' })),
        '',
        '## Summary',
        '',
        ('- Files Checked: {0}' -f $Artifact.summary.files_checked),
        ('- Directories Checked: {0}' -f $Artifact.summary.directories_checked),
        ('- Version Markers Checked: {0}' -f $Artifact.summary.version_markers_checked),
        ('- Failures: {0}' -f $Artifact.summary.failures),
        '',
        '## Presence',
        '',
        ('- Nested Exists: `{0}`' -f $Artifact.targets.nested.exists),
        ('- Nested Required: `{0}`' -f $Artifact.targets.nested.required),
        ''
    )

    if ($Artifact.files.Count -gt 0) {
        $lines += '## File Parity'
        $lines += ''
        foreach ($item in $Artifact.files) {
            $lines += ('- `{0}` :: canonical={1}, bundled={2}, nested={3}, nested_vs_canonical={4}, nested_vs_bundled={5}' -f $item.path, $item.canonical_exists, $item.bundled_exists, $item.nested_exists, $item.nested_matches_canonical, $item.nested_matches_bundled)
        }
        $lines += ''
    }

    if ($Artifact.directories.Count -gt 0) {
        $lines += '## Directory Parity'
        $lines += ''
        foreach ($item in $Artifact.directories) {
            $lines += ('- `{0}` :: canonical_only={1}, bundled_only={2}, nested_only={3}, diff_vs_canonical={4}, diff_vs_bundled={5}' -f $item.path, $item.only_in_canonical.Count, $item.only_in_bundled.Count, $item.only_in_nested.Count, $item.diff_vs_canonical.Count, $item.diff_vs_bundled.Count)
        }
        $lines += ''
    }

    if ($Artifact.version_markers.Count -gt 0) {
        $lines += '## Version Markers'
        $lines += ''
        foreach ($item in $Artifact.version_markers) {
            $lines += ('- `{0}` :: canonical={1}, bundled={2}, nested={3}, bundled_parity={4}, nested_parity={5}' -f $item.id, $item.canonical_exists, $item.bundled_exists, $item.nested_exists, $item.bundled_matches_canonical, $item.nested_matches_canonical)
        }
        $lines += ''
    }

    if ($Artifact.legacy_mismatches.Count -gt 0) {
        $lines += '## Legacy Mismatches'
        $lines += ''
        foreach ($item in $Artifact.legacy_mismatches) {
            $lines += ('- `{0}` expected `{1}` but got `{2}`' -f $item.field, $item.expected, $item.actual)
        }
        $lines += ''
    }

    $lines | Set-Content -LiteralPath $mdPath -Encoding UTF8
}

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$packaging = $context.packaging
$ignoreJsonKeys = @($packaging.normalized_json_ignore_keys)
$allowBundledOnly = @($packaging.allow_bundled_only)
$bundledEffectivePackaging = Get-VgoEffectiveTargetPackaging -Packaging $packaging -TargetId 'bundled'
$nestedEffectivePackaging = Get-VgoEffectiveTargetPackaging -Packaging $packaging -TargetId 'nested_bundled'
$mirrorFiles = @($nestedEffectivePackaging.files)
$mirrorDirs = @($nestedEffectivePackaging.directories)
$bundledTarget = $context.bundledTarget
$nestedTarget = $context.nestedTarget
$canonicalRoot = $context.canonicalRoot
$runtimeConfig = Get-VgoInstalledRuntimeConfig -Governance $context.governance
$generatedCompatibility = if (
    $context.governance.PSObject.Properties.Name -contains 'packaging' -and
    $null -ne $context.governance.packaging -and
    $context.governance.packaging.PSObject.Properties.Name -contains 'generated_compatibility'
) {
    $context.governance.packaging.generated_compatibility
} else {
    $null
}
$nestedRuntimeRoot = if (
    $null -ne $generatedCompatibility -and
    $generatedCompatibility.PSObject.Properties.Name -contains 'nested_runtime_root'
) {
    $generatedCompatibility.nested_runtime_root
} else {
    $null
}
$trackedMirrorRetired = ($null -eq $bundledTarget -and $null -eq $nestedTarget)

$results = [ordered]@{
    gate = 'vibe-nested-bundled-parity-gate'
    repo_root = $context.repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = 'FAIL'
    mode = if ($trackedMirrorRetired) { 'canonical_only_retired_tracked_mirror' } else { 'legacy_nested_parity' }
    legacy_source_of_truth_compatible = [bool]$context.legacySourceOfTruthCompatibility.isCompatible
    legacy_mismatches = @($context.legacySourceOfTruthCompatibility.mismatches)
    targets = [ordered]@{
        bundled = [ordered]@{
            id = if ($null -ne $bundledTarget) { $bundledTarget.id } else { 'bundled' }
            path = if ($null -ne $bundledTarget) { $bundledTarget.path } else { 'bundled/skills/vibe' }
            exists = if ($null -ne $bundledTarget) { [bool]$bundledTarget.exists } else { $false }
        }
        nested = [ordered]@{
            id = if ($null -ne $nestedTarget) { $nestedTarget.id } else { 'nested_bundled' }
            path = if ($null -ne $nestedTarget) { $nestedTarget.path } else { 'bundled/skills/vibe/bundled/skills/vibe' }
            exists = if ($null -ne $nestedTarget) { [bool]$nestedTarget.exists } else { $false }
            required = if ($null -ne $nestedTarget) { [bool]$nestedTarget.required } else { $false }
            presence_policy = if ($null -ne $nestedTarget) { [string]$nestedTarget.presence_policy } else { 'retired_tracked_mirror' }
        }
    }
    files = @()
    directories = @()
    version_markers = @()
    summary = [ordered]@{
        files_checked = 0
        directories_checked = 0
        version_markers_checked = 0
        failures = 0
    }
}

$assertions = @()

Write-Host '=== VCO Nested Bundled Parity Gate ==='
Write-Host ("Repo root      : {0}" -f $context.repoRoot)
Write-Host ("Bundled target : {0}" -f $results.targets.bundled.path)
Write-Host ("Nested target  : {0}" -f $results.targets.nested.path)
Write-Host ''

if ($trackedMirrorRetired) {
    $assertions += Assert-True -Condition $results.legacy_source_of_truth_compatible -Message '[topology] mirror_topology stays compatible with retired source_of_truth fields'
    $assertions += Assert-True -Condition ($null -eq $bundledTarget) -Message '[topology] tracked bundled target is not declared'
    $assertions += Assert-True -Condition ($null -eq $nestedTarget) -Message '[topology] tracked nested_bundled target is not declared'
    $assertions += Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $context.repoRoot 'bundled/skills/vibe'))) -Message '[topology] tracked bundled repo path is absent'
    $assertions += Assert-True -Condition ($null -ne $nestedRuntimeRoot) -Message '[compat] generated nested runtime root is declared'
    if ($null -ne $nestedRuntimeRoot) {
        $assertions += Assert-True -Condition (([string]$nestedRuntimeRoot.relative_path) -eq 'bundled/skills/vibe') -Message '[compat] generated nested runtime root keeps legacy path only as compatibility'
        $assertions += Assert-True -Condition (([string]$nestedRuntimeRoot.materialization_mode) -eq 'install_only') -Message '[compat] generated nested runtime root stays install_only'
    }
    $assertions += Assert-True -Condition (-not [bool]$runtimeConfig.require_nested_bundled_root) -Message '[runtime] nested bundled root remains optional'
} else {
    $assertions += Assert-True -Condition $results.legacy_source_of_truth_compatible -Message '[topology] mirror_topology matches legacy source_of_truth fields'
    $assertions += Assert-True -Condition ($null -ne $bundledTarget) -Message '[topology] bundled target declared'
    $assertions += Assert-True -Condition ($null -ne $nestedTarget) -Message '[topology] nested_bundled target declared'

    if ($null -ne $bundledTarget) {
        $assertions += Assert-True -Condition ([bool]$bundledTarget.exists) -Message '[topology] bundled target exists'
    }

    if ($null -eq $nestedTarget) {
        $results.summary.failures = @($assertions | Where-Object { -not $_ }).Count
        if ($WriteArtifacts) {
            Write-Artifacts -RepoRoot $context.repoRoot -Artifact ([pscustomobject]$results)
        }
        exit 1
    }

    if (-not $nestedTarget.exists) {
        if ($nestedTarget.required -or $nestedTarget.presence_policy -eq 'required') {
            $assertions += Assert-True -Condition $false -Message '[nested] target missing but required by topology'
        } else {
            $assertions += Assert-True -Condition $true -Message ('[nested] target absent and allowed by presence policy: {0}' -f $nestedTarget.presence_policy)
        }
    } else {
        foreach ($rel in $mirrorFiles) {
            $canonicalPath = Join-Path $canonicalRoot $rel
            $bundledPath = Join-Path $bundledTarget.fullPath $rel
            $nestedPath = Join-Path $nestedTarget.fullPath $rel
            $canonicalExists = Test-Path -LiteralPath $canonicalPath
            $bundledExists = Test-Path -LiteralPath $bundledPath
            $nestedExists = Test-Path -LiteralPath $nestedPath
            $nestedMatchesCanonical = $false
            $nestedMatchesBundled = $false
            if ($canonicalExists -and $nestedExists) {
                $nestedMatchesCanonical = Test-VgoFileParity -ReferencePath $canonicalPath -CandidatePath $nestedPath -IgnoreJsonKeys $ignoreJsonKeys
            }
            if ($bundledExists -and $nestedExists) {
                $nestedMatchesBundled = Test-VgoFileParity -ReferencePath $bundledPath -CandidatePath $nestedPath -IgnoreJsonKeys $ignoreJsonKeys
            }

            $assertions += Assert-True -Condition $canonicalExists -Message ("[file:{0}] canonical exists" -f $rel)
            $assertions += Assert-True -Condition $bundledExists -Message ("[file:{0}] bundled exists" -f $rel)
            $assertions += Assert-True -Condition $nestedExists -Message ("[file:{0}] nested exists" -f $rel)
            if ($canonicalExists -and $nestedExists) {
                $assertions += Assert-True -Condition $nestedMatchesCanonical -Message ("[file:{0}] nested matches canonical" -f $rel)
            }
            if ($bundledExists -and $nestedExists) {
                $assertions += Assert-True -Condition $nestedMatchesBundled -Message ("[file:{0}] nested matches bundled" -f $rel)
            }

            $results.files += [pscustomobject]@{
                path = $rel
                canonical_exists = $canonicalExists
                bundled_exists = $bundledExists
                nested_exists = $nestedExists
                nested_matches_canonical = $nestedMatchesCanonical
                nested_matches_bundled = $nestedMatchesBundled
            }
        }

        foreach ($dir in $mirrorDirs) {
            $canonicalDir = Join-Path $canonicalRoot $dir
            $bundledDir = Join-Path $bundledTarget.fullPath $dir
            $nestedDir = Join-Path $nestedTarget.fullPath $dir
            $canonicalExists = Test-Path -LiteralPath $canonicalDir
            $bundledExists = Test-Path -LiteralPath $bundledDir
            $nestedExists = Test-Path -LiteralPath $nestedDir

            $canonicalFiles = if ($canonicalExists) { Get-VgoRelativeFileList -RootPath $canonicalDir } else { @() }
            $bundledFiles = if ($bundledExists) { Get-VgoRelativeFileList -RootPath $bundledDir } else { @() }
            $nestedFiles = if ($nestedExists) { Get-VgoRelativeFileList -RootPath $nestedDir } else { @() }

            $onlyInCanonical = @($canonicalFiles | Where-Object { $_ -notin $nestedFiles } | Sort-Object)
            $onlyInBundledRaw = @($bundledFiles | Where-Object { $_ -notin $nestedFiles } | Sort-Object)
            $onlyInBundled = @(
                $onlyInBundledRaw | Where-Object {
                    $fullRel = ('{0}/{1}' -f $dir, $_).Replace('\', '/')
                    $allowBundledOnly -notcontains $fullRel
                } | Sort-Object
            )
            $onlyInNestedRaw = @($nestedFiles | Where-Object { $_ -notin $canonicalFiles } | Sort-Object)
            $onlyInNested = @(
                $onlyInNestedRaw | Where-Object {
                    $fullRel = ('{0}/{1}' -f $dir, $_).Replace('\', '/')
                    $allowBundledOnly -notcontains $fullRel
                } | Sort-Object
            )
            $nestedExtraVsBundled = @($nestedFiles | Where-Object { $_ -notin $bundledFiles } | Sort-Object)

            $diffVsCanonical = @()
            foreach ($relPath in @($canonicalFiles | Where-Object { $_ -in $nestedFiles } | Sort-Object)) {
                $canonicalPath = Join-Path $canonicalDir $relPath
                $nestedPath = Join-Path $nestedDir $relPath
                if (-not (Test-VgoFileParity -ReferencePath $canonicalPath -CandidatePath $nestedPath -IgnoreJsonKeys $ignoreJsonKeys)) {
                    $diffVsCanonical += $relPath
                }
            }

            $diffVsBundled = @()
            foreach ($relPath in @($bundledFiles | Where-Object { $_ -in $nestedFiles } | Sort-Object)) {
                $bundledPath = Join-Path $bundledDir $relPath
                $nestedPath = Join-Path $nestedDir $relPath
                if (-not (Test-VgoFileParity -ReferencePath $bundledPath -CandidatePath $nestedPath -IgnoreJsonKeys $ignoreJsonKeys)) {
                    $diffVsBundled += $relPath
                }
            }

            $assertions += Assert-True -Condition $canonicalExists -Message ("[dir:{0}] canonical exists" -f $dir)
            $assertions += Assert-True -Condition $bundledExists -Message ("[dir:{0}] bundled exists" -f $dir)
            $assertions += Assert-True -Condition $nestedExists -Message ("[dir:{0}] nested exists" -f $dir)
            if ($canonicalExists -and $nestedExists) {
                $assertions += Assert-True -Condition ($onlyInCanonical.Count -eq 0) -Message ("[dir:{0}] no canonical files missing in nested" -f $dir)
                $assertions += Assert-True -Condition ($onlyInNested.Count -eq 0) -Message ("[dir:{0}] no unexpected nested-only files" -f $dir)
                $assertions += Assert-True -Condition ($diffVsCanonical.Count -eq 0) -Message ("[dir:{0}] nested file parity with canonical" -f $dir)
            }
            if ($bundledExists -and $nestedExists) {
                $assertions += Assert-True -Condition ($onlyInBundled.Count -eq 0) -Message ("[dir:{0}] no bundled files missing in nested" -f $dir)
                $assertions += Assert-True -Condition ($nestedExtraVsBundled.Count -eq 0) -Message ("[dir:{0}] no nested files beyond bundled" -f $dir)
                $assertions += Assert-True -Condition ($diffVsBundled.Count -eq 0) -Message ("[dir:{0}] nested file parity with bundled" -f $dir)
            }

            $results.directories += [pscustomobject]@{
                path = $dir
                canonical_exists = $canonicalExists
                bundled_exists = $bundledExists
                nested_exists = $nestedExists
                only_in_canonical = @($onlyInCanonical)
                only_in_bundled = @($onlyInBundled)
                only_in_nested = @($onlyInNested)
                diff_vs_canonical = @($diffVsCanonical)
                diff_vs_bundled = @($diffVsBundled)
            }
        }

        $skillPath = 'SKILL.md'
        $versionMarkers = @(
            [pscustomobject]@{ id = 'skill'; relpath = $skillPath; canonical = (Join-Path $canonicalRoot $skillPath); bundled = (Join-Path $bundledTarget.fullPath $skillPath); nested = (Join-Path $nestedTarget.fullPath $skillPath) },
            [pscustomobject]@{ id = 'changelog'; relpath = [string]$context.governance.version_markers.changelog_path; canonical = (Join-Path $canonicalRoot $context.governance.version_markers.changelog_path); bundled = (Join-Path $bundledTarget.fullPath $context.governance.version_markers.changelog_path); nested = (Join-Path $nestedTarget.fullPath $context.governance.version_markers.changelog_path) }
        )

        foreach ($marker in $versionMarkers) {
            $bundledGoverned = Test-VgoGovernedMirrorRelativePath -RelativePath ([string]$marker.relpath) -Packaging $packaging -TargetId 'bundled'
            $nestedGoverned = Test-VgoGovernedMirrorRelativePath -RelativePath ([string]$marker.relpath) -Packaging $packaging -TargetId 'nested_bundled'
            $canonicalExists = Test-Path -LiteralPath $marker.canonical
            $bundledExists = Test-Path -LiteralPath $marker.bundled
            $nestedExists = Test-Path -LiteralPath $marker.nested
            $bundledMatchesCanonical = $false
            $nestedMatchesCanonical = $false
            if ($canonicalExists -and $bundledExists) {
                $bundledMatchesCanonical = Test-VgoFileParity -ReferencePath $marker.canonical -CandidatePath $marker.bundled -IgnoreJsonKeys $ignoreJsonKeys
            }
            if ($canonicalExists -and $nestedExists) {
                $nestedMatchesCanonical = Test-VgoFileParity -ReferencePath $marker.canonical -CandidatePath $marker.nested -IgnoreJsonKeys $ignoreJsonKeys
            }

            $assertions += Assert-True -Condition $canonicalExists -Message ("[marker:{0}] canonical exists" -f $marker.id)
            if ($bundledGoverned) {
                $assertions += Assert-True -Condition $bundledExists -Message ("[marker:{0}] bundled exists" -f $marker.id)
            }
            if ($nestedGoverned) {
                $assertions += Assert-True -Condition $nestedExists -Message ("[marker:{0}] nested exists" -f $marker.id)
            }
            if ($bundledGoverned -and $canonicalExists -and $bundledExists) {
                $assertions += Assert-True -Condition $bundledMatchesCanonical -Message ("[marker:{0}] bundled matches canonical" -f $marker.id)
            }
            if ($nestedGoverned -and $canonicalExists -and $nestedExists) {
                $assertions += Assert-True -Condition $nestedMatchesCanonical -Message ("[marker:{0}] nested matches canonical" -f $marker.id)
            }

            $results.version_markers += [pscustomobject]@{
                id = $marker.id
                canonical_exists = $canonicalExists
                bundled_exists = $bundledExists
                nested_exists = $nestedExists
                bundled_matches_canonical = $bundledMatchesCanonical
                nested_matches_canonical = $nestedMatchesCanonical
            }
        }

        $ledgerRel = [string]$context.governance.logs.release_ledger_jsonl
        $bundledLedgerGoverned = Test-VgoGovernedMirrorRelativePath -RelativePath $ledgerRel -Packaging $packaging -TargetId 'bundled'
        $nestedLedgerGoverned = Test-VgoGovernedMirrorRelativePath -RelativePath $ledgerRel -Packaging $packaging -TargetId 'nested_bundled'
        $canonicalLedger = Get-VgoLatestJsonlRecord -Path (Join-Path $canonicalRoot $ledgerRel)
        $bundledLedger = Get-VgoLatestJsonlRecord -Path (Join-Path $bundledTarget.fullPath $ledgerRel)
        $nestedLedger = Get-VgoLatestJsonlRecord -Path (Join-Path $nestedTarget.fullPath $ledgerRel)
        $bundledLedgerMatch = Compare-LatestReleaseRecord -ReferenceRecord $canonicalLedger -CandidateRecord $bundledLedger
        $nestedLedgerMatch = Compare-LatestReleaseRecord -ReferenceRecord $canonicalLedger -CandidateRecord $nestedLedger

        $assertions += Assert-True -Condition ($null -ne $canonicalLedger) -Message '[marker:release-ledger] canonical latest record exists'
        if ($bundledLedgerGoverned) {
            $assertions += Assert-True -Condition ($null -ne $bundledLedger) -Message '[marker:release-ledger] bundled latest record exists'
        }
        if ($nestedLedgerGoverned) {
            $assertions += Assert-True -Condition ($null -ne $nestedLedger) -Message '[marker:release-ledger] nested latest record exists'
        }
        if ($bundledLedgerGoverned -and $null -ne $canonicalLedger -and $null -ne $bundledLedger) {
            $assertions += Assert-True -Condition $bundledLedgerMatch -Message '[marker:release-ledger] bundled latest release matches canonical'
        }
        if ($nestedLedgerGoverned -and $null -ne $canonicalLedger -and $null -ne $nestedLedger) {
            $assertions += Assert-True -Condition $nestedLedgerMatch -Message '[marker:release-ledger] nested latest release matches canonical'
        }

        $results.version_markers += [pscustomobject]@{
            id = 'release-ledger-latest'
            canonical_exists = ($null -ne $canonicalLedger)
            bundled_exists = ($null -ne $bundledLedger)
            nested_exists = ($null -ne $nestedLedger)
            bundled_matches_canonical = $bundledLedgerMatch
            nested_matches_canonical = $nestedLedgerMatch
        }
    }
}

$results.summary.files_checked = $results.files.Count
$results.summary.directories_checked = $results.directories.Count
$results.summary.version_markers_checked = $results.version_markers.Count
$results.summary.failures = @($assertions | Where-Object { -not $_ }).Count
$gatePass = ($results.summary.failures -eq 0)
$results.gate_result = if ($gatePass) { 'PASS' } else { 'FAIL' }

if ($WriteArtifacts) {
    Write-Artifacts -RepoRoot $context.repoRoot -Artifact ([pscustomobject]$results)
}

if (-not $gatePass) {
    exit 1
}
