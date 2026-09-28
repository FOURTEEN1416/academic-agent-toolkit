param(
    [switch]$Fast,
    [switch]$StrictKeywords
)

$ErrorActionPreference = "Stop"

function Invoke-Route {
    param(
        [string]$Prompt,
        [string]$Grade,
        [string]$TaskType,
        [string]$RequestedSkill
    )

    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $resolver = Join-Path $repoRoot "scripts\router\resolve-pack-route.ps1"

    $routeArgs = @{
        Prompt = $Prompt
        Grade = $Grade
        TaskType = $TaskType
    }

    if ($RequestedSkill) {
        $routeArgs["RequestedSkill"] = $RequestedSkill
    }

    $json = & $resolver @routeArgs
    return ($json | ConvertFrom-Json)
}

function Normalize-RouteKeyword {
    param([string]$Keyword)

    if ($null -eq $Keyword) { return "" }
    return ([string]$Keyword).Trim().ToLowerInvariant()
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$configRoot = Join-Path $repoRoot "config"
$packManifestPath = Join-Path $configRoot "pack-manifest.json"
$thresholdPath = Join-Path $configRoot "router-thresholds.json"

$packManifest = Get-Content -LiteralPath $packManifestPath -Raw | ConvertFrom-Json
$thresholds = Get-Content -LiteralPath $thresholdPath -Raw | ConvertFrom-Json

$fallbackThreshold = [double]$thresholds.thresholds.fallback_to_legacy_below
$interferenceGapMin = 0.03

$total = 0
$pass = 0
$fail = 0
$warn = 0
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Record-Check {
    param(
        [bool]$Condition,
        [string]$Message
    )

    $script:total++
    if ($Condition) {
        $script:pass++
        return
    }

    $script:fail++
    $script:failures.Add($Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Record-WarnOrFail {
    param(
        [bool]$Condition,
        [string]$Message
    )

    $script:total++
    if ($Condition) {
        $script:pass++
        return
    }

    if ($StrictKeywords) {
        $script:fail++
        $script:failures.Add($Message)
        Write-Host "[FAIL] $Message" -ForegroundColor Red
        return
    }

    $script:warn++
    $script:warnings.Add($Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

Write-Host "=== VCO Keyword Precision Audit (Bilingual + Interference) ==="

# 1) Keyword health: all packs must have non-empty triggers.
# Core packs should be bilingual (EN + ZH) to avoid regressions for Chinese-first workflows.
$corePacks = @(
    "code-quality",
    "data-ml",
    "bio-science",
    "docs-media",
    "integration-devops",
    "ai-llm",
    "research-design"
)

foreach ($pack in $packManifest.packs) {
    $normalized = @($pack.trigger_keywords | ForEach-Object { Normalize-RouteKeyword -Keyword $_ } | Where-Object { $_ })
    Record-Check -Condition ($normalized.Count -gt 0) -Message "pack '$($pack.id)' has no usable trigger keywords after normalization"

    $hasEnglish = ($normalized | Where-Object { $_ -match "[a-z]" }).Count -gt 0
    $hasChinese = ($normalized | Where-Object { $_ -match "[\u4E00-\u9FFF]" }).Count -gt 0
    if ($corePacks -contains [string]$pack.id) {
        Record-Check -Condition $hasEnglish -Message "pack '$($pack.id)' lacks English trigger keywords (core pack requires bilingual triggers)"
        Record-Check -Condition $hasChinese -Message "pack '$($pack.id)' lacks Chinese trigger keywords (core pack requires bilingual triggers)"
    }

    $rawKeywords = @($pack.trigger_keywords | ForEach-Object { [string]$_ })
    Record-WarnOrFail -Condition (($rawKeywords | Where-Object { -not $_ -or -not $_.Trim() }).Count -eq 0) -Message "pack '$($pack.id)' trigger_keywords contain empty items"
    Record-WarnOrFail -Condition (($rawKeywords | Where-Object { $_ -ne $_.Trim() }).Count -eq 0) -Message "pack '$($pack.id)' trigger_keywords contain leading/trailing whitespace (normalize before scoring)"
    Record-WarnOrFail -Condition (($rawKeywords | Where-Object { $_ -cmatch '[A-Z]' }).Count -eq 0) -Message "pack '$($pack.id)' trigger_keywords contain uppercase ASCII (store lowercase to avoid score drift)"

    $dups = $normalized | Group-Object | Where-Object { $_.Count -gt 1 }
    Record-WarnOrFail -Condition ($dups.Count -eq 0) -Message "pack '$($pack.id)' trigger_keywords have duplicates after normalization (trim+lower)"
}

# 2) Pack-level bilingual routing and interference gap checks.
$probeCases = @(
    [pscustomobject]@{ Pack = "workflow-compatibility"; Grade = "L"; Task = "planning"; En = "/speckit.plan create the technical plan"; Zh = "/speckit.plan 生成技术计划" },
    [pscustomobject]@{ Pack = "code-quality"; Grade = "M"; Task = "review"; En = "Run code review, lint, and debugging quality checks"; Zh = "请做代码审查、调试和质量检查" },
    [pscustomobject]@{ Pack = "data-ml"; Grade = "L"; Task = "research"; En = "Machine learning model training with regression and feature engineering"; Zh = "请做机器学习模型训练、回归和特征工程分析" },
    [pscustomobject]@{ Pack = "bio-science"; Grade = "L"; Task = "research"; En = "Bioinformatics genomics sequencing pathway analysis"; Zh = "请做生物信息基因组测序和通路分析" },
    [pscustomobject]@{ Pack = "docs-media"; Grade = "M"; Task = "coding"; En = "Process spreadsheet xlsx and generate docx pdf output"; Zh = "请处理表格xlsx并生成docx和pdf文档" },
    [pscustomobject]@{ Pack = "integration-devops"; Grade = "L"; Task = "debug"; En = "Debug github ci cd deployment pipeline with sentry"; Zh = "请排查github持续集成部署流水线并结合sentry" },
    [pscustomobject]@{ Pack = "ai-llm"; Grade = "M"; Task = "research"; En = "Optimize llm prompt and rag embedding retrieval with openai"; Zh = "请做大模型提示词和rag嵌入检索优化" },
    [pscustomobject]@{ Pack = "research-design"; Grade = "L"; Task = "planning"; En = "Research methodology, hypothesis, and experimental design"; Zh = "请做研究方法学、假设与实验设计规划" }
)

foreach ($case in $probeCases) {
    $enRoute = Invoke-Route -Prompt $case.En -Grade $case.Grade -TaskType $case.Task -RequestedSkill $null
    $zhRoute = Invoke-Route -Prompt $case.Zh -Grade $case.Grade -TaskType $case.Task -RequestedSkill $null

    Record-Check -Condition ($enRoute.selected.pack_id -eq $case.Pack) -Message "[EN] expected pack '$($case.Pack)', got '$($enRoute.selected.pack_id)'"
    Record-Check -Condition ($zhRoute.selected.pack_id -eq $case.Pack) -Message "[ZH] expected pack '$($case.Pack)', got '$($zhRoute.selected.pack_id)'"
    Record-Check -Condition ($enRoute.route_mode -in @("pack_overlay", "confirm_required")) -Message "[EN] '$($case.Pack)' route mode is invalid: '$($enRoute.route_mode)'"
    Record-Check -Condition ($zhRoute.route_mode -in @("pack_overlay", "confirm_required")) -Message "[ZH] '$($case.Pack)' route mode is invalid: '$($zhRoute.route_mode)'"

    $enTop = [double]$enRoute.ranked[0].score
    $enSecond = if ($enRoute.ranked.Count -gt 1) { [double]$enRoute.ranked[1].score } else { 0.0 }
    $zhTop = [double]$zhRoute.ranked[0].score
    $zhSecond = if ($zhRoute.ranked.Count -gt 1) { [double]$zhRoute.ranked[1].score } else { 0.0 }

    $enGap = [Math]::Round($enTop - $enSecond, 4)
    $zhGap = [Math]::Round($zhTop - $zhSecond, 4)
    Record-Check -Condition ($enGap -ge $interferenceGapMin) -Message "[EN] '$($case.Pack)' interference gap too small: $enGap"
    Record-Check -Condition ($zhGap -ge $interferenceGapMin) -Message "[ZH] '$($case.Pack)' interference gap too small: $zhGap"
}

# 3) Skill-level sweep: every migrated skill should stably map to its pack in EN/ZH prompts.
$packContext = @{
    "workflow-compatibility" = @{ Grade = "L"; Task = "planning" }
    "code-quality"       = @{ Grade = "M"; Task = "review" }
    "data-ml"            = @{ Grade = "L"; Task = "research" }
    "bio-science"        = @{ Grade = "L"; Task = "research" }
    "docs-media"         = @{ Grade = "M"; Task = "coding" }
    "integration-devops" = @{ Grade = "L"; Task = "debug" }
    "ai-llm"             = @{ Grade = "M"; Task = "research" }
    "research-design"    = @{ Grade = "L"; Task = "planning" }
}

$skillToPacks = @{}
foreach ($p in $packManifest.packs) {
    foreach ($s in @($p.skill_candidates)) {
        $skillId = [string]$s
        if (-not $skillToPacks.ContainsKey($skillId)) {
            $skillToPacks[$skillId] = New-Object System.Collections.Generic.HashSet[string]
        }
        [void]$skillToPacks[$skillId].Add([string]$p.id)
    }
}

$skillTotal = 0
if (-not $Fast) {
    foreach ($pack in $packManifest.packs) {
        $ctx = $packContext[$pack.id]
        if (-not $ctx) { continue }

        foreach ($skill in $pack.skill_candidates) {
            $skillTotal++
            $enPrompt = "please use $skill for this task"
            $zhPrompt = "请使用 $skill 处理这个任务"

            $enRoute = Invoke-Route -Prompt $enPrompt -Grade $ctx.Grade -TaskType $ctx.Task -RequestedSkill $skill
            $zhRoute = Invoke-Route -Prompt $zhPrompt -Grade $ctx.Grade -TaskType $ctx.Task -RequestedSkill $skill

            $allowedPacks = @()
            if ($skillToPacks.ContainsKey($skill)) { $allowedPacks = @($skillToPacks[$skill]) }
            Record-Check -Condition (($allowedPacks | Where-Object { $_ -eq $enRoute.selected.pack_id }).Count -gt 0) -Message "[EN skill] $skill selected pack '$($enRoute.selected.pack_id)' is not in manifest candidates for this skill"
            Record-Check -Condition (($allowedPacks | Where-Object { $_ -eq $zhRoute.selected.pack_id }).Count -gt 0) -Message "[ZH skill] $skill selected pack '$($zhRoute.selected.pack_id)' is not in manifest candidates for this skill"

            Record-WarnOrFail -Condition ($enRoute.selected.pack_id -eq $pack.id) -Message "[EN skill] $skill routes to pack '$($enRoute.selected.pack_id)' instead of manifest pack '$($pack.id)' (skill appears in multiple packs)"
            Record-WarnOrFail -Condition ($zhRoute.selected.pack_id -eq $pack.id) -Message "[ZH skill] $skill routes to pack '$($zhRoute.selected.pack_id)' instead of manifest pack '$($pack.id)' (skill appears in multiple packs)"

            Record-Check -Condition ($enRoute.selected.pack_id -eq $zhRoute.selected.pack_id) -Message "[skill] $skill pack differs between EN and ZH: '$($enRoute.selected.pack_id)' vs '$($zhRoute.selected.pack_id)'"
            Record-Check -Condition ($enRoute.selected.skill -eq $skill) -Message "[EN skill] $skill selected skill mismatch: '$($enRoute.selected.skill)'"
            Record-Check -Condition ($zhRoute.selected.skill -eq $skill) -Message "[ZH skill] $skill selected skill mismatch: '$($zhRoute.selected.skill)'"
            Record-Check -Condition ($enRoute.route_mode -in @("pack_overlay", "confirm_required")) -Message "[EN skill] $skill route mode is '$($enRoute.route_mode)'"
            Record-Check -Condition ($zhRoute.route_mode -in @("pack_overlay", "confirm_required")) -Message "[ZH skill] $skill route mode is '$($zhRoute.route_mode)'"
        }
    }
} else {
    Write-Host ""
    Write-Host "[INFO] Fast mode enabled: skipping skill-level sweep."
}

Write-Host ""
Write-Host "=== Summary ==="
Write-Host "Skill candidates checked: $skillTotal"
Write-Host "Total assertions: $total"
Write-Host "Passed: $pass"
Write-Host "Failed: $fail"
Write-Host "Warnings: $warn"

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "Top failures:"
    $failures | Select-Object -First 20 | ForEach-Object { Write-Host " - $_" }
    exit 1
}

if ($warn -gt 0) {
    Write-Host ""
    Write-Host "Top warnings:"
    $warnings | Select-Object -First 20 | ForEach-Object { Write-Host " - $_" }
}

Write-Host "Keyword precision audit passed."
exit 0
