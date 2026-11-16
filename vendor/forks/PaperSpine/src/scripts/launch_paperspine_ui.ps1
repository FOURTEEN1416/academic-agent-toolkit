[CmdletBinding()]
param(
    [string]$OutputDir = "paper_rewriting_output",
    [string]$ProfileRoot = "",
    [switch]$LegacyRunner,
    [switch]$InPlace,
    [switch]$NoOpen,
    [string]$ProjectRoot = "",
    [Alias("h", "help")]
    [switch]$ShowHelp
)

$ErrorActionPreference = "Stop"

if ($ShowHelp -or $OutputDir -eq "--help") {
    @"
PaperSpine5 Product Web launcher

Usage:
  launch_paperspine_ui.ps1 [-ProfileRoot <path>] [-NoOpen] [-ProjectRoot <path>]
  launch_paperspine_ui.ps1 -? | -h | -help | --help

The default reuses the remembered public profile. -LegacyRunner retains the
old -OutputDir launch. Help never starts a process or writes files.
"@ | Write-Output
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillRoot = Split-Path -Parent $scriptDir
$launcher = Join-Path $scriptDir "paperspine5_web.py"

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "PaperSpine5 Web launcher not found: $launcher"
}

$arguments = @($launcher, "launch")
if ($LegacyRunner) {
    $arguments += @("--legacy-runner", "--output-dir", $OutputDir)
} elseif ($ProfileRoot) {
    $arguments += @("--profile-root", $ProfileRoot)
} elseif ($PSBoundParameters.ContainsKey("OutputDir")) {
    throw "Use -ProfileRoot for the public Web, or -LegacyRunner for an existing old -OutputDir workspace. No task was moved."
}
if ($NoOpen) {
    $arguments += "--no-open"
}
if ($ProjectRoot) {
    $arguments += @("--project-root", $ProjectRoot)
}

function Test-PaperSpinePython {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Prefix = @()
    )
    try {
        & $Path @Prefix -B -c "import sys" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PaperSpinePython {
    $explicit = $env:PAPERSPINE5_PYTHON
    if ($explicit) {
        $explicitCommand = Get-Command $explicit -ErrorAction SilentlyContinue
        if ($explicitCommand -and $explicitCommand.CommandType -in @("Application", "ExternalScript")) {
            $explicitPath = if ($explicitCommand.Path) { $explicitCommand.Path } else { $explicitCommand.Source }
            if (Test-PaperSpinePython -Path $explicitPath) {
                return @{ Path = $explicitPath; Prefix = @() }
            }
        }
        throw "PAPERSPINE5_PYTHON does not point to a working Python executable: $explicit"
    }

    $candidatePaths = @(
        (Join-Path $skillRoot "_paperspine5\06_插件化\runtime_vendor\windows-py312\python.exe")
    )
    try {
        $sourceRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
        $candidatePaths += Join-Path $sourceRoot "06_插件化\runtime_vendor\windows-py312\python.exe"
    } catch {
        # The installed Skill may not have a source checkout beside it.
    }
    foreach ($candidate in $candidatePaths) {
        if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (Test-PaperSpinePython -Path $candidate)) {
            return @{ Path = $candidate; Prefix = @() }
        }
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python -and $python.CommandType -in @("Application", "ExternalScript")) {
        $pythonPath = if ($python.Path) { $python.Path } else { $python.Source }
        if (Test-PaperSpinePython -Path $pythonPath) {
            return @{ Path = $pythonPath; Prefix = @() }
        }
    }
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py -and $py.CommandType -in @("Application", "ExternalScript")) {
        $pyPath = if ($py.Path) { $py.Path } else { $py.Source }
        if (Test-PaperSpinePython -Path $pyPath -Prefix @("-3")) {
            return @{ Path = $pyPath; Prefix = @("-3") }
        }
    }
    throw "No working Python interpreter was found for PaperSpine5. Set PAPERSPINE5_PYTHON or install Python 3."
}

# InPlace is retained only for command compatibility. The supported user
# surface is always the loopback Web workspace; no terminal intake is started.
$env:PYTHONUTF8 = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
$runtime = Resolve-PaperSpinePython
if ($runtime.Prefix.Count -gt 0) {
    & $runtime.Path @($runtime.Prefix) -B @arguments
} else {
    & $runtime.Path -B @arguments
}
exit $LASTEXITCODE
