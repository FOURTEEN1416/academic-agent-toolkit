# Repository Cleanliness Governance

## Why This Exists

当前仓库不是一个普通的单根代码仓库；它同时包含：

- canonical root；
- install/runtime 期间按需生成的 `skills/vibe` 兼容面；
- install-only generated compatibility target `bundled/skills/vibe`（不再作为 repo-tracked mirror 存在）；
- 本地操作者 scratch / agent state；
- 运行期 `outputs/*` 证据产物。

因此，“仓库干净”不能简单等价为“盲目删文件直到 `git status` 归零”。

对 VCO 来说，真正需要治理的是：

1. **本地噪声不要污染工作区**；
2. **镜像不要绕开 canonical 直接漂移**；
3. **运行产物不要伪装成长期资产**；
4. **真实工作集要与本地噪声严格分层**。

## Cleanliness Layers

| Layer | Typical Paths | Required Action |
| --- | --- | --- |
| Local operator state | `.serena/`, `task_plan.md`, `findings.md`, `progress.md` | 不入库；通过 shared ignore 或 local exclude 隐藏 |
| Temporary scratch | `.tmp/` | 默认不入库；一次性补丁/调查文件及时删除 |
| Runtime outputs | `outputs/**` | 视为可再生证据，不作为 canonical 资产 |
| Governed workset | `adapters/`, `agents/`, `apps/`, `benchmarks/`, `bundled/`, `commands/`, `config/`, `core/`, `dist/`, `docs/`, `mcp/`, `packages/`, `protocols/`, `references/`, `rules/`, `schemas/`, `scripts/`, `templates/`, `tests/`, `third_party/`, `tmp-kernel-benchmark-artifacts/`, `vendor/`, `vgo_cli/` | 保留为后续分批审阅/提交对象，不要用 ignore 掩盖 |
| High-risk packaging workset | `config/version-governance.json`, runtime packaging configs, install/uninstall/verify scripts | 只能走 canonical truth + generated compatibility，禁止重新引入 tracked mirror |

## Repo Policy

### Shared Ignore

以下路径属于所有开发者都会重复出现的本地状态，应放在 shared `.gitignore`：

- `.serena/`
- `.tmp/`

### Local Worktree Exclude

以下文件属于会话级 scratch，不应强行定义为团队资产；统一通过 `.git/info/exclude` 安装：

- `task_plan.md`
- `findings.md`
- `progress.md`

安装命令：

```powershell
pwsh -NoProfile -File .\scripts\governance\install-local-worktree-excludes.ps1
```

### Text Normalization

仓库级文本规范由根 .gitattributes 定义：

- frontmatter-sensitive 与治理文本资产统一按 LF 管理；
- PowerShell 写入仍必须保持 UTF-8 no-BOM；
- 不要依赖 core.autocrlf 作为结构性契约。

### Cleanup Contract

当前已确认的低风险清理目标：

- `.tmp/wave31_39_patch.ps1`：若没有被任何资产引用，则删除；
- 根目录 planning scratch：若已迁移为正式计划文档，则可删除并交给 local exclude 兜底。

## Verification Contract

新增 `scripts/verify/vibe-repo-cleanliness-gate.ps1`，其目标不是假装仓库已经 zero-dirty，而是先判断：

- 是否仍有**本地噪声**暴露在 `git status`；
- 是否仍有**运行产物**暴露在 `git status`；
- 是否出现了**不在治理范围内的未知 dirty 路径**；
- 另外把真实的 governed workset / high-risk mirror pressure 作为 advisory 单独报告。

这里的 governed workset 必须跟着真实仓库拓扑一起更新。当前 repo 已经不只是 `config/`、`docs/`、`scripts/` 这几个旧根；像 `apps/`、`packages/`、`tests/`、`adapters/`、`benchmarks/` 这类明确属于 canonical repo 的顶层面，也应被视为 managed workset backlog，而不是落到 uncategorized dirty。

补充 operator：scripts/governance/export-repo-cleanliness-inventory.ps1 会导出 plane split、top dirty prefixes 与 bucket summary，用于 Batch0 的 freeze/inventory/classification。

也就是说：

- **PASS** = 本地卫生已经收口；
- **repo_zero_dirty = false** = 仍有真实工作集 backlog，后续要继续分批整理；
- 这两个结论可以同时成立，且语义不同。

## Daily SOP

1. 先运行 local exclude 安装器。
2. 运行 `export-repo-cleanliness-inventory.ps1 -WriteArtifacts`，冻结当前 dirty snapshot。
3. 运行 `vibe-repo-cleanliness-gate.ps1 -WriteArtifacts`，确认本地噪声已收口。
4. 运行 `vibe-output-artifact-boundary-gate.ps1 -WriteArtifacts`，确认 `outputs/**` 没有越界。
5. 如涉及 runtime packaging / compatibility 资产，复跑：
   - `vibe-mirror-edit-hygiene-gate.ps1`
   - `vibe-nested-bundled-parity-gate.ps1`
   - `vibe-version-packaging-gate.ps1`
6. 如涉及 install / release，再运行 runtime freshness / coherence / frontmatter gates。
7. 只有在 local hygiene 与 outputs boundary 都合格后，才继续新的 wave 执行。

## Phase-End Hygiene

Every cleanup batch ends with the same bounded rule:

1. purge temporary scratch first
2. verify repo hygiene second
3. audit managed node ownership third
4. keep node termination report-only unless a managed candidate is explicitly confirmed

The canonical operator entrypoint is:

```powershell
pwsh -NoProfile -File .\scripts\governance\phase-end-cleanup.ps1 -WriteArtifacts
```

What it does:

- removes `.tmp/` when it exists
- refreshes local excludes for `task_plan.md`, `findings.md`, `progress.md`
- reruns `vibe-repo-cleanliness-gate.ps1`
- reruns `vibe-output-artifact-boundary-gate.ps1`
- runs `Invoke-NodeProcessAudit.ps1`
- runs `Invoke-NodeZombieCleanup.ps1` in report-only mode

For batches that changed packaging / compatibility surfaces, use:

```powershell
pwsh -NoProfile -File .\scripts\governance\phase-end-cleanup.ps1 -WriteArtifacts -IncludeMirrorGates
```

`-ApplyManagedNodeCleanup` is intentionally not part of the default path. It may only be used after the audit output proves the target process is `vco-managed`.

## Guardrails

- 不要用 `.gitignore` 去隐藏真实 canonical 工作集。
- 不要重新把 `bundled/skills/vibe/**` 当成 repo-tracked 真实源；该路径只允许作为生成兼容面存在于 install/runtime 边界。
- 不要因为 `.tmp/` 被忽略，就默认删除 `.tmp/vco-runtime-backups/*`；如果 manifest 仍引用它们，必须先审计引用关系。
- planning scratch 可以存在，但它们不应再污染仓库视图。
