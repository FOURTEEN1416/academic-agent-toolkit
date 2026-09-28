[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($null -eq $CliArgs) {
  $CliArgs = @()
}

$engine = 'compat'
$openBinary = if ($env:RALPH_OPEN_BINARY) { $env:RALPH_OPEN_BINARY } else { 'ralph' }
$openAllowCommit = $false
$normalizedArgs = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $CliArgs.Count; $i++) {
  $arg = $CliArgs[$i]
  switch ($arg.ToLowerInvariant()) {
    '--engine' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--engine requires a value: compat|open'
      }

      $i += 1
      $candidate = $CliArgs[$i].ToLowerInvariant()
      if ($candidate -notin @('compat', 'open')) {
        throw "--engine must be 'compat' or 'open'. Got: $($CliArgs[$i])"
      }

      $engine = $candidate
      continue
    }
    '--open-binary' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--open-binary requires a value'
      }

      $i += 1
      $openBinary = $CliArgs[$i]
      continue
    }
    '--open-allow-commit' {
      $openAllowCommit = $true
      continue
    }
    default {
      $normalizedArgs.Add($arg)
      continue
    }
  }
}

$CliArgs = @($normalizedArgs)

function Show-Help {
  @(
    'Ralph Loop (Codex compatibility mode)',
    '',
    'Usage:',
    '  ralph-loop.ps1 [--engine compat|open] <PROMPT...> [--max-iterations N] [--completion-promise TEXT] [--force]',
    '  ralph-loop.ps1 --next',
    '  ralph-loop.ps1 --status',
    '  ralph-loop.ps1 --stop',
    '',
    'Engine Options:',
    '  --engine compat|open   Execution engine. compat=local state loop (default), open=external open-ralph-wiggum CLI',
    '  --open-binary PATH     Override open engine binary (default: ralph or $env:RALPH_OPEN_BINARY)',
    '  --open-allow-commit    For --engine open, do not auto-inject --no-commit',
    '',
    'Options:',
    '  --max-iterations N       Maximum iterations before auto-stop (0 = unlimited)',
    '  --completion-promise TXT Completion promise text stored in state',
    '  --state-file PATH        Override state file path (default: .claude/ralph-loop.local.md)',
    '  --next                   Advance to next iteration',
    '  --status                 Show current loop state',
    '  --stop                   Cancel loop (delegates to cancel-ralph script if available)',
    '  --force                  Replace existing active state when starting a new loop',
    '  -h, --help               Show this help'
  ) | ForEach-Object { Write-Host $_ }
}

function Invoke-OpenEngine {
  param(
    [Parameter(Mandatory = $true)][string[]]$ForwardArgs,
    [Parameter(Mandatory = $true)][string]$Binary,
    [Parameter(Mandatory = $true)][bool]$AllowCommit
  )

  foreach ($blocked in @('--next', '-next', '--force', '-force', '--state-file', '--stop', '-stop')) {
    if ($ForwardArgs -contains $blocked) {
      switch ($blocked) {
        '--next' { throw "--next is compat-only. Use '--engine compat --next' or run a fresh open-engine loop." }
        '-next' { throw "-next is compat-only. Use '--engine compat --next' or run a fresh open-engine loop." }
        '--force' { throw "--force is compat-only. Use '--engine compat --force' for local state replacement." }
        '-force' { throw "-force is compat-only. Use '--engine compat --force' for local state replacement." }
        '--state-file' { throw "--state-file is compat-only. open-ralph-wiggum manages its own .ralph state." }
        '--stop' { throw "--stop is compat-only. For open engine, stop the running process/session directly." }
        '-stop' { throw "-stop is compat-only. For open engine, stop the running process/session directly." }
      }
    }
  }

  $resolvedBinary = $Binary
  if (-not [System.IO.Path]::IsPathRooted($resolvedBinary)) {
    $cmd = Get-Command -Name $resolvedBinary -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
      throw "Open engine binary not found: $resolvedBinary. Install via: npm install -g @th0rgal/ralph-wiggum"
    }
    $resolvedBinary = $cmd.Source
  }

  $argsToPass = New-Object System.Collections.Generic.List[string]
  foreach ($a in $ForwardArgs) { $argsToPass.Add($a) }

  $hasAgent = $false
  $hasNoCommit = $false
  for ($idx = 0; $idx -lt $argsToPass.Count; $idx++) {
    switch ($argsToPass[$idx].ToLowerInvariant()) {
      '--agent' { $hasAgent = $true }
      '--no-commit' { $hasNoCommit = $true }
    }
  }

  if (-not $hasAgent) {
    $argsToPass.Add('--agent')
    $argsToPass.Add('codex')
  }

  if ((-not $AllowCommit) -and (-not $hasNoCommit)) {
    $argsToPass.Add('--no-commit')
  }

  Write-Host "Ralph loop engine: open"
  Write-Host "Binary: $resolvedBinary"

  & $resolvedBinary @argsToPass
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    exit $code
  }

  exit 0
}

