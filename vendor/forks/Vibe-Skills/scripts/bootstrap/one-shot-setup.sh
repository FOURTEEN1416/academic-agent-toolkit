#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
[FAIL] scripts/bootstrap/one-shot-setup.sh is retired.
Use the supported skill installer instead:
  bash ./install.sh --skills-dir "$HOME/.agents/skills"
  bash ./check.sh --skills-dir "$HOME/.agents/skills"
PowerShell users can run:
  .\install.ps1 -SkillsDir "$env:USERPROFILE\.agents\skills"
  .\check.ps1 -SkillsDir "$env:USERPROFILE\.agents\skills"
See docs/install/README.md for the current install contract.
EOF

exit 1
