# CodeSucker Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 vendored CodeSucker core 融合为本套件的标准软著源码资产流水线，并接入资产清点、软著草稿、正式构建、质量门禁和工作流证据。

**Architecture:** 保留上游纯 TypeScript core，新增 JSON CLI 与 Python bridge；技能只调用 bridge，engine 只验证结果和证据。Electron 壳不进入套件，旧 Python 实现只保留显式 legacy 诊断入口。

**Tech Stack:** TypeScript/Node.js 22.12+、Python 3.12+、现有 workflow engine、pytest、docx。

## Global Constraints

- 源码扫描、清洗、分页、渲染和审计必须离线完成。
- 所有路径必须限制在声明的项目根和工作区内。
- 所有步骤必须通过 `WorkflowRunner.start()`、`next_action()`、质量门禁和 `complete_step()`。
- 所有完成声明必须包含 workspace 相对产物、输入/输出哈希、SKILL.md 哈希、命令退出码、门禁结果和非空 `execution_evidence`。
- vendored core 必须保留 Apache-2.0 LICENSE、NOTICE、来源 commit 和修改记录。
- 旧 Python backend 不得静默替代标准 backend。

---

### Task 1: Vendored core and provenance

**Files:**
- Create: `数学建模全流程套件/tools/codesucker-core/` with upstream core sources
- Create: `数学建模全流程套件/tools/codesucker-core/LICENSE`
- Create: `数学建模全流程套件/tools/codesucker-core/NOTICE`
- Create: `数学建模全流程套件/tools/codesucker-core/UPSTREAM.md`
- Create: `数学建模全流程套件/tools/codesucker-core/package.json`
- Create: `数学建模全流程套件/tools/codesucker-core/tsconfig.json`
- Test: `数学建模全流程套件/tests/test_codesucker_vendor.py`

**Interfaces:** Vendored source must expose the upstream core functions through a local package entry and report `coreVersion`, `coreCommit`, and `rulesVersion`.

- [ ] Copy only `packages/core/src` and required package metadata from upstream commit `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c`.
- [ ] Add `UPSTREAM.md` with exact source URL, commit, sync date, copied files, local modifications, and Apache-2.0 obligations.
- [ ] Add a local TypeScript build configuration that does not depend on Electron.
- [ ] Add a Python test asserting license files, provenance fields, expected modules, and no Electron import.
- [ ] Run `node --version`, `npm --version`, `npm install --ignore-scripts`, and `npm run build` in the vendored directory; record exit codes.

### Task 2: JSON CLI adapter

**Files:**
- Create: `数学建模全流程套件/tools/codesucker-cli.mjs`
- Create: `数学建模全流程套件/tools/codesucker-cli.schema.json`
- Create: `数学建模全流程套件/tests/test_codesucker_cli.py`

**Interfaces:** `node tools/codesucker-cli.mjs --config <config.json> --workspace <workspace>` returns exit 0 only when protocol output is valid, and writes the standard JSON artifacts and rendered files.

- [ ] Write failing tests for valid config, malformed config, project-root escape, nonzero core error, stable output paths, and repeated-run determinism.
- [ ] Implement strict JSON parsing and schema validation.
- [ ] Implement discovery, sorting, async processing, rendering, audit and output serialization through the vendored core.
- [ ] Normalize all generated paths to workspace-relative POSIX paths.
- [ ] Write through a temporary directory and atomically replace the output directory.
- [ ] Run the CLI tests and assert stable hashes across two runs on the same fixture.

### Task 3: Python bridge and manifest

**Files:**
- Create: `数学建模全流程套件/tools/codesucker_bridge.py`
- Create: `数学建模全流程套件/tools/codesucker_provenance.py`
- Modify: `数学建模全流程套件/tools/codesucker_python.py`
- Test: `数学建模全流程套件/tests/test_codesucker_bridge.py`

**Interfaces:**

```python
run_source_materials(config: dict, workspace: Path, allow_legacy_fallback: bool = False) -> dict
```

Returns a validated manifest payload with `backend`, `coreVersion`, `coreCommit`, `input_sha256`, `output_sha256`, `artifacts`, `audit`, `commands`, and `exit_codes`.

- [ ] Test standard backend selection, missing Node failure, invalid output failure, manifest hashes, path normalization, and explicit legacy fallback labeling.
- [ ] Implement subprocess invocation without shell interpolation; pass arguments as a list.
- [ ] Capture stdout/stderr to workspace logs while avoiding secret values.
- [ ] Hash config, source file metadata, core source tree, and declared outputs.
- [ ] Mark the existing Python implementation as legacy and require `--allow-legacy-fallback`.
- [ ] Run bridge tests and a fixture project end-to-end.

### Task 4: Source-materials skill

**Files:**
- Create: `数学建模全流程套件/skills/copyright-source-materials/SKILL.md`
- Create: `数学建模全流程套件/skills/copyright-source-materials/references/configuration.md`
- Create: `数学建模全流程套件/skills/copyright-source-materials/references/report-schema.md`
- Test: `数学建模全流程套件/tests/test_skill_smoke.py`