if ($engine -eq 'open') {
  Invoke-OpenEngine -ForwardArgs $CliArgs -Binary $openBinary -AllowCommit:$openAllowCommit
}

function Resolve-AbsolutePath {
  param([Parameter(Mandatory = $true)][string]$PathText)

  if ([System.IO.Path]::IsPathRooted($PathText)) {
    return [System.IO.Path]::GetFullPath($PathText)
  }

  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathText))
}

function Get-State {
  param([Parameter(Mandatory = $true)][string]$StatePath)

  $raw = Get-Content -LiteralPath $StatePath -Raw
  $match = [regex]::Match($raw, '(?s)^---\r?\n(.*?)\r?\n---\r?\n?(.*)$')
  if (-not $match.Success) {
    throw "Ralph state file is invalid: $StatePath"
  }

  $metaBlock = $match.Groups[1].Value
  $promptText = $match.Groups[2].Value

  if ([string]::IsNullOrWhiteSpace($promptText)) {
    throw "Ralph state file has no prompt body: $StatePath"
  }

  $meta = @{}
  foreach ($line in ($metaBlock -split '\r?\n')) {
    if ([string]::IsNullOrWhiteSpace($line)) {
      continue
    }

    $parts = $line -split ':\s*', 2
    if ($parts.Count -eq 2) {
      $meta[$parts[0].Trim()] = $parts[1].Trim()
    }
  }

  if (-not $meta.ContainsKey('iteration')) {
    throw "Ralph state missing 'iteration'"
  }

  if (-not $meta.ContainsKey('max_iterations')) {
    throw "Ralph state missing 'max_iterations'"
  }

  $iteration = 0
  if (-not [int]::TryParse($meta['iteration'], [ref]$iteration)) {
    throw "Ralph state has invalid iteration value: $($meta['iteration'])"
  }

  $maxIterations = 0
  if (-not [int]::TryParse($meta['max_iterations'], [ref]$maxIterations)) {
    throw "Ralph state has invalid max_iterations value: $($meta['max_iterations'])"
  }

  $completionPromise = if ($meta.ContainsKey('completion_promise')) { $meta['completion_promise'] } else { 'null' }
  if ($completionPromise -match '^"(.*)"$') {
    $completionPromise = $Matches[1]
  }
  if ($completionPromise -eq 'null') {
    $completionPromise = $null
  }

  $startedAt = if ($meta.ContainsKey('started_at') -and -not [string]::IsNullOrWhiteSpace($meta['started_at'])) {
    $meta['started_at'].Trim('"')
  }
  else {
    (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  }

  return [pscustomobject]@{
    Iteration         = $iteration
    MaxIterations     = $maxIterations
    CompletionPromise = $completionPromise
    StartedAt         = $startedAt
    Prompt            = ($promptText -replace '^\r?\n', '').TrimEnd()
  }
}

function Convert-CompletionPromiseToYaml {
  param([string]$CompletionPromise)

  if ([string]::IsNullOrWhiteSpace($CompletionPromise)) {
    return 'null'
  }

  $escaped = $CompletionPromise.Replace('\\', '\\\\').Replace('"', '\\"')
  return '"' + $escaped + '"'
}

function Write-State {
  param(
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][int]$Iteration,
    [Parameter(Mandatory = $true)][int]$MaxIterations,
    [string]$CompletionPromise,
    [Parameter(Mandatory = $true)][string]$StartedAt,
    [Parameter(Mandatory = $true)][string]$Prompt
  )

  $parent = Split-Path -Parent $StatePath
  if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }

  $completionYaml = Convert-CompletionPromiseToYaml -CompletionPromise $CompletionPromise

  $content = @(
    '---'
    'active: true'
    "iteration: $Iteration"
    "max_iterations: $MaxIterations"
    "completion_promise: $completionYaml"
    ('started_at: "{0}"' -f $StartedAt)
    '---'
    ''
    $Prompt
  ) -join "`n"

  Set-Content -LiteralPath $StatePath -Value $content -Encoding UTF8
}

