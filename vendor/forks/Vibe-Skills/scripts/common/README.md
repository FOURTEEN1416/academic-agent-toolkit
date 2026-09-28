# Common Script Primitives

- Scripts root: [`../README.md`](../README.md)
- Verify surface: [`../verify/README.md`](../verify/README.md)
- Governance surface: [`../governance/README.md`](../governance/README.md)

## What Lives Here

`scripts/common/` 保存被多个 governance / verify 脚本复用的共享原语，避免各脚本重复实现 BOM 检查、路径归一化、execution-context 校验与 wave gate harness。

## Stable API

### Text / BOM

- `New-VgoUtf8NoBomEncoding`
- `Write-VgoUtf8NoBomText`
- `Append-VgoUtf8NoBomText`
- `Test-VgoUtf8BomBytes`
- `Get-VgoFileBomInfo`

### Path / Repo Context

- `ConvertTo-VgoFullPath`
- `Test-VgoPathWithin`
- `Resolve-VgoRepoRoot`
- `Get-VgoRelativePathPortable`
- `Get-VgoGovernanceContext`
- `Assert-VgoCanonicalExecutionContext`

### Parity / Packaging / Records

- `Remove-VgoIgnoredKeys`
- `Get-VgoNormalizedJsonHash`
- `Test-VgoFileParity`
- `Get-VgoRelativeFileList`
- `Get-VgoLatestJsonlRecord`
- `Get-VgoPackagingContract`
- `Get-VgoInstalledRuntimeConfig`
- `Get-VgoMirrorTopologyTargets`
- `Get-VgoMirrorTarget`
- `Get-VgoLegacySourceOfTruthCompatibility`

## Files

### [`vibe-governance-helpers.ps1`](vibe-governance-helpers.ps1)

Dot-sourced helper library for shared context resolution, no-BOM writing, parity checks, mirror topology lookup, and execution-context enforcement.

### [`vibe-wave-gate-runner.ps1`](vibe-wave-gate-runner.ps1)

Wave83-100 系列 gate 的共享 runner，负责：
- 读取 wave manifest
- 统一 assertion 输出
- 关键字 / 文件存在性检查
- 产出结构化 gate artifacts

## Rules

- 以 dot-source 方式复用 helper；不要把它当作独立 CLI 命令。
- 不要在单脚本里重复实现 no-BOM 写入或 canonical execution-context 逻辑；优先走这里的 stable API。
- 新增 common helper 后，必须更新本 README，并在调用方 README / docs 中补导航锚点。