**Interfaces:** Skill reads `StepAction.workspace`, project root and software metadata; produces `source-materials/*`, `SOURCE_MATERIALS_REPORT.md`, and evidence-ready manifest.

- [ ] Document input contract, configuration defaults, execution commands, output contract, checkpoint behavior, and failure rules.
- [ ] Require upstream literature search only when the workflow adds legal/regulatory claims; do not fabricate legal advice.
- [ ] Require explicit confirmation for title, owner, founded date, file selection, and cleaning options when interactive confirmation is needed.
- [ ] Add smoke coverage for skill metadata, required files, and forbidden silent fallback.

### Task 5: Engine quality gates and evidence

**Files:**
- Modify: `数学建模全流程套件/engine/quality_gates.py`
- Modify: `数学建模全流程套件/engine/workflow_runner.py`
- Modify: `数学建模全流程套件/engine/artifact_manifest.py`
- Test: `数学建模全流程套件/tests/test_quality_gates.py`
- Test: `数学建模全流程套件/tests/test_workflow_runner.py`

**Interfaces:**

```python
QualityGates.check_source_materials() -> dict
```

The gate returns `ok`, `backend`, `failures`, `warnings`, `artifact_count`, and `reason`; any failure prevents `complete_step()` from advancing.

- [ ] Add tests for missing manifest, invalid hashes, audit fail, empty source, short page, legacy backend, valid warning, and valid standard output.
- [ ] Implement manifest-backed validation using existing `ArtifactManifest` conventions.
- [ ] Require `execution_evidence` fields for the new skill: backend, core provenance, command list, exit codes, input/output hashes, and audit summary.
- [ ] Keep existing competition consistency and final-audit behavior unchanged.
- [ ] Run engine tests and verify failed gates do not advance workflow state.

### Task 6: Integrate assets-inventory

**Files:**
- Modify: `数学建模全流程套件/skills/assets-inventory/SKILL.md`
- Create: `数学建模全流程套件/tools/assets_codesucker_adapter.py`
- Test: `数学建模全流程套件/tests/test_assets_codesucker_integration.py`

- [ ] Add a code-project detection branch that calls the bridge for inventory metadata only.
- [ ] Add `source_materials_manifest` and backend/core provenance fields to `ASSETS_INVENTORY.md`.
- [ ] Do not generate final DOCX during inventory.
- [ ] Test real code fixture, empty code directory, excluded directories, and conflict report preservation.

### Task 7: Integrate copyright-draft and copyright-build

**Files:**
- Modify: `数学建模全流程套件/skills/copyright-draft/SKILL.md`
- Modify: `数学建模全流程套件/skills/copyright-build/SKILL.md`
- Modify: `数学建模全流程套件/skills/copyright-build/scripts/build_docx_from_md.py`
- Test: `数学建模全流程套件/tests/test_copyright_codesucker_integration.py`

- [ ] In real-material mode, require standard source-materials manifest before writing code material.
- [ ] Generate code selection and Markdown pages from the selected cleaned source lines and preserve file/line provenance.
- [ ] Prefer rendered DOCX/TXT from source-materials; retain the existing Markdown path for synthetic mode and legacy compatibility.
- [ ] Add report fields for source mode, backend, core version, rule version, audit warnings, and source manifest path.
- [ ] Ensure no generated code is mixed into real-material mode.
- [ ] Run draft/build integration tests with both real and synthetic fixtures.

### Task 8: Upstream sync and dependency audit

**Files:**
- Create: `数学建模全流程套件/tools/sync_codesucker_core.py`
- Create: `数学建模全流程套件/tools/check_codesucker_licenses.py`
- Modify: `数学建模全流程套件/AGENTS.md`
- Modify: `数学建模全流程套件/skills/CLAUDE.md`
- Test: `数学建模全流程套件/tests/test_codesucker_sync.py`

- [ ] Add explicit sync command requiring repository, ref, destination, and expected upstream license.
- [ ] Reject sync when source commit cannot be recorded or license files are missing.
- [ ] Add dependency license check for vendored and npm dependencies.
- [ ] Document upgrade procedure, backend policy, and restart requirement for skill changes.
- [ ] Test dry-run sync, missing license rejection, provenance update, and license audit output.

### Task 9: End-to-end verification and delivery audit

**Files:**
- Create: `数学建模全流程套件/tests/fixtures/codesucker-project/`
- Create: `数学建模全流程套件/tests/test_codesucker_end_to_end.py`
- Modify: `数学建模全流程套件/engine/workflow_cli.py`

- [ ] Build a fixture containing Python/TypeScript strings with comment-like text, real comments, attribution lines, secrets, excluded files, and long lines.
- [ ] Run `WorkflowRunner.start()` and `next_action()` for the source-materials step.
- [ ] Run the bridge, gates, `complete_step()`, and inspect execution evidence.
- [ ] Run copyright build and final audit on the generated artifacts.
- [ ] Run full Python test suite, CLI tests, license checks, and operation audit.
- [ ] Record capability limitations explicitly: no Electron UI, no legal guarantee, and any unavailable XeLaTeX/visual validation.
