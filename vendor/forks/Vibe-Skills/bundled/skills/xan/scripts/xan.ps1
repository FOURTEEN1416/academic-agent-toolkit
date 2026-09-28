param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$XanArgs
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command xan -ErrorAction SilentlyContinue)) {
    Write-Error "xan CLI not found. Install xan first (recommended on Windows: scoop install xan)."
    exit 127
}

if (-not $XanArgs -or $XanArgs.Count -eq 0) {
    Write-Host "Usage: xan.ps1 <xan-subcommand> [args...]"
    Write-Host "Example: xan.ps1 count data.csv"
    exit 1
}

& xan @XanArgs
exit $LASTEXITCODE
