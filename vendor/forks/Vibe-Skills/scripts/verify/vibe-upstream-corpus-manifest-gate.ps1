param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
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

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-upstream-corpus-manifest-gate.json'
    $mdPath = Join-Path $dir 'vibe-upstream-corpus-manifest-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Upstream Corpus Manifest Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Expected entries: `{0}`' -f $Artifact.summary.expected_entries),
        ('- Actual entries: `{0}`' -f $Artifact.summary.actual_entries),
        ('- Failures: `{0}`' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )
    foreach ($assertion in $Artifact.results) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Convert-PropertyBagToHashtable {
    param([object]$InputObject)

    $map = @{}
    if ($null -eq $InputObject) {
        return $map
    }

    foreach ($property in $InputObject.PSObject.Properties) {
        $map[[string]$property.Name] = $property.Value
    }

    return $map
}

function Test-LowerKebabCase {
    param([string]$Value)
    return (-not [string]::IsNullOrWhiteSpace($Value)) -and ($Value -cmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$')
}

function Test-HashtableEqual {
    param(
        [hashtable]$Expected,
        [hashtable]$Actual
    )

    if ($Expected.Count -ne $Actual.Count) {
        return $false
    }

    foreach ($key in $Expected.Keys) {
        if (-not $Actual.ContainsKey($key)) {
            return $false
        }

        if ([string]$Expected[$key] -ne [string]$Actual[$key]) {
            return $false
        }
    }

    return $true
}

function Get-CountMap {
    param([object[]]$Values)

    $map = @{}
    foreach ($value in @($Values)) {
        $key = [string]$value
        if (-not $map.ContainsKey($key)) {
            $map[$key] = 0
        }
        $map[$key]++
    }

    return $map
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot

$manifestPath = Join-Path $repoRoot 'config\upstream-corpus-manifest.json'
$aliasPath = Join-Path $repoRoot 'config\upstream-source-aliases.json'
$boardPath = Join-Path $repoRoot 'config\upstream-value-ops-board.json'
$governanceDocPath = Join-Path $repoRoot 'docs\upstream-corpus-governance.md'
$valueLedgerPath = Join-Path $repoRoot 'references\upstream-value-ledger.md'
$auditScriptPath = Join-Path $repoRoot 'scripts\governance\audit-upstream.ps1'
$expectedEntryCount = 19

$results = [System.Collections.Generic.List[object]]::new()
foreach ($pathInfo in @(
    @{ label = 'manifest'; path = $manifestPath },
    @{ label = 'alias registry'; path = $aliasPath },
    @{ label = 'value ops board'; path = $boardPath },
    @{ label = 'governance doc'; path = $governanceDocPath },
    @{ label = 'value ledger'; path = $valueLedgerPath },
    @{ label = 'audit script'; path = $auditScriptPath }
)) {
    Add-Assertion -Collection $results -Condition (Test-Path -LiteralPath $pathInfo.path) -Message ('exists: ' + $pathInfo.label) -Details $pathInfo.path
}

if (@($results | Where-Object { -not $_.pass }).Count -gt 0) {
    $artifact = [pscustomobject]@{
        gate = 'vibe-upstream-corpus-manifest-gate'
        repo_root = $repoRoot
        generated_at = (Get-Date).ToString('s')
        gate_result = 'FAIL'
        summary = [ordered]@{ expected_entries = $expectedEntryCount; actual_entries = 0; failure_count = @($results | Where-Object { -not $_.pass }).Count }
        results = @($results)
    }
    if ($WriteArtifacts) {
        Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
    }
    exit 1
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$upstreamLockPath = Join-Path $repoRoot 'config\upstream-lock.json'
$upstreamLock = Get-Content -LiteralPath $upstreamLockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$aliases = Get-Content -LiteralPath $aliasPath -Raw -Encoding UTF8 | ConvertFrom-Json
$opsBoard = Get-Content -LiteralPath $boardPath -Raw -Encoding UTF8 | ConvertFrom-Json
$governanceDoc = Get-Content -LiteralPath $governanceDocPath -Raw -Encoding UTF8
$valueLedger = Get-Content -LiteralPath $valueLedgerPath -Raw -Encoding UTF8
$auditScript = Get-Content -LiteralPath $auditScriptPath -Raw -Encoding UTF8

$slugRegex = '^[a-z0-9]+(?:-[a-z0-9]+)*$'
$actualSlugs = @($manifest.entries | ForEach-Object { [string]$_.slug })
$uniqueSlugs = @($actualSlugs | Sort-Object -Unique)
$slugLookup = @{}
foreach ($slug in $uniqueSlugs) {
    $slugLookup[$slug] = $true
}
$freshnessScopeSlugs = @($manifest.freshness_policy.scope_slugs | ForEach-Object { [string]$_ })
$uniqueFreshnessScopeSlugs = @($freshnessScopeSlugs | Sort-Object -Unique)
$lockCanonicalSlugLookup = @{}
foreach ($dep in @($upstreamLock.dependencies)) {
    $canonicalSlug = [string]$dep.canonical_slug
    if (-not [string]::IsNullOrWhiteSpace($canonicalSlug)) {
        $lockCanonicalSlugLookup[$canonicalSlug] = $true
    }
}

$requiredTopLevelFields = @($manifest.schema.required_top_level_fields)
foreach ($field in $requiredTopLevelFields) {
    Add-Assertion -Collection $results -Condition ($manifest.PSObject.Properties.Name -contains [string]$field) -Message ('manifest top-level field exists: ' + $field)
}
Add-Assertion -Collection $results -Condition ($manifest.PSObject.Properties.Name -contains 'alias_config') -Message 'manifest top-level field exists: alias_config'
Add-Assertion -Collection $results -Condition ($manifest.PSObject.Properties.Name -contains 'runtime_mirror_root') -Message 'manifest top-level field exists: runtime_mirror_root'
Add-Assertion -Collection $results -Condition ([string]$manifest.runtime_mirror_root -like '${CODEX_HOME}/*' -or [string]$manifest.runtime_mirror_root -like '${CODEX_HOME}\*') -Message 'manifest runtime_mirror_root is CODEX_HOME-scoped, not author-machine scoped' -Details $manifest.runtime_mirror_root
Add-Assertion -Collection $results -Condition ($manifest.summary.total_entries -eq $expectedEntryCount) -Message ('manifest summary.total_entries = {0}' -f $expectedEntryCount) -Details $manifest.summary.total_entries
Add-Assertion -Collection $results -Condition ($actualSlugs.Count -eq $expectedEntryCount) -Message ('manifest entries count = {0}' -f $expectedEntryCount) -Details $actualSlugs.Count
Add-Assertion -Collection $results -Condition ($uniqueSlugs.Count -eq $actualSlugs.Count) -Message 'manifest slugs are unique'
Add-Assertion -Collection $results -Condition ($actualSlugs.Count -eq $uniqueSlugs.Count) -Message 'manifest canonical slug registry has no duplicates'
Add-Assertion -Collection $results -Condition ($manifest.alias_config -eq 'config/upstream-source-aliases.json') -Message 'manifest alias_config points to canonical alias registry' -Details $manifest.alias_config
Add-Assertion -Collection $results -Condition ($freshnessScopeSlugs.Count -eq 15) -Message 'freshness scope contains 15 mirror-managed slugs' -Details $freshnessScopeSlugs
Add-Assertion -Collection $results -Condition ($freshnessScopeSlugs.Count -eq $uniqueFreshnessScopeSlugs.Count) -Message 'freshness scope slugs are unique'

foreach ($slug in $actualSlugs) {
    Add-Assertion -Collection $results -Condition ($slug -match $slugRegex) -Message ('slug is lower-kebab-case: ' + $slug) -Details $slug
}
foreach ($slug in $freshnessScopeSlugs) {
    Add-Assertion -Collection $results -Condition ($slugLookup.ContainsKey($slug)) -Message ('freshness scope slug exists in manifest: ' + $slug) -Details $slug
    Add-Assertion -Collection $results -Condition ($slug -match $slugRegex) -Message ('freshness scope slug is lower-kebab-case: ' + $slug) -Details $slug
}

$requiredEntryFields = @($manifest.schema.entry_required_fields)
$allowedLanes = @($manifest.schema.allowed_lanes)
$allowedStatuses = @($manifest.schema.allowed_statuses)
foreach ($entry in @($manifest.entries)) {
    foreach ($field in $requiredEntryFields) {
        Add-Assertion -Collection $results -Condition (-not [string]::IsNullOrWhiteSpace([string]$entry.$field)) -Message ('[{0}] field non-empty: {1}' -f $entry.slug, $field)
    }

    Add-Assertion -Collection $results -Condition ($allowedLanes -contains [string]$entry.lane) -Message ('[{0}] lane is allowed' -f $entry.slug) -Details $entry.lane
    Add-Assertion -Collection $results -Condition ($allowedStatuses -contains [string]$entry.status) -Message ('[{0}] status is allowed' -f $entry.slug) -Details $entry.status
    Add-Assertion -Collection $results -Condition (@($entry.canonical_assets).Count -ge 1) -Message ('[{0}] has canonical assets' -f $entry.slug)
}
foreach ($root in @($manifest.mirror_roots)) {
    Add-Assertion -Collection $results -Condition ([int]$root.expected_entry_count -eq $freshnessScopeSlugs.Count) -Message ('mirror root {0} expected_entry_count matches freshness scope' -f $root.id) -Details ([ordered]@{ expected_entry_count = [int]$root.expected_entry_count; scope_count = $freshnessScopeSlugs.Count })
}

$summaryLaneCounts = Convert-PropertyBagToHashtable -InputObject $manifest.summary.lane_counts
$summaryStatusCounts = Convert-PropertyBagToHashtable -InputObject $manifest.summary.status_counts
$actualLaneCounts = Get-CountMap -Values ($manifest.entries | ForEach-Object { [string]$_.lane })
$actualStatusCounts = Get-CountMap -Values ($manifest.entries | ForEach-Object { [string]$_.status })
Add-Assertion -Collection $results -Condition (Test-HashtableEqual -Expected $summaryLaneCounts -Actual $actualLaneCounts) -Message 'manifest summary lane_counts matches entry registry' -Details ([ordered]@{ expected = $summaryLaneCounts; actual = $actualLaneCounts })
Add-Assertion -Collection $results -Condition (Test-HashtableEqual -Expected $summaryStatusCounts -Actual $actualStatusCounts) -Message 'manifest summary status_counts matches entry registry' -Details ([ordered]@{ expected = $summaryStatusCounts; actual = $actualStatusCounts })

$aliasMap = Convert-PropertyBagToHashtable -InputObject $aliases.aliases
$aliasKeys = @($aliasMap.Keys | ForEach-Object { [string]$_ })
$aliasTargets = @($aliasMap.Values | ForEach-Object { [string]$_ })
Add-Assertion -Collection $results -Condition ($aliases.policy -eq 'canonical_slug_registry') -Message 'alias registry policy is canonical_slug_registry'
Add-Assertion -Collection $results -Condition ($aliases.canonical_form -eq 'lower-kebab-case') -Message 'alias registry canonical form is lower-kebab-case'
Add-Assertion -Collection $results -Condition ($aliasKeys.Count -ge 1) -Message 'alias registry contains aliases'
foreach ($aliasKey in $aliasKeys) {
    $canonicalSlug = [string]$aliasMap[$aliasKey]
    $resolvesToCanonicalRegistry = $slugLookup.ContainsKey($canonicalSlug) -or $lockCanonicalSlugLookup.ContainsKey($canonicalSlug)
    Add-Assertion -Collection $results -Condition $resolvesToCanonicalRegistry -Message ('alias resolves to canonical registry slug: {0} -> {1}' -f $aliasKey, $canonicalSlug) -Details $canonicalSlug
    Add-Assertion -Collection $results -Condition ($canonicalSlug -match $slugRegex) -Message ('alias target is canonical lower-kebab-case: ' + $canonicalSlug) -Details $canonicalSlug
}
$conflictingAliasKeys = @($aliasKeys | Where-Object { ($_ -match $slugRegex) -and $slugLookup.ContainsKey($_) -and ($aliasMap[$_] -ne $_) })
Add-Assertion -Collection $results -Condition ($conflictingAliasKeys.Count -eq 0) -Message 'alias registry does not shadow canonical slug names' -Details $conflictingAliasKeys

$boardSources = @($opsBoard.workstreams | ForEach-Object { @($_.source_projects) } | ForEach-Object { [string]$_ } | Select-Object -Unique)
Add-Assertion -Collection $results -Condition ($opsBoard.policy.forbid_unmapped_absorption -eq $true) -Message 'value ops board forbids unmapped absorption'
Add-Assertion -Collection $results -Condition ($opsBoard.policy.require_quality_bar -eq $true) -Message 'value ops board requires quality bar'
foreach ($sourceSlug in $boardSources) {
    Add-Assertion -Collection $results -Condition ($slugLookup.ContainsKey([string]$sourceSlug)) -Message ('value ops board source exists in manifest: ' + $sourceSlug) -Details $sourceSlug
    Add-Assertion -Collection $results -Condition ([string]$sourceSlug -match $slugRegex) -Message ('value ops board source uses canonical slug: ' + $sourceSlug) -Details $sourceSlug
    Add-Assertion -Collection $results -Condition (-not $aliasMap.ContainsKey([string]$sourceSlug) -or ($aliasMap[[string]$sourceSlug] -eq [string]$sourceSlug)) -Message ('value ops board source is not an alias key: ' + $sourceSlug) -Details $sourceSlug
}

foreach ($keyword in @(
    'desktopops_shadow_source',
    'canonical slug',
    'config/upstream-source-aliases.json',
    'mem0',
    'browser-use',
    'agent-s',
    'letta'
)) {
    Add-Assertion -Collection $results -Condition ($governanceDoc.Contains($keyword)) -Message ('governance doc keyword present: ' + $keyword) -Details $keyword
}
foreach ($slug in $actualSlugs) {
    Add-Assertion -Collection $results -Condition ($valueLedger.Contains($slug)) -Message ('value ledger covers slug: ' + $slug) -Details $slug
}
foreach ($keyword in @('CorpusManifestPath', 'WriteJson', 'mirror_state')) {
    Add-Assertion -Collection $results -Condition ($auditScript.Contains($keyword)) -Message ('audit script keyword present: ' + $keyword) -Details $keyword
}

$failureCount = @($results | Where-Object { -not $_.pass }).Count
$artifact = [pscustomobject]@{
    gate = 'vibe-upstream-corpus-manifest-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
    summary = [ordered]@{
        expected_entries = $expectedEntryCount
        actual_entries = $actualSlugs.Count
        alias_count = $aliasKeys.Count
        board_source_count = $boardSources.Count
        failure_count = $failureCount
    }
    results = @($results)
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) {
    exit 1
}