function Show-StateSummary {
  param(
    [Parameter(Mandatory = $true)][int]$Iteration,
    [Parameter(Mandatory = $true)][int]$MaxIterations,
    [string]$CompletionPromise,
    [Parameter(Mandatory = $true)][string]$Prompt,
    [Parameter(Mandatory = $true)][string]$StatePath
  )

  $maxText = if ($MaxIterations -gt 0) { "$MaxIterations" } else { 'unlimited' }
  $promiseText = if ([string]::IsNullOrWhiteSpace($CompletionPromise)) { 'none' } else { "<promise>$CompletionPromise</promise>" }

  Write-Host "Ralph state file: $StatePath"
  Write-Host "Iteration: $Iteration"
  Write-Host "Max iterations: $maxText"
  Write-Host "Completion promise: $promiseText"
  Write-Host ''
  Write-Host 'Prompt:'
  Write-Host $Prompt
}

function Remove-CorruptedState {
  param(
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  Write-Host "Ralph loop: state is corrupted - $Reason"
  Write-Host "Removing state file: $StatePath"
  Remove-Item -LiteralPath $StatePath -Force
}

function Continue-Loop {
  param([Parameter(Mandatory = $true)][string]$StatePath)

  if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Host 'No active Ralph loop found.'
    return
  }

  $state = $null
  try {
    $state = Get-State -StatePath $StatePath
  }
  catch {
    Remove-CorruptedState -StatePath $StatePath -Reason $_.Exception.Message
    return
  }

  if ($state.MaxIterations -gt 0 -and $state.Iteration -ge $state.MaxIterations) {
    Write-Host "Ralph loop stopped: max iterations ($($state.MaxIterations)) reached."
    Remove-Item -LiteralPath $StatePath -Force
    return
  }

  $nextIteration = $state.Iteration + 1
  Write-State -StatePath $StatePath -Iteration $nextIteration -MaxIterations $state.MaxIterations -CompletionPromise $state.CompletionPromise -StartedAt $state.StartedAt -Prompt $state.Prompt

  Write-Host 'Ralph loop continued.'
  Show-StateSummary -Iteration $nextIteration -MaxIterations $state.MaxIterations -CompletionPromise $state.CompletionPromise -Prompt $state.Prompt -StatePath $StatePath
}

function Show-Status {
  param([Parameter(Mandatory = $true)][string]$StatePath)

  if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Host 'No active Ralph loop found.'
    return
  }

  $state = $null
  try {
    $state = Get-State -StatePath $StatePath
  }
  catch {
    Write-Host "Ralph loop: cannot read state. $($_.Exception.Message)"
    return
  }

  Show-StateSummary -Iteration $state.Iteration -MaxIterations $state.MaxIterations -CompletionPromise $state.CompletionPromise -Prompt $state.Prompt -StatePath $StatePath
}

$promptParts = New-Object System.Collections.Generic.List[string]
$maxIterations = 0
$completionPromise = $null
$stateFile = '.claude/ralph-loop.local.md'
$stateFileFromCli = $false
$force = $false
$next = $false
$status = $false
$stop = $false

