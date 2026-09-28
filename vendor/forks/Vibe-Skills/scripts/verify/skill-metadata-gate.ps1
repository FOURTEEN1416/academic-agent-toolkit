param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory
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

function Add-Assertion {
    param(
        [bool]$Condition,
        [string]$Message
    )

    $result = Assert-True -Condition $Condition -Message $Message
    $script:assertions += $result
    return $result
}

function New-CaseInsensitiveSet {
    return New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
}

function Resolve-ManagedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathSpec,
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $normalized = $PathSpec.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    if ($normalized -eq '~') {
        $normalized = $HOME
    } elseif ($normalized -match '^~[\\/](.+)$') {
        $normalized = Join-Path $HOME $matches[1]
    }

    if ([System.IO.Path]::IsPathRooted($normalized)) {
        return [System.IO.Path]::GetFullPath($normalized)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $normalized))
}

function Get-JsonDocument {
    param([string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-ObjectPropertyNames {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    if ($Value -is [System.Collections.IDictionary]) {
        return @($Value.Keys | ForEach-Object { [string]$_ })
    }

    return @($Value.PSObject.Properties.Name | ForEach-Object { [string]$_ })
}

function Get-FrontmatterMap {
    param([string]$SkillMdPath)

    $content = [System.IO.File]::ReadAllText($SkillMdPath, [System.Text.Encoding]::UTF8)
    $content = $content.TrimStart([char]0xFEFF)
    $content = $content -replace "`r`n", "`n"

    if ($content -notmatch '(?s)\A---\n(.*?)\n---(?:\n|$)') {
        return @{}
    }

    $frontmatterBlock = $Matches[1]
    $lines = $frontmatterBlock -split "`n"
    $frontmatter = @{}

    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($line -match '^\s*$' -or $line -match '^\s*#') {
            continue
        }

        if ($line -notmatch '^(?<key>[A-Za-z0-9_-]+)\s*:\s*(?<value>.*)$') {
            continue
        }

        $key = [string]$matches['key']
        $value = [string]$matches['value']

        if ($value -eq '|' -or $value -eq '>') {
            $style = $value
            $blockLines = New-Object System.Collections.Generic.List[string]
            $cursor = $index + 1
            while ($cursor -lt $lines.Count) {
                $next = $lines[$cursor]
                if ($next -match '^[A-Za-z0-9_-]+\s*:\s*' -and -not ($next -match '^\s')) {
                    break
                }
                $blockLines.Add($next)
                $cursor++
            }

            $trimIndent = 0
            $nonEmpty = @($blockLines | Where-Object { $_ -match '\S' })
            if ($nonEmpty.Count -gt 0) {
                $indentWidths = @()
                foreach ($entry in $nonEmpty) {
                    if ($entry -match '^(\s+)') {
                        $indentWidths += $matches[1].Length
                    } else {
                        $indentWidths += 0
                    }
                }
                $trimIndent = ($indentWidths | Measure-Object -Minimum).Minimum
            }

            $normalizedBlock = @()
            foreach ($entry in $blockLines) {
                if ($trimIndent -gt 0 -and $entry.Length -ge $trimIndent) {
                    $normalizedBlock += $entry.Substring($trimIndent)
                } else {
                    $normalizedBlock += $entry.TrimStart()
                }
            }

            $frontmatter[$key] = if ($style -eq '|') {
                [string]::Join("`n", $normalizedBlock).Trim()
            } else {
                ([string]::Join(' ', $normalizedBlock) -replace '\s+', ' ').Trim()
            }

            $index = $cursor - 1
            continue
        }

        $trimmed = $value.Trim()
        if ($trimmed.Length -ge 2) {
            $first = $trimmed[0]
            $last = $trimmed[$trimmed.Length - 1]
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $trimmed = $trimmed.Substring(1, $trimmed.Length - 2)
            }
        }

        $frontmatter[$key] = $trimmed
    }

    return $frontmatter
}

function Normalize-DisplayName {
    param(
        [string]$Name,
        [object]$Policy
    )

    if ($null -eq $Name) {
        return ""
    }

    $normalized = $Name.Trim()
    if ($Policy.skill_frontmatter_rules.normalize_name.trim_quotes) {
        $normalized = $normalized.Trim('"').Trim("'")
    }
    if ($Policy.skill_frontmatter_rules.normalize_name.case_insensitive) {
        $normalized = $normalized.ToLowerInvariant()
    }
    return $normalized.Trim()
}

function Normalize-Key {
    param([string]$InputText)

    if (-not $InputText) {
        return ""
    }

    return ($InputText.Trim().Replace("\", "/")).ToLowerInvariant()
}

function Test-LineContainsTokens {
    param(
        [string[]]$Lines,
        [string[]]$Tokens
    )

    foreach ($line in $Lines) {
        $matched = $true
        foreach ($token in $Tokens) {
            if ([string]::IsNullOrWhiteSpace($token)) {
                continue
            }
            if ($line.IndexOf($token, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            return $true
        }
    }

    return $false
}

function Resolve-SkillEntry {
    param(
        [string]$SkillId,
        [object[]]$SkillRoots,
        [string]$RepoRoot
    )

    foreach ($rootSpec in @($SkillRoots | Sort-Object priority)) {
        $rootPath = Resolve-ManagedPath -PathSpec ([string]$rootSpec.path) -RepoRoot $RepoRoot
        $candidate = Join-Path $rootPath $SkillId
        if (Test-Path -LiteralPath $candidate) {
            return [pscustomobject]@{
                found = $true
                root_id = [string]$rootSpec.id
                directory = $candidate
                skill_md = Join-Path $candidate 'SKILL.md'
            }
        }
    }

    $canonicalSkillManifestPath = Join-Path $RepoRoot ("core/skills/{0}/skill.json" -f $SkillId)
    if (Test-Path -LiteralPath $canonicalSkillManifestPath) {
        $canonicalSkillManifest = Get-JsonDocument -Path $canonicalSkillManifestPath
        $sourceOfTruth = if ($canonicalSkillManifest.PSObject.Properties.Name -contains 'source_of_truth') { $canonicalSkillManifest.source_of_truth } else { $null }
        $sourceKind = if ($null -ne $sourceOfTruth -and $sourceOfTruth.PSObject.Properties.Name -contains 'kind') { [string]$sourceOfTruth.kind } else { '' }
        $sourcePathSpec = if ($null -ne $sourceOfTruth -and $sourceOfTruth.PSObject.Properties.Name -contains 'path') { [string]$sourceOfTruth.path } else { '' }
        if ($sourceKind -eq 'canonical-skill' -and -not [string]::IsNullOrWhiteSpace($sourcePathSpec)) {
            $resolvedSourcePath = Resolve-ManagedPath -PathSpec $sourcePathSpec -RepoRoot $RepoRoot
            $skillDirectory = $resolvedSourcePath
            $skillMd = $resolvedSourcePath
            if (Test-Path -LiteralPath $resolvedSourcePath -PathType Leaf) {
                $skillDirectory = Split-Path -Parent $resolvedSourcePath
                $skillMd = $resolvedSourcePath
            } else {
                $leafName = [System.IO.Path]::GetFileName($resolvedSourcePath)
                if ($leafName.Equals('SKILL.md', [System.StringComparison]::OrdinalIgnoreCase)) {
                    $skillDirectory = Split-Path -Parent $resolvedSourcePath
                    $skillMd = $resolvedSourcePath
                } else {
                    $skillDirectory = $resolvedSourcePath
                    $skillMd = Join-Path $skillDirectory 'SKILL.md'
                }
            }

            return [pscustomobject]@{
                found = (Test-Path -LiteralPath $skillDirectory)
                root_id = 'canonical_repo_skill'
                directory = $skillDirectory
                skill_md = $skillMd
            }
        }
    }

    return [pscustomobject]@{
        found = $false
        root_id = $null
        directory = $null
        skill_md = $null
    }
}

function Test-ReservedSkillId {
    param(
        [string]$SkillId,
        [string[]]$Patterns
    )

    foreach ($pattern in $Patterns) {
        if ($SkillId -match $pattern) {
            return $true
        }
    }

    return $false
}

function Test-SourceEnabled {
    param(
        [object]$Policy,
        [string]$SourceId
    )

    return @($Policy.validation_scope.enabled_sources | ForEach-Object { [string]$_ }) -contains $SourceId
}

function Merge-UniqueStrings {
    param(
        [object[]]$Existing,
        [object[]]$Incoming
    )

    $set = New-CaseInsensitiveSet
    $merged = New-Object System.Collections.Generic.List[string]
    foreach ($item in @($Existing) + @($Incoming)) {
        $text = [string]$item
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }
        if ($set.Add($text)) {
            $merged.Add($text)
        }
    }

    return @($merged | Sort-Object)
}

function Add-OrMergeSkillRegistryEntry {
    param(
        [hashtable]$SkillRegistry,
        [pscustomobject]$Entry,
        [string[]]$SourceTags,
        [string[]]$SourceRefs
    )

    if ($SkillRegistry.ContainsKey($Entry.skill_id)) {
        $existing = $SkillRegistry[$Entry.skill_id]
        $existing.sources = Merge-UniqueStrings -Existing $existing.sources -Incoming $SourceTags
        $existing.source_refs = Merge-UniqueStrings -Existing $existing.source_refs -Incoming $SourceRefs
        $existing.resolved = ($existing.resolved -or $Entry.resolved)
        $existing.frontmatter_ok = ($existing.frontmatter_ok -or $Entry.frontmatter_ok)
        if ([string]::IsNullOrWhiteSpace([string]$existing.display_name) -and -not [string]::IsNullOrWhiteSpace([string]$Entry.display_name)) {
            $existing.display_name = $Entry.display_name
            $existing.normalized_display_name = $Entry.normalized_display_name
        }
        if ([string]::IsNullOrWhiteSpace([string]$existing.description) -and -not [string]::IsNullOrWhiteSpace([string]$Entry.description)) {
            $existing.description = $Entry.description
        }
        if (([string]$Entry.root_id -eq 'user_skills') -or [string]::IsNullOrWhiteSpace([string]$existing.root_id)) {
            if (-not [string]::IsNullOrWhiteSpace([string]$Entry.root_id)) {
                $existing.root_id = $Entry.root_id
                $existing.directory = $Entry.directory
                $existing.skill_md = $Entry.skill_md
            }
        }
        return $existing
    }

    $Entry | Add-Member -NotePropertyName sources -NotePropertyValue (Merge-UniqueStrings -Existing @() -Incoming $SourceTags)
    $Entry | Add-Member -NotePropertyName source_refs -NotePropertyValue (Merge-UniqueStrings -Existing @() -Incoming $SourceRefs)
    $SkillRegistry[$Entry.skill_id] = $Entry
    return $Entry
}

function Get-RoutingRuleTaskAllow {
    param(
        [object]$RoutingRules,
        [string]$SkillId
    )

    if ($null -eq $RoutingRules -or $null -eq $RoutingRules.skills) {
        return @()
    }

    if (-not (@($RoutingRules.skills.PSObject.Properties.Name) -contains $SkillId)) {
        return @()
    }

    return @($RoutingRules.skills.$SkillId.task_allow | ForEach-Object { [string]$_ })
}

function Validate-RoutedSkillReference {
    param(
        [string]$SkillId,
        [string]$AssertionPrefix,
        [string[]]$SourceTags,
        [string[]]$SourceRefs,
        [object[]]$SkillRoots,
        [string]$RepoRoot,
        [object]$Policy,
        [string[]]$ReservedPatterns,
        [hashtable]$SkillRegistry,
        [object]$RoutingRules,
        [string]$ExpectedTask,
        [switch]$RequireCanonicalTopLevel,
        [System.Collections.Generic.HashSet[string]]$LockSet,
        [switch]$RequireLockEntry
    )

    $isReserved = Test-ReservedSkillId -SkillId $SkillId -Patterns $ReservedPatterns
    Add-Assertion -Condition (-not $isReserved) -Message "$AssertionPrefix skill '$SkillId' is not reserved metadata id" | Out-Null

    $resolvedSkill = Resolve-SkillEntry -SkillId $SkillId -SkillRoots $SkillRoots -RepoRoot $RepoRoot
    $skillMdExists = ($resolvedSkill.found -and (Test-Path -LiteralPath $resolvedSkill.skill_md))
    Add-Assertion -Condition $resolvedSkill.found -Message "$AssertionPrefix skill '$SkillId' resolves to a real skill directory" | Out-Null
    Add-Assertion -Condition $skillMdExists -Message "$AssertionPrefix skill '$SkillId' has SKILL.md" | Out-Null

    if ($RequireCanonicalTopLevel) {
        Add-Assertion -Condition (@('user_skills', 'canonical_repo_skill') -contains [string]$resolvedSkill.root_id) -Message "$AssertionPrefix skill '$SkillId' resolves to canonical top-level skill root" | Out-Null
    }

    if ($RequireLockEntry) {
        $needsBundledLockEntry = ([string]$resolvedSkill.root_id -eq 'bundled_skills')
        $inLock = ((-not $needsBundledLockEntry) -or ($null -ne $LockSet -and $LockSet.Contains($SkillId)))
        Add-Assertion -Condition $inLock -Message "$AssertionPrefix skill '$SkillId' present in skills-lock" | Out-Null
    }

    $frontmatter = @{}
    $frontmatterOk = $false
    if ($skillMdExists) {
        $frontmatter = Get-FrontmatterMap -SkillMdPath $resolvedSkill.skill_md
        $frontmatterOk = ($frontmatter.Count -gt 0)
    }
    Add-Assertion -Condition $frontmatterOk -Message "$AssertionPrefix skill '$SkillId' frontmatter parsed" | Out-Null

    foreach ($field in @($Policy.skill_frontmatter_rules.required_fields)) {
        $value = if ($frontmatter.ContainsKey($field)) { [string]$frontmatter[$field] } else { '' }
        Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($value)) -Message "$AssertionPrefix skill '$SkillId' frontmatter '$field' non-empty" | Out-Null
    }

    $normalizedDisplayName = Normalize-DisplayName -Name ([string]$frontmatter['name']) -Policy $Policy
    $description = if ($frontmatter.ContainsKey('description')) { [string]$frontmatter['description'] } else { '' }
    $routingRuleExists = ($null -ne $RoutingRules -and $null -ne $RoutingRules.skills -and (@($RoutingRules.skills.PSObject.Properties.Name) -contains $SkillId))
    $routingTaskAllow = Get-RoutingRuleTaskAllow -RoutingRules $RoutingRules -SkillId $SkillId
    $supportsExpectedTask = $null
    if (-not [string]::IsNullOrWhiteSpace($ExpectedTask)) {
        if ($routingRuleExists) {
            $supportsExpectedTask = ($routingTaskAllow -contains $ExpectedTask)
            Add-Assertion -Condition $supportsExpectedTask -Message "$AssertionPrefix skill '$SkillId' supports task '$ExpectedTask' in skill-routing-rules" | Out-Null
        } else {
            $supportsExpectedTask = $null
            Write-Host "[WARN] $AssertionPrefix skill '$SkillId' has no routing rule entry for task validation" -ForegroundColor Yellow
            $script:defaultTaskRoutingRuleWarnings += [pscustomobject]@{
                assertion_prefix = $AssertionPrefix
                skill_id = $SkillId
                expected_task = $ExpectedTask
            }
        }
    }

    $entry = [pscustomobject]@{
        skill_id = $SkillId
        resolved = $resolvedSkill.found
        root_id = $resolvedSkill.root_id
        directory = $resolvedSkill.directory
        skill_md = $resolvedSkill.skill_md
        frontmatter_ok = $frontmatterOk
        display_name = [string]$frontmatter['name']
        normalized_display_name = $normalizedDisplayName
        description = $description
        routing_task_allow = $routingTaskAllow
    }
    Add-OrMergeSkillRegistryEntry -SkillRegistry $SkillRegistry -Entry $entry -SourceTags $SourceTags -SourceRefs $SourceRefs | Out-Null

    return [pscustomobject]@{
        skill_id = $SkillId
        resolved = $resolvedSkill.found
        root_id = $resolvedSkill.root_id
        skill_md = $resolvedSkill.skill_md
        frontmatter_ok = $frontmatterOk
        display_name = [string]$frontmatter['name']
        routing_task_allow = $routingTaskAllow
        expected_task = $ExpectedTask
        supports_expected_task = $supportsExpectedTask
        sources = $SourceTags
        source_refs = $SourceRefs
    }
}

function Resolve-AliasTerminalTarget {
    param(
        [string]$AliasKey,
        [hashtable]$AliasNormalizedMap
    )

    $normalizedKey = Normalize-Key -InputText $AliasKey
    $visited = New-CaseInsensitiveSet
    $path = New-Object System.Collections.Generic.List[string]
    $currentKey = $normalizedKey

    while ($AliasNormalizedMap.ContainsKey($currentKey)) {
        if (-not $visited.Add($currentKey)) {
            return [pscustomobject]@{
                normalized_key = $normalizedKey
                terminal_target = $null
                cycle_detected = $true
                hop_count = $path.Count
                path = @($path)
            }
        }

        $nextTarget = [string]$AliasNormalizedMap[$currentKey]
        $path.Add($nextTarget)
        $normalizedTarget = Normalize-Key -InputText $nextTarget
        if (-not $AliasNormalizedMap.ContainsKey($normalizedTarget)) {
            return [pscustomobject]@{
                normalized_key = $normalizedKey
                terminal_target = $nextTarget
                cycle_detected = $false
                hop_count = $path.Count
                path = @($path)
            }
        }

        $currentKey = $normalizedTarget
    }

    return [pscustomobject]@{
        normalized_key = $normalizedKey
        terminal_target = $null
        cycle_detected = $false
        hop_count = 0
        path = @()
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$policyPath = Join-Path $repoRoot 'config\skill-metadata-policy.json'

if (-not (Test-Path -LiteralPath $policyPath)) {
    throw "Policy file not found: $policyPath"
}

$policy = Get-JsonDocument -Path $policyPath
$catalogEnabled = Test-SourceEnabled -Policy $policy -SourceId 'capability_catalog'
$packEnabled = Test-SourceEnabled -Policy $policy -SourceId 'pack_manifest'
$aliasEnabled = Test-SourceEnabled -Policy $policy -SourceId 'skill_alias_map'
$roleSurfaceEnabled = Test-SourceEnabled -Policy $policy -SourceId 'local_role_surfaces'
$alwaysRequiredEnabled = Test-SourceEnabled -Policy $policy -SourceId 'always_required_skills'

$catalogPath = if ($catalogEnabled) { Resolve-ManagedPath -PathSpec ([string]$policy.paths.capability_catalog) -RepoRoot $repoRoot } else { $null }
$packManifestPath = if ($packEnabled) { Resolve-ManagedPath -PathSpec ([string]$policy.paths.pack_manifest) -RepoRoot $repoRoot } else { $null }
$aliasMapPath = if ($aliasEnabled) { Resolve-ManagedPath -PathSpec ([string]$policy.paths.skill_alias_map) -RepoRoot $repoRoot } else { $null }
$teamTemplatesPath = if ($roleSurfaceEnabled) { Resolve-ManagedPath -PathSpec ([string]$policy.paths.team_templates) -RepoRoot $repoRoot } else { $null }
$roleTaxonomyPath = if ($roleSurfaceEnabled) { Resolve-ManagedPath -PathSpec ([string]$policy.paths.role_taxonomy) -RepoRoot $repoRoot } else { $null }
$routingRulesPath = if ($packEnabled) { Join-Path $repoRoot 'config\skill-routing-rules.json' } else { $null }
$skillsLockPath = if ($aliasEnabled) { Join-Path $repoRoot 'config\skills-lock.json' } else { $null }

$script:assertions = @()
$catalog = $null
$packManifest = $null
$aliasMap = $null
$routingRules = $null
$skillsLock = $null
$skillsLockSet = $null
$teamTemplateLines = @()
$roleTaxonomyLines = @()

Write-Host '=== VCO Skill Metadata Gate ==='
if ($catalogEnabled) {
    Add-Assertion -Condition (Test-Path -LiteralPath $catalogPath) -Message '[sources] capability catalog exists' | Out-Null
    $catalog = Get-JsonDocument -Path $catalogPath
}
if ($packEnabled) {
    Add-Assertion -Condition (Test-Path -LiteralPath $packManifestPath) -Message '[sources] pack manifest exists' | Out-Null
    Add-Assertion -Condition (Test-Path -LiteralPath $routingRulesPath) -Message '[sources] skill routing rules exists' | Out-Null
    $packManifest = Get-JsonDocument -Path $packManifestPath
    $routingRules = Get-JsonDocument -Path $routingRulesPath
}
if ($aliasEnabled) {
    Add-Assertion -Condition (Test-Path -LiteralPath $aliasMapPath) -Message '[sources] skill alias map exists' | Out-Null
    Add-Assertion -Condition (Test-Path -LiteralPath $skillsLockPath) -Message '[sources] skills lock exists' | Out-Null
    $aliasMap = Get-JsonDocument -Path $aliasMapPath
    $skillsLock = Get-JsonDocument -Path $skillsLockPath
    $skillsLockSet = New-CaseInsensitiveSet
    foreach ($lockSkill in @($skillsLock.skills)) {
        $lockName = [string]$lockSkill.name
        if (-not [string]::IsNullOrWhiteSpace($lockName)) {
            [void]$skillsLockSet.Add($lockName)
        }
    }
}
if ($roleSurfaceEnabled) {
    Add-Assertion -Condition (Test-Path -LiteralPath $teamTemplatesPath) -Message '[sources] team templates exists' | Out-Null
    Add-Assertion -Condition (Test-Path -LiteralPath $roleTaxonomyPath) -Message '[sources] role taxonomy exists' | Out-Null
    $teamTemplateLines = Get-Content -LiteralPath $teamTemplatesPath -Encoding UTF8
    $roleTaxonomyLines = Get-Content -LiteralPath $roleTaxonomyPath -Encoding UTF8
}

$skillRegistry = @{}
$capabilityResults = @()
$packResults = @()
$aliasResults = @()
$alwaysRequiredResults = @()
$roleSurfaceResults = @()
$packCoverageWarnings = @()
$defaultTaskRoutingRuleWarnings = @()
$aliasDisplayNameCollisions = @()

$skillRoots = @($policy.paths.skills_roots)
$reservedPatterns = @($policy.catalog_rules.reserved_non_skill_patterns)

if ($catalogEnabled) {
    $catalogTopLevelNames = Get-ObjectPropertyNames -Value $catalog
    foreach ($field in @($policy.catalog_rules.required_top_level_fields)) {
        Add-Assertion -Condition ($catalogTopLevelNames -contains [string]$field) -Message "[catalog] top-level field '$field' present" | Out-Null
    }

    $metadataBlock = $catalog.metadata_hardening
    $metadataBlockNames = Get-ObjectPropertyNames -Value $metadataBlock
    foreach ($field in @($policy.metadata_contract.required_catalog_block_fields)) {
        Add-Assertion -Condition ($metadataBlockNames -contains [string]$field) -Message "[catalog.metadata_hardening] field '$field' present" | Out-Null
    }
    Add-Assertion -Condition ([string]$metadataBlock.mode -eq [string]$policy.validation_scope.mode) -Message '[catalog.metadata_hardening] mode matches policy' | Out-Null
    Add-Assertion -Condition ((Resolve-ManagedPath -PathSpec ([string]$metadataBlock.policy) -RepoRoot $repoRoot) -eq $policyPath) -Message '[catalog.metadata_hardening] policy path resolves to current policy' | Out-Null
    Add-Assertion -Condition ((Resolve-ManagedPath -PathSpec ([string]$metadataBlock.gate) -RepoRoot $repoRoot) -eq [System.IO.Path]::GetFullPath($PSCommandPath)) -Message '[catalog.metadata_hardening] gate path resolves to current gate' | Out-Null
    foreach ($scope in @($policy.metadata_contract.required_scopes)) {
        Add-Assertion -Condition (@($metadataBlock.enforced_scopes) -contains [string]$scope) -Message "[catalog.metadata_hardening] enforced scope '$scope' present" | Out-Null
    }

    $interviewQuestions = @($catalog.default_interview_questions)
    Add-Assertion -Condition ($interviewQuestions.Count -ge [int]$policy.default_interview_question_rules.minimum_count) -Message '[catalog] default interview question count meets minimum' | Out-Null
    $questionIds = New-CaseInsensitiveSet
    foreach ($question in $interviewQuestions) {
        foreach ($field in @($policy.default_interview_question_rules.required_fields)) {
            $value = [string]$question.$field
            Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($value)) -Message "[default_interview_question] $field is non-empty" | Out-Null
        }
        $added = $questionIds.Add([string]$question.id)
        Add-Assertion -Condition $added -Message "[default_interview_question] id '$([string]$question.id)' unique" | Out-Null
    }

    $capabilityIds = New-CaseInsensitiveSet
    $allowedTaskTypes = @($policy.catalog_rules.allowed_task_types)
    $adviceOverlayPattern = [string]$policy.catalog_rules.advice_overlay_pattern

    foreach ($capability in @($catalog.capabilities)) {
        $capabilityId = [string]$capability.id
        $capabilityName = [string]$capability.display_name
        $capabilityFieldNames = Get-ObjectPropertyNames -Value $capability

        foreach ($field in @($policy.catalog_rules.required_capability_fields)) {
            Add-Assertion -Condition ($capabilityFieldNames -contains [string]$field) -Message "[capability:$capabilityId] field '$field' present" | Out-Null
        }

        Add-Assertion -Condition ($capabilityIds.Add($capabilityId)) -Message "[capability:$capabilityId] id unique" | Out-Null
        Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($capabilityName)) -Message "[capability:$capabilityId] display_name non-empty" | Out-Null

        $taskAllow = @($capability.task_allow | ForEach-Object { [string]$_ })
        $keywords = @($capability.keywords | ForEach-Object { [string]$_ })
        $skills = @($capability.skills | ForEach-Object { [string]$_ })
        $adviceOverlays = @()
        if ($capabilityFieldNames -contains 'advice_overlays') {
            $adviceOverlays = @($capability.advice_overlays | ForEach-Object { [string]$_ })
        }

        Add-Assertion -Condition ($taskAllow.Count -gt 0) -Message "[capability:$capabilityId] task_allow non-empty" | Out-Null
        foreach ($taskType in $taskAllow) {
            Add-Assertion -Condition ($allowedTaskTypes -contains $taskType) -Message "[capability:$capabilityId] task_allow '$taskType' allowed" | Out-Null
        }

        Add-Assertion -Condition ($keywords.Count -ge [int]$policy.catalog_rules.minimum_keywords) -Message "[capability:$capabilityId] keyword count meets minimum" | Out-Null
        Add-Assertion -Condition ($skills.Count -ge [int]$policy.catalog_rules.minimum_skills) -Message "[capability:$capabilityId] skill count meets minimum" | Out-Null
        Add-Assertion -Condition ($skills.Count -le [int]$policy.catalog_rules.maximum_skills) -Message "[capability:$capabilityId] skill count within maximum" | Out-Null

        $capSkillSet = New-CaseInsensitiveSet
        $duplicateSkills = @()
        $capabilitySkillResults = @()
        foreach ($skillId in $skills) {
            if (-not $capSkillSet.Add($skillId)) {
                $duplicateSkills += $skillId
            }

            $capabilitySkillResults += Validate-RoutedSkillReference -SkillId $skillId -AssertionPrefix "[capability:$capabilityId]" -SourceTags @('capability_catalog.skills') -SourceRefs @("capability:$capabilityId") -SkillRoots $skillRoots -RepoRoot $repoRoot -Policy $policy -ReservedPatterns $reservedPatterns -SkillRegistry $skillRegistry -RoutingRules $null -ExpectedTask $null
        }

        Add-Assertion -Condition ($duplicateSkills.Count -eq 0) -Message "[capability:$capabilityId] no duplicate skills inside capability" | Out-Null

        $overlaySet = New-CaseInsensitiveSet
        foreach ($overlayId in $adviceOverlays) {
            $matchesOverlayPattern = ($overlayId -match $adviceOverlayPattern)
            Add-Assertion -Condition $matchesOverlayPattern -Message "[capability:$capabilityId] advice overlay '$overlayId' matches overlay contract" | Out-Null
            Add-Assertion -Condition (-not ($skills -contains $overlayId)) -Message "[capability:$capabilityId] advice overlay '$overlayId' kept out of skills[]" | Out-Null
            Add-Assertion -Condition ($overlaySet.Add($overlayId)) -Message "[capability:$capabilityId] advice overlay '$overlayId' unique" | Out-Null
        }

        $capabilityResults += [pscustomobject]@{
            capability_id = $capabilityId
            display_name = $capabilityName
            task_allow = $taskAllow
            keyword_count = $keywords.Count
            skills = $capabilitySkillResults
            advice_overlays = $adviceOverlays
        }
    }
}

if ($packEnabled) {
    $packTopLevelNames = Get-ObjectPropertyNames -Value $packManifest
    foreach ($field in @($policy.pack_rules.required_top_level_fields)) {
        Add-Assertion -Condition ($packTopLevelNames -contains [string]$field) -Message "[pack_manifest] top-level field '$field' present" | Out-Null
    }
    if ($policy.pack_rules.require_legacy_matrix_fallback) {
        Add-Assertion -Condition ([bool]$packManifest.legacy_matrix_fallback) -Message '[pack_manifest] legacy_matrix_fallback enabled' | Out-Null
    }

    $allowedGrades = @($policy.pack_rules.allowed_grades)
    $allowedTaskTypes = @($policy.pack_rules.allowed_task_types)
    $packIds = New-CaseInsensitiveSet

    foreach ($pack in @($packManifest.packs)) {
        $packId = [string]$pack.id
        $packFieldNames = Get-ObjectPropertyNames -Value $pack
        foreach ($field in @($policy.pack_rules.required_pack_fields)) {
            Add-Assertion -Condition ($packFieldNames -contains [string]$field) -Message "[pack:$packId] field '$field' present" | Out-Null
        }

        if ($policy.pack_rules.disallow_duplicate_pack_ids) {
            Add-Assertion -Condition ($packIds.Add($packId)) -Message "[pack:$packId] id unique" | Out-Null
        }

        $gradeAllow = @($pack.grade_allow | ForEach-Object { [string]$_ })
        $taskAllow = @($pack.task_allow | ForEach-Object { [string]$_ })
        $triggerKeywords = @($pack.trigger_keywords | ForEach-Object { [string]$_ })
        $skillCandidates = @($pack.skill_candidates | ForEach-Object { [string]$_ })
        $defaultPairs = @()
        if ($null -ne $pack.defaults_by_task) {
            $defaultPairs = @($pack.defaults_by_task.PSObject.Properties)
        }
        $defaultTaskKeys = @($defaultPairs | ForEach-Object { [string]$_.Name })

        Add-Assertion -Condition ($gradeAllow.Count -gt 0) -Message "[pack:$packId] grade_allow non-empty" | Out-Null
        foreach ($grade in $gradeAllow) {
            Add-Assertion -Condition ($allowedGrades -contains $grade) -Message "[pack:$packId] grade_allow '$grade' allowed" | Out-Null
        }

        Add-Assertion -Condition ($taskAllow.Count -gt 0) -Message "[pack:$packId] task_allow non-empty" | Out-Null
        foreach ($taskType in $taskAllow) {
            Add-Assertion -Condition ($allowedTaskTypes -contains $taskType) -Message "[pack:$packId] task_allow '$taskType' allowed" | Out-Null
            if ($policy.pack_rules.require_defaults_cover_task_allow) {
                Add-Assertion -Condition ($defaultTaskKeys -contains $taskType) -Message "[pack:$packId] default exists for task '$taskType'" | Out-Null
            }
        }

        Add-Assertion -Condition ($triggerKeywords.Count -ge [int]$policy.pack_rules.minimum_trigger_keywords) -Message "[pack:$packId] trigger keyword count meets minimum" | Out-Null
        Add-Assertion -Condition ($skillCandidates.Count -ge [int]$policy.pack_rules.minimum_skill_candidates) -Message "[pack:$packId] skill candidate count meets minimum" | Out-Null
        Add-Assertion -Condition ($null -ne $pack.defaults_by_task) -Message "[pack:$packId] defaults_by_task present" | Out-Null

        $candidateSet = New-CaseInsensitiveSet
        $duplicateCandidateSkills = @()
        $candidateResults = @()
        foreach ($skillId in $skillCandidates) {
            if ($policy.pack_rules.disallow_duplicate_skills_within_pack -and -not $candidateSet.Add($skillId)) {
                $duplicateCandidateSkills += $skillId
            }

            $candidateResults += Validate-RoutedSkillReference -SkillId $skillId -AssertionPrefix "[pack:$packId] candidate" -SourceTags @('pack_manifest.skill_candidates') -SourceRefs @("pack:$packId:candidate") -SkillRoots $skillRoots -RepoRoot $repoRoot -Policy $policy -ReservedPatterns $reservedPatterns -SkillRegistry $skillRegistry -RoutingRules $null -ExpectedTask $null
        }
        if ($policy.pack_rules.disallow_duplicate_skills_within_pack) {
            Add-Assertion -Condition ($duplicateCandidateSkills.Count -eq 0) -Message "[pack:$packId] no duplicate skill candidates" | Out-Null
        }

        $supportedTaskCoverage = @{}
        foreach ($taskType in $taskAllow) {
            $supportingCandidates = @()
            foreach ($skillId in $skillCandidates) {
                $candidateTaskAllow = Get-RoutingRuleTaskAllow -RoutingRules $routingRules -SkillId $skillId
                if ($candidateTaskAllow -contains $taskType) {
                    $supportingCandidates += $skillId
                }
            }
            $supportedTaskCoverage[$taskType] = $supportingCandidates
            if ($supportingCandidates.Count -eq 0) {
                Write-Host "[WARN] [pack:$packId] no candidate supports task '$taskType' in skill-routing-rules" -ForegroundColor Yellow
                $packCoverageWarnings += [pscustomobject]@{
                    pack_id = $packId
                    task = $taskType
                    skill_candidates = $skillCandidates
                }
            }
        }

        $defaultResults = @()
        foreach ($pair in $defaultPairs) {
            $taskKey = [string]$pair.Name
            $defaultSkill = [string]$pair.Value
            if ($policy.pack_rules.require_default_tasks_in_task_allow) {
                Add-Assertion -Condition ($taskAllow -contains $taskKey) -Message "[pack:$packId] default task '$taskKey' is task-allowed" | Out-Null
            }
            if ($policy.pack_rules.require_defaults_in_candidates) {
                Add-Assertion -Condition ($skillCandidates -contains $defaultSkill) -Message "[pack:$packId] default skill '$defaultSkill' exists in candidates" | Out-Null
            }

            $defaultResults += Validate-RoutedSkillReference -SkillId $defaultSkill -AssertionPrefix "[pack:$packId] default '$taskKey'" -SourceTags @('pack_manifest.defaults_by_task') -SourceRefs @("pack:$packId:default:$taskKey") -SkillRoots $skillRoots -RepoRoot $repoRoot -Policy $policy -ReservedPatterns $reservedPatterns -SkillRegistry $skillRegistry -RoutingRules $routingRules -ExpectedTask $taskKey
        }

        $packResults += [pscustomobject]@{
            pack_id = $packId
            priority = $pack.priority
            grade_allow = $gradeAllow
            task_allow = $taskAllow
            trigger_keyword_count = $triggerKeywords.Count
            skill_candidates = $candidateResults
            defaults = $defaultResults
            coverage_by_task = @($supportedTaskCoverage.GetEnumerator() | Sort-Object Name | ForEach-Object {
                [pscustomobject]@{
                    task = [string]$_.Name
                    supporting_candidates = @($_.Value)
                }
            })
        }
    }
}

if ($aliasEnabled) {
    $aliasTopLevelNames = Get-ObjectPropertyNames -Value $aliasMap
    foreach ($field in @($policy.alias_rules.required_top_level_fields)) {
        Add-Assertion -Condition ($aliasTopLevelNames -contains [string]$field) -Message "[skill_alias_map] top-level field '$field' present" | Out-Null
    }

    $aliasPairs = @()
    if ($null -ne $aliasMap.aliases) {
        $aliasPairs = @($aliasMap.aliases.PSObject.Properties)
    }
    Add-Assertion -Condition ($null -ne $aliasMap.aliases) -Message '[skill_alias_map] aliases container exists' | Out-Null

    $normalizedAliasKeys = New-CaseInsensitiveSet
    $aliasNormalizedMap = @{}
    foreach ($pair in $aliasPairs) {
        $aliasKey = [string]$pair.Name
        $normalizedKey = Normalize-Key -InputText $aliasKey
        Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($normalizedKey)) -Message "[alias:$aliasKey] normalized key non-empty" | Out-Null
        Add-Assertion -Condition ($normalizedAliasKeys.Add($normalizedKey)) -Message "[alias:$aliasKey] normalized key unique" | Out-Null
        $aliasNormalizedMap[$normalizedKey] = [string]$pair.Value
    }

    foreach ($pair in $aliasPairs) {
        $aliasKey = [string]$pair.Name
        $normalizedKey = Normalize-Key -InputText $aliasKey
        $target = [string]$pair.Value
        $normalizedTarget = Normalize-Key -InputText $target

        if ($policy.alias_rules.require_non_empty_target) {
            Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($target)) -Message "[alias:$aliasKey] target non-empty" | Out-Null
        }

        Add-Assertion -Condition ($normalizedKey -ne $normalizedTarget) -Message "[alias:$aliasKey] does not self-reference" | Out-Null

        $resolution = Resolve-AliasTerminalTarget -AliasKey $aliasKey -AliasNormalizedMap $aliasNormalizedMap
        Add-Assertion -Condition (-not $resolution.cycle_detected) -Message "[alias:$aliasKey] does not participate in alias cycle" | Out-Null

        $directTargetIsAlias = $aliasNormalizedMap.ContainsKey($normalizedTarget)
        if ($policy.alias_rules.forbid_targeting_another_alias) {
            Add-Assertion -Condition (-not $directTargetIsAlias) -Message "[alias:$aliasKey] direct target is canonical skill id, not another alias" | Out-Null
        }

        $terminalTarget = if (-not [string]::IsNullOrWhiteSpace([string]$resolution.terminal_target)) { [string]$resolution.terminal_target } else { $target }
        $terminalResult = $null
        if ($policy.alias_rules.require_target_resolves -and -not $resolution.cycle_detected -and -not [string]::IsNullOrWhiteSpace($terminalTarget)) {
            $terminalResult = Validate-RoutedSkillReference -SkillId $terminalTarget -AssertionPrefix "[alias:$aliasKey] target" -SourceTags @('skill_alias_map.alias_targets') -SourceRefs @("alias:$aliasKey") -SkillRoots $skillRoots -RepoRoot $repoRoot -Policy $policy -ReservedPatterns $reservedPatterns -SkillRegistry $skillRegistry -RoutingRules $null -ExpectedTask $null -RequireCanonicalTopLevel -LockSet $skillsLockSet -RequireLockEntry
        }

        $aliasResults += [pscustomobject]@{
            alias = $aliasKey
            normalized_key = $normalizedKey
            target = $target
            normalized_target = $normalizedTarget
            direct_target_is_alias = $directTargetIsAlias
            terminal_target = $terminalTarget
            hop_count = $resolution.hop_count
            cycle_detected = $resolution.cycle_detected
            path = $resolution.path
            target_result = $terminalResult
        }
    }
}

if ($alwaysRequiredEnabled) {
    $alwaysRequiredSkills = @($policy.routed_surface_rules.always_required_skills | ForEach-Object { [string]$_ })
    $alwaysRequiredSet = New-CaseInsensitiveSet
    foreach ($skillId in $alwaysRequiredSkills) {
        Add-Assertion -Condition (-not [string]::IsNullOrWhiteSpace($skillId)) -Message "[always_required] skill id '$skillId' non-empty" | Out-Null
        Add-Assertion -Condition ($alwaysRequiredSet.Add($skillId)) -Message "[always_required] skill '$skillId' unique" | Out-Null
        $alwaysRequiredResults += Validate-RoutedSkillReference -SkillId $skillId -AssertionPrefix '[always_required]' -SourceTags @('always_required_skills') -SourceRefs @("always_required:$skillId") -SkillRoots $skillRoots -RepoRoot $repoRoot -Policy $policy -ReservedPatterns $reservedPatterns -SkillRegistry $skillRegistry -RoutingRules $null -ExpectedTask $null
    }
}

$displayNameBuckets = @{}
foreach ($entry in $skillRegistry.GetEnumerator()) {
    $value = $entry.Value
    if ([string]::IsNullOrWhiteSpace([string]$value.normalized_display_name)) {
        continue
    }

    if (-not $displayNameBuckets.ContainsKey($value.normalized_display_name)) {
        $displayNameBuckets[$value.normalized_display_name] = New-Object System.Collections.Generic.List[string]
    }
    $displayNameBuckets[$value.normalized_display_name].Add($value.skill_id)
}

$duplicateDisplayAllowlist = New-CaseInsensitiveSet
foreach ($allowedName in @($policy.skill_frontmatter_rules.duplicate_display_name_allowlist)) {
    [void]$duplicateDisplayAllowlist.Add((Normalize-DisplayName -Name ([string]$allowedName) -Policy $policy))
}

$duplicateDisplayNameViolations = @()
foreach ($bucket in $displayNameBuckets.GetEnumerator()) {
    if ($bucket.Value.Count -le 1) {
        continue
    }

    $isAllowed = $duplicateDisplayAllowlist.Contains([string]$bucket.Key)
    Add-Assertion -Condition $isAllowed -Message "[frontmatter] duplicate display name '$($bucket.Key)' explicitly allowlisted" | Out-Null
    if (-not $isAllowed) {
        $duplicateDisplayNameViolations += [pscustomobject]@{
            normalized_display_name = [string]$bucket.Key
            skill_ids = @($bucket.Value)
        }
    }
}

if ($aliasEnabled) {
    foreach ($aliasResult in $aliasResults) {
        if ($displayNameBuckets.ContainsKey($aliasResult.normalized_key)) {
            Write-Host "[WARN] [alias:$($aliasResult.alias)] normalized alias key collides with skill display name '$($aliasResult.normalized_key)'" -ForegroundColor Yellow
            $aliasDisplayNameCollisions += [pscustomobject]@{
                alias = $aliasResult.alias
                normalized_key = $aliasResult.normalized_key
                colliding_skill_ids = @($displayNameBuckets[$aliasResult.normalized_key])
            }
        }
    }
}

if ($roleSurfaceEnabled) {
    $requiredPermissionBundles = @($policy.role_surface_rules.required_permission_bundles)
    foreach ($surface in @($policy.role_surface_rules.surfaces)) {
        $surfaceId = [string]$surface.id
        $templateMarker = [string]$surface.template_marker
        $taxonomyMarker = [string]$surface.taxonomy_marker
        Add-Assertion -Condition (Test-LineContainsTokens -Lines $teamTemplateLines -Tokens @($templateMarker)) -Message "[role_surface:$surfaceId] template marker present" | Out-Null
        Add-Assertion -Condition (Test-LineContainsTokens -Lines $roleTaxonomyLines -Tokens @($taxonomyMarker)) -Message "[role_surface:$surfaceId] taxonomy marker present" | Out-Null

        $surfaceRoleResults = @()
        foreach ($role in @($surface.roles)) {
            $roleName = [string]$role.role
            $nativeAgentType = [string]$role.native_agent_type
            $permissionBundle = [string]$role.permission_bundle
            $templatePromptPath = Resolve-ManagedPath -PathSpec ([string]$role.template_prompt_path) -RepoRoot $repoRoot
            $taxonomyPromptPath = Resolve-ManagedPath -PathSpec ([string]$role.taxonomy_prompt_path) -RepoRoot $repoRoot

            Add-Assertion -Condition ($requiredPermissionBundles -contains $permissionBundle) -Message "[role_surface:$surfaceId] role '$roleName' uses declared permission bundle" | Out-Null
            Add-Assertion -Condition (Test-Path -LiteralPath $templatePromptPath) -Message "[role_surface:$surfaceId] role '$roleName' template prompt exists" | Out-Null
            Add-Assertion -Condition (Test-Path -LiteralPath $taxonomyPromptPath) -Message "[role_surface:$surfaceId] role '$roleName' taxonomy prompt exists" | Out-Null

            $templateRowOk = Test-LineContainsTokens -Lines $teamTemplateLines -Tokens @($roleName, $nativeAgentType, ([System.IO.Path]::GetFileName($templatePromptPath)))
            $taxonomyRowOk = Test-LineContainsTokens -Lines $roleTaxonomyLines -Tokens @($roleName, $nativeAgentType, $permissionBundle, ([System.IO.Path]::GetFileName($taxonomyPromptPath)))
            Add-Assertion -Condition $templateRowOk -Message "[role_surface:$surfaceId] role '$roleName' present in team template" | Out-Null
            Add-Assertion -Condition $taxonomyRowOk -Message "[role_surface:$surfaceId] role '$roleName' present in role taxonomy" | Out-Null

            $surfaceRoleResults += [pscustomobject]@{
                role = $roleName
                native_agent_type = $nativeAgentType
                permission_bundle = $permissionBundle
                template_prompt_path = $templatePromptPath
                taxonomy_prompt_path = $taxonomyPromptPath
                template_prompt_exists = (Test-Path -LiteralPath $templatePromptPath)
                taxonomy_prompt_exists = (Test-Path -LiteralPath $taxonomyPromptPath)
                team_template_row = $templateRowOk
                role_taxonomy_row = $taxonomyRowOk
            }
        }

        $roleSurfaceResults += [pscustomobject]@{
            surface_id = $surfaceId
            role_count = @($surface.roles).Count
            roles = $surfaceRoleResults
        }
    }
}

$totalAssertions = $script:assertions.Count
$passedAssertions = @($script:assertions | Where-Object { $_ }).Count
$failedAssertions = $totalAssertions - $passedAssertions
$gatePassed = ($failedAssertions -eq 0)

Write-Host ''
Write-Host '=== Summary ==='
if ($catalogEnabled) {
    Write-Host ("Capabilities checked: {0}" -f @($catalog.capabilities).Count)
}
if ($packEnabled) {
    Write-Host ("Packs checked: {0}" -f @($packManifest.packs).Count)
}
if ($aliasEnabled) {
    Write-Host ("Aliases checked: {0}" -f @($aliasResults).Count)
}
if ($alwaysRequiredEnabled) {
    Write-Host ("Always-required skills checked: {0}" -f @($alwaysRequiredResults).Count)
}
Write-Host ("Unique routed skills checked: {0}" -f $skillRegistry.Count)
if ($roleSurfaceEnabled) {
    Write-Host ("Role surfaces checked: {0}" -f $roleSurfaceResults.Count)
}
Write-Host ("Assertions passed: {0}" -f $passedAssertions)
Write-Host ("Assertions failed: {0}" -f $failedAssertions)
Write-Host ("Pack coverage warnings: {0}" -f @($packCoverageWarnings).Count)
Write-Host ("Default task routing-rule warnings: {0}" -f @($defaultTaskRoutingRuleWarnings).Count)
Write-Host ("Alias display-name collisions: {0}" -f @($aliasDisplayNameCollisions).Count)
Write-Host ("Gate Result: {0}" -f $(if ($gatePassed) { 'PASS' } else { 'FAIL' }))

$reportSources = [ordered]@{}
if ($catalogEnabled) { $reportSources.capability_catalog = $catalogPath }
if ($packEnabled) { $reportSources.pack_manifest = $packManifestPath; $reportSources.skill_routing_rules = $routingRulesPath }
if ($aliasEnabled) { $reportSources.skill_alias_map = $aliasMapPath; $reportSources.skills_lock = $skillsLockPath }
if ($roleSurfaceEnabled) { $reportSources.team_templates = $teamTemplatesPath; $reportSources.role_taxonomy = $roleTaxonomyPath }

$reportMetrics = [ordered]@{
    capability_count = if ($catalogEnabled) { @($catalog.capabilities).Count } else { 0 }
    pack_count = if ($packEnabled) { @($packManifest.packs).Count } else { 0 }
    alias_count = if ($aliasEnabled) { @($aliasResults).Count } else { 0 }
    always_required_count = if ($alwaysRequiredEnabled) { @($alwaysRequiredResults).Count } else { 0 }
    unique_skill_count = $skillRegistry.Count
    role_surface_count = $roleSurfaceResults.Count
    assertion_total = $totalAssertions
    assertion_passed = $passedAssertions
    assertion_failed = $failedAssertions
    duplicate_display_name_violations = @($duplicateDisplayNameViolations).Count
    pack_coverage_warnings = @($packCoverageWarnings).Count
    default_task_routing_rule_warnings = @($defaultTaskRoutingRuleWarnings).Count
    alias_display_name_collisions = @($aliasDisplayNameCollisions).Count
}

$report = [pscustomobject]@{
    generated_at = (Get-Date).ToString('s')
    policy = [pscustomobject]@{
        path = $policyPath
        policy_id = [string]$policy.policy_id
        version = [int]$policy.version
        mode = [string]$policy.validation_scope.mode
        enabled_sources = @($policy.validation_scope.enabled_sources)
    }
    sources = [pscustomobject]$reportSources
    metrics = [pscustomobject]$reportMetrics
    gate_passed = $gatePassed
    capability_results = $capabilityResults
    pack_results = $packResults
    alias_results = $aliasResults
    always_required_results = $alwaysRequiredResults
    routed_skills = @($skillRegistry.Values | Sort-Object skill_id)
    duplicate_display_name_violations = $duplicateDisplayNameViolations
    pack_coverage_warnings = $packCoverageWarnings
    default_task_routing_rule_warnings = $defaultTaskRoutingRuleWarnings
    alias_display_name_collisions = $aliasDisplayNameCollisions
    role_surface_results = $roleSurfaceResults
}

if ($WriteArtifacts) {
    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        $OutputDirectory = Join-Path $repoRoot 'outputs\verify'
    }

    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $jsonPath = Join-Path $OutputDirectory 'skill-metadata-gate.json'
    $mdPath = Join-Path $OutputDirectory 'skill-metadata-gate.md'

    $report | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $lines = @()
    $lines += '# VCO Skill Metadata Gate'
    $lines += ''
    $lines += "- generated_at: ``$($report.generated_at)``"
    $lines += "- gate_passed: ``$($report.gate_passed)``"
    $lines += "- capability_count: ``$($report.metrics.capability_count)``"
    $lines += "- pack_count: ``$($report.metrics.pack_count)``"
    $lines += "- alias_count: ``$($report.metrics.alias_count)``"
    $lines += "- always_required_count: ``$($report.metrics.always_required_count)``"
    $lines += "- unique_skill_count: ``$($report.metrics.unique_skill_count)``"
    $lines += "- role_surface_count: ``$($report.metrics.role_surface_count)``"
    $lines += "- assertion_failed: ``$($report.metrics.assertion_failed)``"
    $lines += "- pack_coverage_warnings: ``$($report.metrics.pack_coverage_warnings)``"
    $lines += "- default_task_routing_rule_warnings: ``$($report.metrics.default_task_routing_rule_warnings)``"
    $lines += "- alias_display_name_collisions: ``$($report.metrics.alias_display_name_collisions)``"

    if (@($duplicateDisplayNameViolations).Count -gt 0) {
        $lines += ''
        $lines += '## Duplicate Display Name Violations'
        $lines += ''
        foreach ($entry in $duplicateDisplayNameViolations) {
            $lines += "- ``$($entry.normalized_display_name)`` => $([string]::Join(', ', @($entry.skill_ids)))"
        }
    }

    if (@($packCoverageWarnings).Count -gt 0) {
        $lines += ''
        $lines += '## Pack Coverage Warnings'
        $lines += ''
        foreach ($warning in $packCoverageWarnings) {
            $lines += "- ``$($warning.pack_id)`` / ``$($warning.task)`` => $([string]::Join(', ', @($warning.skill_candidates)))"
        }
    }

    if (@($defaultTaskRoutingRuleWarnings).Count -gt 0) {
        $lines += ''
        $lines += '## Default Task Routing Rule Warnings'
        $lines += ''
        foreach ($warning in $defaultTaskRoutingRuleWarnings) {
            $lines += "- ``$($warning.assertion_prefix)`` => ``$($warning.skill_id)`` / ``$($warning.expected_task)``"
        }
    }

    if (@($aliasDisplayNameCollisions).Count -gt 0) {
        $lines += ''
        $lines += '## Alias Display Name Collisions'
        $lines += ''
        foreach ($collision in $aliasDisplayNameCollisions) {
            $lines += "- ``$($collision.alias)`` => $([string]::Join(', ', @($collision.colliding_skill_ids)))"
        }
    }

    $lines -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8

    Write-Host ''
    Write-Host 'Artifacts written:'
    Write-Host "- $jsonPath"
    Write-Host "- $mdPath"
}

if (-not $gatePassed) {
    exit 1
}

exit 0
