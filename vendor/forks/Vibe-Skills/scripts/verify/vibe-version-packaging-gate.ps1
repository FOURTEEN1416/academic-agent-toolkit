param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = "Stop"

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

function Get-IsDictionaryLike {
    param([object]$Value)

    if ($null -eq $Value) { return $false }
    return ($Value -is [System.Collections.IDictionary]) -or ($Value -is [pscustomobject])
}

function Get-IsListLike {
    param([object]$Value)

    if ($null -eq $Value) { return $false }
    if ($Value -is [string]) { return $false }
    return ($Value -is [System.Collections.IEnumerable])
}

function Remove-IgnoredKeys {
    param(
        [object]$Node,
        [string[]]$IgnoreKeys
    )

    if ($null -eq $Node) { return $null }

    if (Get-IsDictionaryLike -Value $Node) {
        $names = @()
        if ($Node -is [System.Collections.IDictionary]) {
            $names = @($Node.Keys)
        } else {
            $names = @($Node.PSObject.Properties.Name)
        }

        $ordered = [ordered]@{}
        foreach ($name in @($names | Where-Object { $IgnoreKeys -notcontains [string]$_ } | Sort-Object)) {
            $value = if ($Node -is [System.Collections.IDictionary]) { $Node[$name] } else { $Node.$name }
            $ordered[[string]$name] = Remove-IgnoredKeys -Node $value -IgnoreKeys $IgnoreKeys
        }
        return $ordered
    }

    if (Get-IsListLike -Value $Node) {
        $items = @()
        foreach ($item in $Node) {
            $items += Remove-IgnoredKeys -Node $item -IgnoreKeys $IgnoreKeys
        }
        return $items
    }

    return $Node
}

function Get-NormalizedJsonHash {
    param(
        [string]$Path,
        [string[]]$IgnoreKeys
    )

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $obj = $raw | ConvertFrom-Json
    $normalizedObj = Remove-IgnoredKeys -Node $obj -IgnoreKeys $IgnoreKeys
    $normalized = $normalizedObj | ConvertTo-Json -Depth 100 -Compress
    return (Get-FileHash -InputStream ([System.IO.MemoryStream]::new([System.Text.Encoding]::UTF8.GetBytes($normalized))) -Algorithm SHA256).Hash
}

