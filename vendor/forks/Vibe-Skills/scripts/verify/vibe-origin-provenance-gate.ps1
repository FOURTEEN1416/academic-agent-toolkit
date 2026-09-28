param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [string]$OutputDirectory,
        [psobject]$Artifact
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-origin-provenance-gate.json'
    $mdPath = Join-Path $dir 'vibe-origin-provenance-gate.md'
    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VCO ORIGIN Provenance Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Policy Only Mode: `{0}`' -f $Artifact.summary.policy_only_mode),
        ('- Real vendor roots: `{0}`' -f $Artifact.summary.real_vendor_roots),
        ('- Missing ORIGIN files: `{0}`' -f $Artifact.summary.missing_origin_files)
    )
    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$policyDoc = Join-Path $repoRoot 'docs\governance\origin-provenance-policy.md'
$templatePath = Join-Path $repoRoot 'templates\ORIGIN.md.tmpl'
$vendorReadme = Join-Path $repoRoot 'vendor\README.md'
$generatorPath = Join-Path $repoRoot 'scripts\governance\new-origin-record.ps1'
$vendorRoot = Join-Path $repoRoot 'vendor'

$requiredScaffolding = @($policyDoc, $templatePath, $vendorReadme, $generatorPath)
$missingScaffolding = @($requiredScaffolding | Where-Object { -not (Test-Path -LiteralPath $_) })

$realVendorRoots = New-Object System.Collections.Generic.List[string]
$missingOriginFiles = New-Object System.Collections.Generic.List[string]

if (Test-Path -LiteralPath $vendorRoot) {
    $leafRoots = @(
        Get-ChildItem -LiteralPath $vendorRoot -Directory -Recurse | Where-Object {
            $_.Name -notin @('upstreams', 'mirrors')
        }
    )

    foreach ($dir in $leafRoots) {
        $originPath = Join-Path $dir.FullName 'ORIGIN.md'
        $contentFiles = @(Get-ChildItem -LiteralPath $dir.FullName -Force | Where-Object { $_.Name -notin @('ORIGIN.md', '.gitkeep') })
        if ($contentFiles.Count -eq 0) {
            continue
        }
        [void]$realVendorRoots.Add((Get-VgoRelativePathPortable -BasePath $repoRoot -TargetPath $dir.FullName))
        if (-not (Test-Path -LiteralPath $originPath)) {
            [void]$missingOriginFiles.Add((Get-VgoRelativePathPortable -BasePath $repoRoot -TargetPath $originPath))
        }
    }
}

$policyOnlyMode = ($realVendorRoots.Count -eq 0)
$failures = 0
if ($missingScaffolding.Count -gt 0) { $failures++ }
if ($missingOriginFiles.Count -gt 0) { $failures++ }

$artifact = [pscustomobject]@{
    gate = 'vibe-origin-provenance-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = if ($failures -eq 0) { 'PASS' } else { 'FAIL' }
    summary = [ordered]@{
        policy_only_mode = $policyOnlyMode
        real_vendor_roots = $realVendorRoots.Count
        missing_origin_files = $missingOriginFiles.Count
        missing_scaffolding = $missingScaffolding.Count
        failure_count = $failures
    }
    results = [ordered]@{
        missing_scaffolding = @($missingScaffolding | ForEach-Object { Get-VgoRelativePathPortable -BasePath $repoRoot -TargetPath $_ })
        real_vendor_roots = @($realVendorRoots)
        missing_origin_files = @($missingOriginFiles)
    }
}

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -OutputDirectory $OutputDirectory -Artifact $artifact
}

if ($failures -gt 0) { exit 1 }
