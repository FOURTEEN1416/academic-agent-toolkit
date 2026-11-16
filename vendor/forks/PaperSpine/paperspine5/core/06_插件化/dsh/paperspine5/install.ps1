param(
  [string]$Profile = "web",
  [string]$Target = "",
  [string]$DshBin = "",
  [switch]$NoLink
)
$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "core/runtime_vendor/windows-py312/python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "core/suite-manifest.json")) {
    throw "This bundle is not for Windows x64, or its bundled runtime is missing."
  }
  $python = (Get-Command python -ErrorAction Stop).Source
}
$installArgs = @("-B", "-X", "utf8", (Join-Path $PSScriptRoot "install_bundle.py"), "--profile", $Profile)
if ($Target) { $installArgs += @("--target", $Target) }
if ($DshBin) { $installArgs += @("--dsh-bin", $DshBin) }
if ($NoLink) { $installArgs += "--no-link" }
& $python @installArgs
if ($LASTEXITCODE -ne 0) { throw "DSH bundle installation failed; see the error above." }
