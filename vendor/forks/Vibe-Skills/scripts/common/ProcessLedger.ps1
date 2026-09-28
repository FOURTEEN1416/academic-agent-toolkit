Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot 'vibe-governance-helpers.ps1')

function Get-VgoUtcTimestamp {
    return (Get-Date).ToUniversalTime().ToString('o')
}

function Test-VgoIsWindows {
    if (Get-Variable -Name IsWindows -Scope Global -ErrorAction SilentlyContinue) {
        return [bool]$global:IsWindows
    }

    return ($env:OS -eq 'Windows_NT')
}

function ConvertFrom-VgoNullableTimestamp {
    param([AllowNull()] [object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return [datetimeoffset]::Parse(
            $text,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        )
    } catch {
        return $null
    }
}

function Get-VgoElapsedSeconds {
    param(
        [AllowNull()] [object]$Timestamp,
        [AllowNull()] [datetimeoffset]$Now
    )

    $parsed = ConvertFrom-VgoNullableTimestamp -Value $Timestamp
    if ($null -eq $parsed) {
        return $null
    }

    $baseline = if ($null -ne $Now) { $Now } else { [datetimeoffset]::UtcNow }
    return [int][Math]::Max(0, [Math]::Floor(($baseline - $parsed).TotalSeconds))
}

function Get-VgoProcessHealthContext {
    param([string]$RepoRoot)

    $resolvedRoot = if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
        Resolve-VgoRepoRoot -StartPath $PSScriptRoot
    } else {
        [System.IO.Path]::GetFullPath($RepoRoot)
    }

    $healthPolicyPath = Join-Path $resolvedRoot 'config\process-health-policy.json'
    $ledgerPolicyPath = Join-Path $resolvedRoot 'config\process-ledger-policy.json'

    if (-not (Test-Path -LiteralPath $healthPolicyPath)) {
        throw "Missing process-health policy: $healthPolicyPath"
    }
    if (-not (Test-Path -LiteralPath $ledgerPolicyPath)) {
        throw "Missing process-ledger policy: $ledgerPolicyPath"
    }

    $healthPolicy = Get-Content -LiteralPath $healthPolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $ledgerPolicy = Get-Content -LiteralPath $ledgerPolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json

    $runtimeRoot = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.runtime_root)
    $ledgerPath = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.ledger)
    $eventsPath = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.events)
    $heartbeatsDir = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.heartbeats)
    $auditsDir = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.audits)
    $cleanupsDir = Join-Path $resolvedRoot ([string]$ledgerPolicy.paths.cleanups)

    return [pscustomobject]@{
        repoRoot = $resolvedRoot
        healthPolicyPath = $healthPolicyPath
        ledgerPolicyPath = $ledgerPolicyPath
        healthPolicy = $healthPolicy
        ledgerPolicy = $ledgerPolicy
        runtimeRoot = $runtimeRoot
        ledgerPath = $ledgerPath
        eventsPath = $eventsPath
        heartbeatsDir = $heartbeatsDir
        auditsDir = $auditsDir
        cleanupsDir = $cleanupsDir
    }
}

function Initialize-VgoProcessHealthRuntime {
    param([string]$RepoRoot)

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    foreach ($dir in @($context.runtimeRoot, $context.heartbeatsDir, $context.auditsDir, $context.cleanupsDir)) {
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    if (-not (Test-Path -LiteralPath $context.ledgerPath)) {
        $initialLedger = [ordered]@{
            version = [int]$context.ledgerPolicy.schema_version
            updated_at = $null
            entries = @()
        }
        Write-VgoUtf8NoBomText -Path $context.ledgerPath -Content ($initialLedger | ConvertTo-Json -Depth 20)
    }

    return $context
}

function Get-VgoProcessLedgerMutexName {
    param([string]$RepoRoot)

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    $prefix = [string]$context.ledgerPolicy.locking.named_mutex_prefix
    if ([string]::IsNullOrWhiteSpace($prefix)) {
        $prefix = 'Global\VgoProcessLedger'
    }

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($context.repoRoot))
    } finally {
        $sha256.Dispose()
    }

    $repoHash = [System.BitConverter]::ToString($hashBytes).Replace('-', '').Substring(0, 16)

    return '{0}_{1}' -f $prefix, $repoHash
}

