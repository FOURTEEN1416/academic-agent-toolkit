# comp-review P0 公开基准

## 任务
验收逻辑审稿能力（comp-review）的**缺陷检出率**——审稿必须能发现预埋的逻辑缺陷，而不是"无问题通过"。

## 输入（fixtures/）
- `defective_modeling_report.md`：预埋 4 类典型缺陷的建模报告
  - D1 方向反（识别高峰 → 最小化高峰数）
  - D2 外推过硬（预测 500 远超观测区间）
  - D3 符号冲突/重复计量（d12 两个值）
  - D4 漏变量（缺容量约束）
- `defect_manifest.json`：缺陷清单（含关键词提示）

## 被测对象（工作区）
- `COMP_REVIEW.md`：审稿报告
- `COMP_REVIEW_VERDICT.json`：审稿裁定（fatal_count 整数 + findings 列表）

## 验收命令
```bash
python evaluate.py <工作区路径>
```

## 评分量表
| 检查项 | 最低要求 |
|--------|---------|
| 缺陷检出率 | ≥75%（4 类检出 ≥3 类） |
| verdict JSON | fatal_count + findings 结构 |
| 证据型审稿 | 引用具体行/数值 |
| 文件大小 | ≥500 B |

全部通过 → exit 0；任一失败 → exit 1。

## 与系统防伪造机制的关系
本基准的审稿产物必须由**真实审稿子智能体**产生（requires_subagent 强制）——预埋缺陷的存在让"伪造 PASS"无处遁形。