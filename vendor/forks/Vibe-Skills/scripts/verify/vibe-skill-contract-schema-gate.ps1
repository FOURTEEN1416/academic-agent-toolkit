param(
    [string]$ContractsIndexPath = '',
    [switch]$WriteArtifacts,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot '..\common\vibe-governance-helpers.ps1')

function New-Failure {
    param(
        [string]$Code,
        [string]$Message,
        [string]$Path = ''
    )
    return [pscustomobject]@{
        code = $Code
        message = $Message
        path = $Path
    }
}

function Assert-String {
    param(
        [string]$Name,
        [object]$Value,
        [System.Collections.Generic.List[object]]$Failures,
        [string]$PathHint
    )

    if ($null -eq $Value -or -not ($Value -is [string]) -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        $Failures.Add((New-Failure -Code 'schema.invalid_type' -Message ("{0} must be a non-empty string" -f $Name) -Path $PathHint))
        return $false
    }

    return $true
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact,
        [string]$OutputDirectory
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-skill-contract-schema-gate.json'
    $mdPath = Join-Path $dir 'vibe-skill-contract-schema-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VibeSkills Skill Contract Schema Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Index Path: `{0}`' -f $Artifact.index_path),
        ('- Checked Contracts: {0}' -f $Artifact.summary.contracts_checked),
        ('- Failures: {0}' -f $Artifact.summary.failures),
        ''
    )

    if ($Artifact.failures.Count -gt 0) {
        $lines += '## Failures'
        $lines += ''
        foreach ($f in $Artifact.failures) {
            $lines += ('- `{0}` {1} ({2})' -f $f.code, $f.message, $(if ([string]::IsNullOrWhiteSpace($f.path)) { '<no path>' } else { $f.path }))
        }
        $lines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot

$schemaIndexPath = Join-Path $repoRoot 'schemas\skill-contract-index.v1.schema.json'
$schemaContractPath = Join-Path $repoRoot 'schemas\skill-contract.v1.schema.json'

$indexPath = if ([string]::IsNullOrWhiteSpace($ContractsIndexPath)) {
    Join-Path $repoRoot 'core\skill-contracts\index.json'
} else {
    [System.IO.Path]::GetFullPath($ContractsIndexPath)
}

$result = [pscustomobject]([ordered]@{
    gate = 'vibe-skill-contract-schema-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = 'FAIL'
    index_path = $indexPath
    failures = @()
    contracts = @()
    summary = [pscustomobject]([ordered]@{
        contracts_checked = 0
        failures = 0
    })
})

$failures = New-Object 'System.Collections.Generic.List[object]'

foreach ($p in @($schemaIndexPath, $schemaContractPath, $indexPath)) {
    if (-not (Test-Path -LiteralPath $p)) {
        $failures.Add((New-Failure -Code 'schema.missing_file' -Message 'required file missing' -Path $p))
    }
}

$index = $null
if ($failures.Count -eq 0) {
    try {
        $index = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        $failures.Add((New-Failure -Code 'schema.invalid_json' -Message ('failed to parse index json: {0}' -f $_.Exception.Message) -Path $indexPath))
    }
}

if ($null -ne $index) {
    if (-not ($index.PSObject.Properties.Name -contains 'schema_version') -or [string]$index.schema_version -ne 'skill-contract-index.v1') {
        $failures.Add((New-Failure -Code 'schema.index_version_mismatch' -Message 'index.schema_version must be skill-contract-index.v1' -Path $indexPath))
    }

    if (-not ($index.PSObject.Properties.Name -contains 'contracts') -or $null -eq $index.contracts -or -not ($index.contracts -is [System.Collections.IEnumerable])) {
        $failures.Add((New-Failure -Code 'schema.index_contracts_missing' -Message 'index.contracts must be an array' -Path $indexPath))
    } else {
        $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($c in @($index.contracts)) {
            $contractFailures = New-Object 'System.Collections.Generic.List[object]'
            $okSkill = Assert-String -Name 'contracts[].skill_id' -Value $c.skill_id -Failures $contractFailures -PathHint $indexPath
            $okPath = Assert-String -Name 'contracts[].contract_path' -Value $c.contract_path -Failures $contractFailures -PathHint $indexPath

            $skillId = if ($okSkill) { [string]$c.skill_id } else { '' }
            if ($okSkill -and -not $seen.Add($skillId)) {
                $contractFailures.Add((New-Failure -Code 'schema.duplicate_skill_id' -Message ('duplicate skill_id in index: {0}' -f $skillId) -Path $indexPath))
            }

            $contractPathFull = $null
            if ($okPath) {
                $contractPathFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ([string]$c.contract_path)))
                if (-not (Test-VgoPathWithin -ParentPath $repoRoot -ChildPath $contractPathFull)) {
                    $contractFailures.Add((New-Failure -Code 'schema.path_outside_repo' -Message 'contract_path must resolve within repo root' -Path $contractPathFull))
                } elseif (-not (Test-Path -LiteralPath $contractPathFull)) {
                    $contractFailures.Add((New-Failure -Code 'schema.contract_missing' -Message 'contract file missing' -Path $contractPathFull))
                }
            }

            $contractObj = $null
            if ($okSkill -and $okPath -and $null -ne $contractPathFull -and (Test-Path -LiteralPath $contractPathFull)) {
                try {
                    $contractObj = Get-Content -LiteralPath $contractPathFull -Raw -Encoding UTF8 | ConvertFrom-Json
                } catch {
                    $contractFailures.Add((New-Failure -Code 'schema.contract_invalid_json' -Message ('failed to parse contract json: {0}' -f $_.Exception.Message) -Path $contractPathFull))
                }
            }

            if ($null -ne $contractObj) {
                if (-not ($contractObj.PSObject.Properties.Name -contains 'schema_version') -or [string]$contractObj.schema_version -ne 'skill-contract.v1') {
                    $contractFailures.Add((New-Failure -Code 'schema.contract_version_mismatch' -Message 'contract.schema_version must be skill-contract.v1' -Path $contractPathFull))
                }
                if (-not ($contractObj.PSObject.Properties.Name -contains 'skill_id') -or [string]$contractObj.skill_id -ne $skillId) {
                    $contractFailures.Add((New-Failure -Code 'schema.contract_skill_id_mismatch' -Message 'contract.skill_id must equal index skill_id' -Path $contractPathFull))
                }

                $primary = $null
                if ($contractObj.PSObject.Properties.Name -contains 'sources' -and $contractObj.sources -and
                    $contractObj.sources.PSObject.Properties.Name -contains 'skill_md' -and $contractObj.sources.skill_md) {
                    $primary = $contractObj.sources.skill_md.primary
                }
                if ([string]::IsNullOrWhiteSpace([string]$primary)) {
                    $contractFailures.Add((New-Failure -Code 'schema.contract_primary_missing' -Message 'contract.sources.skill_md.primary must be set' -Path $contractPathFull))
                } else {
                    $primaryFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ([string]$primary)))
                    if (-not (Test-VgoPathWithin -ParentPath $repoRoot -ChildPath $primaryFull)) {
                        $contractFailures.Add((New-Failure -Code 'schema.primary_outside_repo' -Message 'primary SKILL.md path must resolve within repo root' -Path $primaryFull))
                    } elseif (-not (Test-Path -LiteralPath $primaryFull)) {
                        $contractFailures.Add((New-Failure -Code 'schema.primary_missing' -Message 'primary SKILL.md missing' -Path $primaryFull))
                    }
                }
            }

            foreach ($f in $contractFailures) { $failures.Add($f) }
            $result.summary.contracts_checked++
            $result.contracts += [pscustomobject]@{
                skill_id = $skillId
                contract_path = if ($null -eq $contractPathFull) { '' } else { $contractPathFull }
                failure_count = $contractFailures.Count
            }
        }
    }
}

$result.failures = @($failures.ToArray())
$result.summary.failures = $failures.Count
$result.gate_result = if ($failures.Count -eq 0) { 'PASS' } else { 'FAIL' }

if ($WriteArtifacts) {
    Write-GateArtifacts -RepoRoot $repoRoot -Artifact $result -OutputDirectory $OutputDirectory
}

if ($result.gate_result -ne 'PASS') {
    throw "vibe-skill-contract-schema-gate FAILED ($($result.summary.failures) failures). See outputs/verify for details."
}
