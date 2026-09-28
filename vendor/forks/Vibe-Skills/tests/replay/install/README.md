# Install Isolation Replay Fixtures

These fixtures encode **install/runtime isolation expectations** for the official runtime lane.

The goal is to prove:

- Running the replay harness does not create "pollution markers" in the repo root.
- Runtime state is written under `outputs/` (allowed) rather than into canonical source-of-truth directories.

Validated by: `scripts/verify/vibe-cross-host-install-isolation-gate.ps1`

