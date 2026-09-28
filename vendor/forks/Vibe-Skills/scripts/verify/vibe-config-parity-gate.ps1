param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory,
    [string[]]$IgnoreKeys = @("updated", "generated_at")
)

$ErrorActionPreference = "Stop"

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

function Normalize-JsonNode {
    param(
        [object]$Node,
        [string[]]$KeysToIgnore
    )

    if (Get-IsDictionaryLike -Value $Node) {
        $names = @()
        if ($Node -is [System.Collections.IDictionary]) {
            $names = @($Node.Keys)
        } else {
            $names = @($Node.PSObject.Properties.Name)
        }

        $filtered = @($names | Where-Object { $KeysToIgnore -notcontains [string]$_ } | Sort-Object)
        $ordered = [ordered]@{}
        foreach ($name in $filtered) {
            $value = if ($Node -is [System.Collections.IDictionary]) { $Node[$name] } else { $Node.$name }
            $ordered[[string]$name] = Normalize-JsonNode -Node $value -KeysToIgnore $KeysToIgnore
        }
        return $ordered
    }

    if (Get-IsListLike -Value $Node) {
        $arr = @()
        foreach ($item in $Node) {
            $arr += Normalize-JsonNode -Node $item -KeysToIgnore $KeysToIgnore
        }
        return $arr
    }

    return $Node
}

function Get-CanonicalJson {
    param([object]$Node)
    return ($Node | ConvertTo-Json -Depth 100 -Compress)
}

function Get-StringHash {
    param([Parameter(Mandatory)] [string]$Text)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha.ComputeHash($bytes)
    } finally {
        $sha.Dispose()
    }
    return ([BitConverter]::ToString($hashBytes)).Replace("-", "").ToLowerInvariant()
}

function Get-NodeTypeName {
    param([object]$Value)

    if ($null -eq $Value) { return "null" }
    if (Get-IsDictionaryLike -Value $Value) { return "object" }
    if (Get-IsListLike -Value $Value) { return "array" }
    return "scalar"
}

function Compare-NormalizedNode {
    param(
        [object]$Left,
        [object]$Right,
        [string]$Path,
        [ref]$DiffPaths
    )

    $leftType = Get-NodeTypeName -Value $Left
    $rightType = Get-NodeTypeName -Value $Right

    if ($leftType -ne $rightType) {
        $DiffPaths.Value += "$Path (type: $leftType != $rightType)"
        return
    }

    if ($leftType -eq "object") {
        $leftKeys = @($Left.Keys)
        $rightKeys = @($Right.Keys)
        $allKeys = @($leftKeys + $rightKeys | Sort-Object -Unique)
        foreach ($key in $allKeys) {
            $leftHas = $leftKeys -contains $key
            $rightHas = $rightKeys -contains $key
            $childPath = "$Path/$key"
            if (-not $leftHas) {
                $DiffPaths.Value += "$childPath (missing in main)"
                continue
            }
            if (-not $rightHas) {
                $DiffPaths.Value += "$childPath (missing in bundled)"
                continue
            }
            Compare-NormalizedNode -Left $Left[$key] -Right $Right[$key] -Path $childPath -DiffPaths $DiffPaths
        }
        return
    }

    if ($leftType -eq "array") {
        $leftCount = @($Left).Count
        $rightCount = @($Right).Count
        if ($leftCount -ne $rightCount) {
            $DiffPaths.Value += "$Path (length: $leftCount != $rightCount)"
        }

        $max = [Math]::Max($leftCount, $rightCount)
        for ($i = 0; $i -lt $max; $i++) {
            $childPath = "$Path[$i]"
            if ($i -ge $leftCount) {
                $DiffPaths.Value += "$childPath (missing in main)"
                continue
            }
            if ($i -ge $rightCount) {
                $DiffPaths.Value += "$childPath (missing in bundled)"
                continue
            }
            Compare-NormalizedNode -Left $Left[$i] -Right $Right[$i] -Path $childPath -DiffPaths $DiffPaths
        }
        return
    }

    $leftScalar = if ($null -eq $Left) { "null" } else { [string]$Left }
    $rightScalar = if ($null -eq $Right) { "null" } else { [string]$Right }
    if ($leftScalar -ne $rightScalar) {
        $DiffPaths.Value += "$Path ($leftScalar != $rightScalar)"
    }
}

