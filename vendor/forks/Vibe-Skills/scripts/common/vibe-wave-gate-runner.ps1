param(
    [Parameter(Mandatory)] [int]$Wave,
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'vibe-governance-helpers.ps1')

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

    $color = if ($Pass) { 'Green' } else { 'Red' }
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ('[{0}] {1}' -f $status, $Message) -ForegroundColor $color
}

function Get-WaveManifestEntry {
    param(
        [Parameter(Mandatory)] [string]$RepoRoot,
        [Parameter(Mandatory)] [int]$Wave
    )

    $configRoot = Join-Path $RepoRoot 'config'
    $manifestPaths = @(
        Get-ChildItem -LiteralPath $configRoot -Filter 'wave*-gate-manifest.json' -File -ErrorAction SilentlyContinue |
            Sort-Object Name |
            ForEach-Object { $_.FullName }
    )
    if ($manifestPaths.Count -eq 0) {
        throw "no wave gate manifests found under: $configRoot"
    }

    $matches = @()
    foreach ($manifestPath in $manifestPaths) {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $matchedEntries = @($manifest.waves | Where-Object { [int]$_.wave -eq $Wave } | Select-Object -First 1)
        if ($matchedEntries.Count -gt 0) {
            $entry = $matchedEntries[0]
            $matches += [pscustomobject]@{
                manifest_path = $manifestPath
                entry = $entry
            }
        }
    }

    if ($matches.Count -eq 0) {
        throw "wave not found in any manifest: $Wave"
    }
    if ($matches.Count -gt 1) {
        $paths = @($matches | ForEach-Object { $_.manifest_path }) -join ', '
        throw "wave found in multiple manifests: $Wave -> $paths"
    }

    $selected = $matches[0]
    if (-not ($selected.entry.PSObject.Properties.Name -contains 'manifest_path')) {
        $selected.entry | Add-Member -NotePropertyName manifest_path -NotePropertyValue $selected.manifest_path
    }
    return $selected.entry
}

function Test-FileContainsKeywords {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [object[]]$Keywords,
        [Parameter(Mandatory)] [System.Collections.Generic.List[object]]$Assertions
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        foreach ($keyword in $Keywords) {
            Add-Assertion -Assertions $Assertions -Pass $false -Message ('missing file for keyword check: ' + $keyword) -Details $Path
        }
        return
    }

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $normalizedRaw = (($raw.ToLowerInvariant() -replace '[_-]+', ' ') -replace '\s+', ' ').Trim()
    foreach ($keyword in $Keywords) {
        $keywordText = [string]$keyword
        $normalizedKeyword = (($keywordText.ToLowerInvariant() -replace '[_-]+', ' ') -replace '\s+', ' ').Trim()
        $pass = $raw.Contains($keywordText) -or $normalizedRaw.Contains($normalizedKeyword)
        Add-Assertion -Assertions $Assertions -Pass $pass -Message ('keyword present: {0} -> {1}' -f $keyword, (Get-VgoRelativePathPortable -BasePath $RepoRoot -TargetPath $Path)) -Details $keyword
    }
}

function Get-LatestReleaseLedgerEntry {
    param([string]$RepoRoot)
    $ledgerPath = Join-Path $RepoRoot 'references\release-ledger.jsonl'
    if (-not (Test-Path -LiteralPath $ledgerPath)) {
        return $null
    }
    $lines = @(Get-Content -LiteralPath $ledgerPath -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -eq 0) {
        return $null
    }
    return ($lines[-1] | ConvertFrom-Json)
}

function Get-ShortGitHead {
    param([string]$RepoRoot)
    try {
        return ((git -C $RepoRoot rev-parse --short HEAD) | Select-Object -First 1).Trim()
    } catch {
        return $null
    }
}

