# Academic Agent Toolkit

An academic Agent toolkit for mathematical modeling competitions, academic papers, literature and research, course and research materials, intellectual-property materials, and figures and document production.

## Start Here

Open the project root `D:\Desktop\数模竞赛` in OpenCode Desktop (official v1 host) or ZCode (compatibility layer: root `AGENTS.md` + `.zcode/`), then describe the academic task and provide the materials.

OpenCode Desktop is the officially supported v1 host; ZCode is supported through the compatibility layer (same skill library, L2+L3 audit only). The system asks only for information that materially changes the delivery route, then carries out local work in the same session. It does not depend on the `opencode` CLI being present on the system PATH. **不依赖 `opencode` CLI。**

## Current Boundary

- The 2026 CUMCM work is a validation scenario, not the product definition.
- Existing skills and scripts are not all formal released capabilities.
- Public-core/private-extension inventory, capability catalog (`capabilities/catalog.json`, 269 entries / 10 formal), benchmarks, dual licensing (CC-BY-NC-4.0 core + CC-BY-4.0 public benchmarks), and provenance ledger are established as of v1.0.0; ongoing changes follow the governance entry index in `AGENTS.md`.
- Actions that use keys or potentially paid APIs, send materials outside the workspace, overwrite or delete files, or make irreversible remote changes require confirmation in the OpenCode conversation.

## Read Next

- [`CURRENT_STATE.md`](./CURRENT_STATE.md): current status, authority order, support boundary, and historical-asset policy.
- [`docs/superpowers/specs/2026-08-13-academic-agent-toolkit-design.md`](./docs/superpowers/specs/2026-08-13-academic-agent-toolkit-design.md): approved product design.
- [`科研工具箱/AGENTS.md`](./科研工具箱/AGENTS.md): runtime routing and execution protocol for OpenCode Desktop.

## Historical References

Legacy CUMCM menus, checklists, audits, and the older toolset remain in this workspace for traceability. They are not recommended entry points and do not certify current product capabilities. Their status notices link back to `CURRENT_STATE.md`.