for ($i = 0; $i -lt $CliArgs.Count; $i++) {
  $arg = $CliArgs[$i]
  switch ($arg.ToLowerInvariant()) {
    '--help' { Show-Help; exit 0 }
    '-h' { Show-Help; exit 0 }
    '--next' { $next = $true; continue }
    '-next' { $next = $true; continue }
    '--status' { $status = $true; continue }
    '-status' { $status = $true; continue }
    '--stop' { $stop = $true; continue }
    '-stop' { $stop = $true; continue }
    '--force' { $force = $true; continue }
    '-force' { $force = $true; continue }
    '--max-iterations' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--max-iterations requires a numeric value'
      }

      $i += 1
      $parsedMax = 0
      if (-not [int]::TryParse($CliArgs[$i], [ref]$parsedMax) -or $parsedMax -lt 0) {
        throw "--max-iterations must be an integer >= 0. Got: $($CliArgs[$i])"
      }

      $maxIterations = $parsedMax
      continue
    }
    '--completion-promise' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--completion-promise requires a value'
      }

      $i += 1
      $completionPromise = $CliArgs[$i]
      continue
    }
    '--state-file' {
      if ($i + 1 -ge $CliArgs.Count) {
        throw '--state-file requires a path'
      }

      $i += 1
      $stateFile = $CliArgs[$i]
      $stateFileFromCli = $true
      continue
    }
    default {
      $promptParts.Add($arg)
      continue
    }
  }
}

$resolvedStatePath = Resolve-AbsolutePath -PathText $stateFile
if (-not $stateFileFromCli) {
  $fallbackPath = Resolve-AbsolutePath -PathText '.codex/ralph-loop.local.md'
  if (-not (Test-Path -LiteralPath $resolvedStatePath) -and (Test-Path -LiteralPath $fallbackPath)) {
    $resolvedStatePath = $fallbackPath
  }
}

if ($status) {
  Show-Status -StatePath $resolvedStatePath
  exit 0
}

if ($stop) {
  $codeHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
  $cancelScript = Join-Path $codeHome 'skills/cancel-ralph/scripts/cancel-ralph.ps1'

  if (Test-Path -LiteralPath $cancelScript) {
    & $cancelScript --state-file $resolvedStatePath
  }
  else {
    if (-not (Test-Path -LiteralPath $resolvedStatePath)) {
      Write-Host 'No active Ralph loop found.'
      exit 0
    }

    $raw = Get-Content -LiteralPath $resolvedStatePath -Raw
    $iteration = if ($raw -match '(?m)^iteration:\s*([0-9]+)\s*$') { $Matches[1] } else { 'unknown' }
    Remove-Item -LiteralPath $resolvedStatePath -Force
    Write-Host "Cancelled Ralph loop (was at iteration $iteration)"
  }

  exit 0
}

if ($next) {
  Continue-Loop -StatePath $resolvedStatePath
  exit 0
}

$prompt = ($promptParts -join ' ').Trim()

if ([string]::IsNullOrWhiteSpace($prompt)) {
  if (Test-Path -LiteralPath $resolvedStatePath) {
    Continue-Loop -StatePath $resolvedStatePath
    exit 0
  }

  throw 'No prompt provided. Use --help for usage.'
}

if ((Test-Path -LiteralPath $resolvedStatePath) -and -not $force) {
  throw "An active Ralph loop already exists at: $resolvedStatePath. Use --next to continue or --force to replace it."
}

if ($force -and (Test-Path -LiteralPath $resolvedStatePath)) {
  Remove-Item -LiteralPath $resolvedStatePath -Force
}

$startedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
Write-State -StatePath $resolvedStatePath -Iteration 1 -MaxIterations $maxIterations -CompletionPromise $completionPromise -StartedAt $startedAt -Prompt $prompt

Write-Host 'Ralph loop activated.'
Show-StateSummary -Iteration 1 -MaxIterations $maxIterations -CompletionPromise $completionPromise -Prompt $prompt -StatePath $resolvedStatePath

if (-not [string]::IsNullOrWhiteSpace($completionPromise)) {
  Write-Host ''
  Write-Host 'Completion marker (emit only when true):'
  Write-Host "<promise>$completionPromise</promise>"
}

