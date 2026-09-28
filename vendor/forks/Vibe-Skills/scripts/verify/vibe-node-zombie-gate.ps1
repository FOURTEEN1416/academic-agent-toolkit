param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "..\common\vibe-governance-helpers.ps1")

function Add-Assertion {
    param(
        [ref]$Results,
        [bool]$Condition,
        [string]$Message,
        [string]$Details = ""
    )

    $record = [pscustomobject]@{
        passed = [bool]$Condition
        message = $Message
        details = $Details
    }
    $Results.Value += $record

    if ($Condition) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
        if ($Details) {
            Write-Host "       $Details" -ForegroundColor DarkRed
        }
    }
}

function Invoke-ParsedScript {
    param(
        [string]$Path,
        [hashtable]$Parameters
    )

    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $Path), [ref]$tokens, [ref]$errors)
    if ($errors -and $errors.Count -gt 0) {
        $messages = @($errors | ForEach-Object { $_.Message }) -join "; "
        throw "Unable to parse ${Path}: $messages"
    }

    return (& $ast.GetScriptBlock() @Parameters)
}

function Get-StringSet {
    param([AllowNull()] [object[]]$Values)

    return @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [string]$_ } | Sort-Object -Unique)
}

function Get-ClassificationMap {
    param([AllowNull()] [object]$Map)

    $result = @{}
    if ($null -eq $Map) {
        return $result
    }

    if ($Map -is [System.Collections.IDictionary]) {
        foreach ($entry in $Map.GetEnumerator()) {
            $result[[string]$entry.Key] = [int]$entry.Value
        }
        return $result
    }

    foreach ($prop in $Map.PSObject.Properties) {
        $result[[string]$prop.Name] = [int]$prop.Value
    }

    return $result
}

function Compare-ClassificationMap {
    param(
        [hashtable]$Actual,
        [hashtable]$Expected
    )

    $actualKeys = @($Actual.Keys | Sort-Object)
    $expectedKeys = @($Expected.Keys | Sort-Object)
    if ((@($actualKeys) -join "|") -ne (@($expectedKeys) -join "|")) {
        return $false
    }

    foreach ($key in $expectedKeys) {
        if (-not $Actual.ContainsKey($key)) {
            return $false
        }
        if ([int]$Actual[$key] -ne [int]$Expected[$key]) {
            return $false
        }
    }

    return $true
}

function Write-GateArtifacts {
    param(
        [string]$Directory,
        [object]$Summary
    )

    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $jsonPath = Join-Path $Directory "vibe-node-zombie-gate.json"
    $mdPath = Join-Path $Directory "vibe-node-zombie-gate.md"

    $Summary | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $md = New-Object System.Text.StringBuilder
    [void]$md.AppendLine("# Vibe Node Zombie Gate")
    [void]$md.AppendLine("")
    [void]$md.AppendLine("- Generated: $($Summary.generated_at)")
    [void]$md.AppendLine("- Passed: $($Summary.gate_passed)")
    [void]$md.AppendLine("- Assertions: $($Summary.assertion_count)")
    [void]$md.AppendLine("- Failures: $($Summary.failure_count)")
    [void]$md.AppendLine("")
    [void]$md.AppendLine("## Cases")
    [void]$md.AppendLine("")
    foreach ($case in $Summary.case_summaries) {
        [void]$md.AppendLine("- $($case.case_id): classifications=$($case.classification_summary), candidates=$($case.cleanup_candidate_count)")
    }
    [void]$md.AppendLine("")
    [void]$md.AppendLine("## Failures")
    [void]$md.AppendLine("")
    $failed = @($Summary.results | Where-Object { -not $_.passed })
    if ($failed.Count -eq 0) {
        [void]$md.AppendLine("- None")
    } else {
        foreach ($item in $failed) {
            [void]$md.AppendLine("- $($item.message): $($item.details)")
        }
    }

    $md.ToString() | Set-Content -LiteralPath $mdPath -Encoding UTF8
    Write-Host "Artifacts written: $jsonPath"
    Write-Host "Artifacts written: $mdPath"
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$targetDir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    Join-Path $repoRoot "outputs\verify\node-zombie-guardian"
} elseif ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    [System.IO.Path]::GetFullPath($OutputDirectory)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
}

