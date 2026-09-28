from __future__ import annotations


ISSUE_167_MANAGED_PROTOCOL_SURFACES = (
    'protocols/runtime.md',
    'protocols/think.md',
    'protocols/do.md',
    'protocols/review.md',
    'protocols/team.md',
    'protocols/retro.md',
)

ISSUE_167_MANAGED_RUNTIME_SURFACES = (
    'docs/requirements/README.md',
    *ISSUE_167_MANAGED_PROTOCOL_SURFACES,
    'core/skill-contracts/v1/vibe.json',
    'scripts/verify/vibe-bootstrap-doctor-gate.ps1',
    'scripts/verify/vibe-no-silent-fallback-contract-gate.ps1',
    'scripts/verify/vibe-no-self-introduced-fallback-gate.ps1',
    'scripts/verify/vibe-release-truth-consistency-gate.ps1',
    'config/operator-preview-contract.json',
)
