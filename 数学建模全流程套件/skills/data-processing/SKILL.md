# Data Processing Skill

## 用途
把原始数据（CSV/Excel/JSON/爬虫）变成"能直接喂给模型"的干净数据。

## 触发时机
- 拿到赛题自带数据后立刻做
- 爬到的数据入库前做

## 输入
1. 原始数据文件（`work/data/raw/*.csv` 或 `*.xlsx`）
2. 数据字典（每列什么含义）
3. 分析阶段定的数据需求清单

## 输出
1. **清洗后数据**（`work/data/clean/*.csv`）
2. **数据质量报告**（`work/data/quality_report.md`）
3. **可视化预览**（`work/figures/data_overview.png`）

## 强制处理流程
```
读入（pd.read_csv/excel）→ 概览（head/info/describe）→ 缺失值处理 → 异常值检测 → 标准化/归一化 → 拆分训练/测试 → 导出
```

## 缺失值 4 种处理方式
| 场景 | 处理方式 | 代码 |
|------|----------|------|
| 缺失率 < 5% | 均值/中位数/众数填充 | `df.fillna(df.mean())` |
| 缺失率 5-30% | 回归预测填充 | `IterativeImputer` |
| 缺失率 > 30% | 删列 or 标记为 "未知" 类别 | `df.drop(columns=...)` |
| 时间序列 | 前向/后向填充 | `df.fillna(method='ffill')` |

## 异常值 3 种检测
1. **3σ 原则**：超出均值 ±3 倍标准差
2. **IQR 原则**：超出 Q1-1.5*IQR 或 Q3+1.5*IQR
3. **业务规则**：年龄 < 0、价格 < 0 等明显错误

## 数据质量报告模板
```markdown
# 数据质量报告

## 1. 数据规模
- 行数：xxxx
- 列数：xx
- 内存占用：xx MB

## 2. 缺失值
- 总缺失率：xx%
- 缺失率 > 30% 的列：[列名列表]
- 处理方式：xxx

## 3. 异常值
- 3σ 检测出 xx 个
- IQR 检测出 xx 个
- 业务规则检测出 xx 个
- 处理方式：xxx

## 4. 分布概览
- 数值型：均值/中位数/标准差/分位数
- 分类型：top 5 类别占比
```

## 常用代码片段
```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split

# 读入
df = pd.read_csv('work/data/raw/xxx.csv')

# 概览
print(df.head())
print(df.info())
print(df.describe())

# 缺失值
print(df.isnull().sum())

# 异常值（IQR）
Q1 = df.quantile(0.25)
Q3 = df.quantile(0.75)
IQR = Q3 - Q1
outliers = ((df < (Q1 - 1.5 * IQR)) | (df > (Q3 + 1.5 * IQR))).sum()

# 标准化
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df)

# 拆分
train, test = train_test_split(df, test_size=0.2, random_state=42)
```

## 必填交付物
- `work/data/clean/xxx_cleaned.csv`
- `work/data/quality_report.md`
- `work/figures/data_overview.png`（4 子图：缺失值/分布/相关性/异常值）

## 后续 Skill
- `model-building`：用清洗后的数据建模
- `visualization`：用质量报告中的图做正文
