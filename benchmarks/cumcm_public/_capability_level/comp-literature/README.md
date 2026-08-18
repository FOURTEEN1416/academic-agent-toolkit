# comp-literature P0 基准 — 文献调研能力验收

## 任务描述

本基准测试评估数学建模竞赛智能体的**文献调研能力**。智能体以预置检索结果（`fixtures/preset_search_results.json`，模拟 `tools/scholar_fetch.py` 的返回）为唯一文献来源，产出文献综述报告、带完整溯源（query/来源/验证状态）的检索证据台账，以及可复用的 BibTeX 参考文献文件。核心验收点是**引用真实性**（不得编造 preset 之外的论文）与**证据记录完整性**。

## 输入

- `fixtures/preset_search_results.json` — 预置检索结果，2 条真实论文（arXiv 可验证）：
  - **arXiv:2012.00513** — "DNA mixture deconvolution using an evolutionary algorithm with multiple populations, hill-climbing, and guided mutation"（Vilsen, Tvedebrink, Eriksen, 2020）
  - **arXiv:1108.1884** — "Estimation of Parameters in DNA Mixture Analysis"（Graversen, Lauritzen, 2011）

## 验收方式

```powershell
python evaluate.py <工作区路径>
```

工作区路径应包含智能体产出的以下文件：
- `LITERATURE.md` — 文献综述报告（含引用 preset 论文）
- `literature/search_evidence.json` — 检索证据台账（list，每条含 key/title/authors/year/source/id/doi/verification_status 等）
- `paper/references.bib` — BibTeX 参考文献（citation key 与证据台账一致）

## 评分项与最低要求

| 评分项 | 最低要求 |
|--------|---------|
| LITERATURE.md 存在 | 文件存在 |
| 最小大小 | LITERATURE.md ≥ 1000 字节 |
| search_evidence.json 存在 | 文件存在且为 list |
| 记录数 | ≥ 2 条 |
| 防编造 | 每条记录的 `key` 或 `title` 必须命中 preset 检索结果（不允许虚构论文） |
| references.bib 存在 | 文件存在 |
| key 交集 | references.bib 的 citation key 与 search_evidence 的 key 交集 ≥ 2 |

所有检查项通过即 `all_pass: true`，评分脚本退出码 0。

## 评分量表（满分 100）

| 维度 | 权重 | 通过条件 |
|------|------|---------|
| 产出完整 | 30 | LITERATURE.md + search_evidence.json + references.bib 全部存在 |
| 引用真实 | 30 | search_evidence 无编造记录（全部命中 preset） |
| 证据完整 | 20 | search_evidence ≥ 2 条且为 list |
| BibTeX 闭环 | 20 | bib 与证据台账 key 交集 ≥ 2 |

未通过任一检查项则该项得 0 分；`all_pass` 视为 100 分通过。

## 许可

本基准的 preset 论文为 arXiv 公开文献（arXiv:2012.00513、arXiv:1108.1884），仅用于内部验收测试。