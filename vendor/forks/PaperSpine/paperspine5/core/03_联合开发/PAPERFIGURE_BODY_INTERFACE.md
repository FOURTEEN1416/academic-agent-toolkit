# PaperFigure → PaperSpine 正文结合接口

## 目的

该接口把“已确认科研图”发布为 PaperSpine 可以直接消费、可以独立验真的正文合同。它解决四个此前彼此分离的问题：最终图文件是哪一个、正文用什么标签引用、图支持哪一段 Results 和哪条主张、可编辑源文件如何随论文保留。

公开合同是 `paper_rewriting_output/figure_body_contract.json`，Schema 位于 `contracts/figure-body-contract.schema.json`。正文措辞仍由 PaperSpine 负责；PaperFigure 只发布已经由图件证据支持的主张范围，不代写或扩大论文结论。

## 自动产物

整图确认并装配后自动生成：

- `figure_body_contract.json`：机器可读正文结合合同；
- `figure_body_contract.md`：供写作 Agent/人工阅读的同义视图；
- `figure_asset_map.md`：在保留已有人工内容的前提下更新 `PAPERFIGURE-BODY-MAP` 区块；
- `final_paper/figures/<figure-id>.<format>`：投稿/正文使用的出版图；
- `final_paper/figure_sources/<figure-id>.pptx`：Img2PPT 图件的真实可编辑 PowerPoint 源；SVG 图件直接把出版 SVG 登记为可编辑源；
- `final_paper/figure_includes.tex`：规范化 `includegraphics/caption/label` 片段；
- `final_paper/figure_integration_manifest.json`：装配、哈希和正文接口收据。

## 每张图的正文合同

每条记录同时包含：

- `publication_asset`：论文实际使用的相对路径、格式、候选 ID 和 SHA-256；生成/重设计图的候选 ID 为 A/B/C，保留现图为 `existing`；
- `editable_source`：PPTX/SVG 可编辑源路径与 SHA-256；
- `label`、`caption` 和规范化 `latex.reference`；
- `results_units`：图件必须进入的 Results 单元；
- `scientific_question`、`claim`、`intended_conclusion` 与 `claim_boundary`；
- `hero_panel`、逐 panel 职责、证据锚点和预期读法；
- `prose_contract`：PaperSpine 正文允许表达的主张、必须保留的边界和可引用证据。

`figure_role`、科学问题、主张、结论、边界、Results 单元、hero panel 和 panels 是一个原子合同。旧的最小请求仍可读取和规划，但缺失任一字段时不能完成正文装配。

## 消费接口

文件接口：

```text
paper_rewriting_output/figure_body_contract.json
```

Python：

```python
from paperspine_figure_integration import validate_figure_body_contract
```

CLI：

```powershell
python 03_联合开发/scripts/paperspine_figure.py body-contract <integration_job.json>
```

本地 HTTP：

```text
GET /api/body-contract
GET /api/workflow
GET /api/publication-cycle
```

`GET /api/snapshot` 也会在装配完成后返回同一合同和全流程快照。`GET /api/workflow` 对应 CLI `workflow`，依次报告图理解与故事、候选创作/QA、整图审阅、装配与正文合同、正文真实引用、最终像素与论文审计。所有接口只读取项目内文件，不增加远程服务或数据库。

## PaperSpine 正文规则

1. Results 按 `results_units` 组织为科学问题 → 可见证据 → 有边界的回答，不按 panel 字母流水账叙述。
2. 每张装配图必须在 `final_paper/main.tex` 的正文中以 `\ref`、`\autoref` 或 `\cref` 真实引用；仅存在 `\label`、图注或文件不算完成结合。
3. 图注和正文不得超出 `claim_boundary`，不得把 schematic 当作测量结果。
4. 不允许手工改写资产路径、候选 ID 或哈希；资产变化会使正文合同和最终图件故事关卡失效。
5. 最终像素仍由 `visual_audit_manifest.json` 回证；正文合同不能替代实际渲染检查。
6. 协调器在正文合同发布后保持 `awaiting_paper_integration`；只有 PaperSpine 五维 readiness 全绿才进入 `canonical_paper_ready`。这表示规范主稿完成，不表示目标投稿包已经装配。

## 验收

- integration tests 验证 SVG 出版图、Img2PPT PNG + PPTX、`keep` 现图直通，以及装配后等待正文/像素回证再完成的状态语义；
- PaperSpine `figure_story_check.py --phase final` 验证合同与原始故事逐字段一致、资产/可编辑源哈希一致、LaTeX 标签存在且正文真实引用；
- Atlas 把该接口登记为跨模块公开合同，任何字段、路径或关卡变化都必须重新 build + verify。
