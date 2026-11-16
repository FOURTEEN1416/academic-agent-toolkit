# 转写-自检留痕（NS-2 新技能验证批）

> 日期：2026-11-16。对应技能：`latex-equation-from-image`（SKILL.md 工作流五步）。
> 样例图由 `make_sample_images.py` 从**已知 LaTeX** 渲染生成（构造性夹具，非真实论文截图）。

## 诚实边界（必读）

本验证批所在会话的驱动模型**不具备图像输入能力**（Read 图片返回
"Media omitted … model does not support image input"），故第 1 步"视觉转写"未由
独立视觉模型真实执行；三张样例图的"转写结果"取自 `make_sample_images.py` 的
渲染源（构造性已知），**sympy 数值自检环节（第 3 步）为真实执行**。置信度按判据
表如实标注：构造性样例 + 真实自检通过记 `high` 仅对"自检机制有效性"成立；
对"视觉转写正确性"本批不提供证据，真实使用时须由具备视觉能力的驱动侧模型
重新转写并复跑自检。

## 样例 1：eq1_quadratic.png（二次公式）

- 图内容（渲染源）：`x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}`
- 转写 LaTeX：
  ```latex
  x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
  ```
- 自检（取 a=2, b=3, c=-5，先求两根再回代原方程 ax²+bx+c）：
  ```
  $ python scripts/verify_latex.py eval --expr "(-b + \sqrt{b^2 - 4ac})/(2a)" --assign a=2 b=3 c=-5
  ✅ eval = 1.0
  $ python scripts/verify_latex.py eval --expr "(-b - \sqrt{b^2 - 4ac})/(2a)" --assign a=2 b=3 c=-5
  ✅ eval = -2.5
  $ python scripts/verify_latex.py eval --expr "a x**2 + b x + c" --assign a=2 b=3 c=-5 x=1
  ✅ eval = 0.0
  $ python scripts/verify_latex.py eval --expr "a x**2 + b x + c" --assign a=2 b=3 c=-5 x=-2.5
  ✅ eval = 0.0
  ```
- 结论：回代残差精确为 0，转写结构自洽。**置信度：high**（自检机制验证通过；视觉正确性待真实视觉模型复核）。

## 样例 2：eq2_gaussian.png（高斯密度）

- 图内容（渲染源）：`f(x) = \frac{1}{\sigma\sqrt{2\pi}}\; e^{-\frac{(x-\mu)^2}{2\sigma^2}}`
- 转写 LaTeX：
  ```latex
  f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}
  ```
- 自检（μ=0、σ=1 时与独立参考式 e^{-x²/2}/√(2π) 做 8 采样点比对；另在 x=1.5 处与纯 Python 计算对账）：
  ```
  $ python scripts/verify_latex.py check --lhs "1/(\sigma \sqrt{2\pi}) e^{-(x-\mu)^2/(2\sigma^2)}" --rhs "e^{-x^2/2}/\sqrt{2\pi}" --assign mu=0 sigma=1 --samples 8
  check 结果：8/8 点一致，0 点不一致，0 点跳过（自由符号采样：['x']）
  ✅ lhs 与 rhs 在全部有效采样点一致（tol=1e-09）
  $ python scripts/verify_latex.py eval --expr "1/(\sigma \sqrt{2\pi}) e^{-(x-\mu)^2/(2\sigma^2)}" --assign x=1.5 mu=0 sigma=1
  ✅ eval = 0.12951759566589172
  $ python -c "import math; print('独立参考值:', math.exp(-1.5**2/2)/math.sqrt(2*math.pi))"
  独立参考值: 0.12951759566589174
  ```
- 结论：8/8 采样点一致；x=1.5 处与独立计算在 1e-15 内吻合。**置信度：high**（同上边界说明）。

## 样例 3：tab1_summary.png（结果摘要表）

- 图内容（渲染源）：

  | Group | Mean | SD | Delta vs A |
  |---|---|---|---|
  | A | 12.4 | 0.8 | - |
  | B | 15.1 | 1.2 | 2.7 |
  | C | 9.8 | 0.5 | -2.6 |

- 转写 LaTeX：
  ```latex
  \begin{tabular}{lrrr}
  \toprule
  Group & Mean & SD & $\Delta$ vs A \\
  \midrule
  A & 12.4 & 0.8 & -- \\
  B & 15.1 & 1.2 & 2.7 \\
  C & 9.8 & 0.5 & $-2.6$ \\
  \bottomrule
  \end{tabular}
  ```
- 自检（Δ 列勾稽）：
  ```
  $ python scripts/verify_latex.py eval --expr "15.1 - 12.4"
  ✅ eval = 2.6999999999999993
  $ python scripts/verify_latex.py eval --expr "9.8 - 12.4"
  ✅ eval = -2.5999999999999996
  ```
- 结论：Δ 列与 Mean 列差值勾稽一致（浮点尾差 3e-16 在容差内）。**置信度：medium**——
  图片数字转写天然易错（0/8、1/7、小数点），虽勾稽通过，仍建议人工对照原图复核每一位数字。

## 汇总

| 样例 | 自检结果 | 置信度 | 待人工复核项 |
|---|---|---|---|
| eq1 二次公式 | 回代残差 0 | high | 视觉转写正确性（本会话无视觉能力，构造性样例） |
| eq2 高斯密度 | 8/8 采样点一致 + 独立对账 | high | 同上 |
| tab1 摘要表 | Δ 列勾稽一致 | medium | 逐位数字对照原图 |
