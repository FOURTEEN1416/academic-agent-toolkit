param(
    [string]$FilePath,
    [string[]]$ArgumentList = @(),
    [string]$Label = 'node-runtime',
    [string]$WorkingDirectory,
    [string]$OwnerId,
    [int]$WaitForNodeSec = 20,
    [int]$HeartbeatIntervalSec = 0,
    [switch]$PassThru,
    [switch]$NoHeartbeatMonitor,
    [switch]$MonitorMode,
    [string]$EntryId,
    [int]$LauncherPid,
    [string]$RepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'ProcessLedger.ps1')

function Get-VgoProcessTableSnapshot {
    param([Nullable[int]]$RootPid)

    if (-not (Test-VgoIsWindows)) {
        return @()
    }

    $selected = @()
    $rootStartedAt = $null
    if ($null -ne $RootPid -and $RootPid -gt 0) {
        try {
            $rootProcess = Get-Process -Id $RootPid -ErrorAction Stop
            $selected += @($rootProcess)
            try {
                $rootStartedAt = $rootProcess.StartTime.ToUniversalTime()
            } catch {
                $rootStartedAt = $null
            }
        } catch {
        }
    }

    try {
        $nodeProcesses = @(Get-Process -Name node,node.exe -ErrorAction SilentlyContinue)
        if ($null -ne $rootStartedAt) {
            $cutoff = $rootStartedAt.AddSeconds(-2)
            $nodeProcesses = @(
                $nodeProcesses | Where-Object {
                    try {
                        $_.StartTime.ToUniversalTime() -ge $cutoff
                    } catch {
                        $true
                    }
                }
            )
        }
        $selected += $nodeProcesses
    } catch {
    }

    $selected = @($selected | Sort-Object Id -Unique)
    if ($selected.Count -eq 0) {
        return @()
    }

    $metadataByPid = Get-VgoWindowsProcessMetadata -Pids @($selected | ForEach-Object { [int]$_.Id })
    return @(
        foreach ($proc in $selected) {
            $processId = [int]$proc.Id
            $metadata = if ($metadataByPid.ContainsKey([string]$processId)) { $metadataByPid[[string]$processId] } else { $null }
            [pscustomobject]@{
                pid = $processId
                parent_pid = if ($null -ne $metadata) { [int]$metadata.parent_pid } else { $null }
                process_name = if ($null -ne $metadata -and $metadata.process_name) { [string]$metadata.process_name } else { [string]$proc.ProcessName }
                command_line = if ($null -ne $metadata) { [string]$metadata.command_line } else { $null }
            }
        }
    )
}

function Get-VgoProcessDepthToRoot {
    param(
        [hashtable]$ByPid,
        [int]$ProcessId,
        [int]$RootPid
    )

    $depth = 0
    $cursor = $ProcessId
    $guard = 0
    while ($cursor -gt 0 -and $guard -lt 512) {
        if ($cursor -eq $RootPid) {
            return $depth
        }
        if (-not $ByPid.ContainsKey([string]$cursor)) {
            return $null
        }
        $cursor = [int]$ByPid[[string]$cursor].parent_pid
        $depth++
        $guard++
    }

    return $null
}

function Find-VgoNodeProcessForLauncher {
    param(
        [int]$RootPid,
        [string]$RepoRoot
    )

    if ($RootPid -le 0) {
        return $null
    }

    $context = Get-VgoProcessHealthContext -RepoRoot $RepoRoot
    $table = @(Get-VgoProcessTableSnapshot -RootPid $RootPid)
    if ($table.Count -eq 0) {
        try {
            $root = Get-Process -Id $RootPid -ErrorAction Stop
            if ($root.ProcessName -eq 'node') {
                return [pscustomobject]@{
                    pid = [int]$root.Id
                    parent_pid = $null
                    process_name = 'node'
                    command_line = $null
                }
            }
        } catch {
            return $null
        }
        return $null
    }

    $byPid = @{}
    foreach ($row in $table) {
        $byPid[[string]$row.pid] = $row
    }

    $candidates = @()
    foreach ($row in $table) {
        if (-not (Test-VgoNodeProcessName -ProcessName $row.process_name -HealthPolicy $context.healthPolicy)) {
            continue
        }

        $depth = Get-VgoProcessDepthToRoot -ByPid $byPid -ProcessId ([int]$row.pid) -RootPid $RootPid
        if ($null -eq $depth) {
            continue
        }

        $candidates += [pscustomobject]@{
            pid = [int]$row.pid
            parent_pid = [int]$row.parent_pid
            process_name = [string]$row.process_name
            command_line = [string]$row.command_line
            depth = $depth
        }
    }

    if ($candidates.Count -eq 0) {
        return $null
    }

    return $candidates | Sort-Object depth, pid | Select-Object -First 1
}

