param(
    [switch]$WriteArtifacts
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function Assert-Collect {
    param(
        [bool]$Condition,
        [string]$Message,
        [object]$Details = $null
    )
    if ($Condition) {
        Write-Host "[PASS] $Message"
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
    }
    return [pscustomobject]@{ pass = $Condition; message = $Message; details = $Details }
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot
$specPath = Join-Path $repoRoot 'references\docling-output-spec.md'
$docPath = Join-Path $repoRoot 'docs\docling-document-plane-integration.md'
$policyPath = Join-Path $repoRoot 'config\docling-provider-policy.json'
$results = New-Object System.Collections.Generic.List[object]

$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $specPath) -Message '存在 canonical docling output spec')) | Out-Null
$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $docPath) -Message '存在 docling integration 文档')) | Out-Null
$results.Add((Assert-Collect -Condition (Test-Path -LiteralPath $policyPath) -Message '存在 docling provider policy')) | Out-Null
if (@($results | Where-Object { -not $_.pass }).Count -gt 0) {
    exit 1
}

$specText = Get-Content -LiteralPath $specPath -Raw -Encoding UTF8
$docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json

$results.Add((Assert-Collect -Condition ($policy.plane -eq 'document_plane_contract') -Message 'policy.plane = document_plane_contract')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.mode -eq 'canonical_contract') -Message 'policy.mode = canonical_contract')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.control_plane_owner -eq 'vco') -Message 'policy.control_plane_owner = vco')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.tool_id -eq 'docling-mcp') -Message 'policy.tool_id = docling-mcp')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.artifact_first -eq $true) -Message 'policy 固定 artifact_first = true')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.isolated_runtime_required -eq $true) -Message 'policy 固定 isolated_runtime_required = true')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.selection_policy.allow_second_orchestrator -eq $false) -Message 'policy 禁止 second orchestrator')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.template_posture.approved_template -eq 'not-enabled') -Message 'approved-template 默认 not-enabled')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.template_posture.project_enabled -eq 'scoped') -Message 'project-enabled 默认 scoped')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.provider_status.document_plane_role -eq 'primary') -Message 'document_plane_role = primary')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.admission_filter.profile -eq 'document_plane_primary') -Message 'admission_filter.profile = document_plane_primary')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.admission_filter.risk_tier -eq 'tier1_bounded_transform') -Message 'admission_filter.risk_tier = tier1_bounded_transform')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.admission_filter.egress_profile -eq 'none') -Message 'admission_filter.egress_profile = none')) | Out-Null
$results.Add((Assert-Collect -Condition ($policy.admission_filter.write_surface_class -eq 'artifact_only') -Message 'admission_filter.write_surface_class = artifact_only')) | Out-Null

$expectedModes = @('markdown_plus_pages', 'text_plus_provenance', 'page_ocr_only', 'failure_object')
$results.Add((Assert-Collect -Condition (@((Compare-Object -ReferenceObject ($expectedModes | Sort-Object) -DifferenceObject (@($policy.degraded_modes | Sort-Object)))).Count -eq 0) -Message 'policy.degraded_modes 词表正确')) | Out-Null
$requiredFields = @('artifact_bundle', 'provenance', 'degraded_mode', 'failure_object')
foreach ($field in $requiredFields) {
    $results.Add((Assert-Collect -Condition (@($policy.required_output_fields) -contains $field) -Message ('required_output_fields 包含 {0}' -f $field))) | Out-Null
}

$specKeywords = @('Docling Output Spec', 'approved-template', 'project-enabled', 'artifact_bundle', 'markdown_plus_pages', 'text_plus_provenance', 'page_ocr_only', 'failure_object', 'document_plane_primary', 'Office Open XML', 'application/zip')
foreach ($keyword in $specKeywords) {
    $results.Add((Assert-Collect -Condition ($specText.Contains($keyword)) -Message ('spec 包含关键词 {0}' -f $keyword))) | Out-Null
}
$docKeywords = @('artifact-first', 'isolated-runtime', 'second document orchestrator', 'approved-template', 'project-enabled', 'ZIP 容器内容检查')
foreach ($keyword in $docKeywords) {
    $results.Add((Assert-Collect -Condition ($docText.Contains($keyword)) -Message ('integration 文档包含关键词 {0}' -f $keyword))) | Out-Null
}

$backupRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '..\..\.tmp\vco-runtime-backups'))
$backupSpecs = @()
if (Test-Path -LiteralPath $backupRoot) {
    $backupSpecs = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Sort-Object LastWriteTime -Descending | ForEach-Object {
        $candidate = Join-Path $_.FullName 'references\docling-output-spec.md'
        if (Test-Path -LiteralPath $candidate) { $candidate }
    })
}
$backupRootExists = Test-Path -LiteralPath $backupRoot
if ($backupRootExists) {
    $results.Add((Assert-Collect -Condition ($backupSpecs.Count -ge 1) -Message '找到 runtime backup 中的 docling spec 副本')) | Out-Null
} else {
    $results.Add((Assert-Collect -Condition $true -Message 'runtime backup root 未物化；docling backup 副本检查以 advisory 模式记录' -Details $backupRoot)) | Out-Null
}
if ($backupSpecs.Count -ge 1) {
    $canonicalHash = (Get-FileHash -LiteralPath $specPath -Algorithm SHA256).Hash
    $matching = @($backupSpecs | Where-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash -eq $canonicalHash })
    $results.Add((Assert-Collect -Condition ($matching.Count -ge 1) -Message 'canonical docling spec 与 runtime backup 副本同源')) | Out-Null
} else {
    $results.Add((Assert-Collect -Condition $true -Message '未找到 runtime backup docling spec；跳过同源性比较')) | Out-Null
}

$total = $results.Count
$passed = @($results | Where-Object { $_.pass }).Count
$failed = $total - $passed
$gatePass = ($failed -eq 0)
$gateResultText = if ($gatePass) { 'PASS' } else { 'FAIL' }

Write-Host ''
Write-Host '=== Summary ==='
Write-Host ('Total assertions: ' + $total)
Write-Host ('Passed: ' + $passed)
Write-Host ('Failed: ' + $failed)
Write-Host ('Gate Result: ' + $gateResultText)

if ($WriteArtifacts) {
    $outDir = Join-Path $repoRoot 'outputs\verify'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonPath = Join-Path $outDir 'vibe-docling-contract-gate.json'
    $mdPath = Join-Path $outDir 'vibe-docling-contract-gate.md'
    $assertionSummary = @{ total = $total; passed = $passed; failed = $failed }
    $artifact = @{
        generated_at = [DateTime]::UtcNow.ToString('o')
        gate_result = $gateResultText
        assertions = $assertionSummary
        spec_path = $specPath
        policy_path = $policyPath
        backup_specs = [object[]]$backupSpecs
        results = [object[]]$results
    }
    $artifact | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    $md = @(
        '# VCO Docling Contract Gate',
        '',
        ('- Gate Result: **' + $artifact.gate_result + '**'),
        ('- Assertions: total=' + $total + ', passed=' + $passed + ', failed=' + $failed),
        ('- Spec: `' + $specPath + '`'),
        ('- Policy: `' + $policyPath + '`')
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $mdPath -Value $md -Encoding UTF8
}

if (-not $gatePass) {
    exit 1
}
