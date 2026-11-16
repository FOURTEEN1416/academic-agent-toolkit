param(
  [ValidateSet("codex", "claude-code", "both")]
  [string]$Target = "codex",
  [switch]$CleanLegacy,
  [switch]$CheckOnly,
  [string]$ProfileRoot = (Join-Path $env:USERPROFILE ".paperspine5\profiles\default"),
  [string]$ManifestPath = "",
  [string]$BundlePath = "",
  [string]$CodexSkillsRoot = "",
  [string]$ClaudeSkillsRoot = "",
  [string]$LegacyArchiveRoot = (Join-Path $env:USERPROFILE ".paperspine5\legacy-migrations")
)
$ErrorActionPreference = "Stop"
$Version = "0.4.0-alpha.3"
$ManifestUrl = "https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/website/downloads/manifest.json"
$MirrorManifestUrl = "https://wubing2023.github.io/PaperSpine/v5/downloads/manifest.json"

# GitHub only speaks TLS 1.2 and newer. Windows PowerShell 5.1 on older Windows
# builds still offers SSL3/TLS1.0 by default, and the handshake then dies with
# SEC_E_NO_CREDENTIALS or "Could not create SSL/TLS secure channel" before any
# HTTP status exists. That reads like a missing file, but it is a local TLS
# fault: the release assets are published and downloadable from a healthy host.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$nativeArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
try { $nativeArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() } catch { }
if ($env:OS -ne "Windows_NT" -or $nativeArch -notin @("AMD64", "X64")) {
  throw "This installer supports Windows x64 only; detected $($env:OS)/$nativeArch."
}
$ProfileRoot = [IO.Path]::GetFullPath($ProfileRoot)
if ($ManifestPath) {
  $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
  try { $manifest = Invoke-RestMethod -Uri $ManifestUrl -UseBasicParsing }
  catch {
    try { $manifest = Invoke-RestMethod -Uri $MirrorManifestUrl -UseBasicParsing }
    catch { throw "Cannot read the current manifest from GitHub or the website. For offline installation supply BOTH -ManifestPath and -BundlePath. $($_.Exception.Message)" }
  }
}
$suiteCandidates = @($manifest.artifacts | Where-Object { $_.kind -eq "suite" -and $_.platform -eq "windows-amd64" })
if ($suiteCandidates.Count -ne 1) { throw "Expected exactly one Windows x64 suite artifact in the current manifest." }
$artifact = $suiteCandidates[0]
$availableBuild = [string]$artifact.build_id
if ($availableBuild -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or [string]$manifest.version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or
    [string]$artifact.file -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$' -or [string]$artifact.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
    [string]$artifact.bytes -notmatch '^[1-9][0-9]*$' -or [string]$artifact.download_url -notmatch '^https://github\.com/WUBING2023/PaperSpine/releases/download/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.zip$') {
  throw "The selected suite metadata is invalid; no package will be guessed or installed."
}
if (($artifact.download_url -split "/")[-1] -ne $artifact.file) { throw "The artifact URL does not match its filename." }
$Version = [string]$manifest.version
$profileStatePath = Join-Path $ProfileRoot ".paperspine5-lifecycle\profile-state.json"
$currentBuild = $null
if (Test-Path -LiteralPath $profileStatePath) {
  $profileState = Get-Content -LiteralPath $profileStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
  $currentBuild = [string]$profileState.active_build_id
}
$targets = if ($Target -eq "both") { @("codex", "claude-code") } else { @($Target) }
$roots = @{}
foreach ($name in $targets) {
  $roots[$name] = if ($name -eq "codex") { if ($CodexSkillsRoot) { $CodexSkillsRoot } else { Join-Path $env:USERPROFILE ".codex\skills" } } else { if ($ClaudeSkillsRoot) { $ClaudeSkillsRoot } else { Join-Path $env:USERPROFILE ".claude\skills" } }
}
$installedRoot = Join-Path $ProfileRoot ".paperspine5-lifecycle\installs\$availableBuild"
$skillsReady = $true
foreach ($root in $roots.Values) {
  $skillRoot = Join-Path $root "paper-spine"
  $pointerPath = Join-Path $skillRoot "references\installed-suite.json"
  if (-not (Test-Path -LiteralPath (Join-Path $skillRoot "SKILL.md") -PathType Leaf) -or -not (Test-Path -LiteralPath $pointerPath -PathType Leaf)) { $skillsReady = $false; continue }
  try { $pointer = Get-Content -LiteralPath $pointerPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $skillsReady = $false; continue }
  if ($pointer.build_id -ne $availableBuild -or $pointer.suite_root -ne $installedRoot -or -not (Test-Path -LiteralPath $installedRoot -PathType Container)) { $skillsReady = $false }
}
$status = if (-not $currentBuild) { "not_installed" } elseif ($currentBuild -eq $availableBuild) { "up_to_date" } else { "update_available" }
if ($CheckOnly) {
  [ordered]@{ status = $status; platform = "windows-amd64"; current_build_id = $currentBuild; available_build_id = $availableBuild; version = $Version; skills_ready = $skillsReady; release_url = $manifest.release_url } | ConvertTo-Json
  return
}
if ($status -eq "up_to_date" -and $skillsReady) {
  if ($CleanLegacy) {
    $installed = Join-Path $ProfileRoot ".paperspine5-lifecycle\installs\$availableBuild"
    $localLauncher = Join-Path $installed "paperspine.cmd"
    $localPython = Join-Path $installed "runtime_vendor\windows-py312\python.exe"
    $localMigrator = Join-Path $installed "standalone\paper-spine\scripts\skill_discovery_migration.py"
    if (-not (Test-Path -LiteralPath $localLauncher) -or -not (Test-Path -LiteralPath $localPython) -or -not (Test-Path -LiteralPath $localMigrator)) { throw "The current profile is incomplete; cannot safely clean legacy discovery folders." }
    & $localLauncher verify-bundle --bundle $installed | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "The installed suite failed verification; legacy folders were not touched." }
    $migrationRoots = @()
    foreach ($entry in $roots.GetEnumerator()) { $migrationRoots += @("--skills-root", "$($entry.Key)=$($entry.Value)") }
    $previewText = & $localPython -I -B $localMigrator preview --archive-root $LegacyArchiveRoot --operation-id ("v5-preview-" + [guid]::NewGuid().ToString("N")) @migrationRoots
    if ($LASTEXITCODE -ne 0) { throw "Known legacy Skill migration preview failed." }
    $preview = $previewText | ConvertFrom-Json
    if ([int]$preview.item_count -gt 0) {
      & $localPython -I -B $localMigrator migrate --archive-root $LegacyArchiveRoot --operation-id ("v5-clean-" + [guid]::NewGuid().ToString("N")) @migrationRoots | Out-Host
      if ($LASTEXITCODE -ne 0) { throw "Known legacy Skill migration did not complete. Check permissions for -LegacyArchiveRoot; existing user data was retained." }
    }
  }
  Write-Output "PaperSpine5 $Version is up to date. Existing profile and Skills retained; no suite download required."
  return
}
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$downloadRoot = Join-Path ([IO.Path]::GetTempPath()) ("paperspine5-v5-" + [guid]::NewGuid().ToString("N"))
$extractRoot = Join-Path $downloadRoot "suite"
New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
$zipPath = Join-Path $downloadRoot $artifact.file
try {
  if ($BundlePath) { Copy-Item -LiteralPath $BundlePath -Destination $zipPath -Force } else { Invoke-WebRequest -Uri $artifact.download_url -OutFile $zipPath -UseBasicParsing }
  $actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualHash -ne $artifact.sha256.ToLowerInvariant()) { throw "SHA-256 mismatch for $($artifact.file)." }
  if ((Get-Item -LiteralPath $zipPath).Length -ne [int64]$artifact.bytes) { throw "Byte-size mismatch for $($artifact.file)." }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force
  $launcher = Join-Path $extractRoot "paperspine.cmd"
  $runtime = Join-Path $extractRoot "runtime_vendor\windows-py312\python.exe"
  $migrator = Join-Path $extractRoot "standalone\paper-spine\scripts\skill_discovery_migration.py"
  $skillStager = Join-Path $extractRoot "release\install_skill.py"
  if (-not (Test-Path -LiteralPath $launcher) -or -not (Test-Path -LiteralPath $runtime)) { throw "The downloaded V5 suite is incomplete." }
  & $launcher verify-bundle --bundle $zipPath | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "The downloaded V5 suite failed its internal verification." }
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $backupRoot = Join-Path $env:USERPROFILE ".paperspine5\backups\v5-install\$stamp"
  $operationId = if (Test-Path -LiteralPath $profileStatePath) { "v5-update-$stamp" } else { "v5-install-$stamp" }
  if ($CleanLegacy) {
    $migrationRoots = @()
    foreach ($entry in $roots.GetEnumerator()) { $migrationRoots += @("--skills-root", "$($entry.Key)=$($entry.Value)") }
    $previewText = & $runtime -I -B $migrator preview --archive-root $LegacyArchiveRoot --operation-id ("v5-preview-" + [guid]::NewGuid().ToString("N")) @migrationRoots
    if ($LASTEXITCODE -ne 0) { throw "Known legacy Skill migration preview failed." }
    $preview = $previewText | ConvertFrom-Json
    if ([int]$preview.item_count -gt 0) {
      & $runtime -I -B $migrator migrate --archive-root $LegacyArchiveRoot --operation-id $operationId @migrationRoots | Out-Host
      if ($LASTEXITCODE -ne 0) { throw "Known legacy Skill migration did not complete. Check permissions for -LegacyArchiveRoot; no V5 Skill was activated." }
    }
  }
  New-Item -ItemType Directory -Path $ProfileRoot -Force | Out-Null
  if ($status -eq "up_to_date") {
    Write-Output "Current profile retained; installed only missing target Skills."
  } elseif (Test-Path -LiteralPath $profileStatePath) {
    & $launcher update --profile-root $ProfileRoot --bundle $zipPath --operation-id $operationId --confirm | Out-Host
  } else {
    & $launcher install --profile-root $ProfileRoot --bundle $zipPath --operation-id $operationId | Out-Host
  }
  if ($LASTEXITCODE -ne 0) { throw "V5 profile installation/update failed." }
  & $launcher first-start --profile-root $ProfileRoot | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "V5 first-start health check failed." }
  foreach ($entry in $roots.GetEnumerator()) {
    $hostRoot = [IO.Path]::GetFullPath($entry.Value); $destination = Join-Path $hostRoot "paper-spine"
    if ($status -eq "up_to_date" -and $skillsReady) { continue }
    $prepared = Join-Path $downloadRoot ("prepared-skill-" + $entry.Key)
    & $runtime -I -B $skillStager --archive $zipPath --installed-root $installedRoot --prepared-root $prepared | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "V5 Skill staging failed; existing Skill was retained." }
    New-Item -ItemType Directory -Path $hostRoot -Force | Out-Null
    if (Test-Path -LiteralPath $destination) {
      $targetBackup = Join-Path $backupRoot (Join-Path $entry.Key "paper-spine")
      New-Item -ItemType Directory -Path (Split-Path $targetBackup) -Force | Out-Null
      $resolvedSource = [IO.Path]::GetFullPath($destination)
      $resolvedBackup = [IO.Path]::GetFullPath($targetBackup)
      $expectedBackupRoot = [IO.Path]::GetFullPath($backupRoot).TrimEnd('\') + '\'
      if ([IO.Path]::GetDirectoryName($resolvedSource) -ne $hostRoot.TrimEnd('\') -or -not $resolvedBackup.StartsWith($expectedBackupRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Skill backup path escaped its intended directory." }
      Move-Item -LiteralPath $resolvedSource -Destination $resolvedBackup
    }
    Move-Item -LiteralPath $prepared -Destination $destination
    Write-Output "Installed V5 paper-spine Skill for $($entry.Key): $destination"
  }
  Write-Output "PaperSpine5 V5 installed. Start a new host session before invoking paper-spine."
  Write-Output "Profile: $ProfileRoot"
  if ($CleanLegacy) { Write-Output "Known V3/V4 discovery folders were archived; user task data was retained." }
  Write-Output "Backup root: $backupRoot"
} finally {
  if (Test-Path -LiteralPath $downloadRoot) {
    $cleanup = [IO.Path]::GetFullPath($downloadRoot)
    $item = Get-Item -LiteralPath $cleanup -Force
    if ([IO.Path]::GetDirectoryName($cleanup) -ne $tempBase -or [IO.Path]::GetFileName($cleanup) -notmatch '^paperspine5-v5-[0-9a-f]{32}$' -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Refusing cleanup outside the unique installer temporary directory." }
    Remove-Item -LiteralPath $cleanup -Recurse -Force
  }
}
