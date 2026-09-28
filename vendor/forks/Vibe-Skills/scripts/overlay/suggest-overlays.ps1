param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('agency', 'gitnexus', 'turix-cua', 'ruc-nlpir', 'vco')]
  [string]$Catalog,

  [Parameter(Mandatory = $true)]
  [string]$Task,

  [ValidateSet('think', 'do', 'review', 'team', 'retro', 'any')]
  [string]$Stage = 'any',

  [int]$TopK = 0,

  [string]$Select = '',

  [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
$script:SelfPath = $PSCommandPath

function Get-VcoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot '..\..') | Select-Object -ExpandProperty Path)
}

function Normalize-Text([string]$Text) {
  if ($null -eq $Text) { return '' }
  return $Text.ToLowerInvariant()
}

function Test-KeywordHit([string]$NormalizedText, [string]$Keyword) {
  if ([string]::IsNullOrWhiteSpace($Keyword)) { return $false }

  $kw = Normalize-Text $Keyword
  $isShortToken = $kw -match '^[a-z0-9]{1,3}$'
  if (-not $isShortToken) {
    return $NormalizedText.Contains($kw)
  }

  $pattern = "(?<![a-z0-9])$([regex]::Escape($kw))(?![a-z0-9])"
  return [regex]::IsMatch($NormalizedText, $pattern)
}

function Read-JsonFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "JSON file not found: $Path"
  }
  return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Resolve-RepoChildPath([string]$VcoRoot, [string]$RelativePath, [string]$AllowedSubtree) {
  if ([string]::IsNullOrWhiteSpace($RelativePath)) {
    throw "Path is required."
  }

  $repoRoot = [System.IO.Path]::GetFullPath($VcoRoot)
  $allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $AllowedSubtree))
  $resolvedPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
  $allowedPrefix = $allowedRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

  $isAllowed = $resolvedPath.Equals($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $resolvedPath.StartsWith($allowedPrefix, [System.StringComparison]::OrdinalIgnoreCase)

  if (-not $isAllowed) {
    throw "Path escapes allowed subtree '$AllowedSubtree': $RelativePath"
  }

  if (-not (Test-Path -LiteralPath $resolvedPath)) {
    throw "Path not found: $RelativePath"
  }

  return (Resolve-Path -LiteralPath $resolvedPath | Select-Object -ExpandProperty Path)
}

function Resolve-OverlayPath([string]$VcoRoot, [string]$OverlayPath) {
  return (Resolve-RepoChildPath -VcoRoot $VcoRoot -RelativePath $OverlayPath -AllowedSubtree 'references/overlays')
}

function Format-MatchSummary([string[]]$Hits) {
  if ($null -eq $Hits -or $Hits.Count -eq 0) { return 'hits: (none)' }
  $top = $Hits | Select-Object -First 6
  if ($Hits.Count -le 6) { return ('hits: ' + ($top -join ', ')) }
  return ('hits: ' + ($top -join ', ') + " ... +$($Hits.Count - $top.Count)")
}

function Find-OverlayByNumber([object[]]$RecommendedRows, [int]$Number) {
  if ($Number -lt 1 -or $Number -gt $RecommendedRows.Count) { return $null }
  return $RecommendedRows[$Number - 1]
}

function Render-OverlayInjection([string]$VcoRootPath, [object[]]$SelectedOverlays) {
  $parts = New-Object System.Collections.Generic.List[string]
  $parts.Add('--- BEGIN VCO PROMPT OVERLAY (advice-only) ---')

  foreach ($sel in $SelectedOverlays) {
    $overlayFile = Resolve-OverlayPath -VcoRoot $VcoRootPath -OverlayPath ([string]$sel.overlay_path)
    $body = Get-Content -LiteralPath $overlayFile -Raw -Encoding UTF8

    $parts.Add('')
    if ($sel.PSObject.Properties.Name -contains 'provider_id') {
      $parts.Add(("# Overlay: [{0}] {1}" -f [string]$sel.provider_id, [string]$sel.name))
    } else {
      $parts.Add(("# Overlay: {0}" -f [string]$sel.name))
    }
    $parts.Add($body.Trim())
  }

  $parts.Add('')
  $parts.Add('--- END VCO PROMPT OVERLAY ---')
  return ($parts -join "`n")
}

