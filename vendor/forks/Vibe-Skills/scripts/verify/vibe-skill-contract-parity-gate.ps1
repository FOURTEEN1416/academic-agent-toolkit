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
        [string]$Path = '',
        [string]$SkillId = ''
    )
    return [pscustomobject]@{
        code = $Code
        message = $Message
        path = $Path
        skill_id = $SkillId
    }
}

function Get-BytesHash {
    param([byte[]]$Bytes)
    $stream = [System.IO.MemoryStream]::new($Bytes)
    try {
        return (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash.ToLowerInvariant()
    } finally {
        $stream.Dispose()
    }
}

function Get-NormalizedTextHash {
    param([string]$Path)
    $rawBytes = [System.IO.File]::ReadAllBytes($Path)
    $text = [System.Text.Encoding]::UTF8.GetString($rawBytes)
    $normalized = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    return Get-BytesHash -Bytes ([System.Text.Encoding]::UTF8.GetBytes($normalized))
}

function Read-Frontmatter {
    param(
        [string]$SkillMdPath,
        [System.Collections.Generic.List[object]]$Failures,
        [string]$SkillId
    )

    $lines = Get-Content -LiteralPath $SkillMdPath -Encoding UTF8
    if ($lines.Count -lt 3 -or $lines[0].Trim() -ne '---') {
        $Failures.Add((New-Failure -Code 'parity.frontmatter_missing' -Message 'SKILL.md must start with YAML frontmatter (--- on line 1)' -Path $SkillMdPath -SkillId $SkillId))
        return $null
    }

    $endIdx = -1
    for ($i = 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq '---') {
            $endIdx = $i
            break
        }
    }
    if ($endIdx -lt 0) {
        $Failures.Add((New-Failure -Code 'parity.frontmatter_unterminated' -Message 'SKILL.md frontmatter missing closing ---' -Path $SkillMdPath -SkillId $SkillId))
        return $null
    }

    $map = [ordered]@{}
    for ($i = 1; $i -lt $endIdx; $i++) {
        $line = [string]$lines[$i]
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $trim = $line.Trim()
        if ($trim.StartsWith('#')) { continue }
        $colonIdx = $trim.IndexOf(':')
        if ($colonIdx -le 0) { continue }
        $key = $trim.Substring(0, $colonIdx).Trim()
        $val = $trim.Substring($colonIdx + 1).Trim()
        if ($val.StartsWith('"') -and $val.EndsWith('"') -and $val.Length -ge 2) {
            $val = $val.Substring(1, $val.Length - 2)
        } elseif ($val.StartsWith("'") -and $val.EndsWith("'") -and $val.Length -ge 2) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $map[$key] = $val
        }
    }

    return [pscustomobject]@{
        start_line = 1
        end_line = $endIdx + 1
        data = $map
    }
}

function Write-GateArtifacts {
    param(
        [string]$RepoRoot,
        [psobject]$Artifact,
        [string]$OutputDirectory
    )

    $dir = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { Join-Path $RepoRoot 'outputs\verify' } else { $OutputDirectory }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $jsonPath = Join-Path $dir 'vibe-skill-contract-parity-gate.json'
    $mdPath = Join-Path $dir 'vibe-skill-contract-parity-gate.md'

    Write-VgoUtf8NoBomText -Path $jsonPath -Content ($Artifact | ConvertTo-Json -Depth 100)

    $lines = @(
        '# VibeSkills Skill Contract Parity Gate',
        '',
        ('- Gate Result: **{0}**' -f $Artifact.gate_result),
        ('- Repo Root: `{0}`' -f $Artifact.repo_root),
        ('- Index Path: `{0}`' -f $Artifact.index_path),
        ('- Skills Checked: {0}' -f $Artifact.summary.skills_checked),
        ('- Failures: {0}' -f $Artifact.summary.failures),
        ''
    )

    if ($Artifact.failures.Count -gt 0) {
        $lines += '## Failures'
        $lines += ''
        foreach ($f in $Artifact.failures) {
            $lines += ('- `{0}` skill={1} :: {2} ({3})' -f $f.code, $(if ([string]::IsNullOrWhiteSpace($f.skill_id)) { '<unknown>' } else { $f.skill_id }), $f.message, $(if ([string]::IsNullOrWhiteSpace($f.path)) { '<no path>' } else { $f.path }))
        }
        $lines += ''
    }

    Write-VgoUtf8NoBomText -Path $mdPath -Content ($lines -join "`n")
}

$context = Get-VgoGovernanceContext -ScriptPath $PSCommandPath -EnforceExecutionContext
$repoRoot = $context.repoRoot

$indexPath = if ([string]::IsNullOrWhiteSpace($ContractsIndexPath)) {
    Join-Path $repoRoot 'core\skill-contracts\index.json'
} else {
    [System.IO.Path]::GetFullPath($ContractsIndexPath)
}

