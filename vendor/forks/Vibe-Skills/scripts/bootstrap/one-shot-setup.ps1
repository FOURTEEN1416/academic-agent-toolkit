[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

[Console]::Error.WriteLine('[FAIL] scripts/bootstrap/one-shot-setup.ps1 is retired.')
[Console]::Error.WriteLine('Use the supported skill installer instead:')
[Console]::Error.WriteLine('  bash ./install.sh --skills-dir "$HOME/.agents/skills"')
[Console]::Error.WriteLine('  bash ./check.sh --skills-dir "$HOME/.agents/skills"')
[Console]::Error.WriteLine('PowerShell users can run:')
[Console]::Error.WriteLine('  .\install.ps1 -SkillsDir "$env:USERPROFILE\.agents\skills"')
[Console]::Error.WriteLine('  .\check.ps1 -SkillsDir "$env:USERPROFILE\.agents\skills"')
[Console]::Error.WriteLine('See docs/install/README.md for the current install contract.')
exit 1