function Build-FamilyCatalogResult {
  param(
    [string]$CatalogId,
    [string]$VcoRoot,
    [object]$Config,
    [string]$TaskText,
    [string]$StageName,
    [int]$RequestedTopK,
    [string]$SelectText
  )

  $maxSelect = 1
  if ($null -ne $Config.max_select -and [int]$Config.max_select -gt 0) {
    $maxSelect = [int]$Config.max_select
  }

  $resolvedTopK = $RequestedTopK
  if ($resolvedTopK -le 0) {
    $resolvedTopK = [int]$Config.top_k
  }
  if ($resolvedTopK -le 0) { $resolvedTopK = 3 }

  $normalizedText = Normalize-Text $TaskText
  $overlayRows = @()

  foreach ($overlay in $Config.overlays) {
    $hits = @()
    foreach ($kw in $overlay.keywords) {
      if (Test-KeywordHit -NormalizedText $normalizedText -Keyword ([string]$kw)) {
        $hits += [string]$kw
      }
    }

    $score = [double]$hits.Count
    if ($StageName -ne 'any' -and $null -ne $overlay.preferred_stages) {
      $preferred = @($overlay.preferred_stages | ForEach-Object { Normalize-Text ([string]$_) })
      if ($preferred -contains (Normalize-Text $StageName)) {
        $score += 0.25
      }
    }

    $department = $null
    if ($overlay.PSObject.Properties.Name -contains 'department') {
      $department = [string]$overlay.department
    }

    $overlayRows += [pscustomobject]@{
      Id = [string]$overlay.id
      Name = [string]$overlay.name
      Department = $department
      Description = [string]$overlay.description
      OverlayPath = [string]$overlay.overlay_path
      PreferredStages = @($overlay.preferred_stages)
      Score = $score
      Hits = $hits
    }
  }

  $hasSignal = ($overlayRows | Where-Object { @($_.Hits).Count -gt 0 } | Measure-Object).Count -gt 0
  if (-not $hasSignal) {
    $fallbackIds = @()
    if ($null -ne $Config.stage_fallbacks) {
      $fallbackIds = @($Config.stage_fallbacks.$StageName)
      if ($fallbackIds.Count -eq 0) { $fallbackIds = @($Config.stage_fallbacks.any) }
    }

    $fallbackSet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($id in $fallbackIds) { [void]$fallbackSet.Add([string]$id) }

    $overlayRows = $overlayRows | Sort-Object -Property `
      @{ Expression = { $fallbackSet.Contains($_.Id) }; Descending = $true }, `
      @{ Expression = { $_.Score }; Descending = $true }, `
      @{ Expression = { $_.Name }; Descending = $false }
  } else {
    $overlayRows = $overlayRows | Sort-Object -Property `
      @{ Expression = { $_.Score }; Descending = $true }, `
      @{ Expression = { $_.Name }; Descending = $false }
  }

  $recommended = @($overlayRows | Select-Object -First $resolvedTopK)

  $menuLines = New-Object System.Collections.Generic.List[string]
  $menuLines.Add("Results: catalog=$CatalogId recommend $($recommended.Count) overlay(s) (advice-only), stage=$StageName.")
  $menuLines.Add("Options (select up to $maxSelect):")

  for ($i = 0; $i -lt $recommended.Count; $i++) {
    $row = $recommended[$i]
    $scoreText = "score=$([math]::Round($row.Score, 2))"
    $hitText = Format-MatchSummary $row.Hits
    $menuLines.Add(("{0}. {1} - {2} ({3}; {4})" -f ($i + 1), $row.Name, $row.Description, $scoreText, $hitText))
  }

  $menuLines.Add('')
  $menuLines.Add('Usage:')
  $menuLines.Add(("- Suggestions only: powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Catalog {1} -Task `"<text>`" -Stage {2}" -f $script:SelfPath, $CatalogId, $StageName))
  $menuLines.Add(("- Render injection:  powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Catalog {1} -Task `"<text>`" -Stage {2} -Select `"1`"" -f $script:SelfPath, $CatalogId, $StageName))

  $confirmUi = @{
    rendered_text = ($menuLines -join "`n")
    max_select = $maxSelect
    top_k = $resolvedTopK
  }

  $selectedOverlayObjs = @()
  if (-not [string]::IsNullOrWhiteSpace($SelectText)) {
    $tokens = $SelectText -split '[,\s]+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $selectedIds = [System.Collections.Generic.List[string]]::new()

    foreach ($t in $tokens) {
      $token = $t.Trim()
      if ($token -match '^\d+$') {
        $row = Find-OverlayByNumber -RecommendedRows $recommended -Number ([int]$token)
        if ($null -eq $row) { throw "Invalid selection number: $token" }
        $selectedIds.Add([string]$row.Id)
        continue
      }

      $match = @($Config.overlays | Where-Object { [string]$_.id -ieq $token } | Select-Object -First 1)
      if ($match.Count -eq 0) { throw "Unknown overlay id: $token" }
      $selectedIds.Add([string]$match[0].id)
    }

    $dedup = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($id in $selectedIds) { [void]$dedup.Add([string]$id) }
    $finalIds = @($dedup)
    if ($finalIds.Count -gt $maxSelect) {
      throw "Too many overlays selected ($($finalIds.Count)); max_select=$maxSelect"
    }

    foreach ($id in $finalIds) {
      $obj = @($Config.overlays | Where-Object { [string]$_.id -ieq $id } | Select-Object -First 1)[0]
      if ($null -eq $obj) { throw "Overlay config not found: $id" }
      $selectedOverlayObjs += $obj
    }
  }

  $result = @{
    version = 1
    catalog = $CatalogId
    task = $TaskText
    stage = $StageName
    top_k = $resolvedTopK
    recommendations = @(
      $recommended | ForEach-Object {
        $payload = @{
          id = $_.Id
          name = $_.Name
          description = $_.Description
          score = [math]::Round($_.Score, 2)
          hits = $_.Hits
          overlay_path = $_.OverlayPath
        }
        if (-not [string]::IsNullOrWhiteSpace($_.Department)) {
          $payload.department = $_.Department
        }
        $payload
      }
    )
    confirm_ui = $confirmUi
  }

  if ($selectedOverlayObjs.Count -gt 0) {
    $result.selected = @($selectedOverlayObjs | ForEach-Object { @{ id = $_.id; name = $_.name; overlay_path = $_.overlay_path } })
    $result.overlay_injection = Render-OverlayInjection -VcoRootPath $VcoRoot -SelectedOverlays $selectedOverlayObjs
  }

  return $result
}

function Build-VcoCatalogResult {
  param(
    [string]$VcoRoot,
    [object]$CatalogConfig,
    [string]$TaskText,
    [string]$StageName,
    [int]$RequestedTopK,
    [string]$SelectText
  )

  $maxSelect = 2
  if ($null -ne $CatalogConfig.max_select -and [int]$CatalogConfig.max_select -gt 0) {
    $maxSelect = [int]$CatalogConfig.max_select
  }

  $resolvedTopK = $RequestedTopK
  if ($resolvedTopK -le 0) {
    $resolvedTopK = [int]$CatalogConfig.top_k
  }
  if ($resolvedTopK -le 0) { $resolvedTopK = 4 }

  $providers = @()
  foreach ($p in $CatalogConfig.providers) {
    $providerConfig = Read-JsonFile (Resolve-RepoChildPath -VcoRoot $VcoRoot -RelativePath ([string]$p.config_path) -AllowedSubtree 'config')
    $priorityBoost = 0.0
    if ($null -ne $p.priority_boost) { $priorityBoost = [double]$p.priority_boost }
    $providers += [pscustomobject]@{
      Id = [string]$p.id
      Name = [string]$p.name
      PriorityBoost = $priorityBoost
      Config = $providerConfig
    }
  }

  $overlayById = [System.Collections.Generic.Dictionary[string, object]]::new([StringComparer]::OrdinalIgnoreCase)
  $overlayRows = @()
  $normalizedText = Normalize-Text $TaskText

  foreach ($provider in $providers) {
    foreach ($overlay in $provider.Config.overlays) {
      $overlayId = [string]$overlay.id
      if ($overlayById.ContainsKey($overlayId)) {
        throw "Duplicate overlay id across providers: $overlayId"
      }

      $hits = @()
      foreach ($kw in $overlay.keywords) {
        if (Test-KeywordHit -NormalizedText $normalizedText -Keyword ([string]$kw)) {
          $hits += [string]$kw
        }
      }

      $score = [double]$hits.Count
      if ($StageName -ne 'any' -and $null -ne $overlay.preferred_stages) {
        $preferred = @($overlay.preferred_stages | ForEach-Object { Normalize-Text ([string]$_) })
        if ($preferred -contains (Normalize-Text $StageName)) {
          $score += 0.25
        }
      }

      $score += [double]$provider.PriorityBoost

      $overlayById[$overlayId] = @{
        provider_id = $provider.Id
        provider_name = $provider.Name
        overlay = $overlay
      }

      $overlayRows += [pscustomobject]@{
        ProviderId = $provider.Id
        ProviderName = $provider.Name
        Id = $overlayId
        Name = [string]$overlay.name
        Description = [string]$overlay.description
        OverlayPath = [string]$overlay.overlay_path
        Score = $score
        HitCount = [int]$hits.Count
        Hits = $hits
      }
    }
  }

  $hasSignal = ($overlayRows | Where-Object { $_.HitCount -gt 0 } | Measure-Object).Count -gt 0
  if (-not $hasSignal) {
    $fallbackIds = @()
    if ($null -ne $CatalogConfig.stage_fallbacks) {
      $fallbackIds = @($CatalogConfig.stage_fallbacks.$StageName)
      if ($fallbackIds.Count -eq 0) { $fallbackIds = @($CatalogConfig.stage_fallbacks.any) }
    }

    $fallbackSet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($id in $fallbackIds) { [void]$fallbackSet.Add([string]$id) }

    $overlayRows = $overlayRows | Sort-Object -Property `
      @{ Expression = { $fallbackSet.Contains($_.Id) }; Descending = $true }, `
      @{ Expression = { $_.Score }; Descending = $true }, `
      @{ Expression = { $_.Name }; Descending = $false }
  } else {
    $overlayRows = $overlayRows | Sort-Object -Property `
      @{ Expression = { $_.Score }; Descending = $true }, `
      @{ Expression = { $_.Name }; Descending = $false }
  }

  $recommended = @($overlayRows | Select-Object -First $resolvedTopK)
  $menuLines = New-Object System.Collections.Generic.List[string]
  $menuLines.Add("Results: catalog=vco recommend $($recommended.Count) overlay(s) (advice-only), stage=$StageName.")
  $menuLines.Add("Options (select up to $maxSelect):")

  for ($i = 0; $i -lt $recommended.Count; $i++) {
    $row = $recommended[$i]
    $scoreText = "score=$([math]::Round($row.Score, 2))"
    $hitText = Format-MatchSummary $row.Hits
    $menuLines.Add(("{0}. [{1}] {2} - {3} ({4}; {5})" -f ($i + 1), $row.ProviderId, $row.Name, $row.Description, $scoreText, $hitText))
  }

  $menuLines.Add('')
  $menuLines.Add('Usage:')
  $menuLines.Add(("- Suggestions only: powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Catalog vco -Task `"<text>`" -Stage {1}" -f $script:SelfPath, $StageName))
  $menuLines.Add(("- Render injection:  powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Catalog vco -Task `"<text>`" -Stage {1} -Select `"1,2`"" -f $script:SelfPath, $StageName))

  $confirmUi = @{
    rendered_text = ($menuLines -join "`n")
    max_select = $maxSelect
    top_k = $resolvedTopK
  }

  $selectedOverlayRows = @()
  if (-not [string]::IsNullOrWhiteSpace($SelectText)) {
    $tokens = $SelectText -split '[,\s]+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $selectedIds = [System.Collections.Generic.List[string]]::new()

    foreach ($t in $tokens) {
      $token = $t.Trim()
      if ($token -match '^\d+$') {
        $row = Find-OverlayByNumber -RecommendedRows $recommended -Number ([int]$token)
        if ($null -eq $row) { throw "Invalid selection number: $token" }
        $selectedIds.Add([string]$row.Id)
        continue
      }

      if (-not $overlayById.ContainsKey($token)) { throw "Unknown overlay id: $token" }
      $selectedIds.Add([string]$token)
    }

    $dedup = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($id in $selectedIds) { [void]$dedup.Add([string]$id) }
    $finalIds = @($dedup)
    if ($finalIds.Count -gt $maxSelect) {
      throw "Too many overlays selected ($($finalIds.Count)); max_select=$maxSelect"
    }

    foreach ($id in $finalIds) {
      $meta = $overlayById[$id]
      $o = $meta.overlay
      $selectedOverlayRows += [pscustomobject]@{
        id = [string]$o.id
        name = [string]$o.name
        overlay_path = [string]$o.overlay_path
        provider_id = [string]$meta.provider_id
        provider_name = [string]$meta.provider_name
      }
    }
  }

  $result = @{
    version = 1
    catalog = 'vco'
    task = $TaskText
    stage = $StageName
    top_k = $resolvedTopK
    providers = @($providers | ForEach-Object { @{ id = $_.Id; name = $_.Name } })
    recommendations = @(
      $recommended | ForEach-Object {
        @{
          id = $_.Id
          name = $_.Name
          provider_id = $_.ProviderId
          description = $_.Description
          score = [math]::Round($_.Score, 2)
          hits = $_.Hits
          overlay_path = $_.OverlayPath
        }
      }
    )
    confirm_ui = $confirmUi
  }

  if ($selectedOverlayRows.Count -gt 0) {
    $result.selected = @($selectedOverlayRows | ForEach-Object { @{ id = $_.id; name = $_.name; provider_id = $_.provider_id; overlay_path = $_.overlay_path } })
    $result.overlay_injection = Render-OverlayInjection -VcoRootPath $VcoRoot -SelectedOverlays $selectedOverlayRows
  }

  return $result
}

$vcoRoot = Get-VcoRoot
$catalogSpecs = @{
  'agency' = 'config\agency-overlays.json'
  'gitnexus' = 'config\gitnexus-overlays.json'
  'turix-cua' = 'config\turix-cua-overlays.json'
  'ruc-nlpir' = 'config\ruc-nlpir-overlays.json'
  'vco' = 'config\vco-overlays.json'
}

$config = Read-JsonFile (Resolve-RepoChildPath -VcoRoot $vcoRoot -RelativePath $catalogSpecs[$Catalog] -AllowedSubtree 'config')
$result = if ($Catalog -eq 'vco') {
  Build-VcoCatalogResult -VcoRoot $vcoRoot -CatalogConfig $config -TaskText $Task -StageName $Stage -RequestedTopK $TopK -SelectText $Select
} else {
  Build-FamilyCatalogResult -CatalogId $Catalog -VcoRoot $vcoRoot -Config $config -TaskText $Task -StageName $Stage -RequestedTopK $TopK -SelectText $Select
}

if ($AsJson) {
  $result | ConvertTo-Json -Depth 8
  exit 0
}

Write-Output $result.confirm_ui.rendered_text
if ($result.ContainsKey('overlay_injection')) {
  Write-Output ''
  Write-Output $result.overlay_injection
}
