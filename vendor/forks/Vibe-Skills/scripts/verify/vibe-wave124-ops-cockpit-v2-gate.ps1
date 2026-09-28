param(
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '..\common\vibe-wave-gate-runner.ps1') -Wave 124 -WriteArtifacts:$WriteArtifacts -OutputDirectory $OutputDirectory
exit $LASTEXITCODE
