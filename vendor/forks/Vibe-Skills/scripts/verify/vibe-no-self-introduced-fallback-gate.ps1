param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [System.Collections.Generic.List[object]]$Assertions,
        [bool]$Pass,
        [string]$Message,
        [object]$Details = $null
    )

    $Assertions.Add([pscustomobject]@{
        pass = [bool]$Pass
        message = $Message
        details = $Details
    }) | Out-Null

    Write-Host ("[{0}] {1}" -f $(if ($Pass) { 'PASS' } else { 'FAIL' }), $Message) -ForegroundColor $(if ($Pass) { 'Green' } else { 'Red' })
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-no-self-introduced-fallback-gate.json'
    $mdPath = Join-Path $dir 'vibe-no-self-introduced-fallback-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO No Self-Introduced Fallback Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Risky addition count: `{0}`' -f $Artifact.summary.risky_addition_count),
        ('- Requirement approval present: `{0}`' -f $Artifact.summary.requirement_approval_present),
        '',
        '## Assertions',
        ''
    )

    foreach ($assertion in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }

    if (@($Artifact.risky_addition_summaries).Count -gt 0) {
        $lines += ''
        $lines += '## Risky Additions'
        $lines += ''
        foreach ($row in @($Artifact.risky_addition_summaries)) {
            $lines += ('- {0}' -f $row)
        }
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Test-GlobMatch {
    param(
        [string]$Path,
        [string[]]$Patterns
    )

    foreach ($pattern in @($Patterns)) {
        if ([System.Management.Automation.WildcardPattern]::Get($pattern, 'IgnoreCase').IsMatch($Path)) {
            return $true
        }
    }
    return $false
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$guardrailsPath = Join-Path $repoRoot 'config\implementation-guardrails.json'
$guardrails = Get-Content -LiteralPath $guardrailsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$assertions = [System.Collections.Generic.List[object]]::new()

Add-Assertion -Assertions $assertions -Pass ([string]$guardrails.self_introduced_fallback -eq 'forbidden_by_default') -Message 'implementation guardrails forbid self-introduced fallback by default'
Add-Assertion -Assertions $assertions -Pass ([bool]$guardrails.allowed_only_when_requirement_explicit) -Message 'implementation guardrails require explicit requirement approval'

$statusLines = @(git -C $repoRoot status --porcelain)
$changedRequirementDocs = @()
$changedFiles = New-Object System.Collections.Generic.List[string]
foreach ($line in $statusLines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $path = ($line.Substring(3)).Trim()
    if ([string]::IsNullOrWhiteSpace($path)) { continue }
    $path = $path.Replace('\', '/')
    $changedFiles.Add($path) | Out-Null
    if ($path -like 'docs/requirements/*.md') {
        $changedRequirementDocs += $path
    }
}

$riskyAdditions = New-Object System.Collections.Generic.List[object]
$trackedDiff = @(git -C $repoRoot diff --unified=0 --no-color HEAD --)
$currentPath = ''
foreach ($line in $trackedDiff) {
    if ($line -like '+++ b/*') {
        $currentPath = ($line.Substring(6)).Trim()
        continue
    }
    if (-not $currentPath) { continue }
    if (-not (Test-GlobMatch -Path $currentPath -Patterns @($guardrails.diff_guard.include_globs))) { continue }
    if (Test-GlobMatch -Path $currentPath -Patterns @($guardrails.diff_guard.exempt_paths)) { continue }
    if ($line -notmatch '^\+([^+].*)?$') { continue }
    $content = $line.Substring(1)
    foreach ($term in @($guardrails.diff_guard.risky_terms)) {
        if ($content -match [regex]::Escape([string]$term)) {
            $riskyAdditions.Add([pscustomobject]@{
                path = $currentPath
                line_number = 0
                term = [string]$term
                source = 'tracked_diff'
            }) | Out-Null
        }
    }
}

foreach ($path in @($changedFiles | Where-Object { $_ -notin @($trackedDiff | Where-Object { $_ -like '+++ b/*' } | ForEach-Object { $_.Substring(6).Trim() }) })) {
    if (-not (Test-GlobMatch -Path $path -Patterns @($guardrails.diff_guard.include_globs))) { continue }
    if (Test-GlobMatch -Path $path -Patterns @($guardrails.diff_guard.exempt_paths)) { continue }
    $fullPath = Join-Path $repoRoot ($path.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $fullPath)) { continue }
    $lineNumber = 0
    foreach ($content in Get-Content -LiteralPath $fullPath -Encoding UTF8) {
        $lineNumber++
        foreach ($term in @($guardrails.diff_guard.risky_terms)) {
            if ($content -match [regex]::Escape([string]$term)) {
                $riskyAdditions.Add([pscustomobject]@{
                    path = $path
                    line_number = $lineNumber
                    term = [string]$term
                    source = 'untracked_file'
                }) | Out-Null
            }
        }
    }
}

$approvalMarkers = @($guardrails.required_approval_markers)
$requirementApprovalPresent = $false
foreach ($requirementPath in @($changedRequirementDocs)) {
    $fullRequirementPath = Join-Path $repoRoot ($requirementPath.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $fullRequirementPath)) { continue }
    $text = Get-Content -LiteralPath $fullRequirementPath -Raw -Encoding UTF8
    $hasAll = $true
    foreach ($marker in $approvalMarkers) {
        if (-not $text.Contains([string]$marker)) {
            $hasAll = $false
            break
        }
    }
    if ($hasAll) {
        $requirementApprovalPresent = $true
        break
    }
}

Add-Assertion -Assertions $assertions -Pass (($riskyAdditions.Count -eq 0) -or $requirementApprovalPresent) -Message 'risky fallback additions require an explicitly approved requirement document' -Details ([pscustomobject]@{
    risky_addition_count = $riskyAdditions.Count
    changed_requirement_docs = @($changedRequirementDocs)
})

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
$riskyAdditionSummaries = @($riskyAdditions | ForEach-Object {
    '{0} line {1} term {2} ({3})' -f $_.path, $_.line_number, $_.term, $_.source
})
$summary = @{}
$summary['failure_count'] = $failureCount
$summary['risky_addition_count'] = $riskyAdditions.Count
$summary['requirement_approval_present'] = $requirementApprovalPresent
$artifactData = @{}
$artifactData['gate'] = 'vibe-no-self-introduced-fallback-gate'
$artifactData['repo_root'] = $repoRoot
$artifactData['gate_result'] = $gateResult
$artifactData['generated_at'] = (Get-Date).ToString('s')
$artifactData['assertions'] = @($assertions)
$artifactData['risky_addition_summaries'] = $riskyAdditionSummaries
$artifactData['summary'] = (New-Object psobject -Property $summary)
$artifact = New-Object psobject -Property $artifactData

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failureCount -gt 0) {
    exit 1
}