function Invoke-VgoProcessLedgerLocked {
    param(
        [string]$RepoRoot,
        [Parameter(Mandatory)] [scriptblock]$ScriptBlock
    )

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    $mutexName = Get-VgoProcessLedgerMutexName -RepoRoot $context.repoRoot
    $timeoutSec = [int]$context.ledgerPolicy.locking.wait_timeout_sec
    $createdNew = $false
    $mutex = [System.Threading.Mutex]::new($false, $mutexName, [ref]$createdNew)
    $lockAcquired = $false

    try {
        try {
            $lockAcquired = $mutex.WaitOne([TimeSpan]::FromSeconds($timeoutSec))
        } catch [System.Threading.AbandonedMutexException] {
            $lockAcquired = $true
        }

        if (-not $lockAcquired) {
            throw "Timed out waiting for process ledger mutex '$mutexName'."
        }

        return (& $ScriptBlock $context)
    } finally {
        if ($lockAcquired) {
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

function Get-VgoProcessLedger {
    param(
        [string]$RepoRoot,
        [AllowNull()] [object]$LedgerOverride
    )

    if ($null -ne $LedgerOverride) {
        return $LedgerOverride
    }

    Initialize-VgoProcessHealthRuntime -RepoRoot $RepoRoot | Out-Null

    return Invoke-VgoProcessLedgerLocked -RepoRoot $RepoRoot -ScriptBlock {
        param($Context)
        Get-Content -LiteralPath $Context.ledgerPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
}

function Write-VgoProcessLedgerEventUnsafe {
    param(
        [Parameter(Mandatory)] $Context,
        [Parameter(Mandatory)] [hashtable]$Event
    )

    $payload = [ordered]@{
        timestamp = Get-VgoUtcTimestamp
        event = [string]$Event.event
        entry_id = $Event.entry_id
        pid = $Event.pid
        launcher_pid = $Event.launcher_pid
        status = $Event.status
        note = $Event.note
        data = $Event.data
    }

    Append-VgoUtf8NoBomText -Path $Context.eventsPath -Content (($payload | ConvertTo-Json -Depth 20 -Compress) + [Environment]::NewLine)
}

function New-VgoProcessLedgerEntryId {
    return ('vgo-node-{0}' -f ([guid]::NewGuid().ToString('N')))
}

function Update-VgoProcessLedgerEntry {
    param(
        [Parameter(Mandatory)] [string]$EntryId,
        [Parameter(Mandatory)] [hashtable]$Patch,
        [string]$RepoRoot,
        [string]$EventType = 'entry.updated',
        [string]$Note
    )

    Initialize-VgoProcessHealthRuntime -RepoRoot $RepoRoot | Out-Null

    return Invoke-VgoProcessLedgerLocked -RepoRoot $RepoRoot -ScriptBlock {
        param($Context)

        $ledger = Get-Content -LiteralPath $Context.ledgerPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $entries = @($ledger.entries)
        $found = $false
        $updatedEntry = $null

        for ($index = 0; $index -lt $entries.Count; $index++) {
            if ([string]$entries[$index].entry_id -ne $EntryId) {
                continue
            }

            foreach ($key in $Patch.Keys) {
                $entries[$index] | Add-Member -NotePropertyName $key -NotePropertyValue $Patch[$key] -Force
            }
            $updatedEntry = $entries[$index]
            $found = $true
            break
        }

        if (-not $found) {
            throw "Ledger entry not found: $EntryId"
        }

        $ledger | Add-Member -NotePropertyName entries -NotePropertyValue $entries -Force
        $ledger | Add-Member -NotePropertyName updated_at -NotePropertyValue (Get-VgoUtcTimestamp) -Force
        Write-VgoUtf8NoBomText -Path $Context.ledgerPath -Content ($ledger | ConvertTo-Json -Depth 40)

        Write-VgoProcessLedgerEventUnsafe -Context $Context -Event @{
            event = $EventType
            entry_id = $updatedEntry.entry_id
            pid = $updatedEntry.pid
            launcher_pid = $updatedEntry.launcher_pid
            status = $updatedEntry.status
            note = $Note
            data = $Patch
        }

        return $updatedEntry
    }
}

function Register-VgoProcessLedgerEntry {
    param(
        [Parameter(Mandatory)] [hashtable]$Entry,
        [string]$RepoRoot,
        [string]$Note = 'registered'
    )

    $context = Initialize-VgoProcessHealthRuntime -RepoRoot $RepoRoot
    $defaults = $context.ledgerPolicy.defaults
    $entryId = if ($Entry.ContainsKey('entry_id') -and $null -ne $Entry.entry_id -and -not [string]::IsNullOrWhiteSpace([string]$Entry.entry_id)) { [string]$Entry.entry_id } else { New-VgoProcessLedgerEntryId }
    $startedAt = if ($Entry.ContainsKey('started_at') -and $null -ne $Entry.started_at -and -not [string]::IsNullOrWhiteSpace([string]$Entry.started_at)) { [string]$Entry.started_at } else { Get-VgoUtcTimestamp }

    $normalizedEntry = [ordered]@{
        entry_id = $entryId
        label = if ($Entry.ContainsKey('label') -and $null -ne $Entry.label -and -not [string]::IsNullOrWhiteSpace([string]$Entry.label)) { [string]$Entry.label } else { 'node-runtime' }
        owner_id = if ($Entry.ContainsKey('owner_id') -and $null -ne $Entry.owner_id -and -not [string]::IsNullOrWhiteSpace([string]$Entry.owner_id)) { [string]$Entry.owner_id } else { $env:USERNAME }
        pid = if ($Entry.ContainsKey('pid')) { [int]$Entry.pid } else { $null }
        launcher_pid = if ($Entry.ContainsKey('launcher_pid')) { [int]$Entry.launcher_pid } else { $null }
        working_directory = if ($Entry.ContainsKey('working_directory') -and $null -ne $Entry.working_directory -and -not [string]::IsNullOrWhiteSpace([string]$Entry.working_directory)) { [string]$Entry.working_directory } else { $null }
        command_line = if ($Entry.ContainsKey('command_line') -and $null -ne $Entry.command_line -and -not [string]::IsNullOrWhiteSpace([string]$Entry.command_line)) { [string]$Entry.command_line } else { $null }
        status = if ($Entry.ContainsKey('status') -and $null -ne $Entry.status -and -not [string]::IsNullOrWhiteSpace([string]$Entry.status)) { [string]$Entry.status } else { [string]$defaults.status }
        started_at = $startedAt
        closed_at = if ($Entry.ContainsKey('closed_at') -and $null -ne $Entry.closed_at -and -not [string]::IsNullOrWhiteSpace([string]$Entry.closed_at)) { [string]$Entry.closed_at } else { $null }
        last_heartbeat_at = if ($Entry.ContainsKey('last_heartbeat_at') -and $null -ne $Entry.last_heartbeat_at -and -not [string]::IsNullOrWhiteSpace([string]$Entry.last_heartbeat_at)) { [string]$Entry.last_heartbeat_at } else { $startedAt }
        last_seen_alive_at = if ($Entry.ContainsKey('last_seen_alive_at') -and $null -ne $Entry.last_seen_alive_at -and -not [string]::IsNullOrWhiteSpace([string]$Entry.last_seen_alive_at)) { [string]$Entry.last_seen_alive_at } else { $startedAt }
        heartbeat_path = if ($Entry.ContainsKey('heartbeat_path') -and $null -ne $Entry.heartbeat_path -and -not [string]::IsNullOrWhiteSpace([string]$Entry.heartbeat_path)) { [string]$Entry.heartbeat_path } else { $null }
        ownership = if ($Entry.ContainsKey('ownership') -and $null -ne $Entry.ownership -and -not [string]::IsNullOrWhiteSpace([string]$Entry.ownership)) { [string]$Entry.ownership } else { [string]$defaults.ownership }
        cleanup_safe = if ($Entry.ContainsKey('cleanup_safe')) { [bool]$Entry.cleanup_safe } else { [bool]$defaults.cleanup_safe }
        stale_after_sec = if ($Entry.ContainsKey('stale_after_sec')) { [int]$Entry.stale_after_sec } else { [int]$defaults.stale_after_sec }
        heartbeat_interval_sec = if ($Entry.ContainsKey('heartbeat_interval_sec')) { [int]$Entry.heartbeat_interval_sec } else { [int]$defaults.heartbeat_interval_sec }
        node_pid_confirmed = if ($Entry.ContainsKey('node_pid_confirmed')) { [bool]$Entry.node_pid_confirmed } else { $false }
        target_process_name = if ($Entry.ContainsKey('target_process_name') -and $null -ne $Entry.target_process_name -and -not [string]::IsNullOrWhiteSpace([string]$Entry.target_process_name)) { [string]$Entry.target_process_name } else { $null }
    }

    return Invoke-VgoProcessLedgerLocked -RepoRoot $RepoRoot -ScriptBlock {
        param($LockedContext)
        $ledger = Get-Content -LiteralPath $LockedContext.ledgerPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $entries = @($ledger.entries)
        $entries += ([pscustomobject]$normalizedEntry)
        $ledger | Add-Member -NotePropertyName entries -NotePropertyValue $entries -Force
        $ledger | Add-Member -NotePropertyName updated_at -NotePropertyValue (Get-VgoUtcTimestamp) -Force
        Write-VgoUtf8NoBomText -Path $LockedContext.ledgerPath -Content ($ledger | ConvertTo-Json -Depth 40)

        Write-VgoProcessLedgerEventUnsafe -Context $LockedContext -Event @{
            event = 'entry.registered'
            entry_id = $normalizedEntry.entry_id
            pid = $normalizedEntry.pid
            launcher_pid = $normalizedEntry.launcher_pid
            status = $normalizedEntry.status
            note = $Note
            data = $normalizedEntry
        }

        return [pscustomobject]$normalizedEntry
    }
}

function Complete-VgoProcessLedgerEntry {
    param(
        [Parameter(Mandatory)] [string]$EntryId,
        [string]$RepoRoot,
        [string]$FinalStatus = 'completed',
        [string]$Note = 'completed'
    )

    return Update-VgoProcessLedgerEntry -EntryId $EntryId -RepoRoot $RepoRoot -EventType 'entry.completed' -Note $Note -Patch @{
        status = $FinalStatus
        closed_at = Get-VgoUtcTimestamp
    }
}

function Write-VgoProcessHeartbeatFile {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$EntryId,
        [Parameter(Mandatory)] [string]$State,
        [string]$Note,
        [int]$ProcessId,
        [int]$LauncherPid
    )

    $payload = [ordered]@{
        entry_id = $EntryId
        state = $State
        pid = if ($ProcessId -gt 0) { $ProcessId } else { $null }
        launcher_pid = if ($LauncherPid -gt 0) { $LauncherPid } else { $null }
        note = $Note
        updated_at = Get-VgoUtcTimestamp
    }

    Write-VgoUtf8NoBomText -Path $Path -Content ($payload | ConvertTo-Json -Depth 10)
}

function Test-VgoNodeProcessName {
    param(
        [AllowNull()] [string]$ProcessName,
        [AllowNull()] [object]$HealthPolicy
    )

    if ([string]::IsNullOrWhiteSpace($ProcessName)) {
        return $false
    }

    $names = if ($HealthPolicy -and $HealthPolicy.process_detection -and $HealthPolicy.process_detection.node_process_names) {
        @($HealthPolicy.process_detection.node_process_names | ForEach-Object { [string]$_ })
    } else {
        @('node', 'node.exe')
    }

    return ($names -contains $ProcessName.ToLowerInvariant())
}

function Test-VgoProcessAlive {
    param([Nullable[int]]$ProcessId)

    if ($null -eq $ProcessId -or $ProcessId -le 0) {
        return $false
    }

    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Get-VgoWindowsProcessMetadata {
    param([AllowNull()] [int[]]$Pids)

    $metadata = @{}
    $uniquePids = @($Pids | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    foreach ($processId in $uniquePids) {
        try {
            $proc = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $processId) -OperationTimeoutSec 2 -ErrorAction Stop
            if ($null -eq $proc) {
                continue
            }

            $metadata[[string]$processId] = [pscustomobject]@{
                pid = [int]$proc.ProcessId
                parent_pid = [int]$proc.ParentProcessId
                process_name = [string]$proc.Name
                command_line = [string]$proc.CommandLine
            }
        } catch {
            continue
        }
    }

    return $metadata
}

function Get-VgoLiveNodeProcessSnapshot {
    param([string]$RepoRoot)

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    $healthPolicy = $context.healthPolicy

    $rows = @()
    if (Test-VgoIsWindows) {
        $processes = @(Get-Process -Name node,node.exe -ErrorAction SilentlyContinue)
        foreach ($proc in $processes) {
            $processId = [int]$proc.Id
            $workingSetBytes = [int64]$proc.WorkingSet64

            $rows += [pscustomobject]@{
                pid = $processId
                parent_pid = $null
                process_name = [string]$proc.ProcessName
                command_line = $null
                working_set_bytes = [int64]$workingSetBytes
                working_set_mb = [double][Math]::Round(($workingSetBytes / 1MB), 2)
            }
        }
    } else {
        $processes = @(Get-Process -Name node -ErrorAction SilentlyContinue)
        foreach ($proc in $processes) {
            $rows += [pscustomobject]@{
                pid = [int]$proc.Id
                parent_pid = $null
                process_name = [string]$proc.ProcessName
                command_line = $null
                working_set_bytes = [int64]$proc.WorkingSet64
                working_set_mb = [double][Math]::Round(($proc.WorkingSet64 / 1MB), 2)
            }
        }
    }

    return $rows
}

function Get-VgoNodeAuditInput {
    param(
        [string]$RepoRoot,
        [string]$FixturePath
    )

    if (-not [string]::IsNullOrWhiteSpace($FixturePath)) {
        if (-not (Test-Path -LiteralPath $FixturePath)) {
            throw "Fixture not found: $FixturePath"
        }

        $fixture = Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $now = ConvertFrom-VgoNullableTimestamp -Value $fixture.now
        if ($null -eq $now) {
            $now = [datetimeoffset]::UtcNow
        }

        return [pscustomobject]@{
            source = 'fixture'
            fixture_path = [System.IO.Path]::GetFullPath($FixturePath)
            now = $now
            live_processes = @($fixture.live_processes)
            ledger = if ($fixture.ledger) { $fixture.ledger } else { [pscustomobject]@{ entries = @() } }
            case_id = if ($fixture.case_id) { [string]$fixture.case_id } else { [System.IO.Path]::GetFileNameWithoutExtension($FixturePath) }
        }
    }

    return [pscustomobject]@{
        source = 'live'
        fixture_path = $null
        now = [datetimeoffset]::UtcNow
        live_processes = @(Get-VgoLiveNodeProcessSnapshot -RepoRoot $RepoRoot)
        ledger = Get-VgoProcessLedger -RepoRoot $RepoRoot
        case_id = 'live-runtime'
    }
}

function Find-VgoLedgerEntryForPid {
    param(
        [AllowNull()] [object[]]$Entries,
        [Nullable[int]]$ProcessId
    )

    if ($null -eq $ProcessId -or $ProcessId -le 0) {
        return $null
    }

    $matches = @($Entries | Where-Object { $_ -and $_.pid -eq $ProcessId })
    if ($matches.Count -eq 0) {
        return $null
    }

    return $matches | Sort-Object {
        $dt = ConvertFrom-VgoNullableTimestamp -Value $_.started_at
        if ($null -eq $dt) { [datetimeoffset]::MinValue } else { $dt }
    } -Descending | Select-Object -First 1
}

function Get-VgoNodeProcessAuditRows {
    param(
        [string]$RepoRoot,
        [string]$FixturePath
    )

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    $healthPolicy = $context.healthPolicy
    $inputData = Get-VgoNodeAuditInput -RepoRoot $context.repoRoot -FixturePath $FixturePath
    $now = [datetimeoffset]$inputData.now
    $entries = @($inputData.ledger.entries)
    $protectOwnership = @($healthPolicy.cleanup.protect_ownership | ForEach-Object { [string]$_ })
    $allowedCleanupStates = @($healthPolicy.cleanup.allowed_classifications | ForEach-Object { [string]$_ })
    $rows = @()

    foreach ($process in @($inputData.live_processes)) {
        $processId = if ($process.PSObject.Properties.Name -contains 'pid' -and $process.pid -ne $null) { [int]$process.pid } else { $null }
        $processName = if ($process.PSObject.Properties.Name -contains 'process_name') { [string]$process.process_name } else { $null }
        $entry = Find-VgoLedgerEntryForPid -Entries $entries -ProcessId $processId
        $ownership = if ($null -ne $entry) { [string]$entry.ownership } else { [string]$healthPolicy.ownership_contract.external }
        $cleanupSafe = if ($null -ne $entry) { [bool]$entry.cleanup_safe } else { $false }
        $classification = $null
        $reasons = New-Object System.Collections.Generic.List[string]
        $heartbeatAge = $null
        $staleAfterSec = if ($null -ne $entry -and $entry.stale_after_sec -ne $null) { [int]$entry.stale_after_sec } else { [int]$healthPolicy.audit.stale_heartbeat_sec }

        if ($null -eq $processId -or $processId -le 0 -or -not (Test-VgoNodeProcessName -ProcessName $processName -HealthPolicy $healthPolicy)) {
            $classification = [string]$healthPolicy.ownership_contract.unknown + '_audit_only'
            $ownership = [string]$healthPolicy.ownership_contract.unknown
            $cleanupSafe = $false
            $reasons.Add('missing_or_non_node_process_identity') | Out-Null
        } elseif ($null -eq $entry) {
            $classification = 'external_audit_only'
            $reasons.Add('no_ledger_owner_for_pid') | Out-Null
        } else {
            $startedAge = Get-VgoElapsedSeconds -Timestamp $entry.started_at -Now $now
            $heartbeatAge = Get-VgoElapsedSeconds -Timestamp $entry.last_heartbeat_at -Now $now
            $entryStatus = [string]$entry.status
            if ($entryStatus -in @('completed', 'terminated')) {
                $classification = 'managed_completed_process_alive'
                $reasons.Add("ledger_status=$entryStatus") | Out-Null
                $reasons.Add('process_still_alive_after_completion') | Out-Null
            } elseif ($null -eq $heartbeatAge) {
                if ($null -ne $startedAge -and $startedAge -gt [int]$healthPolicy.audit.startup_grace_sec) {
                    $classification = 'managed_missing_heartbeat'
                    $reasons.Add('heartbeat_missing_after_startup_grace') | Out-Null
                } else {
                    $classification = 'managed_live'
                    $reasons.Add('inside_startup_grace_without_heartbeat') | Out-Null
                }
            } elseif ($heartbeatAge -gt $staleAfterSec) {
                $classification = 'managed_stale'
                $reasons.Add("heartbeat_age_sec=$heartbeatAge") | Out-Null
                $reasons.Add("stale_after_sec=$staleAfterSec") | Out-Null
            } elseif ($heartbeatAge -gt [int]$healthPolicy.audit.missing_heartbeat_sec) {
                $classification = 'managed_missing_heartbeat'
                $reasons.Add("heartbeat_age_sec=$heartbeatAge") | Out-Null
                $reasons.Add('heartbeat_missing_threshold_exceeded') | Out-Null
            } else {
                $classification = 'managed_live'
                $reasons.Add("heartbeat_age_sec=$heartbeatAge") | Out-Null
                $reasons.Add('heartbeat_fresh') | Out-Null
            }
        }

        $cleanupCandidate = (
            $ownership -eq [string]$healthPolicy.ownership_contract.managed -and
            $cleanupSafe -and
            ($allowedCleanupStates -contains $classification) -and
            -not ($protectOwnership -contains $ownership)
        )

        $rows += [pscustomobject]@{
            pid = $processId
            parent_pid = if ($process.PSObject.Properties.Name -contains 'parent_pid' -and $process.parent_pid -ne $null) { [int]$process.parent_pid } else { $null }
            process_name = $processName
            command_line = if ($process.PSObject.Properties.Name -contains 'command_line') { [string]$process.command_line } else { $null }
            working_set_bytes = if ($process.PSObject.Properties.Name -contains 'working_set_bytes') { [int64]$process.working_set_bytes } else { 0 }
            working_set_mb = if ($process.PSObject.Properties.Name -contains 'working_set_mb') { [double]$process.working_set_mb } else { 0.0 }
            classification = $classification
            ownership = $ownership
            cleanup_safe = $cleanupSafe
            cleanup_candidate = $cleanupCandidate
            entry_id = if ($null -ne $entry) { [string]$entry.entry_id } else { $null }
            label = if ($null -ne $entry) { [string]$entry.label } else { $null }
            launcher_pid = if ($null -ne $entry -and $entry.launcher_pid -ne $null) { [int]$entry.launcher_pid } else { $null }
            status = if ($null -ne $entry) { [string]$entry.status } else { $null }
            last_heartbeat_at = if ($null -ne $entry) { [string]$entry.last_heartbeat_at } else { $null }
            heartbeat_age_sec = $heartbeatAge
            stale_after_sec = if ($null -ne $entry) { $staleAfterSec } else { $null }
            reasons = @($reasons)
        }
    }

    $classificationCounts = [ordered]@{}
    foreach ($row in $rows) {
        $key = [string]$row.classification
        if (-not $classificationCounts.Contains($key)) {
            $classificationCounts[$key] = 0
        }
        $classificationCounts[$key]++
    }

    $workingSetSum = 0.0
    if ($rows.Count -gt 0) {
        $measure = $rows | Measure-Object -Property working_set_mb -Sum
        if ($null -ne $measure -and $measure.PSObject.Properties.Name -contains 'Sum' -and $null -ne $measure.Sum) {
            $workingSetSum = [double]$measure.Sum
        }
    }

    $summary = [ordered]@{
        case_id = [string]$inputData.case_id
        source = [string]$inputData.source
        generated_at = Get-VgoUtcTimestamp
        total_processes = $rows.Count
        cleanup_candidate_count = @($rows | Where-Object { $_.cleanup_candidate }).Count
        external_count = @($rows | Where-Object { $_.ownership -eq [string]$healthPolicy.ownership_contract.external }).Count
        unknown_count = @($rows | Where-Object { $_.ownership -eq [string]$healthPolicy.ownership_contract.unknown }).Count
        total_working_set_mb = [double][Math]::Round($workingSetSum, 2)
        classifications = $classificationCounts
    }

    return [pscustomobject]@{
        source = [string]$inputData.source
        fixture_path = $inputData.fixture_path
        case_id = [string]$inputData.case_id
        now = $now.ToString('o')
        rows = $rows
        summary = [pscustomobject]$summary
    }
}

function Get-VgoNodeCleanupCandidates {
    param(
        [AllowNull()] [object[]]$Rows,
        [AllowNull()] [object]$HealthPolicy
    )

    if ($null -eq $Rows) {
        return @()
    }

    $allowed = if ($HealthPolicy -and $HealthPolicy.cleanup -and $HealthPolicy.cleanup.allowed_classifications) {
        @($HealthPolicy.cleanup.allowed_classifications | ForEach-Object { [string]$_ })
    } else {
        @('managed_stale', 'managed_completed_process_alive')
    }

    $managedOwnership = if ($HealthPolicy -and $HealthPolicy.ownership_contract -and $HealthPolicy.ownership_contract.managed) {
        [string]$HealthPolicy.ownership_contract.managed
    } else {
        'vco-managed'
    }

    return @(
        $Rows | Where-Object {
            $_ -and
            $_.ownership -eq $managedOwnership -and
            [bool]$_.cleanup_safe -and
            ($allowed -contains [string]$_.classification)
        }
    )
}
