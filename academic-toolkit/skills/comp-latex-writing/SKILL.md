---
name: comp-latex-writing
description: "国赛 LaTeX 写作（Latex Writing for CUMCM）——数模竞赛论文写作方法技能（公式/表格/算法三件套+摘要页精修）；骨架一律走 comp-paper-zh 主线 _templates，禁止自造 preamble。"
---

# 国赛 LaTeX 写作（Latex Writing for CUMCM）

## 定位
数学建模竞赛论文专用的 LaTeX 技能。封装 CTeX 中文模板 + 公式/表格/算法三件套 + 国赛摘要页精修。

## 依赖
- `doc-poster-latex`（scientific-agent-skills 子 skill）— 通用 LaTeX 排版
- 本地编译器：MiKTeX / TeX Live（需预先安装）

## 核心资产

### 1. 国赛专用模板（CUMCM）——一律用主线骨架，禁止自造 preamble

⛔ 本技能不再内嵌模板：竞赛论文骨架唯一来源是 `academic-toolkit/skills/comp-paper-zh/_templates/<赛事>/`（cumcmthesis/gmcmthesis 等官方 cls，页码/摘要页/边距/匿名要求已烧进骨架，想错都难）。自造 `ctexart`+`natbib` 裸模板会绕过赛事版式基线（承诺书/编号页/无目录/页码位置），历史上曾造成格式违约。写作方法（公式/表格/算法速查）照常使用本技能，preamble 一律以主线骨架为准。

```latex
% 骨架获取（在技能正文步中）：
% cp academic-toolkit/skills/comp-paper-zh/_templates/cumcm/* paper/
% 完整赛事清单见 comp-paper-zh/SKILL.md 模板表；禁止另行手写 documentclass
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
skill("doc-poster-latex")
# 加载国赛专用模板
skill("comp-latex-writing")
```