$fixturesDir = Join-Path $repoRoot "scripts\verify\fixtures\process-health"
$artifactsDir = Join-Path $targetDir "artifacts"
$auditScript = Join-Path $repoRoot "scripts\governance\Invoke-NodeProcessAudit.ps1"
$cleanupScript = Join-Path $repoRoot "scripts\governance\Invoke-NodeZombieCleanup.ps1"

$cases = @(
    [pscustomobject]@{
        case_id = "no-node-processes"
        fixture = Join-Path $fixturesDir "no-node-processes-fixture.json"
        expected_classifications = @{}
        expected_candidate_entry_ids = @()
        expect_report_reason = $null
        expect_apply_reason = $null
    },
    [pscustomobject]@{
        case_id = "healthy-managed"
        fixture = Join-Path $fixturesDir "healthy-managed-fixture.json"
        expected_classifications = @{ managed_live = 1 }
        expected_candidate_entry_ids = @()
        expect_report_reason = $null
        expect_apply_reason = $null
    },
    [pscustomobject]@{
        case_id = "managed-stale"
        fixture = Join-Path $fixturesDir "managed-stale-fixture.json"
        expected_classifications = @{ managed_stale = 1 }
        expected_candidate_entry_ids = @("vgo-node-stale-42001")
        expect_report_reason = "report_only_mode"
        expect_apply_reason = "fixture_mode_simulation"
    },
    [pscustomobject]@{
        case_id = "managed-completed-alive"
        fixture = Join-Path $fixturesDir "managed-completed-alive-fixture.json"
        expected_classifications = @{ managed_completed_process_alive = 1 }
        expected_candidate_entry_ids = @("vgo-node-completed-43001")
        expect_report_reason = "report_only_mode"
        expect_apply_reason = "fixture_mode_simulation"
    },
    [pscustomobject]@{
        case_id = "external-node-protected"
        fixture = Join-Path $fixturesDir "external-node-protected-fixture.json"
        expected_classifications = @{ external_audit_only = 1 }
        expected_candidate_entry_ids = @()
        expect_report_reason = $null
        expect_apply_reason = $null
    }
)

$results = @()
$caseSummaries = @()

Add-Assertion -Results ([ref]$results) -Condition (Test-Path -LiteralPath $auditScript) -Message "audit governance script exists" -Details $auditScript
Add-Assertion -Results ([ref]$results) -Condition (Test-Path -LiteralPath $cleanupScript) -Message "cleanup governance script exists" -Details $cleanupScript