function Get-OpsCockpitGapMatrixRows {
    param([string]$RepoRoot)

    $gapMatrixPath = Join-Path $RepoRoot 'references\ops-cockpit-gap-matrix.md'
    if (-not (Test-Path -LiteralPath $gapMatrixPath)) {
        return @()
    }

    $rows = @()
    foreach ($line in Get-Content -LiteralPath $gapMatrixPath -Encoding UTF8) {
        $trimmed = [string]$line
        if (-not $trimmed.Trim().StartsWith('|')) {
            continue
        }

        $cells = @($trimmed.Trim().Trim('|').Split('|') | ForEach-Object { $_.Trim() })
        if ($cells.Count -lt 5) {
            continue
        }

        if ($cells[0] -eq 'plane_id' -or $cells[0] -eq '---') {
            continue
        }

        $rows += [pscustomobject]@{
            plane_id = $cells[0].Trim('`')
            panel = $cells[1].Trim('`')
            blocker = $cells[2]
            evidence_ref = $cells[3].Trim('`')
            next_action = $cells[4]
        }
    }

    return @($rows)
}

function New-OpsCockpitPanelArtifact {
    param(
        [Parameter(Mandatory)] [string]$PanelId,
        [Parameter(Mandatory)] [object[]]$PlaneRows,
        [Parameter(Mandatory)] [object[]]$GapRows,
        [string]$BoardMode,
        [object]$ReleaseEntry,
        [string]$GitHead,
        [int]$VerifyArtifactCount,
        [string]$ObservabilityMode
    )

    $panelGapRows = @($GapRows | Where-Object { $_.panel -eq $PanelId })
    $planeCount = $PlaneRows.Count
    $scorecardReady = @($PlaneRows | Where-Object {
        $_.PSObject.Properties.Name -contains 'evidence' -and $_.evidence -and
        $_.evidence.PSObject.Properties.Name -contains 'scorecard_ready' -and $_.evidence.scorecard_ready -eq $true
    }).Count
    $replayReady = @($PlaneRows | Where-Object {
        $_.PSObject.Properties.Name -contains 'evidence' -and $_.evidence -and
        $_.evidence.PSObject.Properties.Name -contains 'replay_ready' -and $_.evidence.replay_ready -eq $true
    }).Count
    $rollbackReady = @($PlaneRows | Where-Object {
        $_.PSObject.Properties.Name -contains 'evidence' -and $_.evidence -and
        $_.evidence.PSObject.Properties.Name -contains 'rollback_ready' -and $_.evidence.rollback_ready -eq $true
    }).Count
    $releaseReady = @($PlaneRows | Where-Object {
        $_.PSObject.Properties.Name -contains 'evidence' -and $_.evidence -and
        $_.evidence.PSObject.Properties.Name -contains 'release_train_ready' -and $_.evidence.release_train_ready -eq $true
    }).Count

    $scorecardMissing = @($PlaneRows | Where-Object {
        -not ($_.PSObject.Properties.Name -contains 'evidence') -or
        -not $_.evidence -or
        -not ($_.evidence.PSObject.Properties.Name -contains 'scorecard_ready') -or
        $_.evidence.scorecard_ready -ne $true -or
        -not ($_.evidence.PSObject.Properties.Name -contains 'ops_cockpit_ready') -or
        $_.evidence.ops_cockpit_ready -ne $true
    })
    $replayMissing = @($PlaneRows | Where-Object {
        -not ($_.PSObject.Properties.Name -contains 'evidence') -or
        -not $_.evidence -or
        -not ($_.evidence.PSObject.Properties.Name -contains 'replay_ready') -or
        $_.evidence.replay_ready -ne $true
    })
    $rollbackMissing = @($PlaneRows | Where-Object {
        -not ($_.PSObject.Properties.Name -contains 'evidence') -or
        -not $_.evidence -or
        -not ($_.evidence.PSObject.Properties.Name -contains 'rollback_ready') -or
        $_.evidence.rollback_ready -ne $true
    })
    $releaseMissing = @($PlaneRows | Where-Object {
        -not ($_.PSObject.Properties.Name -contains 'evidence') -or
        -not $_.evidence -or
        -not ($_.evidence.PSObject.Properties.Name -contains 'release_train_ready') -or
        $_.evidence.release_train_ready -ne $true
    })

    $blockers = [System.Collections.Generic.List[string]]::new()
    $evidenceRefs = [System.Collections.Generic.List[string]]::new()
    $nextActions = [System.Collections.Generic.List[string]]::new()
    foreach ($row in $panelGapRows) {
        if (-not [string]::IsNullOrWhiteSpace([string]$row.blocker)) { $blockers.Add([string]$row.blocker) | Out-Null }
        if (-not [string]::IsNullOrWhiteSpace([string]$row.evidence_ref)) { $evidenceRefs.Add([string]$row.evidence_ref) | Out-Null }
        if (-not [string]::IsNullOrWhiteSpace([string]$row.next_action)) { $nextActions.Add([string]$row.next_action) | Out-Null }
    }

    switch ($PanelId) {
        'freshness' {
            if ($null -eq $ReleaseEntry) {
                $blockers.Add('release ledger entry missing for runtime freshness comparison') | Out-Null
            }
            $conclusion = if ($blockers.Count -gt 0) {
                'Freshness evidence still has open blockers and requires operator review before widening runtime changes.'
            } else {
                'Freshness evidence is present with no recorded cockpit blockers.'
            }
            $metrics = [ordered]@{
                git_head = $GitHead
                release_ledger_present = ($null -ne $ReleaseEntry)
                verify_artifact_count = $VerifyArtifactCount
                observability_mode = $ObservabilityMode
            }
            if ($evidenceRefs.Count -eq 0) {
                $evidenceRefs.Add('references/release-ledger.jsonl') | Out-Null
                $evidenceRefs.Add('outputs/verify/vibe-installed-runtime-freshness-gate.json') | Out-Null
            }
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('re-run runtime freshness and packaging coherence gates before release review.') | Out-Null
            }
        }
        'promotion' {
            if ($scorecardMissing.Count -gt 0) {
                $blockers.Add(('{0} plane(s) still lack scorecard or cockpit readiness' -f $scorecardMissing.Count)) | Out-Null
            }
            $conclusion = if ($blockers.Count -gt 0) {
                ('Promotion posture is incomplete: {0}/{1} planes are scorecard-ready under board mode {2}.' -f $scorecardReady, $planeCount, $BoardMode)
            } else {
                'Promotion posture is fully evidenced for the current tracked planes.'
            }
            $metrics = [ordered]@{
                board_mode = $BoardMode
                tracked_planes = $planeCount
                scorecard_ready_planes = $scorecardReady
                planes_needing_attention = @($scorecardMissing | ForEach-Object { $_.plane_id })
            }
            if ($evidenceRefs.Count -eq 0) {
                $evidenceRefs.Add('config/promotion-board.json') | Out-Null
            }
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('close promotion-board blockers before considering strict or promote stages.') | Out-Null
            }
        }
        'replay' {
            if ($replayMissing.Count -gt 0) {
                $blockers.Add(('{0} plane(s) still lack replay readiness' -f $replayMissing.Count)) | Out-Null
            }
            $conclusion = if ($blockers.Count -gt 0) {
                ('Replay coverage remains partial: {0}/{1} planes are replay-ready.' -f $replayReady, $planeCount)
            } else {
                'Replay coverage is visible and replay blockers are cleared in the cockpit.'
            }
            $metrics = [ordered]@{
                tracked_planes = $planeCount
                replay_ready_planes = $replayReady
                planes_needing_attention = @($replayMissing | ForEach-Object { $_.plane_id })
            }
            if ($evidenceRefs.Count -eq 0) {
                $evidenceRefs.Add('outputs/verify') | Out-Null
            }
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('surface replay evidence for any plane that is not yet replay-ready.') | Out-Null
            }
        }
        'rollback' {
            if ($rollbackMissing.Count -gt 0) {
                $blockers.Add(('{0} plane(s) still lack rollback readiness' -f $rollbackMissing.Count)) | Out-Null
            }
            $conclusion = if ($blockers.Count -gt 0) {
                ('Rollback readiness is incomplete: {0}/{1} planes are rollback-ready.' -f $rollbackReady, $planeCount)
            } else {
                'Rollback posture is visible and no rollback blockers are currently recorded.'
            }
            $metrics = [ordered]@{
                tracked_planes = $planeCount
                rollback_ready_planes = $rollbackReady
                planes_needing_attention = @($rollbackMissing | ForEach-Object { $_.plane_id })
            }
            if ($evidenceRefs.Count -eq 0) {
                $evidenceRefs.Add('outputs/verify/vibe-rollback-drill-gate.json') | Out-Null
            }
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('keep rollback drill evidence attached to every soft/strict candidate review.') | Out-Null
            }
        }
        'release' {
            if ($releaseMissing.Count -gt 0) {
                $blockers.Add(('{0} plane(s) still lack release_train_ready evidence' -f $releaseMissing.Count)) | Out-Null
            }
            if ($null -eq $ReleaseEntry) {
                $blockers.Add('release ledger entry missing') | Out-Null
            }
            $conclusion = if ($blockers.Count -gt 0) {
                'Release train is not ready; stop-ship blockers remain in plane evidence and/or release ledger state.'
            } else {
                'Release train evidence is present and no cockpit release blockers are recorded.'
            }
            $metrics = [ordered]@{
                tracked_planes = $planeCount
                release_ready_planes = $releaseReady
                release_ledger_present = ($null -ne $ReleaseEntry)
                planes_needing_attention = @($releaseMissing | ForEach-Object { $_.plane_id })
            }
            if ($evidenceRefs.Count -eq 0) {
                $evidenceRefs.Add('references/release-ledger.jsonl') | Out-Null
                $evidenceRefs.Add('config/promotion-board.json') | Out-Null
            }
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('finish release evidence bundle and operator handoff review before any release cut.') | Out-Null
            }
        }
        default {
            $conclusion = 'panel is governed but does not yet have a specialized summary.'
            $metrics = [ordered]@{}
            if ($nextActions.Count -eq 0) {
                $nextActions.Add('extend ops cockpit synthesis for this governed panel.') | Out-Null
            }
        }
    }

    $dedupedBlockers = @($blockers | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    $dedupedEvidence = @($evidenceRefs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    $dedupedNextActions = @($nextActions | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    if ($dedupedBlockers.Count -eq 0) { $dedupedBlockers = @('none') }
    if ($dedupedEvidence.Count -eq 0) { $dedupedEvidence = @('config/ops-cockpit-panel-contract.json') }
    if ($dedupedNextActions.Count -eq 0) { $dedupedNextActions = @('maintain governed evidence and re-run cockpit generation as part of release review.') }

    return [ordered]@{
        panel_id = $PanelId
        conclusion = $conclusion
        blockers = @($dedupedBlockers)
        evidence_ref = @($dedupedEvidence)
        next_action = @($dedupedNextActions)
        metrics = $metrics
    }
}

function New-OpsDashboardArtifacts {
    param([string]$RepoRoot)

    $boardPath = Join-Path $RepoRoot 'config\promotion-board.json'
    $contractPath = Join-Path $RepoRoot 'config\ops-cockpit-panel-contract.json'
    $observabilityPath = Join-Path $RepoRoot 'config\observability-policy.json'
    $verifyDir = Join-Path $RepoRoot 'outputs\verify'
    $dashboardDir = Join-Path $RepoRoot 'outputs\dashboard'
    $releaseEntry = Get-LatestReleaseLedgerEntry -RepoRoot $RepoRoot
    $gitHead = Get-ShortGitHead -RepoRoot $RepoRoot

    $board = if (Test-Path -LiteralPath $boardPath) { Get-Content -LiteralPath $boardPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $contract = if (Test-Path -LiteralPath $contractPath) { Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $observability = if (Test-Path -LiteralPath $observabilityPath) { Get-Content -LiteralPath $observabilityPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $verifyJson = if (Test-Path -LiteralPath $verifyDir) { @(Get-ChildItem -LiteralPath $verifyDir -Filter '*.json' | Sort-Object Name) } else { @() }
    $planeRows = if ($null -ne $board) { @($board.planes) } else { @() }
    $gapRows = Get-OpsCockpitGapMatrixRows -RepoRoot $RepoRoot
    $panelDefinitions = if ($null -ne $contract) { @($contract.panels) } else { @() }
    $verifyArtifactCount = @($verifyJson).Count
    $trackedPlaneCount = @($planeRows).Count
    $boardMode = if ($null -ne $board) { [string]$board.board_policy.mode } else { $null }
    $observabilityMode = if ($null -ne $observability) { [string]$observability.mode } else { $null }

    $actionablePanels = @()
    foreach ($panelDef in $panelDefinitions) {
        $actionablePanels += [pscustomobject](New-OpsCockpitPanelArtifact -PanelId ([string]$panelDef.panel_id) -PlaneRows $planeRows -GapRows $gapRows -BoardMode $boardMode -ReleaseEntry $releaseEntry -GitHead $gitHead -VerifyArtifactCount $verifyArtifactCount -ObservabilityMode $observabilityMode)
    }

    $artifact = [ordered]@{
        generated_at = (Get-Date).ToString('s')
        source = 'wave124_ops_dashboard_v2'
        contract = 'config/ops-cockpit-panel-contract.json'
        promotion_board = 'config/promotion-board.json'
        gap_matrix = 'references/ops-cockpit-gap-matrix.md'
        actionable_panels = @($actionablePanels)
        summary = [ordered]@{
            panel_count = @($actionablePanels).Count
            tracked_planes = $trackedPlaneCount
            release_ledger_present = ($null -ne $releaseEntry)
            verify_artifact_count = $verifyArtifactCount
        }
        evidence_refs = @(
            'config/ops-cockpit-panel-contract.json',
            'config/promotion-board.json',
            'references/ops-cockpit-gap-matrix.md',
            'references/release-ledger.jsonl',
            'outputs/verify'
        )
    }

    New-Item -ItemType Directory -Force -Path $dashboardDir | Out-Null
    $jsonPath = Join-Path $dashboardDir 'ops-dashboard.json'
    $mdPath = Join-Path $dashboardDir 'ops-dashboard.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($artifact | ConvertTo-Json -Depth 50)

    $mdLines = @(
        '# Ops Dashboard',
        '',
        ('- Generated at: `{0}`' -f $artifact.generated_at),
        ('- Contract: `{0}`' -f $artifact.contract),
        ('- Tracked planes: `{0}`' -f $artifact.summary.tracked_planes),
        '',
        '## Actionable Panels',
        ''
    )
    foreach ($panel in $artifact.actionable_panels) {
        $mdLines += ('### {0}' -f $panel.panel_id)
        $mdLines += ''
        $mdLines += ('- Conclusion: {0}' -f $panel.conclusion)
        $mdLines += '- Blockers:'
        foreach ($blocker in @($panel.blockers)) {
            $mdLines += ('  - {0}' -f $blocker)
        }
        $mdLines += '- Evidence:'
        foreach ($evidence in @($panel.evidence_ref)) {
            $mdLines += ('  - `{0}`' -f $evidence)
        }
        $mdLines += '- Next Action:'
        foreach ($nextAction in @($panel.next_action)) {
            $mdLines += ('  - {0}' -f $nextAction)
        }
        $mdLines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($mdLines -join "`n")
}

function New-ReleaseEvidenceBundle {
    param([string]$RepoRoot)
    $governancePath = Join-Path $RepoRoot 'config\version-governance.json'
    $boardPath = Join-Path $RepoRoot 'config\promotion-board.json'
    $dashboardPath = Join-Path $RepoRoot 'outputs\dashboard\ops-dashboard.json'
    $releaseReadme = Join-Path $RepoRoot 'docs\releases\README.md'
    $verifyDir = Join-Path $RepoRoot 'outputs\verify'
    $gitHead = Get-ShortGitHead -RepoRoot $RepoRoot
    $releaseEntry = Get-LatestReleaseLedgerEntry -RepoRoot $RepoRoot
    $governance = if (Test-Path -LiteralPath $governancePath) { Get-Content -LiteralPath $governancePath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $board = if (Test-Path -LiteralPath $boardPath) { Get-Content -LiteralPath $boardPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $verifyRefs = if (Test-Path -LiteralPath $verifyDir) { @(Get-ChildItem -LiteralPath $verifyDir -Filter '*.json' | Sort-Object Name | ForEach-Object { Get-VgoRelativePathPortable -BasePath $RepoRoot -TargetPath $_.FullName }) } else { @() }

    $artifact = [ordered]@{
        bundle_version = 'v3'
        generated_at = (Get-Date).ToString('s')
        version = if ($null -ne $governance) { $governance.release.version } else { $null }
        updated = if ($null -ne $governance) { $governance.release.updated } else { $null }
        git_head = $gitHead
        board_mode = if ($null -ne $board) { $board.board_policy.mode } else { $null }
        ledger_tail = $releaseEntry
        evidence_refs = [ordered]@{
            release_readme = 'docs/releases/README.md'
            promotion_board = 'config/promotion-board.json'
            ops_dashboard = 'outputs/dashboard/ops-dashboard.json'
            verify_artifacts = $verifyRefs
            release_ledger = 'references/release-ledger.jsonl'
        }
    }

    $jsonPath = Join-Path $RepoRoot 'outputs\release\release-evidence-bundle.json'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($artifact | ConvertTo-Json -Depth 100)
}

function New-RolloutSuggestionBundle {
    param([string]$RepoRoot)
    $routerPath = Join-Path $RepoRoot 'config\router-thresholds.json'
    $observabilityPath = Join-Path $RepoRoot 'config\observability-policy.json'
    if (-not (Test-Path -LiteralPath $routerPath) -or -not (Test-Path -LiteralPath $observabilityPath)) {
        throw 'router thresholds or observability policy missing for wave98 output generation.'
    }
    $router = Get-Content -LiteralPath $routerPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $observability = Get-Content -LiteralPath $observabilityPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $bounds = $observability.learning.bounded_adjustments
    $recommendations = @(
        [ordered]@{
            knob = 'confirm_required'
            current = [double]$router.thresholds.confirm_required
            proposed = [math]::Round([double]$router.thresholds.confirm_required + 0.02, 2)
            delta = 0.02
            rationale = 'slightly widen confirm-required posture for borderline ambiguous routes'
            apply_policy = 'manual_review_required'
        },
        [ordered]@{
            knob = 'fallback_to_legacy_below'
            current = [double]$router.thresholds.fallback_to_legacy_below
            proposed = [math]::Round([double]$router.thresholds.fallback_to_legacy_below - 0.02, 2)
            delta = -0.02
            rationale = 'reduce premature fallback while remaining bounded'
            apply_policy = 'manual_review_required'
        },
        [ordered]@{
            knob = 'min_top1_top2_gap'
            current = [double]$router.thresholds.min_top1_top2_gap
            proposed = [math]::Round([double]$router.thresholds.min_top1_top2_gap + 0.02, 2)
            delta = 0.02
            rationale = 'increase gap sensitivity for near-tied candidates without bypassing manual review'
            apply_policy = 'manual_review_required'
        }
    )
    $artifact = [ordered]@{
        generated_at = (Get-Date).ToString('s')
        source = 'wave98_rollout_proposal_gate'
        apply_policy = 'manual_review_required'
        bounded_adjustments = $bounds
        recommendations = $recommendations
    }
    $outPath = Join-Path $RepoRoot 'outputs\learn\vibe-adaptive-suggestions.json'
    Write-VgoUtf8NoBomText -Path $outPath -Content ($artifact | ConvertTo-Json -Depth 50)
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact,
        [string]$BaseName
    )
    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir ($BaseName + '.json')
    $mdPath = Join-Path $dir ($BaseName + '.md')
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)
    $lines = @(
        ('# ' + $Artifact.title),
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Wave: `{0}`' -f $Artifact.wave),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Failures: {0}' -f $Artifact.summary.failure_count),
        '',
        '## Assertions',
        ''
    )
    foreach ($assertion in $Artifact.assertions) {
        $lines += ('- `{0}` {1}' -f $(if ($assertion.pass) { 'PASS' } else { 'FAIL' }), $assertion.message)
    }
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$entry = Get-WaveManifestEntry -RepoRoot $repoRoot -Wave $Wave
$assertions = [System.Collections.Generic.List[object]]::new()

if ($WriteArtifacts -and $entry.PSObject.Properties.Name -contains 'write_artifacts_action') {
    switch ([string]$entry.write_artifacts_action) {
        'ops_dashboard' { New-OpsDashboardArtifacts -RepoRoot $repoRoot }
        'release_bundle' { New-ReleaseEvidenceBundle -RepoRoot $repoRoot }
        'rollout_suggestions' { New-RolloutSuggestionBundle -RepoRoot $repoRoot }
    }
}

foreach ($asset in @($entry.required_assets)) {
    $full = Join-Path $repoRoot ([string]$asset)
    Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $full) -Message ('required asset exists: ' + $asset) -Details $asset
}
if ($entry.PSObject.Properties.Name -contains 'generated_outputs') {
    foreach ($asset in @($entry.generated_outputs)) {
        $full = Join-Path $repoRoot ([string]$asset)
        Add-Assertion -Assertions $assertions -Pass (Test-Path -LiteralPath $full) -Message ('generated output exists: ' + $asset) -Details $asset
    }
}

foreach ($check in @($entry.keyword_checks)) {
    $path = Join-Path $repoRoot ([string]$check.path)
    Test-FileContainsKeywords -Path $path -Keywords @($check.keywords) -Assertions $assertions
}
if ($entry.PSObject.Properties.Name -contains 'generated_output_keywords') {
    foreach ($check in @($entry.generated_output_keywords)) {
        $path = Join-Path $repoRoot ([string]$check.path)
        Test-FileContainsKeywords -Path $path -Keywords @($check.keywords) -Assertions $assertions
    }
}

if ($Wave -eq 98) {
    $suggestionsPath = Join-Path $repoRoot 'outputs\learn\vibe-adaptive-suggestions.json'
    if (Test-Path -LiteralPath $suggestionsPath) {
        $artifact = Get-Content -LiteralPath $suggestionsPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $bounds = $artifact.bounded_adjustments
        foreach ($row in @($artifact.recommendations)) {
            if ($row.knob -eq 'confirm_required') {
                Add-Assertion -Assertions $assertions -Pass ([math]::Abs([double]$row.delta) -le [double]$bounds.confirm_required_max_delta) -Message 'confirm_required delta stays bounded' -Details $row.delta
            }
            if ($row.knob -eq 'fallback_to_legacy_below') {
                Add-Assertion -Assertions $assertions -Pass ([math]::Abs([double]$row.delta) -le [double]$bounds.fallback_threshold_max_delta) -Message 'fallback threshold delta stays bounded' -Details $row.delta
            }
            if ($row.knob -eq 'min_top1_top2_gap') {
                Add-Assertion -Assertions $assertions -Pass ([math]::Abs([double]$row.delta) -le [double]$bounds.min_top_gap_max_delta) -Message 'top-gap delta stays bounded' -Details $row.delta
            }
        }
    }
}

$failureCount = @($assertions | Where-Object { -not $_.pass }).Count
$result = if ($failureCount -eq 0) { 'PASS' } else { 'FAIL' }
$artifact = [pscustomobject]@{
    gate = [string]$entry.artifact_basename
    title = [string]$entry.title
    wave = $Wave
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = $result
    assertions = @($assertions)
    summary = [ordered]@{ total = $assertions.Count; failure_count = $failureCount }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact -BaseName ([string]$entry.artifact_basename)
}

if ($failureCount -gt 0) {
    exit 1
}
