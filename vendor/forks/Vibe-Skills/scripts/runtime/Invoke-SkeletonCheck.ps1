param(
    [Parameter(Mandatory)] [string]$Task,
    [string]$Mode = 'interactive_governed',
    [string]$RunId = '',
    [string]$ArtifactRoot = '',
    [AllowEmptyString()] [string]$WorkspaceRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'VibeRuntime.Common.ps1')

$runtime = Get-VibeRuntimeContext -ScriptPath $PSCommandPath
if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = New-VibeRunId
}

$artifactContract = Get-VibeArtifactContractDescriptor -RepoRoot $runtime.repo_root -RunId $RunId -WorkspaceRoot $WorkspaceRoot -ArtifactRoot $ArtifactRoot
$sessionRoot = Ensure-VibeSessionRoot -RepoRoot $runtime.repo_root -RunId $RunId -Runtime $runtime -WorkspaceRoot $WorkspaceRoot -ArtifactRoot $ArtifactRoot
$runSinkRoot = [System.IO.Path]::GetDirectoryName([string]$artifactContract.artifact_root)
$existingRequirementDocs = @()
$existingPlanDocs = @()
if (-not [string]::IsNullOrWhiteSpace($runSinkRoot) -and (Test-Path -LiteralPath $runSinkRoot -PathType Container)) {
    $existingRequirementDocs = @(
        Get-ChildItem -LiteralPath $runSinkRoot -Recurse -Filter 'requirement.md' -File |
            ForEach-Object { Get-VibeRelativePathCompat -BasePath ([string]$artifactContract.workspace_root) -TargetPath ([string]$_.FullName) } |
            Sort-Object
    )
    $existingPlanDocs = @(
        Get-ChildItem -LiteralPath $runSinkRoot -Recurse -Filter 'plan.md' -File |
            ForEach-Object { Get-VibeRelativePathCompat -BasePath ([string]$artifactContract.workspace_root) -TargetPath ([string]$_.FullName) } |
            Sort-Object
    )
}
$requiredPaths = @(
    'SKILL.md',
    'protocols/runtime.md',
    'protocols/think.md',
    'protocols/do.md',
    'protocols/team.md',
    'protocols/retro.md',
    'config/runtime-contract.json',
    'config/runtime-modes.json',
    'config/requirement-doc-policy.json',
    'config/plan-execution-policy.json',
    'config/phase-cleanup-policy.json'
)

$pathChecks = @(
    foreach ($relativePath in $requiredPaths) {
        $fullPath = Join-Path $runtime.repo_root $relativePath
        [pscustomobject]@{
            path = $relativePath
            exists = [bool](Test-Path -LiteralPath $fullPath)
        }
    }
)

$gitBranch = ''
$gitStatus = @()
try {
    $gitBranch = (& git -C $runtime.repo_root rev-parse --abbrev-ref HEAD 2>$null)
    $gitStatus = @(& git -C $runtime.repo_root status --short 2>$null)
} catch {
    $gitBranch = ''
    $gitStatus = @()
}

$receipt = [pscustomobject]@{
    stage = 'skeleton_check'
    run_id = $RunId
    mode = $Mode
    task = $Task
    generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    repo_root = $runtime.repo_root
    git_branch = $gitBranch
    git_status = @($gitStatus)
    required_paths = @($pathChecks)
    existing_requirement_docs = @($existingRequirementDocs)
    existing_plan_docs = @($existingPlanDocs)
}

$receiptPath = Join-Path $sessionRoot 'skeleton-receipt.json'
Write-VibeJsonArtifact -Path $receiptPath -Value $receipt

[pscustomobject]@{
    run_id = $RunId
    session_root = $sessionRoot
    receipt_path = $receiptPath
    receipt = $receipt
}
