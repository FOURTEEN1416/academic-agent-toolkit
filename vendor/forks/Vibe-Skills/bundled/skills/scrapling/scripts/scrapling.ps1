# Thin wrapper for Scrapling CLI on Windows (PowerShell).
# - Verifies `scrapling` is available
# - If missing, prints install hints
# - Otherwise, forwards all args to `scrapling`

$ErrorActionPreference = "Stop"

$cmd = Get-Command scrapling -ErrorAction SilentlyContinue
if (-not $cmd) {
  Write-Host "[scrapling] Command not found on PATH." -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Install (recommended: CLI + MCP + fetchers):" -ForegroundColor Yellow
  Write-Host "  python -m pip install ""scrapling[ai]""" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Alternative (CLI fetch/extract only):" -ForegroundColor Yellow
  Write-Host "  python -m pip install ""scrapling[fetchers]""" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "If you use browser-based fetchers, install browsers:" -ForegroundColor Yellow
  Write-Host "  scrapling install" -ForegroundColor Yellow
  Write-Host "  # or: python -m playwright install" -ForegroundColor Yellow
  Write-Host ""
  exit 1
}

$target = if ($cmd.CommandType -in @("Application", "ExternalScript")) { $cmd.Source } else { $cmd.Name }
& $target @args
exit $LASTEXITCODE
