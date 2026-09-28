param(
    [switch]$PruneBundledExtras,
    [switch]$Preview,
    [string]$PreviewOutputPath = '',
    [switch]$IncludeGeneratedCompatibilityTargets
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Copy-DirContent {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $directories = @(
        Get-ChildItem -LiteralPath $Source -Recurse -Directory | Sort-Object FullName
    )
    foreach ($directory in $directories) {
        $relativePath = Get-VgoRelativePathPortable -BasePath $Source -TargetPath $directory.FullName
        $targetDirectory = Join-Path $Destination $relativePath
        New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
    }

    $files = @(
        Get-ChildItem -LiteralPath $Source -Recurse -File | Sort-Object FullName
    )
    foreach ($file in $files) {
        $relativePath = Get-VgoRelativePathPortable -BasePath $Source -TargetPath $file.FullName
        $targetPath = Join-Path $Destination $relativePath
        $targetDirectory = Split-Path -Parent $targetPath
        if (-not [string]::IsNullOrWhiteSpace($targetDirectory)) {
            New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force
    }
}

function Add-PreviewAction {
    param(
        [System.Collections.Generic.List[object]]$Collection,
        [string]$Type,
        [string]$TargetId,
        [string]$RelativePath,
        [string]$Message
    )

    $Collection.Add([pscustomobject]@{
        type = $Type
        target_id = $TargetId
        relative_path = $RelativePath
        message = $Message
    }) | Out-Null
}

function Get-PreviewReceiptPath {
    param(
        [string]$CanonicalRoot,
        [string]$RequestedPath,
        [psobject]$Contract
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        return $RequestedPath
    }

    $root = if ($null -ne $Contract -and $Contract.PSObject.Properties.Name -contains 'preview_output_root') {
        [string]$Contract.preview_output_root
    } else {
        'outputs/governance/preview'
    }
    return Join-Path $CanonicalRoot (Join-Path $root 'sync-bundled-vibe.json')
}

function Get-TopLevelMirrorSegment {
    param(
        [Parameter(Mandatory)] [string]$RelativePath
    )

    $normalized = ([string]$RelativePath).Replace('\', '/').Trim('/')
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return ''
    }
    return ($normalized -split '/', 2)[0]
}

function Remove-MirrorPath {
    param(
        [Parameter(Mandatory)] [string]$TargetId,
        [Parameter(Mandatory)] [string]$RelativePath,
        [Parameter(Mandatory)] [string]$TargetPath,
        [Parameter(Mandatory)] [string]$Reason
    )

    if ($Preview) {
        Add-PreviewAction -Collection $previewActions -Type 'prune-legacy' -TargetId $TargetId -RelativePath $RelativePath -Message ('would prune legacy mirror path ' + $TargetPath + ' (' + $Reason + ')')
        return
    }

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    Remove-Item -LiteralPath $TargetPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ("[PRUNE] {0} {1} ({2})" -f $TargetId, $RelativePath, $Reason)
}

function Remove-ObsoleteMirrorRoots {
    param(
        [Parameter(Mandatory)] [psobject]$Target,
        [string[]]$MirrorFiles = @(),
        [string[]]$MirrorDirs = @(),
        [string[]]$AllowBundledOnly = @(),
        [object[]]$MirrorTargets = @()
    )

    $targetRoot = [string]$Target.fullPath
    if (-not (Test-Path -LiteralPath $targetRoot)) {
        return
    }

    $expectedRoots = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($rel in @($MirrorFiles + $MirrorDirs)) {
        $segment = Get-TopLevelMirrorSegment -RelativePath $rel
        if (-not [string]::IsNullOrWhiteSpace($segment)) {
            $expectedRoots.Add($segment) | Out-Null
        }
    }

    $preservedRoots = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($otherTarget in $MirrorTargets) {
        if ($null -eq $otherTarget -or [string]::IsNullOrWhiteSpace([string]$otherTarget.fullPath)) {
            continue
        }
        if ([string]$otherTarget.id -eq [string]$Target.id) {
            continue
        }

        $otherFullPath = [string]$otherTarget.fullPath
        try {
            $relativeToTarget = Get-VgoRelativePathPortable -BasePath $targetRoot -TargetPath $otherFullPath
        } catch {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($relativeToTarget) -or $relativeToTarget.StartsWith('..')) {
            continue
        }

        $segment = Get-TopLevelMirrorSegment -RelativePath $relativeToTarget
        if (-not [string]::IsNullOrWhiteSpace($segment)) {
            $preservedRoots.Add($segment) | Out-Null
        }
    }

    $topLevelEntries = @(Get-ChildItem -LiteralPath $targetRoot -Force)
    foreach ($entry in $topLevelEntries) {
        $relativePath = [string]$entry.Name
        if ($expectedRoots.Contains($relativePath) -or $preservedRoots.Contains($relativePath)) {
            continue
        }

        $allowlistedPaths = @(
            $AllowBundledOnly | Where-Object {
                $_ -eq $relativePath -or $_.StartsWith(($relativePath + '/'))
            }
        )
        if ($allowlistedPaths.Count -eq 0) {
            Remove-MirrorPath -TargetId ([string]$Target.id) -RelativePath $relativePath -TargetPath $entry.FullName -Reason 'dropped-from-mirror-contract'
            continue
        }

        if (-not $entry.PSIsContainer) {
            continue
        }

        $files = @(
            Get-ChildItem -LiteralPath $entry.FullName -Recurse -File -Force | Sort-Object FullName
        )
        foreach ($file in $files) {
            $childRelative = Get-VgoRelativePathPortable -BasePath $entry.FullName -TargetPath $file.FullName
            $allowRelative = ('{0}/{1}' -f $relativePath, $childRelative).Replace('\', '/')
            if ($AllowBundledOnly -contains $allowRelative) {
                continue
            }
            Remove-MirrorPath -TargetId ([string]$Target.id) -RelativePath $allowRelative -TargetPath $file.FullName -Reason 'dropped-from-mirror-contract'
        }

        $directories = @(
            Get-ChildItem -LiteralPath $entry.FullName -Recurse -Directory -Force | Sort-Object FullName -Descending
        )
        foreach ($directory in $directories) {
            if (@(Get-ChildItem -LiteralPath $directory.FullName -Force).Count -eq 0) {
                Remove-MirrorPath -TargetId ([string]$Target.id) -RelativePath (Get-VgoRelativePathPortable -BasePath $targetRoot -TargetPath $directory.FullName) -TargetPath $directory.FullName -Reason 'empty-after-prune'
            }
        }

        if (@(Get-ChildItem -LiteralPath $entry.FullName -Force).Count -eq 0) {
            Remove-MirrorPath -TargetId ([string]$Target.id) -RelativePath $relativePath -TargetPath $entry.FullName -Reason 'empty-after-prune'
        }
    }
}

function Get-AllowedMirrorRelativeFiles {
    param(
        [Parameter(Mandatory)] [string]$CanonicalRoot,
        [string[]]$MirrorFiles = @(),
        [string[]]$MirrorDirs = @()
    )

    $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($rel in $MirrorFiles) {
        $sourcePath = Join-Path $CanonicalRoot $rel
        if (Test-Path -LiteralPath $sourcePath -PathType Leaf) {
            $null = $allowed.Add(([string]$rel).Replace('\', '/'))
        }
    }

    foreach ($dir in $MirrorDirs) {
        $sourceDir = Join-Path $CanonicalRoot $dir
        if (-not (Test-Path -LiteralPath $sourceDir -PathType Container)) {
            continue
        }

        $files = @(Get-ChildItem -LiteralPath $sourceDir -Recurse -File | Sort-Object FullName)
        foreach ($file in $files) {
            $relativeFile = Get-VgoRelativePathPortable -BasePath $CanonicalRoot -TargetPath $file.FullName
            $null = $allowed.Add($relativeFile.Replace('\', '/'))
        }
    }

    return @($allowed)
}

function Remove-ObsoleteMirrorFiles {
    param(
        [Parameter(Mandatory)] [psobject]$Target,
        [string[]]$AllowedRelativeFiles = @(),
        [string[]]$AllowBundledOnly = @(),
        [object[]]$MirrorTargets = @()
    )

    $targetRoot = [string]$Target.fullPath
    if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
        return
    }

    $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($item in $AllowedRelativeFiles) {
        if (-not [string]::IsNullOrWhiteSpace([string]$item)) {
            $null = $allowed.Add(([string]$item).Replace('\', '/'))
        }
    }

    $preservedRoots = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($otherTarget in $MirrorTargets) {
        if ($null -eq $otherTarget -or [string]::IsNullOrWhiteSpace([string]$otherTarget.fullPath)) {
            continue
        }
        if ([string]$otherTarget.id -eq [string]$Target.id) {
            continue
        }

        try {
            $relativeToTarget = Get-VgoRelativePathPortable -BasePath $targetRoot -TargetPath ([string]$otherTarget.fullPath)
        } catch {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($relativeToTarget) -or $relativeToTarget.StartsWith('..')) {
            continue
        }

        $segment = Get-TopLevelMirrorSegment -RelativePath $relativeToTarget
        if (-not [string]::IsNullOrWhiteSpace($segment)) {
            $null = $preservedRoots.Add($segment)
        }
    }

    $targetFiles = @(Get-ChildItem -LiteralPath $targetRoot -Recurse -File -Force | Sort-Object FullName)
    foreach ($file in $targetFiles) {
        $relativePath = (Get-VgoRelativePathPortable -BasePath $targetRoot -TargetPath $file.FullName).Replace('\', '/')
        $topSegment = Get-TopLevelMirrorSegment -RelativePath $relativePath
        if ($preservedRoots.Contains($topSegment)) {
            continue
        }
        if ($allowed.Contains($relativePath)) {
            continue
        }
        if ($AllowBundledOnly -contains $relativePath) {
            continue
        }

        if ($Preview) {
            Add-PreviewAction -Collection $previewActions -Type 'prune-file' -TargetId ([string]$Target.id) -RelativePath $relativePath -Message ('would prune extra bundled file ' + $file.FullName)
        } else {
            Remove-Item -LiteralPath $file.FullName -Force -ErrorAction SilentlyContinue
            Write-Host ("[PRUNE] {0} {1}" -f $Target.id, $relativePath)
        }
    }

    $directories = @(Get-ChildItem -LiteralPath $targetRoot -Recurse -Directory -Force | Sort-Object FullName -Descending)
    foreach ($directory in $directories) {
        $relativePath = (Get-VgoRelativePathPortable -BasePath $targetRoot -TargetPath $directory.FullName).Replace('\', '/')
        $topSegment = Get-TopLevelMirrorSegment -RelativePath $relativePath
        if ($preservedRoots.Contains($topSegment)) {
            continue
        }
        if (@(Get-ChildItem -LiteralPath $directory.FullName -Force).Count -gt 0) {
            continue
        }

        if ($Preview) {
            Add-PreviewAction -Collection $previewActions -Type 'prune-empty-dir' -TargetId ([string]$Target.id) -RelativePath $relativePath -Message ('would prune empty mirror directory ' + $directory.FullName)
        } else {
            Remove-Item -LiteralPath $directory.FullName -Force -Recurse -ErrorAction SilentlyContinue
            Write-Host ("[PRUNE] {0} {1} (empty-after-prune)" -f $Target.id, $relativePath)
        }
    }
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$canonicalRoot = $context.canonicalRoot
$packaging = $context.packaging
$allowBundledOnly = @($packaging.allow_bundled_only)
$syncTargets = @(
    $context.mirrorTargets | Where-Object {
        -not $_.isCanonical -and (
            $_.sync_enabled -or
            $_.exists -or
            (
                $IncludeGeneratedCompatibilityTargets -and
                $_.PSObject.Properties.Name -contains 'materialization_mode' -and
                [string]$_.materialization_mode -eq 'release_install_only'
            )
        )
    }
)
$previewContractPath = Join-Path $canonicalRoot 'config/operator-preview-contract.json'
$previewContract = if (Test-Path -LiteralPath $previewContractPath) {
    Get-Content -LiteralPath $previewContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $null
}
$previewActions = [System.Collections.Generic.List[object]]::new()

function Sync-ToMirrorTarget {
    param(
        [Parameter(Mandatory)] [psobject]$Target
    )

    $targetRoot = [string]$Target.fullPath
    $allowedRelativeFiles = Get-AllowedMirrorRelativeFiles -CanonicalRoot $canonicalRoot -MirrorFiles $mirrorFiles -MirrorDirs $mirrorDirs
    $shouldCreate = [bool]$Target.required -or ([string]$Target.presence_policy -eq 'required') -or (
        $IncludeGeneratedCompatibilityTargets -and
        $Target.PSObject.Properties.Name -contains 'materialization_mode' -and
        [string]$Target.materialization_mode -eq 'release_install_only'
    )
    $targetExists = [bool]$Target.exists
    $targetPathExists = Test-Path -LiteralPath $targetRoot
    if (-not $targetExists) {
        if ($shouldCreate -or $targetPathExists) {
            if ($Preview) {
                $message = if ($targetPathExists) {
                    'would materialize partial mirror root ' + $targetRoot
                } else {
                    'would create mirror root ' + $targetRoot
                }
                Add-PreviewAction -Collection $previewActions -Type 'create-target' -TargetId ([string]$Target.id) -RelativePath '.' -Message $message
            } else {
                New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
                if ($targetPathExists) {
                    Write-Host ("[MATERIALIZE] {0} -> {1}" -f $Target.id, $targetRoot)
                } else {
                    Write-Host ("[CREATE] {0} -> {1}" -f $Target.id, $targetRoot)
                }
            }
        } else {
            $message = ("skip missing optional target {0} ({1})" -f $Target.id, $Target.presence_policy)
            if ($Preview) {
                Add-PreviewAction -Collection $previewActions -Type 'skip-target' -TargetId ([string]$Target.id) -RelativePath '.' -Message $message
            } else {
                Write-Host ("[SKIP] {0} missing and policy is {1}" -f $Target.id, $Target.presence_policy) -ForegroundColor Yellow
            }
            return
        }
    }

    foreach ($rel in $mirrorFiles) {
        $sourcePath = Join-Path $canonicalRoot $rel
        $targetPath = Join-Path $targetRoot $rel
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            if (-not $Preview) {
                Write-Warning ("Skip missing canonical file: {0}" -f $rel)
            }
            continue
        }

        $targetDir = Split-Path -Parent $targetPath
        if ($Preview) {
            Add-PreviewAction -Collection $previewActions -Type 'sync-file' -TargetId ([string]$Target.id) -RelativePath $rel -Message ('would sync file to ' + $targetPath)
        } else {
            if (-not [string]::IsNullOrWhiteSpace($targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            Write-Host ("[SYNC] {0} file {1}" -f $Target.id, $rel)
        }
    }

    foreach ($dir in $mirrorDirs) {
        $sourceDir = Join-Path $canonicalRoot $dir
        $targetDir = Join-Path $targetRoot $dir
        if (-not (Test-Path -LiteralPath $sourceDir)) {
            if (-not $Preview) {
                Write-Warning ("Skip missing canonical dir: {0}" -f $dir)
            }
            continue
        }

        if ($Preview) {
            Add-PreviewAction -Collection $previewActions -Type 'sync-dir' -TargetId ([string]$Target.id) -RelativePath $dir -Message ('would sync directory to ' + $targetDir)
        } else {
            Copy-DirContent -Source $sourceDir -Destination $targetDir
            Write-Host ("[SYNC] {0} dir {1}" -f $Target.id, $dir)
        }

        if ($PruneBundledExtras -and (Test-Path -LiteralPath $targetDir)) {
            $sourceFiles = Get-VgoRelativeFileList -RootPath $sourceDir
            $targetFiles = Get-VgoRelativeFileList -RootPath $targetDir
            foreach ($relPath in @($targetFiles | Where-Object { $_ -notin $sourceFiles })) {
                $allowRel = ('{0}/{1}' -f $dir, $relPath).Replace('\', '/')
                if ($allowBundledOnly -contains $allowRel) {
                    continue
                }

                $candidatePath = Join-Path $targetDir $relPath
                if ($Preview) {
                    Add-PreviewAction -Collection $previewActions -Type 'prune-file' -TargetId ([string]$Target.id) -RelativePath $allowRel -Message ('would prune extra bundled file ' + $candidatePath)
                } elseif (Test-Path -LiteralPath $candidatePath) {
                    Remove-Item -LiteralPath $candidatePath -Force -ErrorAction SilentlyContinue
                    Write-Host ("[PRUNE] {0} {1}" -f $Target.id, $allowRel)
                }
            }
        }
    }

    if ($PruneBundledExtras) {
        Remove-ObsoleteMirrorFiles -Target $Target -AllowedRelativeFiles $allowedRelativeFiles -AllowBundledOnly $allowBundledOnly -MirrorTargets $context.mirrorTargets
        Remove-ObsoleteMirrorRoots -Target $Target -MirrorFiles $mirrorFiles -MirrorDirs $mirrorDirs -AllowBundledOnly $allowBundledOnly -MirrorTargets $context.mirrorTargets
    }
}

Write-Host '=== Sync Bundled Vibe ===' -ForegroundColor Cyan
Write-Host ("Canonical root : {0}" -f $canonicalRoot)
Write-Host ("Sync source    : {0}" -f $context.syncSourceTarget.id)
foreach ($target in $syncTargets) {
    Write-Host ("Mirror target  : {0} -> {1} [{2}]" -f $target.id, $target.fullPath, $target.presence_policy)
}
Write-Host ''

foreach ($target in $syncTargets) {
    $effectivePackaging = Get-VgoEffectiveTargetPackaging -Packaging $packaging -TargetId ([string]$target.id)
    $script:mirrorFiles = @($effectivePackaging.files)
    $script:mirrorDirs = @($effectivePackaging.directories)
    Sync-ToMirrorTarget -Target $target
}

if ($Preview) {
    $receiptPath = Get-PreviewReceiptPath -CanonicalRoot $canonicalRoot -RequestedPath $PreviewOutputPath -Contract $previewContract
    $receipt = [ordered]@{
        operator = 'sync-bundled-vibe'
        contract_version = if ($null -ne $previewContract -and $previewContract.PSObject.Properties.Name -contains 'contract_version') { $previewContract.contract_version } else { 1 }
        mode = 'preview'
        precheck = [ordered]@{
            canonical_root = $canonicalRoot
            canonical_target_id = $context.canonicalTarget.id
            sync_source_target_id = $context.syncSourceTarget.id
            prune_bundled_extras = [bool]$PruneBundledExtras
            mirror_targets = @($syncTargets | ForEach-Object {
                [ordered]@{
                    id = $_.id
                    full_path = $_.fullPath
                    presence_policy = $_.presence_policy
                    materialization_mode = if ($_.PSObject.Properties.Name -contains 'materialization_mode') { $_.materialization_mode } else { 'tracked_mirror' }
                }
            })
            include_generated_compatibility_targets = [bool]$IncludeGeneratedCompatibilityTargets
        }
        preview = [ordered]@{
            generated_at = (Get-Date).ToString('s')
            action_count = $previewActions.Count
            planned_actions = @($previewActions)
        }
        postcheck = [ordered]@{
            verify_after_apply = @(
                'scripts/verify/vibe-mirror-edit-hygiene-gate.ps1',
                'scripts/verify/vibe-nested-bundled-parity-gate.ps1'
            )
        }
    }
    Write-VgoUtf8NoBomText -Path $receiptPath -Content ($receipt | ConvertTo-Json -Depth 100)
    Write-Host ("Preview receipt written: {0}" -f $receiptPath) -ForegroundColor Yellow
    return
}

Write-Host 'Sync complete.' -ForegroundColor Green
