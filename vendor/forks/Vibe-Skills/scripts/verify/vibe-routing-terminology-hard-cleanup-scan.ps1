param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([Parameter(Mandatory)] [string]$Path)
    Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-TextFileLines {
    param([Parameter(Mandatory)] [string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    return Get-Content -LiteralPath $Path -Encoding UTF8
}

function New-Finding {
    param(
        [Parameter(Mandatory)] [string]$Category,
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [int]$Line,
        [Parameter(Mandatory)] [string]$Pattern,
        [Parameter(Mandatory)] [string]$Text
    )
    [pscustomobject]@{
        category = $Category
        path = $Path
        line = $Line
        pattern = $Pattern
        text = $Text.Trim()
    }
}

function Test-LineHasRetiredContext {
    param([Parameter(Mandatory)] [string]$Line)
    foreach ($marker in @('retired', 'historical', 'old-format', 'old routing', 'not current', 'deprecated')) {
        if ($Line.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

function Test-LineIsNegativeAssertion {
    param([Parameter(Mandatory)] [string]$Line)

    foreach ($needle in @('assertNotIn', 'assertNotRegex', 'not in', 'forbidden', 'must not', 'do not', 'absence', 'leaked', 'retired')) {
        if ($Line.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

function Test-LineIsCompatibilityExplanation {
    param([Parameter(Mandatory)] [string]$Line)

    foreach ($needle in @('compatibility', 'compat_', 'retired input', 'migration input', 'old input', 'legacy fallback', 'retired old routing')) {
        if ($Line.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

function ConvertTo-RepoRelativePath {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Root
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ($pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathFull.Substring($rootFull.Length).TrimStart('\', '/').Replace('\', '/')
    }
    return $pathFull.Replace('\', '/')
}

function Test-PathPrefix {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string[]]$Prefixes
    )

    $normalized = $Path.Replace('\', '/').TrimStart('/')
    foreach ($prefix in $Prefixes) {
        $candidate = [string]$prefix
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        $candidate = $candidate.Replace('\', '/').TrimEnd('/')
        if ($normalized.Equals($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
        if ($normalized.StartsWith($candidate + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-BudgetScanFiles {
    param(
        [Parameter(Mandatory)] [string]$Root,
        [Parameter(Mandatory)] [string[]]$Roots,
        [string[]]$HistoricalRoots = @(),
        [string[]]$HistoricalExemptions = @()
    )

    $extensions = @('.ps1', '.py', '.json', '.md', '.yaml', '.yml', '.toml')
    $files = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($relative in $Roots) {
        $full = Join-Path $Root $relative
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            $item = Get-Item -LiteralPath $full
            $repoRelative = ConvertTo-RepoRelativePath -Path $item.FullName -Root $Root
            $isHistorical = (Test-PathPrefix -Path $repoRelative -Prefixes $HistoricalRoots) -and -not (Test-PathPrefix -Path $repoRelative -Prefixes $HistoricalExemptions)
            if (($extensions -contains $item.Extension.ToLowerInvariant()) -and -not $isHistorical -and $seen.Add($item.FullName)) {
                $files.Add($item) | Out-Null
            }
            continue
        }
        if (-not (Test-Path -LiteralPath $full -PathType Container)) {
            continue
        }
        foreach ($file in Get-ChildItem -LiteralPath $full -Recurse -File) {
            $repoRelative = ConvertTo-RepoRelativePath -Path $file.FullName -Root $Root
            $isHistorical = (Test-PathPrefix -Path $repoRelative -Prefixes $HistoricalRoots) -and -not (Test-PathPrefix -Path $repoRelative -Prefixes $HistoricalExemptions)
            if ($isHistorical) {
                continue
            }
            if (($extensions -contains $file.Extension.ToLowerInvariant()) -and $seen.Add($file.FullName)) {
                $files.Add($file) | Out-Null
            }
        }
    }

    return @($files.ToArray() | Sort-Object FullName)
}

$configPath = Join-Path $RepoRoot 'config\routing-terminology-hard-cleanup.json'
$config = Read-JsonFile -Path $configPath
$findings = New-Object System.Collections.Generic.List[object]

foreach ($relative in @($config.current_docs)) {
    $fullPath = Join-Path $RepoRoot $relative
    $lines = @(Get-TextFileLines -Path $fullPath)
    $insideCodeBlock = $false
    $insideRetiredSection = $false

    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        $trimmedLine = $lineText.Trim()

        if ($trimmedLine.StartsWith('```')) {
            $insideCodeBlock = -not $insideCodeBlock
        }

        if (-not $insideCodeBlock -and $trimmedLine -match '^##\s+') {
            $insideRetiredSection = $trimmedLine -match '^##\s+Retired'
        }

        foreach ($pattern in @($config.retired_terms)) {
            if ($lineText.IndexOf([string]$pattern, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                continue
            }
            if (-not $insideRetiredSection -and -not (Test-LineHasRetiredContext -Line $lineText)) {
                $findings.Add((New-Finding -Category 'current_doc_retired_term' -Path $relative -Line ($index + 1) -Pattern ([string]$pattern) -Text $lineText)) | Out-Null
            }
        }
    }
}

foreach ($relative in @($config.current_behavior_tests)) {
    $fullPath = Join-Path $RepoRoot $relative
    $lines = @(Get-TextFileLines -Path $fullPath)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        if ($lineText.IndexOf('assertNotIn(', [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            continue
        }
        foreach ($pattern in @($config.current_behavior_test_forbidden_patterns)) {
            if (
                [string]$pattern -eq 'specialist_recommendations' -and
                $lineText.IndexOf('no_specialist_recommendations', [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            ) {
                continue
            }
            if ($lineText.IndexOf([string]$pattern, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $findings.Add((New-Finding -Category 'current_behavior_test_retired_field_read' -Path $relative -Line ($index + 1) -Pattern ([string]$pattern) -Text $lineText)) | Out-Null
            }
        }
    }
}

$historicalDocFiles = [ordered]@{}
foreach ($relative in @($config.historical_docs)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$relative)) {
        $historicalDocFiles[[string]$relative] = $true
    }
}

if ($config.PSObject.Properties.Name -contains 'historical_doc_roots') {
    foreach ($rootRelative in @($config.historical_doc_roots)) {
        if ([string]::IsNullOrWhiteSpace([string]$rootRelative)) {
            continue
        }
        $rootPath = Join-Path $RepoRoot ([string]$rootRelative)
        if (-not (Test-Path -LiteralPath $rootPath)) {
            continue
        }
        foreach ($file in @(Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter '*.md')) {
            $relativePath = ConvertTo-RepoRelativePath -Path $file.FullName -Root $RepoRoot
            $historicalDocFiles[$relativePath] = $true
        }
    }
}

$historicalDocExemptions = @{}
foreach ($relative in @($config.current_docs)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$relative)) {
        $historicalDocExemptions[[string]$relative] = $true
    }
}
if ($config.PSObject.Properties.Name -contains 'historical_doc_exemptions') {
    foreach ($relative in @($config.historical_doc_exemptions)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$relative)) {
            $historicalDocExemptions[[string]$relative] = $true
        }
    }
}

$historicalMarkedCount = 0
$historicalRetiredTermFileCount = 0
foreach ($relative in @($historicalDocFiles.Keys | Sort-Object)) {
    if ($historicalDocExemptions.Contains([string]$relative)) {
        continue
    }

    $fullPath = Join-Path $RepoRoot ([string]$relative)
    $lines = @(Get-TextFileLines -Path $fullPath)
    if ($lines.Count -eq 0) {
        continue
    }

    $hasRetiredTerm = $false
    foreach ($lineText in @($lines)) {
        $lineString = [string]$lineText
        foreach ($pattern in @($config.retired_terms)) {
            $patternString = [string]$pattern
            if (-not [string]::IsNullOrWhiteSpace($lineString) -and $lineString.IndexOf($patternString, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $hasRetiredTerm = $true
                break
            }
        }
        if ($hasRetiredTerm) { break }
    }
    if (-not $hasRetiredTerm) {
        continue
    }

    $historicalRetiredTermFileCount += 1
    $header = (@($lines | Select-Object -First 20) -join "`n")
    $hasMarker = $false
    foreach ($marker in @($config.historical_markers)) {
        if ($header.IndexOf([string]$marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $hasMarker = $true
            break
        }
    }
    if ($hasMarker) {
        $historicalMarkedCount += 1
    } else {
        $findings.Add((New-Finding -Category 'historical_doc_unmarked_retired_term' -Path ([string]$relative) -Line 1 -Pattern 'historical_marker' -Text 'Historical document contains retired terms but lacks a retired/historical marker in the first 20 lines.')) | Out-Null
    }
}

$executionInternalCount = 0
foreach ($relative in @($config.execution_internal_scan_files)) {
    $fullPath = Join-Path $RepoRoot $relative
    $lines = @(Get-TextFileLines -Path $fullPath)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        if ([string]$lineText -and $lineText.IndexOf('specialist_dispatch', [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $executionInternalCount += 1
            $findings.Add((New-Finding -Category 'execution_internal_specialist_dispatch_reference' -Path ([string]$relative) -Line ($index + 1) -Pattern 'specialist_dispatch' -Text $lineText)) | Out-Null
        }
    }
}

$currentPolicyHelperCount = 0
$currentPolicyHelperFiles = if ($config.PSObject.Properties.Name -contains 'current_policy_helper_files') {
    @($config.current_policy_helper_files)
} else {
    @()
}
$currentPolicyHelperForbiddenPatterns = if ($config.PSObject.Properties.Name -contains 'current_policy_helper_forbidden_patterns') {
    @($config.current_policy_helper_forbidden_patterns)
} else {
    @()
}
foreach ($relative in @($currentPolicyHelperFiles)) {
    $fullPath = Join-Path $RepoRoot ([string]$relative)
    $lines = @(Get-TextFileLines -Path $fullPath)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        foreach ($pattern in @($currentPolicyHelperForbiddenPatterns)) {
            if ([string]::IsNullOrWhiteSpace([string]$pattern)) {
                continue
            }
            if ($lineText.IndexOf([string]$pattern, [System.StringComparison]::Ordinal) -ge 0) {
                $currentPolicyHelperCount += 1
                $findings.Add((New-Finding -Category 'current_policy_helper_dispatch_vocabulary_reference' -Path ([string]$relative) -Line ($index + 1) -Pattern ([string]$pattern) -Text $lineText)) | Out-Null
            }
        }
    }
}

$budgetFailures = New-Object System.Collections.Generic.List[object]
$allowedNegative = New-Object System.Collections.Generic.List[object]
$allowedHistorical = New-Object System.Collections.Generic.List[object]
$compatibilityReview = New-Object System.Collections.Generic.List[object]

$budgetTerms = @()
if ($config.PSObject.Properties.Name -contains 'retired_positive_terms') {
    $budgetTerms = @($config.retired_positive_terms | ForEach-Object { [string]$_ })
} else {
    $budgetTerms = @($config.retired_terms | ForEach-Object { [string]$_ })
}

$currentSurfaceRoots = @($config.current_surface_roots | ForEach-Object { [string]$_ })
$historicalSurfaceRoots = @($config.historical_surface_roots | ForEach-Object { [string]$_ })
$historicalSurfaceExemptions = @($config.historical_surface_exemptions | ForEach-Object { [string]$_ })
$allowedNegativeFiles = @($config.allowed_negative_files | ForEach-Object { [string]$_ })
$compatibilityReviewFiles = @($config.compatibility_review_files | ForEach-Object { [string]$_ })

$budgetFiles = @(Get-BudgetScanFiles -Root $RepoRoot -Roots $currentSurfaceRoots -HistoricalRoots $historicalSurfaceRoots -HistoricalExemptions $historicalSurfaceExemptions)
foreach ($file in $budgetFiles) {
    $relative = ConvertTo-RepoRelativePath -Path $file.FullName -Root $RepoRoot
    $lines = @(Get-TextFileLines -Path $file.FullName)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        foreach ($pattern in $budgetTerms) {
            if ([string]::IsNullOrWhiteSpace($pattern)) {
                continue
            }
            $patternText = [string]$pattern
            $matchIndex = $lineText.IndexOf($patternText, [System.StringComparison]::OrdinalIgnoreCase)
            if ($matchIndex -lt 0) {
                continue
            }
            if (
                ($patternText.Equals('primary skill', [System.StringComparison]::OrdinalIgnoreCase) -or
                    $patternText.Equals('secondary skill', [System.StringComparison]::OrdinalIgnoreCase)) -and
                ($matchIndex + $patternText.Length -lt $lineText.Length) -and
                ($lineText[$matchIndex + $patternText.Length] -eq '.')
            ) {
                continue
            }

            $finding = New-Finding -Category 'current_surface_retired_term' -Path $relative -Line ($index + 1) -Pattern $patternText -Text $lineText
            if (Test-PathPrefix -Path $relative -Prefixes $allowedNegativeFiles) {
                $allowedNegative.Add($finding) | Out-Null
                continue
            }
            if ($relative.StartsWith('tests/', [System.StringComparison]::OrdinalIgnoreCase) -and (Test-LineIsNegativeAssertion -Line $lineText)) {
                $allowedNegative.Add($finding) | Out-Null
                continue
            }
            if (Test-PathPrefix -Path $relative -Prefixes $compatibilityReviewFiles) {
                $compatibilityReview.Add($finding) | Out-Null
                continue
            }
            $budgetFailures.Add($finding) | Out-Null
        }
    }
}

foreach ($relative in @($historicalDocFiles.Keys | Sort-Object)) {
    if ($historicalDocExemptions.Contains([string]$relative)) {
        continue
    }
    if (-not (Test-PathPrefix -Path ([string]$relative) -Prefixes $historicalSurfaceRoots)) {
        continue
    }
    $fullPath = Join-Path $RepoRoot ([string]$relative)
    $lines = @(Get-TextFileLines -Path $fullPath)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $lineText = [string]$lines[$index]
        foreach ($pattern in $budgetTerms) {
            $patternText = [string]$pattern
            if ([string]::IsNullOrWhiteSpace($patternText)) {
                continue
            }
            $matchIndex = $lineText.IndexOf($patternText, [System.StringComparison]::OrdinalIgnoreCase)
            if ($matchIndex -lt 0) {
                continue
            }
            if (
                ($patternText.Equals('primary skill', [System.StringComparison]::OrdinalIgnoreCase) -or
                    $patternText.Equals('secondary skill', [System.StringComparison]::OrdinalIgnoreCase)) -and
                ($matchIndex + $patternText.Length -lt $lineText.Length) -and
                ($lineText[$matchIndex + $patternText.Length] -eq '.')
            ) {
                continue
            }
            $allowedHistorical.Add((New-Finding -Category 'allowed_historical' -Path ([string]$relative) -Line ($index + 1) -Pattern $patternText -Text $lineText)) | Out-Null
            break
        }
    }
}

$legacyBlockingFindings = @($findings.ToArray() | Where-Object { $_.category -ne 'historical_doc_unmarked_retired_term' })
$allFindings = New-Object System.Collections.Generic.List[object]
foreach ($finding in @($legacyBlockingFindings)) { $allFindings.Add($finding) | Out-Null }
foreach ($finding in @($budgetFailures.ToArray())) { $allFindings.Add($finding) | Out-Null }

$summary = [pscustomobject]@{
    current_doc_retired_term_violation_count = @($findings.ToArray() | Where-Object { $_.category -eq 'current_doc_retired_term' }).Count
    current_behavior_test_retired_field_read_count = @($findings.ToArray() | Where-Object { $_.category -eq 'current_behavior_test_retired_field_read' }).Count
    historical_doc_retired_term_file_count = [int]$historicalRetiredTermFileCount
    historical_doc_marked_retired_term_count = [int]$historicalMarkedCount
    historical_doc_unmarked_retired_term_count = @($findings.ToArray() | Where-Object { $_.category -eq 'historical_doc_unmarked_retired_term' }).Count
    execution_internal_specialist_dispatch_reference_count = [int]$executionInternalCount
    current_policy_helper_dispatch_vocabulary_reference_count = [int]$currentPolicyHelperCount
    fail_count = @($allFindings.ToArray()).Count
    allowed_negative_count = @($allowedNegative.ToArray()).Count
    allowed_historical_count = @($allowedHistorical.ToArray()).Count
    review_count = @($compatibilityReview.ToArray()).Count
}

$status = if (@($allFindings.ToArray()).Count -eq 0) { 'pass' } else { 'fail' }
$payload = [pscustomobject]@{
    status = $status
    summary = $summary
    findings = [object[]]$allFindings.ToArray()
    failures = [object[]]$budgetFailures.ToArray()
    allowed_negative = [object[]]$allowedNegative.ToArray()
    allowed_historical = [object[]]$allowedHistorical.ToArray()
    review = [object[]]$compatibilityReview.ToArray()
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 20
} else {
    '=== VCO Routing Terminology Hard Cleanup Scan ==='
    ('Current docs retired-term violations: {0}' -f [int]$summary.current_doc_retired_term_violation_count)
    ('Current behavior test retired-field reads: {0}' -f [int]$summary.current_behavior_test_retired_field_read_count)
    ('Historical docs with retired terms: {0}' -f [int]$summary.historical_doc_retired_term_file_count)
    ('Historical docs with retired marker: {0}' -f [int]$summary.historical_doc_marked_retired_term_count)
    ('Historical docs without retired marker: {0}' -f [int]$summary.historical_doc_unmarked_retired_term_count)
    ('Execution-internal specialist_dispatch allowlist references: {0}' -f [int]$summary.execution_internal_specialist_dispatch_reference_count)
    ('Current policy/helper dispatch vocabulary references: {0}' -f [int]$summary.current_policy_helper_dispatch_vocabulary_reference_count)
    ('Current surface failures: {0}' -f [int]$summary.fail_count)
    ('Allowed negative hits: {0}' -f [int]$summary.allowed_negative_count)
    ('Allowed historical hits: {0}' -f [int]$summary.allowed_historical_count)
    ('Compatibility review hits: {0}' -f [int]$summary.review_count)
    foreach ($finding in @($payload.findings)) {
        '[FAIL] {0}:{1} [{2}] {3}' -f $finding.path, $finding.line, $finding.pattern, $finding.text
    }
    if ($status -eq 'pass') {
        'Gate Result: PASS'
    } else {
        'Gate Result: FAIL'
    }
}

if ($status -ne 'pass') {
    exit 1
}
exit 0
