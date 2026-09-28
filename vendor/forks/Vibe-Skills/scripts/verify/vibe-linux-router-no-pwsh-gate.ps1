param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $repoRoot "scripts\common\vibe-governance-helpers.ps1")
$gateScript = Join-Path $repoRoot "scripts\verify\runtime_neutral\router_bridge_gate.py"

if (-not (Test-Path -LiteralPath $gateScript)) {
    throw "runtime-neutral router bridge gate missing: $gateScript"
}

$args = @($gateScript)
if ($WriteArtifacts) {
    $args += "--write-artifacts"
}

$pythonInvocation = Get-VgoPythonCommand
& $pythonInvocation.host_path @($pythonInvocation.prefix_arguments) @args
exit $LASTEXITCODE
