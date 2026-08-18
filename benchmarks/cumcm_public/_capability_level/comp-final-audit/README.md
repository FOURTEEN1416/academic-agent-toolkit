# comp-final-audit P0 公开基准

## 任务
验收最终交付审计能力（comp-final-audit）的**证据链完整性**——交付审计报告、审稿执行证据、一致性报告三方齐全且 schema 正确。

## 输入
无 fixture（验收对象是工作区产物本身）。

## 被测对象（工作区）
- `AUDIT_REPORT.json`：交付审计（workflow_id / artifacts(sha256) / gate_outcomes / waivers / delivery_decision=ready）
- `REVIEW_EXECUTION_EVIDENCE.json`：审稿执行证据（4 角色 reviewer/visual_reviewer/editor/final_reviewer + output_sha256）
- `CONSISTENCY_REPORT.json`：一致性报告（ok=true + claims 非空）

## 验收命令
```bash
python evaluate.py <工作区路径>
```

## 评分量表
| 检查项 | 最低要求 |
|--------|---------|
| AUDIT schema | 5 必填键齐全 |
| artifacts sha256 | 每条含 path + 64 位哈希 |
| delivery_decision | = ready |
| review 证据 | 4 角色齐全且带哈希 |
| consistency | ok=true + claims 非空 |

全部通过 → exit 0；任一失败 → exit 1。