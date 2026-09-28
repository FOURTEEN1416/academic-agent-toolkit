# Host Adapters

This directory holds host-specific compatibility contracts for the universalization program.

Rules:

- Adapters do not replace the official runtime.
- Adapters do not own routing truth.
- Adapters describe host capabilities, host-managed surfaces, settings mapping, and honest degradation states.
- A host adapter can be `supported`, `preview`, or `not-yet-proven`, but it must never overclaim closure that has not been verified.

Current adapter intent:

All listed adapters connect the same host-neutral VibeSkills core. These notes
describe the integration shape rather than ranking one AI application above
another.

The public install interface is always `install --skills-dir <SkillsDir>`, and
the installed layout is always `<SkillsDir>/vibe`. An adapter may map a native
Skills directory, invocation syntax, or optional command, agent, and workflow
projection. It does not define a separate VibeSkills package or runtime.

- `codex/`: governed adapter with Codex-specific install, settings, and plugin guidance.
- `claude-code/`: adapter with a bounded managed Claude settings surface.
- `cursor/`: preview adapter with truthful host-managed boundaries; no full closure claim yet.
- `windsurf/`: preview runtime-core adapter with documented host-root payload materialization.
- `openclaw/`: preview runtime-core adapter with documented host-root payload materialization.
- `opencode/`: preview adapter with host-native command/agent/example-config scaffolds, but still no full host closure claim.
- `generic/`: contract-consumer path for other Skills-capable applications.

The official runtime remains the canonical execution owner until replay, install isolation, and platform truth gates are passed.
