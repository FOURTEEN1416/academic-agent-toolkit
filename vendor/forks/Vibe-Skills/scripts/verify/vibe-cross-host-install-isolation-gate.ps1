param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Add-Assertion {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [System.Collections.Generic.List[object]]$Assertions,
        [Parameter(Mandatory)] [bool]$Pass,
        [Parameter(Mandatory)] [string]$Message,
        [AllowNull()] [object]$Details = $null
    )

    [void]$Assertions.Add([pscustomobject]@{
        pass = [bool]$Pass
        message = [string]$Message
        details = $Details
    })

    if ($Pass) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
    }
}

function Write-GateArtifacts {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [AllowEmptyString()] [string]$OutputDirectory,
        [Parameter(Mandatory)] [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $jsonPath = Join-Path $dir 'vibe-cross-host-install-isolation-gate.json'
    $mdPath = Join-Path $dir 'vibe-cross-host-install-isolation-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO Cross-Host Install Isolation Gate (Diff-Based)',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Changed paths examined: {0}' -f $Artifact.summary.changed_path_count),
        ('- Approved protected-path changes: {0}' -f $Artifact.summary.approved_change_count),
        ('- Violations: {0}' -f $Artifact.summary.violation_count),
        '',
        '## Notes',
        '',
        '- This gate enforces the official-runtime main-chain freeze by default.',
        '- Protected-path edits only pass when they are covered by an active, file-scoped policy window.',
        '- It is intentionally conservative and uses `git status --porcelain` as the evidence source.',
        '',
        '## Assertions',
        ''
    )

    foreach ($a in @($Artifact.assertions)) {
        $lines += ('- `{0}` {1}' -f $(if ($a.pass) { 'PASS' } else { 'FAIL' }), $a.message)
    }

    if (@($Artifact.approved_changes).Count -gt 0) {
        $lines += ''
        $lines += '## Approved Protected-Path Changes'
        $lines += ''
        foreach ($item in @($Artifact.approved_changes)) {
            $lines += ('- {0} :: `{1}`' -f $item.window_id, $item.path)
        }
    }

    if (@($Artifact.violations).Count -gt 0) {
        $lines += ''
        $lines += '## Violations'
        $lines += ''
        foreach ($v in @($Artifact.violations)) {
            $lines += ('- {0}' -f $v)
        }
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

function Get-GitStatusPaths {
    param([Parameter(Mandatory)][string]$RepoRoot)

    $out = & git -C $RepoRoot status --porcelain=v1 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed with exit code $LASTEXITCODE"
    }

    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($line in @($out)) {
        $t = [string]$line
        if ([string]::IsNullOrWhiteSpace($t)) { continue }

        if ($t.Length -lt 4) { continue }
        $pathPart = $t.Substring(3)

        # Handle rename: "R  old -> new"
        if ($pathPart -like '* -> *') {
            $parts = $pathPart -split ' -> '
            foreach ($p in $parts) {
                if (-not [string]::IsNullOrWhiteSpace($p)) { [void]$paths.Add([string]$p) }
            }
        } else {
            [void]$paths.Add([string]$pathPart)
        }
    }

    return @($paths)
}

function Test-PathMatch {
    param(
        [Parameter(Mandatory)][string]$Path,
        [AllowEmptyCollection()][string[]]$Exact = @(),
        [AllowEmptyCollection()][string[]]$Prefixes = @()
    )

    $normalized = ([string]$Path).Replace('\', '/').ToLowerInvariant()
    foreach ($exact in @($Exact)) {
        if ($normalized -eq ([string]$exact).Replace('\', '/').ToLowerInvariant()) {
            return $true
        }
    }

    foreach ($prefix in @($Prefixes)) {
        if ($normalized.StartsWith(([string]$prefix).Replace('\', '/').ToLowerInvariant())) {
            return $true
        }
    }

    return $false
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = [string]$context.repoRoot

$assertions = [System.Collections.Generic.List[object]]::new()
$violations = [System.Collections.Generic.List[string]]::new()
$approvedChanges = [System.Collections.Generic.List[object]]::new()
$policyIssues = [System.Collections.Generic.List[string]]::new()

$gitOk = $true
try {
    & git --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { $gitOk = $false }
} catch {
    $gitOk = $false
}
Add-Assertion -Assertions $assertions -Pass $gitOk -Message 'git is available for diff-based isolation checks' -Details $null

$changed = @()
if ($gitOk) {
    try {
        $changed = Get-GitStatusPaths -RepoRoot $repoRoot
        Add-Assertion -Assertions $assertions -Pass $true -Message 'git status parsed' -Details ("paths={0}" -f $changed.Count)
    } catch {
        Add-Assertion -Assertions $assertions -Pass $false -Message 'git status parsed' -Details $_.Exception.Message
        $gitOk = $false
    }
}

$policyPath = Join-Path $repoRoot 'config\official-runtime-main-chain-policy.json'
$policyExists = Test-Path -LiteralPath $policyPath
Add-Assertion -Assertions $assertions -Pass $policyExists -Message 'official-runtime main-chain policy exists' -Details 'config/official-runtime-main-chain-policy.json'

$protectedPrefixes = @('scripts/router/', 'scripts/bootstrap/')
$protectedExact = @('install.ps1', 'check.ps1', 'install.sh', 'check.sh', 'config/version-governance.json')
$approvedWindows = @()

if ($policyExists) {
    try {
        $policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $policy.protected_prefixes) { $protectedPrefixes = @($policy.protected_prefixes) }
        if ($null -ne $policy.protected_exact) { $protectedExact = @($policy.protected_exact) }
        if ($null -ne $policy.approved_change_windows) { $approvedWindows = @($policy.approved_change_windows) }
        Add-Assertion -Assertions $assertions -Pass $true -Message 'official-runtime main-chain policy parsed' -Details $null
    } catch {
        Add-Assertion -Assertions $assertions -Pass $false -Message 'official-runtime main-chain policy parsed' -Details $_.Exception.Message
    }
}

foreach ($window in @($approvedWindows)) {
    $windowId = [string]$window.id
    if ([string]::IsNullOrWhiteSpace($windowId)) {
        [void]$policyIssues.Add('approved change window has no id')
        continue
    }

    $planRel = [string]$window.plan
    if ([string]::IsNullOrWhiteSpace($planRel)) {
        [void]$policyIssues.Add(("window '{0}' is missing plan reference" -f $windowId))
    } else {
        $planPath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath $planRel
        if (-not (Test-Path -LiteralPath $planPath)) {
            [void]$policyIssues.Add(("window '{0}' references missing plan '{1}'" -f $windowId, $planRel))
        }
    }

    foreach ($evidenceRel in @($window.required_evidence)) {
        $evidencePath = ConvertTo-VgoFullPath -BasePath $repoRoot -RelativePath ([string]$evidenceRel)
        if (-not (Test-Path -LiteralPath $evidencePath)) {
            [void]$policyIssues.Add(("window '{0}' references missing evidence file '{1}'" -f $windowId, [string]$evidenceRel))
        }
    }
}

Add-Assertion -Assertions $assertions -Pass ($policyIssues.Count -eq 0) -Message 'official-runtime main-chain policy windows are valid' -Details ($policyIssues -join '; ')

foreach ($path in @($changed)) {
    $p = ([string]$path).Replace('\', '/')
    $isProtected = Test-PathMatch -Path $p -Exact $protectedExact -Prefixes $protectedPrefixes

    if ($isProtected) {
        $approvedWindow = $null
        foreach ($window in @($approvedWindows)) {
            if ([string]$window.status -ne 'active') { continue }
            if (Test-PathMatch -Path $p -Exact @($window.allowed_paths) -Prefixes @()) {
                $approvedWindow = $window
                break
            }
        }

        if ($null -ne $approvedWindow) {
            [void]$approvedChanges.Add([pscustomobject]@{
                path = $p
                window_id = [string]$approvedWindow.id
                plan = [string]$approvedWindow.plan
            })
        } else {
            [void]$violations.Add($p)
        }
    }
}

Add-Assertion -Assertions $assertions -Pass ($approvedChanges.Count -eq 0 -or $policyIssues.Count -eq 0) -Message 'approved protected-path changes are backed by a valid change window' -Details (($approvedChanges | ForEach-Object { "{0}::{1}" -f $_.window_id, $_.path }) -join ',')
Add-Assertion -Assertions $assertions -Pass ($violations.Count -eq 0) -Message 'no unapproved official-runtime main-chain files changed' -Details ($violations -join ',')

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$gateResult = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }

$artifact = [pscustomobject]@{
    gate = 'vibe-cross-host-install-isolation-gate'
    mode = 'diff-based'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $gateResult
    assertions = @($assertions)
    approved_changes = @($approvedChanges)
    violations = @($violations)
    summary = [pscustomobject]@{
        changed_path_count = @($changed).Count
        approved_change_count = $approvedChanges.Count
        violation_count = $violations.Count
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($gateResult -ne 'PASS') {
    exit 1
}
