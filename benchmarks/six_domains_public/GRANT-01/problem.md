# GRANT-01 基金申请书结构基准（academic_papers 域）

## 任务

给定 `data/topic_brief.md`（研究主题简报）与 `data/verified_sources.json`（已核验证据集），
在目标工作区完成一份 NSFC 青年格式申请书草稿 `GRANT_PROPOSAL.md`：

1. **八节结构**：立项依据/研究内容/研究目标/研究方案/可行性分析/特色与创新/年度计划/研究基础（+经费概算）；
2. **引用纪律**：正文证据键 ⊆ verified_sources.json 登记集合，全部可点开核验；
3. **future-work 口径**：无预支实验结论；创新性以"证据集范围内未见"封顶；
4. **PI 占位**：研究基础节全部【待申请人填实】，零编造履历；
5. **时间维局限**：证据集时间边界在立项依据如实呈现。

## 评分

运行 `python evaluate.py <工作区>`，全部检查通过得 PASS（8 类结构机检）。详见 contract.json。
