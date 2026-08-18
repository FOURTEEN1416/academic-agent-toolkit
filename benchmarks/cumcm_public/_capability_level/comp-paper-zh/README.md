# comp-paper-zh P0 公开基准

## 任务
验收中文竞赛论文（comp-paper-zh 能力）的章节结构完整性与基础质量。

## 输入
- `fixtures/paper_structure_reference.md`：国赛论文标准结构参考（10 章节）

## 被测对象（工作区）
- `paper/main.tex`：论文 LaTeX 源文件

## 验收命令
```bash
python evaluate.py <工作区路径>
```

## 评分量表
| 检查项 | 最低要求 |
|--------|---------|
| 章节数 | ≥8 个标准章节 |
| 摘要 | 必须含 |
| 参考文献 | 必须含 |
| 附录 | 必须含（国赛要求附录含代码） |
| 文件大小 | ≥10000 B |

全部通过 → exit 0；任一失败 → exit 1。

## 许可
本项目自创合成 fixture，无外部版权材料，可自由再分发。