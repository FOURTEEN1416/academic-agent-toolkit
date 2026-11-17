# Vendored CodeSucker Core

- Upstream: https://github.com/fanbuz/codesucker
- Upstream version: `0.5.3`
- Pinned commit: `16fb1e3928eefda14bd8cf56f93fa325a7b9d5d9`
- Vendored on: `2026-08-18`（2026-11-16 升级 v0.5.3，UP-12）
- Local use: only `packages/core/src`; Electron application code is not part of the execution path. Runtime dependencies are declared in the local minimal `package.json`.
- License: Apache-2.0; see `LICENSE` and `NOTICE`.

## Local adaptation

The upstream core is consumed through `third_party/codesucker-core/codesucker-cli.mjs`. The CLI owns
the JSON protocol, workspace-safe output paths, deterministic serialization, and
manifest generation.
The output hash map intentionally excludes the manifest file itself to avoid a
self-referential digest; the manifest hashes all other source-materials files.

## 2026-11-16 upgrade v0.4.4 → v0.5.3 (UP-12)

- 范围：`packages/core/src` 全量同步至上游 16fb1e3（+6585/−365：新增 language-syntax.ts、
  third-party/ 风险分析模块；discover.ts/clean.ts/index.ts/types.ts/version.ts 更新）。
  CLI/测试所依赖的 core 导出全部保留（index.ts 仅新增导出，无删除），上游 core 运行时
  依赖（chardet/docx/fast-glob/iconv-lite/ignore）与本地最小 package.json 一致，无新增。
- **discover.ts 本地可移植补丁退役**：原本地为单扩展名使用 `**/*.ext`（`**/*.{ext}` 在
  受支持 Windows 运行时不匹配）；上游 v0.5.3 的 discover.ts 已改为逐扩展名独立 glob
  （`normalized.map((ext) => `**/*.${ext}`)`，上游第 98 行），本补丁由上游修复取代，
  discover.ts 恢复上游原样。
- **codesucker-cli.mjs 本地适配器保留**：Windows rename 重试补丁（见下节）仍为本仓独有
  （上游无此 CLI 文件）；本次仅同步其中的 coreVersion/coreCommit 标识至 0.5.3/16fb1e3。
- 升级前后同一样本抽取对比（样本 skills/citation-check，extensions=[md]，经
  tools/codesucker_bridge.run_source_materials 实跑）：audit/files.json/selection.json/
  stats.json/cleaned.json/rendered 源程序.txt 的 sha256 完全一致；rendered 源程序.docx
  hash 不同经同版本两次重跑复验为 docx 容器时间戳非确定性（同版本两次运行 hash 亦不同），
  非内容差异。
- 验证：`pytest tests/test_codesucker_materials.py tests/test_codesucker_bridge.py
  tests/test_copyright_codesucker_integration.py tests/test_source_materials_gate.py`
  15 passed；`check_provenance.py` 全过。

## 2026-11-16 收尾批：core 子包 test/ 与 package.json 补齐同步

- 上一批 UP-12 的同步范围声明为 `packages/core/src`；本批把 vendor 补齐至 16fb1e3 全量：
  `packages/core/package.json`（0.4.4→0.5.3，test 链新增 language-compat / third-party-risk /
  scan-reliability / real-projects-isolation）与 `packages/core/test/` 对齐上游（更新 8 件、
  新增 language-compat.ts / scan-reliability.ts / third-party-risk.ts / real-projects-isolation.ts /
  helpers/temporary-directory.ts 共 5 件）。
- `package-lock.json` 根版本字段 0.4.4→0.5.3（仅根包版本记录；依赖集合与 integrity 未动，
  与外层 package.json 0.5.3 对齐）。
- `packages/core/tsconfig.json` 保留本仓形态（不回退上游 `extends: ../../tsconfig.base.json`
  ——vendor 树外无该文件，悬空 extends 已于 2026-09 深读批移除）。
- 上游 core 冒烟实跑（Windows / Node v24.18.0）：11 项中 10 项 PASS；`third-party-risk.ts`
  在 Windows 不可运行——夹具在 `test/third-party-risk.ts:287` 创建含双引号目录名
  `vendor/go"quoted`，该字符为 Windows 文件系统非法字符，属上游测试夹具的平台兼容缺陷，
  非核心逻辑缺陷；如实记档，不改上游测试、不伪造通过。Linux/macOS 上该项可正常执行。
- 本仓最小回归复跑：UP-12 四件（materials / bridge / copyright-integration /
  source-materials-gate）15 passed；vendor + host_dep_scan 8 passed；`check_provenance.py` 全过。

## 2026-09-26 local publication hardening

- File: `codesucker-cli.mjs` (local adapter only; upstream core algorithms unchanged).
- Reason: an independent full regression observed Windows `EPERM` on the final
  temporary-directory rename after all nine material files had been written.
- Change: retry only the final rename for Windows `EPERM` / `EACCES` / `EBUSY`,
  up to five retries (25/50/100/200/400 ms). Never regenerate materials or suppress
  a permanent error; keep the temporary output on failure and refuse a conflicting
  destination. The existing generation and validation contract is unchanged.
- Regression: `tests/test_codesucker_materials.py::test_directory_publication_retries_only_transient_windows_locks`
  covers normal publication, three transient codes, exhaustion, other errors,
  non-Windows behavior and a competing destination. CLI import no longer executes
  its entrypoint, allowing direct tests of the same publication function.

## Upgrade rule

An upgrade must pin a commit, refresh this file and the license audit, then run
the core smoke tests plus the suite bridge and end-to-end tests. Runtime network
access is never required for source processing.