$result = [pscustomobject]([ordered]@{
    gate = 'vibe-skill-contract-parity-gate'
    repo_root = $repoRoot
    generated_at = (Get-Date).ToString('s')
    gate_result = 'FAIL'
    index_path = $indexPath
    failures = @()
    skills = @()
    summary = [pscustomobject]([ordered]@{
        skills_checked = 0
        failures = 0
    })
})

$failures = New-Object 'System.Collections.Generic.List[object]'

if (-not (Test-Path -LiteralPath $indexPath)) {
    $failures.Add((New-Failure -Code 'parity.index_missing' -Message 'contracts index missing' -Path $indexPath))
} else {
    $index = $null
    try {
        $index = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        $failures.Add((New-Failure -Code 'parity.index_invalid_json' -Message ('failed to parse index json: {0}' -f $_.Exception.Message) -Path $indexPath))
    }

    if ($null -ne $index) {
        foreach ($entry in @($index.contracts)) {
            $skillId = [string]$entry.skill_id
            $contractRel = [string]$entry.contract_path
            $contractFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $contractRel))

            if (-not (Test-Path -LiteralPath $contractFull)) {
                $failures.Add((New-Failure -Code 'parity.contract_missing' -Message 'contract file missing' -Path $contractFull -SkillId $skillId))
                continue
            }

            $contract = $null
            try {
                $contract = Get-Content -LiteralPath $contractFull -Raw -Encoding UTF8 | ConvertFrom-Json
            } catch {
                $failures.Add((New-Failure -Code 'parity.contract_invalid_json' -Message ('failed to parse contract json: {0}' -f $_.Exception.Message) -Path $contractFull -SkillId $skillId))
                continue
            }

            $primaryRel = [string]$contract.sources.skill_md.primary
            $primaryFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $primaryRel))
            if (-not (Test-Path -LiteralPath $primaryFull)) {
                $failures.Add((New-Failure -Code 'parity.primary_missing' -Message 'primary SKILL.md missing' -Path $primaryFull -SkillId $skillId))
                continue
            }

            $frontmatterFailures = New-Object 'System.Collections.Generic.List[object]'
            $fm = Read-Frontmatter -SkillMdPath $primaryFull -Failures $frontmatterFailures -SkillId $skillId
            foreach ($f in $frontmatterFailures) { $failures.Add($f) }

            if ($null -ne $fm) {
                $required = @($contract.frontmatter.required_keys)
                foreach ($k in $required) {
                    $key = [string]$k
                    if (-not $fm.data.Contains($key)) {
                        $failures.Add((New-Failure -Code 'parity.frontmatter_key_missing' -Message ("required frontmatter key missing: {0}" -f $key) -Path $primaryFull -SkillId $skillId))
                    }
                }

                $inv = $contract.frontmatter.invariants
                if ($null -ne $inv -and ($inv.PSObject.Properties.Name -contains 'name_equals_skill_id') -and [bool]$inv.name_equals_skill_id) {
                    $nameVal = if ($fm.data.Contains('name')) { [string]$fm.data['name'] } else { '' }
                    if ($nameVal -ne $skillId) {
                        $failures.Add((New-Failure -Code 'parity.name_mismatch' -Message ("frontmatter.name must equal skill_id ({0})" -f $skillId) -Path $primaryFull -SkillId $skillId))
                    }
                }
            }

            $primaryHash = Get-NormalizedTextHash -Path $primaryFull
            $altHashes = @()
            foreach ($altRel in @($contract.sources.skill_md.alternates)) {
                $altRelStr = [string]$altRel
                $altFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $altRelStr))
                if (-not (Test-Path -LiteralPath $altFull)) {
                    $failures.Add((New-Failure -Code 'parity.alternate_missing' -Message 'alternate SKILL.md missing' -Path $altFull -SkillId $skillId))
                    continue
                }

                $altHash = Get-NormalizedTextHash -Path $altFull
                $altHashes += [pscustomobject]@{ path = $altFull; hash = $altHash }
                if ($altHash -ne $primaryHash) {
                    $failures.Add((New-Failure -Code 'parity.alternate_mismatch' -Message 'alternate SKILL.md differs from primary (normalized newline hash mismatch)' -Path $altFull -SkillId $skillId))
                }
            }

            $result.skills += [pscustomobject]@{
                skill_id = $skillId
                contract_path = $contractFull
                primary_skill_md = $primaryFull
                primary_hash = $primaryHash
                alternates = $altHashes
            }
            $result.summary.skills_checked++
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
    throw "vibe-skill-contract-parity-gate FAILED ($($result.summary.failures) failures). See outputs/verify for details."
}
