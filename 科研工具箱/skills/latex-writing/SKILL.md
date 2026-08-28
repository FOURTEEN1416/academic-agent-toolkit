# 国赛 LaTeX 写作（Latex Writing for CUMCM）

## 定位
数学建模竞赛论文专用的 LaTeX 技能。封装 CTeX 中文模板 + 公式/表格/算法三件套 + 国赛摘要页精修。

## 依赖
- `sci-latex-posters`（scientific-agent-skills 子 skill）— 通用 LaTeX 排版
- 本地编译器：MiKTeX / TeX Live（需预先安装）

## 核心资产

### 1. 国赛专用模板（CUMCM）
```latex
\documentclass[11pt,a4paper]{ctexart}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{geometry,graphicx,booktabs,longtable}
\usepackage{algorithm,algpseudocode}
\usepackage[sort&compress,numbers]{natbib}
\usepackage[hidelinks]{hyperref}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
```

### 2. 数学公式速查（国赛高频）
| 类型 | 示例 | LaTeX |
|------|------|-------|
| 矩阵 | $A_{m \times n}$ | `A_{m \times n}` |
| 分段函数 | `\begin{cases}` | 条件约束 |
| 求和/积分 | `\sum_{i=1}^n` | 模型目标 |
| 希腊字母 | `\alpha,\beta,\theta` | 参数符号 |
| 矩阵括号 | `\begin{bmatrix}` | 向量/矩阵 |
| 花体 | `\mathcal{L},\mathbb{R}` | 损失函数/实数集 |

### 3. 三线表
```latex
\begin{table}[htbp]
  \centering
  \caption{标题}
  \begin{tabular}{lccc}
    \toprule
    列1 & 列2 & 列3 & 列4 \\
    \midrule
    x   & y   & z   & w   \\
    \bottomrule
  \end{tabular}
\end{table}
```

### 4. 算法伪代码
```latex
\begin{algorithm}[htbp]
  \caption{算法名称}
  \begin{algorithmic}[1]
    \State 初始化
    \For{迭代次数}
      \State 计算
    \EndFor
    \Return 结果
  \end{algorithmic}
\end{algorithm}
```

## 使用流程

### 论文撰写
```
选题 → 模型建立 → LaTeX 模板初始化 → 写摘要 → 
写正文（问题分析+模型+求解+验证）→ 参考文献 → 附录
```

### 写作优先级
1. **摘要**（国赛阅卷先看摘要，占 50% 权重）
2. **问题分析/重述**（含符号说明）
3. **模型建立**（核心公式，排版第一）
4. **模型求解**（算法伪代码）
5. **结果分析**（三线表+图）
6. **模型评价**（优缺点+改进）

## 国赛要点
- 摘要页单独一页，不编号，300-500 字
- 公式必须编号 `\tag{1}`，文中引用 `\eqref{1}`
- 图表放文中，不要集中附录
- 目录可选，页码从正文开始
- 参考文献 GB/T 7714 格式
- 附录放程序代码/长表格

## 调用方式
```powershell
# 加载通用 LaTeX 技能
skill("sci-latex-posters")
# 加载国赛专用模板
skill("latex-writing")
```
