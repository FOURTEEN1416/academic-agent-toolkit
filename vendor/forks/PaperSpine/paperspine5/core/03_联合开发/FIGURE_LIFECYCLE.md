# 图文全生命周期

这条生命周期把 PaperSpine 的科学论证、paperFig/FigMirror 的图件创作以及最终论文渲染视为同一个可恢复 job。唯一主线是 `figure_requests.json → figure_body_contract.json → final pixels`；规划、候选和审计文件都是这条主线的证据，不另建平行故事表。

| 阶段 | 主责 | 完成证据 |
| --- | --- | --- |
| 图理解与科学故事 | PaperSpine | 逐图/逐 panel 理解后形成原子 `figure_requests.json` |
| 路由 | 整合层 | `keep` 绑定真实 `current_figure`；`redesign/create` 进入 `generation_plan.json` |
| 候选创作与 QA | paperFig / FigMirror | A/B(/C) 的源文件、定稿、authoring report、panel manifest 与视觉判断 |
| 整图确认 | 用户/Agent + FigMirror | 覆盖全部图件的 `review_decision.json`；保留图身份为 `existing` |
| 装配与正文合同 | 整合层 | 出版图、可编辑源、SHA-256、`figure_body_contract.json` 与 LaTeX 片段 |
| 正文消费 | PaperSpine | Results/图注遵守合同，正文对每个 label 真实 `\ref` |
| 最终像素与论文审计 | PaperSpine | `visual_audit_manifest.json`、最终 figure-story check、五维 readiness 与 `is_complete=true` |

协调器只约束身份、证据与完成语义，不替 Agent 选择布局或固定表达风格。`keep` 不触发无意义重画；`redesign/create` 的候选可自由探索视觉形式，但必须保持同一科学故事与证据边界。装配完成后的状态是 `awaiting_paper_integration`；正文与五维审计完成后进入 `canonical_paper_ready`，仍不等同于目标投稿包已就绪。

实时检查：

```powershell
python 03_联合开发/scripts/paperspine_figure.py workflow <integration_job.json>
```

本地工作区也提供 `GET /api/workflow`。六段状态来自真实请求、候选/决定、正文合同、TeX 引用和 PaperSpine readiness，不从聊天文本推断。