function Wait-VgoNodeProcessDiscovery {
    param(
        [int]$RootPid,
        [int]$TimeoutSec,
        [string]$RepoRoot
    )

    $deadline = (Get-Date).ToUniversalTime().AddSeconds([Math]::Max(1, $TimeoutSec))
    do {
        $candidate = Find-VgoNodeProcessForLauncher -RootPid $RootPid -RepoRoot $RepoRoot
        if ($null -ne $candidate) {
            return $candidate
        }

        if (-not (Test-VgoProcessAlive -ProcessId $RootPid)) {
            break
        }

        Start-Sleep -Milliseconds 800
    } while ((Get-Date).ToUniversalTime() -lt $deadline)

    return $null
}

function Resolve-VgoMonitorHostPath {
    foreach ($candidate in @(
        (Join-Path $PSHOME 'powershell.exe'),
        (Get-Command powershell.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        (Get-Command pwsh.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
    )) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw 'Unable to resolve PowerShell host for heartbeat monitor.'
}

function Invoke-VgoNodeHeartbeatMonitor {
    param(
        [Parameter(Mandatory)] [string]$EntryId,
        [Parameter(Mandatory)] [int]$LauncherPid,
        [Parameter(Mandatory)] [string]$RepoRoot,
        [int]$HeartbeatIntervalSec
    )

    $context = Initialize-VgoProcessHealthRuntime -RepoRoot $RepoRoot
    $ledger = Get-VgoProcessLedger -RepoRoot $context.repoRoot
    $entry = @($ledger.entries | Where-Object { [string]$_.entry_id -eq $EntryId } | Select-Object -First 1)
    if ($entry.Count -eq 0) {
        throw "Unable to locate ledger entry '$EntryId'."
    }

    $currentEntry = $entry[0]
    $heartbeatPath = if ([System.IO.Path]::IsPathRooted([string]$currentEntry.heartbeat_path)) {
        [string]$currentEntry.heartbeat_path
    } else {
        Join-Path $context.repoRoot ([string]$currentEntry.heartbeat_path)
    }

    $interval = if ($HeartbeatIntervalSec -gt 0) {
        $HeartbeatIntervalSec
    } elseif ($currentEntry.heartbeat_interval_sec -gt 0) {
        [int]$currentEntry.heartbeat_interval_sec
    } else {
        [int]$context.ledgerPolicy.defaults.heartbeat_interval_sec
    }

    while ($true) {
        $now = Get-VgoUtcTimestamp
        $launcherAlive = Test-VgoProcessAlive -ProcessId $LauncherPid
        $nodeCandidate = Find-VgoNodeProcessForLauncher -RootPid $LauncherPid -RepoRoot $context.repoRoot

        if ($null -ne $nodeCandidate) {
            $currentEntry = Update-VgoProcessLedgerEntry -EntryId $EntryId -RepoRoot $context.repoRoot -EventType 'entry.heartbeat' -Note 'node heartbeat observed' -Patch @{
                pid = [int]$nodeCandidate.pid
                target_process_name = [string]$nodeCandidate.process_name
                command_line = if ($nodeCandidate.command_line) { [string]$nodeCandidate.command_line } else { [string]$currentEntry.command_line }
                node_pid_confirmed = $true
                cleanup_safe = $true
                status = 'running'
                last_heartbeat_at = $now
                last_seen_alive_at = $now
            }
            Write-VgoProcessHeartbeatFile -Path $heartbeatPath -EntryId $EntryId -State 'running' -Note 'node heartbeat observed' -ProcessId ([int]$nodeCandidate.pid) -LauncherPid $LauncherPid
            Start-Sleep -Seconds $interval
            continue
        }

        if ($launcherAlive) {
            $currentEntry = Update-VgoProcessLedgerEntry -EntryId $EntryId -RepoRoot $context.repoRoot -EventType 'entry.heartbeat' -Note 'launcher alive, waiting for node runtime' -Patch @{
                status = 'running'
                last_heartbeat_at = $now
                last_seen_alive_at = $now
            }
            Write-VgoProcessHeartbeatFile -Path $heartbeatPath -EntryId $EntryId -State 'launcher_only' -Note 'launcher alive, waiting for node runtime' -ProcessId ([int]$currentEntry.pid) -LauncherPid $LauncherPid
            Start-Sleep -Seconds $interval
            continue
        }

        $targetAlive = Test-VgoProcessAlive -ProcessId ([int]$currentEntry.pid)
        if ($targetAlive) {
            $currentEntry = Complete-VgoProcessLedgerEntry -EntryId $EntryId -RepoRoot $context.repoRoot -FinalStatus 'completed' -Note 'launcher exited while target remained alive'
            Write-VgoProcessHeartbeatFile -Path $heartbeatPath -EntryId $EntryId -State 'orphaned_after_completion' -Note 'launcher exited while target remained alive' -ProcessId ([int]$currentEntry.pid) -LauncherPid $LauncherPid
            break
        }

        $currentEntry = Complete-VgoProcessLedgerEntry -EntryId $EntryId -RepoRoot $context.repoRoot -FinalStatus 'completed' -Note 'launcher and target exited'
        Write-VgoProcessHeartbeatFile -Path $heartbeatPath -EntryId $EntryId -State 'completed' -Note 'launcher and target exited' -ProcessId ([int]$currentEntry.pid) -LauncherPid $LauncherPid
        break
    }
}

if ($MonitorMode) {
    Invoke-VgoNodeHeartbeatMonitor -EntryId $EntryId -LauncherPid $LauncherPid -RepoRoot $RepoRoot -HeartbeatIntervalSec $HeartbeatIntervalSec
    return
}

if ([string]::IsNullOrWhiteSpace($FilePath)) {
    throw 'FilePath is required unless -MonitorMode is used.'
}

$resolvedRepoRoot = if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    Resolve-VgoRepoRoot -StartPath $PSScriptRoot
} else {
    [System.IO.Path]::GetFullPath($RepoRoot)
}

$context = Initialize-VgoProcessHealthRuntime -RepoRoot $resolvedRepoRoot
$workingDir = if ([string]::IsNullOrWhiteSpace($WorkingDirectory)) { (Get-Location).Path } else { $WorkingDirectory }
$owner = if ([string]::IsNullOrWhiteSpace($OwnerId)) { '{0}@{1}' -f $env:USERNAME, $env:COMPUTERNAME } else { $OwnerId }
$intervalSec = if ($HeartbeatIntervalSec -gt 0) { $HeartbeatIntervalSec } else { [int]$context.ledgerPolicy.defaults.heartbeat_interval_sec }
$commandLine = (($FilePath) + ' ' + (($ArgumentList | Where-Object { $_ -ne $null }) -join ' ')).Trim()

$launched = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $workingDir -PassThru
$nodeCandidate = Wait-VgoNodeProcessDiscovery -RootPid ([int]$launched.Id) -TimeoutSec $WaitForNodeSec -RepoRoot $context.repoRoot
$entryIdValue = New-VgoProcessLedgerEntryId
$heartbeatPath = Join-Path $context.heartbeatsDir ("{0}.json" -f $entryIdValue)
$heartbeatRelPath = Get-VgoRelativePathPortable -BasePath $context.repoRoot -TargetPath $heartbeatPath
$effectivePid = if ($null -ne $nodeCandidate) { [int]$nodeCandidate.pid } else { [int]$launched.Id }

$entry = Register-VgoProcessLedgerEntry -RepoRoot $context.repoRoot -Entry @{
    entry_id = $entryIdValue
    label = $Label
    owner_id = $owner
    pid = $effectivePid
    launcher_pid = [int]$launched.Id
    working_directory = $workingDir
    command_line = if ($null -ne $nodeCandidate -and $nodeCandidate.command_line) { [string]$nodeCandidate.command_line } else { $commandLine }
    heartbeat_path = $heartbeatRelPath
    cleanup_safe = ($null -ne $nodeCandidate)
    node_pid_confirmed = ($null -ne $nodeCandidate)
    stale_after_sec = [int]$context.ledgerPolicy.defaults.stale_after_sec
    heartbeat_interval_sec = $intervalSec
    target_process_name = if ($null -ne $nodeCandidate) { [string]$nodeCandidate.process_name } else { [string]$launched.ProcessName }
} -Note 'wrapper launch registered'

$heartbeatState = if ($null -ne $nodeCandidate) { 'running' } else { 'launcher_only' }
$heartbeatNote = if ($null -ne $nodeCandidate) { 'node runtime discovered at launch' } else { 'launcher registered before node discovery' }
Write-VgoProcessHeartbeatFile -Path $heartbeatPath -EntryId $entry.entry_id -State $heartbeatState -Note $heartbeatNote -ProcessId $effectivePid -LauncherPid ([int]$launched.Id)

if (-not $NoHeartbeatMonitor) {
    $hostPath = Resolve-VgoMonitorHostPath
    $monitorArgs = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $PSCommandPath,
        '-MonitorMode',
        '-EntryId', $entry.entry_id,
        '-LauncherPid', ([string]$launched.Id),
        '-RepoRoot', $context.repoRoot,
        '-HeartbeatIntervalSec', ([string]$intervalSec)
    )
    Start-Process -FilePath $hostPath -ArgumentList $monitorArgs -WindowStyle Hidden | Out-Null
}

$result = [pscustomobject]@{
    entry_id = [string]$entry.entry_id
    label = [string]$entry.label
    launcher_pid = [int]$launched.Id
    pid = [int]$entry.pid
    node_pid_confirmed = [bool]$entry.node_pid_confirmed
    cleanup_safe = [bool]$entry.cleanup_safe
    heartbeat_path = [string]$entry.heartbeat_path
    command_line = [string]$entry.command_line
}

if ($PassThru) {
    return $result
}

$result | ConvertTo-Json -Depth 10
