# Router Surface

- Scripts root: [`../README.md`](../README.md)
- Config index: [`../../config/index.md`](../../config/index.md)

## What Lives Here

`scripts/router/` 保存本地已安装 skill 的候选发现面，也就是 candidate discovery surface。这里只围绕宿主声明的本地 skill roots 给出候选项、补充澄清问题、整理确认界面，以及保留旧调用方仍需要的 compatibility projection。它不负责声明真正的工作归属、执行事实或完成结论；这些事实应由 kernel 侧产物给出。公开治理入口仍然是 `$vibe` / `/vibe`。

Current routing semantic owner: `packages/runtime-core/src/vgo_runtime/router_contract_runtime.py`.

Python direct-first is the current happy path.

`resolve-pack-route.ps1 is a compatibility bridge` for retained callers that still enter through PowerShell or for owner-failure fallback. `modules/ is legacy/helper/compatibility`; it can support retained projections, but it is not the current owner of routing semantics.

## Current Layout

| Path | Role |
| --- | --- |
| [`resolve-pack-route.ps1`](resolve-pack-route.ps1) | compatibility bridge；保留旧 PowerShell 调用方需要的候选发现与兼容字段 |
| [`modules/`](modules) | legacy/helper/compatibility；旧规则候选、澄清提示、候选排序、确认界面的辅助模块 |

## Rule

- router 目录只解释“如何找候选、何时需要确认、如何展示确认面”。
- 兼容字段可以继续存在，但只能当作旧调用方的镜像，不能当作工作真相。
- 公开执行、阶段治理与验证仍分别落到 `SKILL.md`、`protocols/`、`scripts/governance/` 与 `scripts/verify/`。
- 新增当前路由语义时，优先改 Python runtime owner；只有兼容桥接需要时才补 `modules/` 级文档。
