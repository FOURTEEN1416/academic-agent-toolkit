---
name: comp-literature
description: Use when a mathematical modeling competition workflow needs verified literature research, citation provenance, or a reproducible reference ledger before modeling or paper writing.
---

# Competition Literature Evidence

Search with `tools/scholar_fetch.py`; do not invent references. Write `LITERATURE.md`, `literature/search_evidence.json`, and `paper/references.bib`. Each evidence record must preserve the query, returned bibliographic metadata, source, verification status, and BibTeX key. State unavailable services explicitly and do not claim verification without a record.

往届优秀论文借鉴通道（2026-09-11 接入）：查 `data/historical_papers.md`（历年真题与公开渠道索引）与 `data/case_patterns.md`（题型规律+方法查重），并研读本地优秀论文页面图——仅用于**写法/结构/方法模式借鉴与自查**。⚠ 这些资料不含可核验的著录信息（题名/作者/出处），**禁止**据此在 references.bib 中编造往届论文条目；参考文献一律过 `scholar_fetch.py` 三查。正文如需体现借鉴，用泛指表述（如"近年国赛优秀论文的建模与写作范式"），不伪造 bib 条目。

引用质量核验（2026-09-11 接线）：references.bib 成稿后调 `citation-check` 技能（国赛口径：GB/T 7714 规范性+格式一致性+引用完整性+来源可信度）；英文文献占比高时加跑 `check-citations`（CrossRef/Semantic Scholar/OpenAlex 三源核验，专杀 AI 幻觉引用/嵌合引用）。查出的不存在条目直接删除换真实文献，禁止"改一改凑数"。

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 每条文献有核验状态、引用位置与使用方式三要素
- [ ] 检索来源与查询词已写入产物（可追溯）
- [ ] 引用格式符合目标规范（GB/T 7714 等）
- [ ] 无编造条目：所有条目可在检索源中复现

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "文献随便列几条撑篇幅" | 引用是可信度信号也是合规项：编造条目属学术不端，会连带整篇失效。 |
| "搜不到就先空着" | 空着可接受，编造不可接受；搜不到的结论要如实记录检索过程。 |
| "格式以后再统一" | 格式问题会在交付审计集中爆发，此处修复成本最低。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
