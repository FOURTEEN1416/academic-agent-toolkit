---
name: comp-literature
description: Use when a mathematical modeling competition workflow needs verified literature research, citation provenance, or a reproducible reference ledger before modeling or paper writing.
---

# Competition Literature Evidence

Search with `tools/scholar_fetch.py`; do not invent references. Write `LITERATURE.md`, `literature/search_evidence.json`, and `paper/references.bib`. Each evidence record must preserve the query, returned bibliographic metadata, source, verification status, and BibTeX key. State unavailable services explicitly and do not claim verification without a record.

往届优秀论文借鉴通道（2026-09-11 接入）：查 `data/historical_papers.md`（历年真题与公开渠道索引）与 `data/case_patterns.md`（题型规律+方法查重），并研读本地优秀论文页面图——仅用于**写法/结构/方法模式借鉴与自查**。⚠ 这些资料不含可核验的著录信息（题名/作者/出处），**禁止**据此在 references.bib 中编造往届论文条目；参考文献一律过 `scholar_fetch.py` 三查。正文如需体现借鉴，用泛指表述（如"近年国赛优秀论文的建模与写作范式"），不伪造 bib 条目。

引用质量核验（2026-09-11 接线）：references.bib 成稿后调 `citation-check` 技能（国赛口径：GB/T 7714 规范性+格式一致性+引用完整性+来源可信度）；英文文献占比高时加跑 `check-citations`（CrossRef/Semantic Scholar/OpenAlex 三源核验，专杀 AI 幻觉引用/嵌合引用）。查出的不存在条目直接删除换真实文献，禁止"改一改凑数"。