foreach ($case in $cases) {
    Add-Assertion -Results ([ref]$results) -Condition (Test-Path -LiteralPath $case.fixture) -Message ("fixture exists: {0}" -f $case.case_id) -Details $case.fixture
    if (-not (Test-Path -LiteralPath $case.fixture)) {
        continue
    }

    $audit = Invoke-ParsedScript -Path $auditScript -Parameters @{
        RepoRoot = $repoRoot
        FixturePath = $case.fixture
        OutputDirectory = $artifactsDir
        WriteMarkdown = $true
        PassThru = $true
    }

    $classificationMap = Get-ClassificationMap -Map $audit.payload.summary.classifications
    $candidateEntryIds = Get-StringSet -Values @($audit.payload.rows | Where-Object { $_.cleanup_candidate } | ForEach-Object { $_.entry_id })
    $expectedCandidateEntryIds = Get-StringSet -Values $case.expected_candidate_entry_ids
    $classificationSummary = @($classificationMap.GetEnumerator() | Sort-Object Name | ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }) -join ", "

    Add-Assertion -Results ([ref]$results) -Condition ($audit.payload.case_id -eq $case.case_id) -Message ("audit case id matches fixture: {0}" -f $case.case_id)
    Add-Assertion -Results ([ref]$results) -Condition (Compare-ClassificationMap -Actual $classificationMap -Expected $case.expected_classifications) -Message ("classification map matches expectation: {0}" -f $case.case_id) -Details ("actual={0}" -f $classificationSummary)
    Add-Assertion -Results ([ref]$results) -Condition ((@($candidateEntryIds) -join "|") -eq (@($expectedCandidateEntryIds) -join "|")) -Message ("cleanup candidate set matches expectation: {0}" -f $case.case_id) -Details ("actual={0}" -f ((@($candidateEntryIds) -join ", ")))
    Add-Assertion -Results ([ref]$results) -Condition (@($audit.payload.rows | Where-Object { $_.cleanup_candidate -and $_.ownership -ne "vco-managed" }).Count -eq 0) -Message ("no non-managed cleanup candidates: {0}" -f $case.case_id)
    Add-Assertion -Results ([ref]$results) -Condition (@($audit.payload.rows | Where-Object { $_.ownership -eq "external" -and $_.cleanup_candidate }).Count -eq 0) -Message ("external rows stay audit-only: {0}" -f $case.case_id)

    $caseSummaries += [pscustomobject]@{
        case_id = $case.case_id
        classification_summary = $classificationSummary
        cleanup_candidate_count = @($candidateEntryIds).Count
        audit_artifact = $audit.artifact_path
        markdown_artifact = $audit.markdown_path
    }

    if ($null -ne $case.expect_report_reason) {
        $reportOnly = Invoke-ParsedScript -Path $cleanupScript -Parameters @{
            RepoRoot = $repoRoot
            FixturePath = $case.fixture
            OutputDirectory = $artifactsDir
            PassThru = $true
        }

        Add-Assertion -Results ([ref]$results) -Condition ([bool](-not $reportOnly.payload.apply_requested)) -Message ("cleanup defaults to report-only: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($reportOnly.payload.results).Count -eq @($expectedCandidateEntryIds).Count) -Message ("report-only cleanup result count matches candidates: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($reportOnly.payload.results | Where-Object { $_.reason -ne $case.expect_report_reason }).Count -eq 0) -Message ("report-only cleanup reason is deterministic: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($reportOnly.payload.results | Where-Object { $_.terminated }).Count -eq 0) -Message ("report-only cleanup does not terminate anything: {0}" -f $case.case_id)

        $applySimulated = Invoke-ParsedScript -Path $cleanupScript -Parameters @{
            RepoRoot = $repoRoot
            FixturePath = $case.fixture
            OutputDirectory = $artifactsDir
            Apply = $true
            PassThru = $true
        }

        Add-Assertion -Results ([ref]$results) -Condition ([bool]$applySimulated.payload.apply_requested) -Message ("apply flag is accepted for fixture simulation: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($applySimulated.payload.results | Where-Object { -not $_.simulated }).Count -eq 0) -Message ("fixture apply remains simulated: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($applySimulated.payload.results | Where-Object { $_.reason -ne $case.expect_apply_reason }).Count -eq 0) -Message ("fixture apply reason is deterministic: {0}" -f $case.case_id)
        Add-Assertion -Results ([ref]$results) -Condition (@($applySimulated.payload.results | Where-Object { $_.terminated }).Count -eq 0) -Message ("fixture apply does not terminate anything: {0}" -f $case.case_id)
    }
}

$failed = @($results | Where-Object { -not $_.passed })
$summary = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    gate_passed = ($failed.Count -eq 0)
    assertion_count = $results.Count
    failure_count = $failed.Count
    case_summaries = $caseSummaries
    results = $results
}

if ($WriteArtifacts -or $true) {
    Write-GateArtifacts -Directory $targetDir -Summary $summary
}

if ($failed.Count -gt 0) {
    throw ("vibe-node-zombie-gate failed with {0} assertion(s)." -f $failed.Count)
}

$summary | ConvertTo-Json -Depth 30