function Load-JsonFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "File not found: $Path"
    }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-VgoLegacyBundledCompatRoot {
    param(
        [Parameter(Mandatory)] [psobject]$Governance
    )

    if (
        $Governance.PSObject.Properties.Name -contains 'packaging' -and
        $null -ne $Governance.packaging -and
        $Governance.packaging.PSObject.Properties.Name -contains 'generated_compatibility' -and
        $null -ne $Governance.packaging.generated_compatibility -and
        $Governance.packaging.generated_compatibility.PSObject.Properties.Name -contains 'nested_runtime_root' -and
        $null -ne $Governance.packaging.generated_compatibility.nested_runtime_root -and
        $Governance.packaging.generated_compatibility.nested_runtime_root.PSObject.Properties.Name -contains 'relative_path' -and
        -not [string]::IsNullOrWhiteSpace([string]$Governance.packaging.generated_compatibility.nested_runtime_root.relative_path)
    ) {
        return ([string]$Governance.packaging.generated_compatibility.nested_runtime_root.relative_path).Replace('\', '/').TrimEnd('/')
    }

    return 'bundled/skills/vibe'
}

function Get-VgoConfigParityPairs {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [psobject]$Governance,
        [bool]$TrackedMirrorRetired,
        [AllowEmptyString()] [string]$BundledRoot = ''
    )

    $pairs = New-Object System.Collections.Generic.List[object]

    if (-not $TrackedMirrorRetired -and -not [string]::IsNullOrWhiteSpace($BundledRoot)) {
        $bundledConfigRoot = Join-Path $BundledRoot 'config'
        if (Test-Path -LiteralPath $bundledConfigRoot) {
            $bundledFiles = @(Get-ChildItem -LiteralPath $bundledConfigRoot -Recurse -File -Filter *.json | Sort-Object FullName)
            foreach ($file in $bundledFiles) {
                $relativeTail = [System.IO.Path]::GetRelativePath($bundledConfigRoot, $file.FullName).Replace('\', '/')
                $mainRel = "config/$relativeTail"
                $bundledRel = [System.IO.Path]::GetRelativePath($RepoRoot, $file.FullName).Replace('\', '/')
                $pairs.Add([pscustomobject]@{
                    id = $mainRel
                    main = $mainRel
                    bundled = $bundledRel
                }) | Out-Null
            }
            return @($pairs.ToArray())
        }
    }

    $runtimeConfigManifestPath = Join-Path $RepoRoot 'config\runtime-config-manifest.json'
    $runtimeConfigManifest = Load-JsonFile -Path $runtimeConfigManifestPath
    $legacyBundledCompatRoot = Get-VgoLegacyBundledCompatRoot -Governance $Governance
    $configFiles = @(
        @($runtimeConfigManifest.files) |
        Where-Object {
            $file = [string]$_
            $file.StartsWith('config/', [System.StringComparison]::OrdinalIgnoreCase) -and
            ([System.IO.Path]::GetExtension($file) -eq '.json')
        } |
        Sort-Object -Unique
    )

    foreach ($mainRel in $configFiles) {
        $normalizedMainRel = ([string]$mainRel).Replace('\', '/')
        $bundledRel = "$legacyBundledCompatRoot/$normalizedMainRel"
        $pairs.Add([pscustomobject]@{
            id = $normalizedMainRel
            main = $normalizedMainRel
            bundled = $bundledRel
        }) | Out-Null
    }

    return @($pairs.ToArray())
}

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

. (Join-Path $PSScriptRoot "..\common\vibe-governance-helpers.ps1")
$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$governancePath = $context.governancePath
$governance = $context.governance
$canonicalRoot = $context.canonicalRoot
$bundledRoot = $context.bundledRoot
$nestedBundledRoot = $context.nestedBundledRoot
$bundledTarget = $context.bundledTarget
$trackedMirrorRetired = ($null -eq $bundledTarget)
$pairs = @(Get-VgoConfigParityPairs -RepoRoot $repoRoot -Governance $governance -TrackedMirrorRetired:$trackedMirrorRetired -BundledRoot $bundledRoot)

$results = @()
$assertions = @()

Write-Host "=== VCO Config Parity Gate ==="
Write-Host ("Ignore keys: {0}" -f ($IgnoreKeys -join ", "))
Write-Host ("Mode: {0}" -f $(if ($trackedMirrorRetired) { 'canonical_only_retired_tracked_mirror' } else { 'legacy_bundled_parity' }))
Write-Host ""

$assertions += Assert-True -Condition ($pairs.Count -gt 0) -Message 'config parity target set is not empty'

foreach ($pair in $pairs) {
    $mainPath = Join-Path $repoRoot $pair.main
    $bundledPath = Join-Path $repoRoot $pair.bundled
    $existsMain = Test-Path -LiteralPath $mainPath
    $existsBundled = Test-Path -LiteralPath $bundledPath

    $assertions += Assert-True -Condition $existsMain -Message "[$($pair.id)] main config exists"
    if ($trackedMirrorRetired) {
        $assertions += Assert-True -Condition (-not $existsBundled) -Message "[$($pair.id)] retired bundled config copy is absent"
        $results += [pscustomobject]@{
            id = $pair.id
            main_path = $mainPath
            bundled_path = $bundledPath
            main_exists = $existsMain
            bundled_exists = $existsBundled
            main_hash = $null
            bundled_hash = $null
            hash_match = (-not $existsBundled)
            diff_paths_count = if ($existsBundled) { 1 } else { 0 }
            diff_paths = if ($existsBundled) { @("retired_bundled_copy_present") } else { @() }
            parse_error = $null
        }
        continue
    }

    $assertions += Assert-True -Condition $existsBundled -Message "[$($pair.id)] bundled config exists"

    if (-not ($existsMain -and $existsBundled)) {
        $results += [pscustomobject]@{
            id = $pair.id
            main_path = $mainPath
            bundled_path = $bundledPath
            main_exists = $existsMain
            bundled_exists = $existsBundled
            hash_match = $false
            diff_paths_count = $null
            diff_paths = @("missing_file")
            parse_error = $null
        }
        continue
    }

    $parseError = $null
    $mainHash = $null
    $bundledHash = $null
    $hashMatch = $false
    $diffPaths = @()

    try {
        $mainJson = Load-JsonFile -Path $mainPath
        $bundledJson = Load-JsonFile -Path $bundledPath

        $normMain = Normalize-JsonNode -Node $mainJson -KeysToIgnore $IgnoreKeys
        $normBundled = Normalize-JsonNode -Node $bundledJson -KeysToIgnore $IgnoreKeys

        $mainCanonical = Get-CanonicalJson -Node $normMain
        $bundledCanonical = Get-CanonicalJson -Node $normBundled
        $mainHash = Get-StringHash -Text $mainCanonical
        $bundledHash = Get-StringHash -Text $bundledCanonical
        $hashMatch = ($mainHash -eq $bundledHash)

        if (-not $hashMatch) {
            Compare-NormalizedNode -Left $normMain -Right $normBundled -Path "$" -DiffPaths ([ref]$diffPaths)
        }
    } catch {
        $parseError = $_.Exception.Message
        $hashMatch = $false
        if ($diffPaths.Count -eq 0) {
            $diffPaths = @("parse_error")
        }
    }

    $assertions += Assert-True -Condition $hashMatch -Message "[$($pair.id)] normalized hash parity"

    $results += [pscustomobject]@{
        id = $pair.id
        main_path = $mainPath
        bundled_path = $bundledPath
        main_exists = $existsMain
        bundled_exists = $existsBundled
        main_hash = $mainHash
        bundled_hash = $bundledHash
        hash_match = $hashMatch
        diff_paths_count = $diffPaths.Count
        diff_paths = @($diffPaths | Select-Object -First 40)
        parse_error = $parseError
    }
}

$pairsTotal = $pairs.Count
$pairsMatched = (@($results | Where-Object { $_.hash_match }).Count)
$hashMatchRate = if ($pairsTotal -gt 0) { [double]$pairsMatched / [double]$pairsTotal } else { 1.0 }
$totalDiffPaths = (@($results | ForEach-Object { if ($_.diff_paths_count) { $_.diff_paths_count } else { 0 } } | Measure-Object -Sum).Sum)
$gatePassed = ($pairsMatched -eq $pairsTotal) -and (@($assertions | Where-Object { -not $_ }).Count -eq 0)

Write-Host ""
Write-Host "=== Summary ==="
Write-Host ("Pairs total: {0}" -f $pairsTotal)
Write-Host ("Pairs matched: {0}" -f $pairsMatched)
Write-Host ("Hash match rate: {0:N4}" -f $hashMatchRate)
Write-Host ("Total diff paths: {0}" -f $totalDiffPaths)
Write-Host ("Gate Result: {0}" -f $(if ($gatePassed) { "PASS" } else { "FAIL" }))

$report = [pscustomobject]@{
    generated_at = (Get-Date).ToString("s")
    mode = if ($trackedMirrorRetired) { 'canonical_only_retired_tracked_mirror' } else { 'legacy_bundled_parity' }
    ignore_keys = $IgnoreKeys
    metrics = [pscustomobject]@{
        pairs_total = $pairsTotal
        pairs_matched = $pairsMatched
        hash_match_rate = [Math]::Round([double]$hashMatchRate, 4)
        total_diff_paths = [int]$totalDiffPaths
    }
    thresholds = [pscustomobject]@{
        parity_critical_files = 1.0
        hash_match_rate = 1.0
        total_diff_paths = 0
    }
    gate_passed = $gatePassed
    results = $results
}

if ($WriteArtifacts) {
    if (-not $OutputDirectory) {
        $OutputDirectory = Join-Path $repoRoot "outputs/verify"
    }
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

    $jsonPath = Join-Path $OutputDirectory "vibe-config-parity-gate.json"
    $mdPath = Join-Path $OutputDirectory "vibe-config-parity-gate.md"

    $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $lines = @()
    $lines += "# VCO Config Parity Gate"
    $lines += ""
    $lines += "- generated_at: ``$($report.generated_at)``"
    $lines += "- gate_passed: ``$($report.gate_passed)``"
    $lines += "- pairs_total: ``$($report.metrics.pairs_total)``"
    $lines += "- pairs_matched: ``$($report.metrics.pairs_matched)``"
    $lines += "- hash_match_rate: ``$($report.metrics.hash_match_rate)``"
    $lines += "- total_diff_paths: ``$($report.metrics.total_diff_paths)``"
    $lines += ""
    $lines += "## Pair Details"
    $lines += ""
    foreach ($row in $results) {
        $lines += "- ``$($row.id)``: match=``$($row.hash_match)`` diff_paths=``$($row.diff_paths_count)``"
    }

    $lines -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8
    Write-Host ""
    Write-Host "Artifacts written:"
    Write-Host "- $jsonPath"
    Write-Host "- $mdPath"
}

if (-not $gatePassed) {
    exit 1
}

exit 0
