param(
    [Parameter(Mandatory = $true)][string]$PayloadType
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$policyPath = Join-Path $repoRoot "config\mem0-backend-policy.json"
$policy = Get-Content -Raw $policyPath -Encoding UTF8 | ConvertFrom-Json

if (-not $policy.enabled -and $policy.mode -eq 'shadow') {
    Write-Output (@{ allowed = $false; reason = 'mem0_policy_shadow_only'; payload_type = $PayloadType } | ConvertTo-Json -Depth 10)
    exit 0
}

if (@($policy.forbidden_payload_types) -contains $PayloadType) {
    Write-Output (@{ allowed = $false; reason = 'forbidden_payload_type'; payload_type = $PayloadType } | ConvertTo-Json -Depth 10)
    exit 0
}

if (@($policy.allowed_payload_types) -contains $PayloadType) {
    Write-Output (@{ allowed = $true; reason = 'allowed_payload_type'; payload_type = $PayloadType } | ConvertTo-Json -Depth 10)
    exit 0
}

Write-Output (@{ allowed = $false; reason = 'unknown_payload_type'; payload_type = $PayloadType } | ConvertTo-Json -Depth 10)
