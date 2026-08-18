# 六域公开基准集 (six_domains_public)

学术论文、文献研究、课程材料、知识产权、图表文档五个领域的公开验收基准。作为双层基准的**公开层**，用于对应领域能力的正式验收。

## 领域结构

| 领域 | 基准ID | 主题 | 核心能力 |
|------|--------|------|---------|
| 学术论文 | ACADEMIC-01 | 机器学习可解释性综述 | academic_paper_full_pipeline |
| 文献研究 | LITERATURE-01 | 联邦学习文献综述 | literature_review_full |
| 课程材料 | COURSE-01 | 深度学习课程报告 | course_paper_full |
| 知识产权 | IP-01 | 图像识别专利交底 | patent_draft_full |
| 图表文档 | DOC-01 | 数据可视化报告 | figure_generation_pipeline |

## 验收流程

1. 对每个基准运行目标能力技能，产出交付合同要求的 artifacts
2. 运行 `evaluate.py` 进行确定性评分
3. 综合评分 ≥ 70% 视为通过

## 基准规范

每个基准包含：
- `problem.md` - 任务描述
- `delivery_contract.md` - 交付合同
- `evaluate.py` - 验收脚本
- `fixtures/` - 测试数据
- `contract.json` - 能力契约
