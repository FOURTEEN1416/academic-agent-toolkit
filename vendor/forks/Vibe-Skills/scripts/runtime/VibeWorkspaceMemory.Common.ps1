Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-VibeWorkspaceMemoryDriverConfig {
    param(
        [Parameter(Mandatory)] [object]$Runtime
    )

    if ($null -eq $Runtime -or $null -eq $Runtime.PSObject -or -not ($Runtime.PSObject.Properties.Name -contains 'memory_backend_adapters')) {
        return $null
    }

    $memoryBackendAdapters = $Runtime.memory_backend_adapters
    if ($null -eq $memoryBackendAdapters -or $null -eq $memoryBackendAdapters.PSObject -or -not ($memoryBackendAdapters.PSObject.Properties.Name -contains 'driver')) {
        return $null
    }

    return $memoryBackendAdapters.driver
}

function Get-VibeWorkspaceMemoryDriverScriptPath {
    param(
        [Parameter(Mandatory)] [object]$Runtime
    )

    $driver = Get-VibeWorkspaceMemoryDriverConfig -Runtime $Runtime
    $driverPath = if (
        $null -ne $driver -and
        $null -ne $driver.PSObject -and
        $driver.PSObject.Properties.Name -contains 'script_path' -and
        -not [string]::IsNullOrWhiteSpace([string]$driver.script_path)
    ) {
        [string]$driver.script_path
    } else {
        'scripts/runtime/workspace_memory_driver.py'
    }

    $repoRoot = [string]$Runtime.repo_root
    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $driverPath))
}

function Resolve-VibeWorkspaceMemoryCommandSpec {
    param(
        [Parameter(Mandatory)] [object]$Runtime
    )

    $driver = Get-VibeWorkspaceMemoryDriverConfig -Runtime $Runtime
    $command = if (
        $null -ne $driver -and
        $null -ne $driver.PSObject -and
        $driver.PSObject.Properties.Name -contains 'command' -and
        -not [string]::IsNullOrWhiteSpace([string]$driver.command)
    ) {
        [string]$driver.command
    } else {
        '${VGO_PYTHON}'
    }
    return Resolve-VgoPythonCommandSpec -Command $command
}

function Invoke-VibeWorkspaceMemoryAction {
    param(
        [Parameter(Mandatory)] [object]$Runtime,
        [Parameter(Mandatory)] [string]$LaneId,
        [Parameter(Mandatory)] [string]$Action,
        [Parameter(Mandatory)] [object]$Payload,
        [Parameter(Mandatory)] [string]$SessionRoot
    )

    $laneResolution = Resolve-VibeMemoryBackendLane -Runtime $Runtime -LaneId $LaneId
    if (-not $laneResolution.enabled) {
        return [pscustomobject]@{
            ok = $false
            status = [string]$laneResolution.reason
            items = @()
            item_count = 0
            capsule_count = 0
            capsules = @()
            suppressed_count = 0
            workspace_memory_plane = $null
            artifact_path = $null
            store_path = $null
            project_key = $null
            project_key_source = $null
            backend_lane = $LaneId
        }
    }

    $driverScript = Get-VibeWorkspaceMemoryDriverScriptPath -Runtime $Runtime
    if (-not (Test-Path -LiteralPath $driverScript)) {
        return [pscustomobject]@{
            ok = $false
            status = 'workspace_memory_driver_missing'
            items = @()
            item_count = 0
            capsule_count = 0
            capsules = @()
            suppressed_count = 0
            workspace_memory_plane = $null
            artifact_path = $null
            store_path = $null
            project_key = $laneResolution.project_key
            project_key_source = $laneResolution.project_key_source
            backend_lane = $LaneId
        }
    }

    $artifactsRoot = Join-Path $SessionRoot 'workspace-memory'
    New-Item -ItemType Directory -Path $artifactsRoot -Force | Out-Null
    $payloadPath = Join-Path $artifactsRoot ("{0}-{1}-request.json" -f $LaneId, $Action)
    $responsePath = Join-Path $artifactsRoot ("{0}-{1}-response.json" -f $LaneId, $Action)
    Write-VibeJsonArtifact -Path $payloadPath -Value $Payload

    $commandSpec = Resolve-VibeWorkspaceMemoryCommandSpec -Runtime $Runtime
    $args = @($commandSpec.prefix_arguments)
    $args += @(
        $driverScript,
        '--lane', $LaneId,
        '--action', $Action,
        '--repo-root', ([string]$Runtime.repo_root),
        '--session-root', $SessionRoot,
        '--store-path', ([string]$laneResolution.store_path),
        '--payload-path', $payloadPath,
        '--response-path', $responsePath,
        '--driver-mode', 'workspace_broker'
    )
    if (-not [string]::IsNullOrWhiteSpace([string]$laneResolution.project_key)) {
        $args += @('--project-key', [string]$laneResolution.project_key)
    }

    try {
        $global:LASTEXITCODE = 0
        @(& $commandSpec.host_path @args 2>&1) | Out-Null
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
        if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $responsePath)) {
            return [pscustomobject]@{
                ok = $false
                status = 'workspace_memory_invocation_failed'
                items = @()
                item_count = 0
                capsule_count = 0
                capsules = @()
                suppressed_count = 0
                workspace_memory_plane = $null
                artifact_path = $null
                store_path = $null
                project_key = $laneResolution.project_key
                project_key_source = $laneResolution.project_key_source
                backend_lane = $LaneId
            }
        }

        $response = Get-Content -LiteralPath $responsePath -Raw -Encoding UTF8 | ConvertFrom-Json
        return [pscustomobject]@{
            ok = [bool]($response.ok)
            status = [string]$response.status
            items = @($response.items)
            item_count = [int]$response.item_count
            capsule_count = [int]$response.capsule_count
            capsules = if ($response.PSObject.Properties.Name -contains 'capsules') { @($response.capsules) } else { @() }
            suppressed_count = [int]$response.suppressed_count
            workspace_memory_plane = $response.workspace_memory_plane
            artifact_path = $responsePath
            store_path = if ($response.store_path) { [string]$response.store_path } else { $null }
            project_key = if ($response.project_key) { [string]$response.project_key } else { $laneResolution.project_key }
            project_key_source = if ($response.project_key_source) { [string]$response.project_key_source } else { $laneResolution.project_key_source }
            backend_lane = $LaneId
        }
    } catch {
        return [pscustomobject]@{
            ok = $false
            status = 'workspace_memory_exception'
            items = @()
            item_count = 0
            capsule_count = 0
            capsules = @()
            suppressed_count = 0
            workspace_memory_plane = $null
            artifact_path = $null
            store_path = $null
            project_key = $laneResolution.project_key
            project_key_source = $laneResolution.project_key_source
            backend_lane = $LaneId
            error = $_.Exception.Message
        }
    }
}
