# comp-code P0 基准 — 编程求解能力验收

## 任务描述

本基准测试评估数学建模竞赛智能体的**编程求解能力**：读取附件数据（法医 STR 混合图谱），编写求解代码完成"混合样本贡献者人数判定"（问题一），将结果写入统一结果台账并落盘，最后产出结果报告。

## 输入

- `fixtures/str_micro_data.csv` — 微型 STR 合成数据（3 样本 × 3 marker，模拟附件 1 宽表的简化版）

### 数据格式与文件名编码约定

列 = `sample, marker, allele1, height1, allele2, height2, ..., allele6, height6`（宽表；混合样本的等位基因峰按序填入，不足 6 个峰的留空）。

**文件名编码约定**：`<标签>_n<贡献者数>`，样本名中的 `_n` 后缀即贡献者人数：

| 样本 | 含义 | 每 marker 峰数 | 峰高特征 |
|------|------|---------------|---------|
| `A_n2` | 2 人混合（比例约 1:1） | 4 个等位基因峰 | 各峰高相近（约 200） |
| `B_n3` | 3 人混合（比例约 1:1:1） | 6 个等位基因峰 | 各峰高相近（约 130） |
| `C_n2` | 2 人混合（比例约 1:4） | 4 个等位基因峰 | 高比例贡献者峰高约为低比例者的 4 倍 |

等位基因数值为 STR 重复数（如 10, 12, 14, 16），峰高为荧光信号强度相对值，与贡献比例相关。marker 为 D8S1179、D21S11、FGA。

## 验收方式

```powershell
python evaluate.py <工作区路径>    # 评分
python evaluate.py --self-test      # 评分脚本自验证（空工作区 fail、模拟通过场景 pass）
```

工作区路径应包含智能体产出的以下文件：
- `code/main.py` — 求解代码
- `figures/all_results.json` — 统一结果台账（含 `problem_1` 键，含 `accuracy` 或 `predictions` 字段）
- `figures/problem_1_results.json` — 问题一结果明细
- `RESULTS.md` — 结果报告

## 评分项与最低要求

| 评分项 | 最低要求 |
|--------|---------|
| 代码存在 | `code/main.py` ≥ 500 字节 |
| 结果台账 | `figures/all_results.json` 存在且含 `problem_1` 键，`problem_1` 含 `accuracy` 或 `predictions` |
| 问题结果 | `figures/problem_1_results.json` 存在 |
| 语义正确性 | 若 `accuracy` 存在则 0 < accuracy ≤ 1；若 `predictions` 存在则非空 |
| 结果报告 | `RESULTS.md` ≥ 1000 字节 |

所有检查项通过即 `all_pass: true`，评分脚本退出码 0。

## 许可

本基准数据为合成数据，仅供内部验收测试使用。