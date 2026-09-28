param()

$ErrorActionPreference = 'Stop'

function Assert-True {
    param([bool]$Condition,[string]$Message)
    if ($Condition) {
        Write-Host "[PASS] $Message"
        return $true
    }
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    return $false
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$policyPath = Join-Path $repoRoot 'config\desktopops-shadow-policy.json'
$docPath = Join-Path $repoRoot 'docs\agent-s-shadow-integration.md'
$aciPath = Join-Path $repoRoot 'references\aci-dsl.md'
$openWorldPath = Join-Path $repoRoot 'references\openworld-task-contract.md'

$policy = Get-Content -Raw $policyPath -Encoding UTF8 | ConvertFrom-Json
$doc = Get-Content -Raw $docPath -Encoding UTF8
$aci = Get-Content -Raw $aciPath -Encoding UTF8
$openWorld = Get-Content -Raw $openWorldPath -Encoding UTF8

$checks = @()

$checks += Assert-True (
    $policy.role -eq 'desktopops_shadow_advisory_contract_only'
) 'desktopops role is shadow/advisory/contract only'

$checks += Assert-True (
    $policy.single_default_execution_owner -eq $true -and
    $policy.default_execution_owner -eq 'vco_control_plane' -and
    $policy.forbid_second_default_execution_owner -eq $true
) 'no second default execution owner is introduced'

$checks += Assert-True (
    $policy.forbid_second_orchestrator -eq $true
) 'second orchestrator remains forbidden'

$checks += Assert-True (
    $policy.forbid_default_execution_owner -eq $true -and
    $policy.forbid_default_takeover -eq $true -and
    $policy.forbid_default_gui_owner -eq $true
) 'default takeover and gui owner reassignment are forbidden'

$checks += Assert-True (
    @($policy.allow_stages) -contains 'off' -and
    @($policy.allow_stages) -contains 'shadow' -and
    @($policy.allow_stages) -contains 'soft' -and
    -not (@($policy.allow_stages) -contains 'promoted')
) 'desktopops policy is constrained to off/shadow/soft only'

$checks += Assert-True (
    $policy.forbid_implicit_promote -eq $true -and
    $policy.promotion_rules.allow_implicit -eq $false -and
    $policy.promotion_rules.promoted_stage_supported -eq $false
) 'implicit promote is disabled'

$checks += Assert-True (
    $policy.require_human_confirm -eq $true -and
    $policy.human_confirmation_boundary.manual_only -eq $true -and
    $policy.human_confirmation_boundary.never_auto_promote -eq $true
) 'human confirmation boundary is enforced'

$checks += Assert-True (
    ($doc -match 'shadow / advisory / contract source') -and
    ($doc -match '第二执行面') -and
    ($doc -match '第二默认执行 owner')
) 'doc states Agent-S is contract source only, not a second execution plane'

$checks += Assert-True (
    ($aci -match 'owner:\s*vco_control_plane') -and
    ($aci -match 'execution_mode:\s*shadow_only') -and
    ($aci -match 'depends_on')
) 'ACI contract preserves VCO owner, shadow mode, and DAG dependency expression'

$checks += Assert-True (
    ($openWorld -match 'shadow_only:\s*true') -and
    ($openWorld -match 'owner:\s*vco_control_plane') -and
    ($openWorld -match 'promote:\s*false') -and
    ($openWorld -match 'BrowserOps')
) 'open-world contract stays shadow-only, non-promoting, and degrades to BrowserOps when possible'

if ($checks -contains $false) {
    throw 'desktopops shadow gate failed'
}

Write-Host '[PASS] desktopops shadow gate succeeded' -ForegroundColor Green
