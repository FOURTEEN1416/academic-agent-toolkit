> ⛔ **已废止（2026-09-19 治理收口）**：本台账为 **2026-08-13 快照**，其 `Root` 仍写旧路径 `D:\Desktop\数模竞赛`，分类结论（"none are marked 正式"等）已被后续治理取代。**现行权威台账 = [`capabilities/catalog.json`](../capabilities/catalog.json)（307 条，2026-09-19 实测）**。
>
> **决策留痕（2026-09-19，不重跑、不删除）**：① 重跑需扫全仓 6.3 万文件，而产出已被 catalog 取代，成本远超收益；② `dev-docs/` 下 10 处历史报告仍引用本文件作为"当时资产构成"的证据，删除会断链。故就地标废，仅供追溯，**不得作为发布授权依据**。
>
> 历史标注（原文保留）：⚠️ **状态已过期（2026-08-28 治理标注）**：本台账为 2026-08-13 快照。"none are marked 正式"等结论已被取代——capabilities/catalog.json 现为 269 条（正式 10）。刷新请重跑 tools/build_asset_ledger.py。

# File-Level Asset Ledger

> **Status: provisional inventory evidence, not release authorization.** Generated at 2026-08-13T11:50:30.529941+00:00.

## Scope

- Root: `D:\Desktop\数模竞赛`
- Registered files: 11252
- `.env` entries are path-only sensitive records. Their content was not opened and their SHA-256 values are `null`.
- No record establishes ownership, license, redistribution permission, formal capability status, or host compatibility.

## Classification Counts

| Classification | Files |
| --- | ---: |
| `candidate_public_core` | 77 |
| `excluded_sensitive` | 3921 |
| `experimental` | 509 |
| `historical_reference` | 273 |
| `private_extension` | 6472 |

## Asset Group Counts

| Asset group | Files |
| --- | ---: |
| `historical_exercises` | 51 |
| `legacy_toolkit` | 137 |
| `main_reference_data` | 6 |
| `main_skills` | 448 |
| `main_suite_support` | 12 |
| `main_tools` | 61 |
| `opencode_integration` | 8 |
| `private_research_material` | 6466 |
| `publication_governance` | 17 |
| `root_historical_analysis` | 57 |
| `root_unclassified_artifact` | 28 |
| `runtime_core` | 40 |
| `sensitive_local_state` | 3921 |

## Required Follow-Up

Every `candidate_public_core` or `experimental` record remains blocked until provenance, licensing, dependency, security, benchmark, and OpenCode Desktop acceptance evidence is recorded. Private, historical, and sensitive records are excluded from a public package.

## Related Capability Catalog

The minimum capability catalog is available at [`capabilities/catalog.json`](../capabilities/catalog.json). All entries are provisional `experimental` or `private_extension` status; none are marked `正式`. No capability is promoted to formal status without completed source verification, licensing, dependency, security benchmark, and OpenCode Desktop acceptance.