function Get-RelativePathPortable {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath)
    $targetFull = [System.IO.Path]::GetFullPath($TargetPath)
    if (-not $baseFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $baseFull = $baseFull + [System.IO.Path]::DirectorySeparatorChar
    }
    if ($targetFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $targetFull.Substring($baseFull.Length).Replace("\", "/")
    }

    $baseUri = New-Object System.Uri($baseFull)
    $targetUri = New-Object System.Uri($targetFull)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace("\", "/")
}

function Get-FileParity {
    param(
        [string]$MainPath,
        [string]$BundledPath,
        [string[]]$IgnoreJsonKeys
    )

    if (-not (Test-Path -LiteralPath $MainPath) -or -not (Test-Path -LiteralPath $BundledPath)) {
        return $false
    }

    $mainExt = [System.IO.Path]::GetExtension($MainPath).ToLowerInvariant()
    $bundledExt = [System.IO.Path]::GetExtension($BundledPath).ToLowerInvariant()
    if ($mainExt -eq ".json" -and $bundledExt -eq ".json") {
        return (Get-NormalizedJsonHash -Path $MainPath -IgnoreKeys $IgnoreJsonKeys) -eq (Get-NormalizedJsonHash -Path $BundledPath -IgnoreKeys $IgnoreJsonKeys)
    }

    return (Get-FileHash -LiteralPath $MainPath -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $BundledPath -Algorithm SHA256).Hash
}

. (Join-Path $PSScriptRoot "..\common\vibe-governance-helpers.ps1")
$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$governancePath = $context.governancePath
$governance = $context.governance
$canonicalRoot = $context.canonicalRoot
$bundledRoot = $context.bundledRoot
$nestedBundledRoot = $context.nestedBundledRoot
$bundledTarget = $context.bundledTarget
$runtimeConfig = Get-VgoInstalledRuntimeConfig -Governance $governance
$legacySource = if ($governance.PSObject.Properties.Name -contains 'source_of_truth') { $governance.source_of_truth } else { $null }
$legacyTrackedBundledPath = Join-Path $repoRoot 'bundled/skills/vibe'
$generatedCompatibility = if (
    $governance.PSObject.Properties.Name -contains 'packaging' -and
    $null -ne $governance.packaging -and
    $governance.packaging.PSObject.Properties.Name -contains 'generated_compatibility'
) {
    $governance.packaging.generated_compatibility
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
$trackedMirrorRetired = ($null -eq $bundledTarget)
Write-Host "=== VCO Version Packaging Gate ==="
$effectivePackaging = if ($trackedMirrorRetired) {
    Get-VgoEffectiveTargetPackaging -Packaging $context.packaging -TargetId ''
} else {
    Get-VgoEffectiveTargetPackaging -Packaging $context.packaging -TargetId 'bundled'
}
$mirrorFiles = @($effectivePackaging.files)
$mirrorDirs = @($effectivePackaging.directories)
$allowBundledOnly = @($context.packaging.allow_bundled_only)
$ignoreJsonKeys = @($context.packaging.normalized_json_ignore_keys)

$assertions = @()
$results = [ordered]@{
    release_version = [string]$governance.release.version
    release_updated = [string]$governance.release.updated
    mode = if ($trackedMirrorRetired) { 'canonical_only_retired_tracked_mirror' } else { 'legacy_bundled_parity' }
    tracked_mirror_retired = [bool]$trackedMirrorRetired
    generated_compatibility = [ordered]@{
        nested_runtime_root = if ($null -ne $nestedRuntimeRoot -and $nestedRuntimeRoot.PSObject.Properties.Name -contains 'relative_path') { [string]$nestedRuntimeRoot.relative_path } else { $null }
        materialization_mode = if ($null -ne $nestedRuntimeRoot -and $nestedRuntimeRoot.PSObject.Properties.Name -contains 'materialization_mode') { [string]$nestedRuntimeRoot.materialization_mode } else { $null }
        require_nested_bundled_root = [bool]$runtimeConfig.require_nested_bundled_root
    }
    files = @()
    directories = @()
}

$assertions += Assert-True -Condition (Test-Path -LiteralPath $canonicalRoot) -Message "canonical root exists"
if ($trackedMirrorRetired) {
    $assertions += Assert-True -Condition (-not (Test-Path -LiteralPath $legacyTrackedBundledPath)) -Message 'tracked bundled mirror root is absent from repo'
    $assertions += Assert-True -Condition ($null -eq $legacySource -or -not ($legacySource.PSObject.Properties.Name -contains 'bundled_root')) -Message 'legacy source_of_truth.bundled_root is retired'
    $assertions += Assert-True -Condition ($null -eq $legacySource -or -not ($legacySource.PSObject.Properties.Name -contains 'nested_bundled_root')) -Message 'legacy source_of_truth.nested_bundled_root is retired'
    $assertions += Assert-True -Condition ($mirrorFiles.Count -gt 0 -or $mirrorDirs.Count -gt 0) -Message 'runtime payload remains explicitly declared'
    $assertions += Assert-True -Condition ($null -ne $nestedRuntimeRoot) -Message 'generated compatibility nested runtime root is declared'
    if ($null -ne $nestedRuntimeRoot) {
        $assertions += Assert-True -Condition (([string]$nestedRuntimeRoot.relative_path) -eq '') -Message 'generated compatibility keeps no nested runtime path under canonical-only packaging'
        $assertions += Assert-True -Condition (([string]$nestedRuntimeRoot.materialization_mode) -eq 'disabled') -Message 'generated compatibility keeps nested runtime materialization disabled'
    }
    $assertions += Assert-True -Condition (-not [bool]$runtimeConfig.require_nested_bundled_root) -Message 'installed runtime does not require nested bundled root'
} else {
    $assertions += Assert-True -Condition (Test-Path -LiteralPath $bundledRoot) -Message "bundled root exists"

    foreach ($rel in $mirrorFiles) {
        $mainPath = Join-Path $canonicalRoot $rel
        $bundledPath = Join-Path $bundledRoot $rel

        $mainExists = Test-Path -LiteralPath $mainPath
        $bundledExists = Test-Path -LiteralPath $bundledPath
        $parity = $false
        if ($mainExists -and $bundledExists) {
            $parity = Get-FileParity -MainPath $mainPath -BundledPath $bundledPath -IgnoreJsonKeys $ignoreJsonKeys
        }

        $assertions += Assert-True -Condition $mainExists -Message "[file:$rel] canonical exists"
        $assertions += Assert-True -Condition $bundledExists -Message "[file:$rel] bundled exists"
        if ($mainExists -and $bundledExists) {
            $assertions += Assert-True -Condition $parity -Message "[file:$rel] parity"
        }

        $results.files += [pscustomobject]@{
            path = [string]$rel
            canonical_exists = [bool]$mainExists
            bundled_exists = [bool]$bundledExists
            parity = [bool]$parity
        }
    }

    foreach ($dir in $mirrorDirs) {
        $mainDir = Join-Path $canonicalRoot $dir
        $bundledDir = Join-Path $bundledRoot $dir

        $mainExists = Test-Path -LiteralPath $mainDir
        $bundledExists = Test-Path -LiteralPath $bundledDir
        $assertions += Assert-True -Condition $mainExists -Message "[dir:$dir] canonical exists"
        $assertions += Assert-True -Condition $bundledExists -Message "[dir:$dir] bundled exists"

        $onlyMain = @()
        $onlyBundled = @()
        $diffFiles = @()

        if ($mainExists -and $bundledExists) {
            $mainFiles = @(
                Get-ChildItem -LiteralPath $mainDir -Recurse -File | ForEach-Object {
                    Get-RelativePathPortable -BasePath $mainDir -TargetPath $_.FullName
                }
            )
            $bundledFiles = @(
                Get-ChildItem -LiteralPath $bundledDir -Recurse -File | ForEach-Object {
                    Get-RelativePathPortable -BasePath $bundledDir -TargetPath $_.FullName
                }
            )

            $onlyMain = @($mainFiles | Where-Object { $_ -notin $bundledFiles } | Sort-Object)
            $onlyBundledRaw = @($bundledFiles | Where-Object { $_ -notin $mainFiles })
            $onlyBundled = @(
                $onlyBundledRaw | Where-Object {
                    $fullRel = "{0}/{1}" -f $dir, $_
                    $allowBundledOnly -notcontains $fullRel
                } | Sort-Object
            )

            $common = @($mainFiles | Where-Object { $_ -in $bundledFiles } | Sort-Object)
            foreach ($relPath in $common) {
                $mainPath = Join-Path $mainDir $relPath
                $bundledPath = Join-Path $bundledDir $relPath
                $same = Get-FileParity -MainPath $mainPath -BundledPath $bundledPath -IgnoreJsonKeys $ignoreJsonKeys
                if (-not $same) {
                    $diffFiles += $relPath
                }
            }
        }

        $assertions += Assert-True -Condition ($onlyMain.Count -eq 0) -Message "[dir:$dir] no files missing in bundled"
        $assertions += Assert-True -Condition ($onlyBundled.Count -eq 0) -Message "[dir:$dir] no unexpected bundled-only files"
        $assertions += Assert-True -Condition ($diffFiles.Count -eq 0) -Message "[dir:$dir] file parity"

        $results.directories += [pscustomobject]@{
            path = [string]$dir
            only_in_canonical = @($onlyMain)
            only_in_bundled = @($onlyBundled)
            diff_files = @($diffFiles)
        }
    }
}

$total = @($assertions).Count
$passed = @($assertions | Where-Object { $_ }).Count
$failed = $total - $passed
$gatePass = ($failed -eq 0)

Write-Host ""
Write-Host "=== Summary ==="
Write-Host ("Total assertions: {0}" -f $total)
Write-Host ("Passed: {0}" -f $passed)
Write-Host ("Failed: {0}" -f $failed)
Write-Host ("Gate Result: {0}" -f $(if ($gatePass) { "PASS" } else { "FAIL" }))

if ($WriteArtifacts) {
    $outDir = Join-Path $repoRoot "outputs\verify"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonPath = Join-Path $outDir "vibe-version-packaging-gate.json"
    $mdPath = Join-Path $outDir "vibe-version-packaging-gate.md"

    $artifact = [ordered]@{
        generated_at = [DateTime]::UtcNow.ToString("o")
        gate_result = if ($gatePass) { "PASS" } else { "FAIL" }
        assertions = [ordered]@{
            total = $total
            passed = $passed
            failed = $failed
        }
        results = $results
    }

    $artifact | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $md = @(
        "# VCO Version Packaging Gate",
        "",
        ("- Generated: {0}" -f $artifact.generated_at),
        ("- Gate Result: **{0}**" -f $artifact.gate_result),
        ("- Assertions: total={0}, passed={1}, failed={2}" -f $total, $passed, $failed),
        "",
        "## Directory Summary"
    )
    foreach ($d in @($results.directories)) {
        $md += ("- {0}: only_in_canonical={1}, only_in_bundled={2}, diff_files={3}" -f $d.path, @($d.only_in_canonical).Count, @($d.only_in_bundled).Count, @($d.diff_files).Count)
    }
    $md -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8

    Write-Host ""
    Write-Host "Artifacts written:"
    Write-Host ("- {0}" -f $jsonPath)
    Write-Host ("- {0}" -f $mdPath)
}

if (-not $gatePass) { exit 1 }
