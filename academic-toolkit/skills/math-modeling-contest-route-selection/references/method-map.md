# Method Map

Use this file to map problem symptoms to modeling methods. Always pair methods with baseline, solver plan, validation, and paper expression.

This file is the single source of truth for method families. Other files (for example `academic-toolkit/skills/comp-modeling/references/methods_table.md`) are pointers only and must not restate the method list.

## Selection Principle

Choose the smallest method stack that can answer the decision question and survive contest engineering constraints. A strong contest paper often uses:

- Baseline model: simple, explainable, hard to beat.
- Main model: adds the core insight.
- Solver plan: deterministic enough to finish and iterate.
- Validation model: checks robustness, sensitivity, ablation, or external consistency.

Do not select a method because it is advanced. Select it because it changes a decision, improves a baseline, handles a known weakness, or makes the paper more defensible.

## Method Families

| Problem symptom | Baseline | Strong route | Solver plan | Validation |
| --- | --- | --- | --- | --- |
| allocate scarce resources | greedy allocation, LP relaxation | integer programming, robust optimization, multi-objective optimization | scipy/pulp/ortools; exact on small cases, heuristic on large cases | constraint satisfaction, Pareto analysis, sensitivity |
| route or schedule items | nearest-neighbor, shortest path, assignment | MILP, dynamic programming, tabu/genetic/simulated annealing | start with deterministic heuristic, then improve; log convergence | compare with greedy/exact small cases |
| forecast values | naive, moving average, exponential smoothing | ARIMA/state-space, gradient boosting, hybrid mechanism features | rolling training window; keep feature pipeline simple | rolling validation, residual diagnostics, decision regret |
| rank/evaluate alternatives | normalized indicators, dominance, PCA | entropy/AHP/TOPSIS/fuzzy only if indicators are justified | spreadsheet/Python table pipeline with rank-stability loop | weight perturbation, rank stability, known-case check |
| simulate physical process | dimensional analysis, simplified ODE | mechanism equations, finite difference, parameter calibration | solve simple case analytically before numerical simulation | limiting cases, convergence, physical sanity |
| model spread or diffusion | logistic/SIR/SIS | network epidemic, Markov chain, agent-based simulation | calibrate few parameters; avoid huge arbitrary simulations | reproduce known curves, parameter sensitivity |
| classify or extract patterns | rules, thresholding, classical features | random forest/SVM/CNN only when data supports it | cross-validation pipeline; save confusion matrix and errors | confusion matrix, ablation, downstream error |
| analyze compositional or percentage-sum data | raw percentage summaries, boxplots, simple tests | log-ratio transform (CLR/ILR) + closed-sum-aware clustering/discriminant + correction model | check zeros/missing values, transform, then model; keep raw baseline for comparison | sub-composition stability, corrected vs uncorrected ablation, known-class recovery |
| bearing-only or passive localization | analytic triangulation from known transmitters | identifiability/minimum-source proof + condition number/GDOP + error propagation + robust adjustment | solve closed-form cases first, then least-squares/robust optimization with residual checks | reverse-check known positions, Monte Carlo deviation bands, geometric residuals |
| understand policy effect | descriptive statistics, regression | causal graph, scenario simulation, synthetic control | keep assumptions explicit; test placebo or counterfactual cases | placebo tests, sensitivity to assumptions |
| handle uncertainty | deterministic point estimate | Monte Carlo, stochastic programming, Bayesian interval | separate sampling code from model code; report intervals | confidence intervals, scenario stress test |
| manage strategic behavior | payoff matrix, simple equilibrium | evolutionary game, agent simulation | start with 2-3 actor types; calibrate behavior rules | equilibrium plausibility, behavioral sensitivity |

## Method Cards

Cards F1-F12 map one-to-one onto the twelve rows above in order. Every card has the same four blocks: applicable scale thresholds → solver and key parameters → minimal paste-ready code → three known pitfalls.

Reading rules:

- Thresholds are engineering tiers, not theorems. "实测" means measured in the current toolbox environment (numpy 2.5.1 / scipy 1.17.1 / statsmodels 0.14.6 / scikit-learn 1.9.0 / ortools 9.15.6755); treat the numbers as order-of-magnitude, not as a benchmark.
- Code keeps only the solving core. Before it enters `comp-code`, add the timeout tiers and the 30-second progress print required by `academic-toolkit/skills/comp-code/SKILL.md` (关键规则 · 求解器/优化器超时设置). This file does not restate those tiers.
- Every snippet was executed as written on synthetic data; the "示例输出" line is that run's output, proving the snippet runs, not a modeling result.
- Fit the card to the problem statement. If the statement contradicts a threshold, the statement wins; record the deviation in `MODELING_REPORT.md`.

### F1 allocate scarce resources · 资源分配

**适用规模阈值**

- 连续 LP（无整数变量）：变量到 10^5 量级仍是秒级，直接用。
- 0-1 / 整数规划：≤200 个整数变量用 `scipy.optimize.milp`（HiGHS）求到最优；实测 200 个 0-1 变量、50 条约束、1% gap 约 20 s。200–5000 个整数变量必须显式给 gap 与时限，接受次优解。
- 5000 个以上整数变量或强对称（同类物品成百上千）：先 LP 松弛拿界，再用贪心/局部搜索修复，不要硬等最优。
- 多目标：目标数 ≤4 用加权和或 ε-约束；目标数 >4 先做目标筛选，否则权重解释不清。

**求解器与关键参数**

- `scipy.optimize.milp`：`c` 是最小化系数，最大化目标要取负（`c=-profit`）。`integrality` 逐变量给 0/1。`options={'mip_rel_gap': 1e-3, 'time_limit': <按 comp-code 分档>}`。
- 必须判 `res.status`：0 最优；1 到时限/迭代上限（`res.x` 仍是可行解，但未必最优）；2 不可行；3 无界；4 其他。取解前先断言 `status in (0, 1)`。
- 报结果时同时打印 `res.mip_gap` 与 `res.mip_dual_bound`，让读者知道离最优有多远。
- `pulp` + CBC：`prob.solve(PULP_CBC_CMD(msg=False, timeLimit=..., gapRel=0.01, gapAbs=...))`。`gapRel` 是相对 gap，`gapAbs` 是绝对 gap，两个都显式给，不要依赖默认值。
- 多目标加权前先把各目标除以 baseline 值归一化，否则量级大的目标吞掉全部权重。

```python
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

rng = np.random.default_rng(0)
profit = rng.integers(5, 20, 30)
cost = rng.integers(1, 10, 30)
cap = int(cost.sum() * 0.35)
res = milp(c=-profit, integrality=np.ones(30), bounds=Bounds(0, 5),
           constraints=LinearConstraint(cost, -np.inf, cap),
           options={'mip_rel_gap': 1e-3, 'time_limit': 300})
assert res.status in (0, 1), res.message
x = np.round(res.x).astype(int)
print('status', res.status, 'obj', int(profit @ x),
      'load', int(cost @ x), '/', cap, 'gap', round(res.mip_gap, 4))
```

示例输出：`status 0 obj 514 load 49 / 49 gap 0.0`

**已知坑（3 条）**

1. `status == 1` 时 `x` 非空，但直接当"最优方案"写进论文会掩盖 10% 以上的 gap；必须把 `mip_gap` 写进结果表。
2. LP 松弛后 `round()` 取整不保证可行，容量/预算约束常被破坏 1–2 个单位；取整后必须回代全部约束并做贪心修复。
3. 量纲与符号：`sum(cost*x) <= cap` 中 cost 用"万元"、cap 用"元"会让解全 0；最大化忘了给 `c` 取负，`milp` 会把目标最小化，解贴到变量上界。建模前先统一单位，求解前先核对目标方向。

### F2 route or schedule items · 路径与调度

**适用规模阈值**

- 精确 TSP（Held-Karp 状态压缩 DP）：节点 n ≤16 稳妥；实测纯 Python 下 n=16 约 0.95 s、n=17 约 2.24 s、n=18 约 5.49 s，n ≥20 单次数十秒且内存增长快，通常不划算。
- MILP（MTZ/DFJ）：n ≤50 常见可解；带时间窗或强对称时 50 也可能跑满时限。
- n >50、多车、带时间窗：OR-Tools routing（`GUIDED_LOCAL_SEARCH`，30–60 s），或最近邻 + 2-opt（实测 n=40：689.4 → 568.7，耗时 0.09 s）。
- 调度（单机/并行机 makespan）：任务 ≤100 用 CP-SAT，通常秒级；>1000 用派工规则 + 局部搜索。

**求解器与关键参数**

- OR-Tools：`search_parameters.first_solution_strategy = PATH_CHEAPEST_ARC`（默认策略不保证有初始解）；`search_parameters.local_search_metaheuristic = GUIDED_LOCAL_SEARCH`（默认值是 `AUTOMATIC`，实测取值为 6）；`search_parameters.time_limit.FromSeconds(30)`。
- 启发式停止准则要两条同时写：时间上限（按 comp-code 分档）+ 连续无改进代数（如 200 代），先到先停。只写"迭代 1000 次"在不同规模下含义完全不同。
- 2-opt 用首次改进（first improvement）而非最优改进，竞赛里收敛更快、结果更稳。
- DP：`dp[mask][j]` 表示已访问集合 mask、当前在 j 的最小代价；转移前先判 `mask & 1` 保证从起点出发。

```python
import numpy as np
rng = np.random.default_rng(0)
P = rng.random((40, 2)) * 100
D = np.linalg.norm(P[:, None] - P[None], axis=-1)
cost = lambda t: D[t, np.roll(t, -1)].sum()
nn = [0]; left = set(range(1, len(P)))
while left:
    nxt = min(left, key=lambda j: D[nn[-1], j])
    nn.append(nxt); left.remove(nxt)
nn = np.array(nn); t = nn.copy(); improved = True
while improved:
    improved = False
    for i in range(1, len(t) - 2):
        for j in range(i + 1, len(t)):
            cand = np.concatenate([t[:i], t[i:j + 1][::-1], t[j + 1:]])
            if cost(cand) < cost(t) - 1e-9:
                t, improved = cand, True
print('nearest-neighbor %.1f -> 2-opt %.1f' % (cost(nn), cost(t)))
```

示例输出：`nearest-neighbor 689.4 -> 2-opt 568.7`

**已知坑（3 条）**

1. 距离矩阵不对称（单行道、上下坡）时 2-opt 反转一段会改变该段代价；用 `cost(cand)` 整体重算，别只增量算两条边。
2. 闭环假设：题面要求"回到仓库"才是闭环；开环（终点任意）要加虚拟 depot 或去掉最后一段，否则多算一段返程。
3. 只报局部搜索的最终值等于没有证据；必须同时报最近邻 baseline、改进幅度和停止原因（时间到 / 无改进）。

### F3 forecast values · 预测

**适用规模阈值**

- 月度数据 ≥24 点（2 个完整季节）才估季节项，周度 ≥104 点；样本 <50 点用指数平滑或 naive，不要上多参数 SARIMA。
- 特征数 p 与样本 n：线性模型按 n ≥10p 控制；树模型至少数百行才有意义。
- 滚动验证至少 3 折，测试窗要覆盖一个完整季节；只有 1 折的"验证"不能叫验证。

**求解器与关键参数**

- `SARIMAX(order=(p,d,q), seasonal_order=(P,D,Q,s), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=200)`；默认 `maxiter` 常导致收敛告警，显式给 200。
- 差分阶数 d 由 ADF/KPSS 决定，季节差分 D 由季节强度决定；不要为追拟合优度差分两次。
- 残差判据：`acorr_ljungbox(resid, lags=[10], return_df=True)`，p > 0.05 视为未检出显著自相关；残差 ACF 超过 2/√n 的滞后要逐个解释。
- 评价用滚动 origin 的 MAE/RMSE；MAPE 在真值接近 0 时分母爆炸，不能作主指标。

```python
import numpy as np, warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
warnings.filterwarnings('ignore')
rng = np.random.default_rng(0); t = np.arange(120)
y = 50 + 0.2 * t + 3 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1, 120)
cut = 90
fit = SARIMAX(y[:cut], order=(1, 1, 1), seasonal_order=(1, 0, 0, 12),
              enforce_stationarity=False, enforce_invertibility=False
              ).fit(disp=False, maxiter=200)
fc = fit.get_forecast(30).predicted_mean
lb = acorr_ljungbox(fit.resid, lags=[10], return_df=True)
print('MAE %.2f | naive %.2f | Ljung-Box p %.3f'
      % (np.abs(y[cut:] - fc).mean(), np.abs(y[cut:] - y[cut - 1]).mean(),
         lb['lb_pvalue'].iloc[0]))
```

示例输出：`MAE 1.19 | naive 2.37 | Ljung-Box p 0.999`

**已知坑（3 条）**

1. 用样本内拟合误差冒充预测精度；必须滚动 origin 重训，并同时报 naive baseline，差值为负说明模型没学到东西。
2. 手写差分后忘记还原：差分序列预测完要累加回原尺度，少加一个常数会让整条曲线平移。
3. 目标泄漏：全样本归一化、全样本均值、未来协变量都会把测试期信息带进训练，CV 分数虚高且无法在真实场景复现。

### F4 rank/evaluate alternatives · 评价与排序

**适用规模阈值**

- 方案数 n ≥3、指标数 m ≤8；m 更大时先按相关性（|r| > 0.8 合并）或 PCA 去冗余，否则重复指标被重复加权。
- 熵权法在 n <5 时熵值不稳定，结果对小样本波动敏感；此时改用等权或 AHP。
- AHP 只在能给出专家判断矩阵时用，一致性比率 CR <0.1 才可采纳。
- 权重扰动 ±10% 做 500 次重排：实测 6 方案 4 指标下 ±10% 的 min Spearman ρ = 1.000，放宽到 ±25% 时降到 0.943。

**求解器与关键参数**

- 正向化：成本型用 `max/x` 或 `(max-x)/(max-min)`，全表只能选一种公式，不要混用。
- 熵权：`p_ij = z_ij / Σ_i z_ij`，`e_j = -1/ln(n) · Σ p ln p`，`w_j = (1-e_j)/Σ(1-e)`；要求所有 `z_ij ≥ 0`。
- TOPSIS：先向量归一化 `z/√(Σz²)`，再乘权重；到正/负理想解的欧氏距离算 `C = d⁻/(d⁺+d⁻)`。
- 稳定性判据：最小秩相关 ρ <0.9 时，论文只能写"排名对权重敏感"，不能写"最优方案唯一"。

```python
import numpy as np
from scipy.stats import spearmanr
X = np.array([[8, 3, 300, 7], [6, 2, 260, 6], [9, 4, 420, 8],
              [5, 1, 240, 5], [7, 3, 310, 9], [6, 2, 280, 4]], float)
benefit = np.array([True, False, True, True])
Z = np.where(benefit, X, X.max(0) / X)
P = Z / Z.sum(0)
e = -(np.where(P > 0, P * np.log(P), 0)).sum(0) / np.log(len(X))
w = (1 - e) / (1 - e).sum()
V = Z / np.sqrt((Z ** 2).sum(0))
def topsis(V, w):
    Vw = V * w
    dp = np.linalg.norm(Vw - Vw.max(0), axis=1)
    dm = np.linalg.norm(Vw - Vw.min(0), axis=1)
    return dm / (dp + dm)
c0 = topsis(V, w); rng = np.random.default_rng(0); rhos = []
for _ in range(500):
    w2 = w * (1 + 0.10 * rng.uniform(-1, 1, len(w))); w2 /= w2.sum()
    rhos.append(spearmanr(c0, topsis(V, w2)).statistic)
print('weights', w.round(3), 'best alt', int(np.argmax(c0)) + 1,
      'min rank rho %.3f' % min(rhos))
```

示例输出：`weights [0.103 0.613 0.093 0.19 ] best alt 4 min rank rho 1.000`

**已知坑（3 条）**

1. 熵权把"方差大"当"重要"：测量噪声大的指标方差最大，会拿到最高权重，排序被噪声主导。
2. 成本型指标没正向化就进 TOPSIS，正负理想解方向反了，排名整体倒置。
3. 只报排名不报稳定性；权重动 10% 排名就变时，"最优方案是 X"这句话不成立，必须写成条件结论。

### F5 simulate physical process · 物理过程仿真

**适用规模阈值**

- ODE：非刚性用 `RK45`；参数跨 3 个数量级以上或出现化学反应/刚性项，换 `BDF` 或 `Radau`。
- 显式差分 PDE：扩散 `dt ≤ dx²/(2α)`，对流 `dt ≤ dx/|u|`（CFL 条件）。
- 网格无关性：网格加密一倍，解的变化 <1% 才可报结果；实测 51 点与 101 点（插值到同一网格、同一时刻）最大差 1.5e-5。
- 参数标定：待估参数个数 ≤ 数据点数/10，否则欠定。

**求解器与关键参数**

- `solve_ivp(f, [t0, t1], y0, method='RK45', rtol=1e-6, atol=1e-9, t_eval=...)`；默认 `rtol=1e-3` 只够画图，报误差时要收紧。
- 参数反演用 `least_squares(..., bounds=..., loss='soft_l1', f_scale=...)`，有粗差时用 `soft_l1`，别用默认 `linear`。
- 守恒量检查：质量/能量相对残差 <1e-6 才算数值可信；把这个检查写成断言，不要只看图。

```python
import numpy as np
def heat(nx):
    x = np.linspace(0, 1, nx); dx = x[1] - x[0]
    alpha, T = 0.01, 0.5
    dt = 0.4 * dx ** 2 / alpha
    n = int(np.ceil(T / dt)); dt = T / n      # 步数取整，保证跑到同一时刻 T
    u = np.sin(np.pi * x); u[0] = u[-1] = 0.0
    for _ in range(n):
        u[1:-1] += alpha * dt / dx ** 2 * (u[2:] - 2 * u[1:-1] + u[:-2])
    return u
coarse, fine = heat(51), heat(101)
fine_on_coarse = np.interp(np.linspace(0, 1, 51), np.linspace(0, 1, 101), fine)
print('max |coarse - fine| = %.2e' % np.abs(coarse - fine_on_coarse).max())
```

示例输出：`max |coarse - fine| = 1.54e-05`

**已知坑（3 条）**

1. 显式差分超过 CFL 后前几十步看起来正常，随后指数发散；先算 `dt` 上限再进循环，不要靠"跑出来不对再调"。
2. 单位不统一（mm 与 m、min 与 s）会让标定参数出现 10³ 倍偏差，且拟合残差依然好看；建模前统一到 SI。
3. 只报一套网格的结果，没有网格无关性与守恒量证据；评审会直接质疑数值解的可信度。

### F6 model spread or diffusion · 传播与扩散

**适用规模阈值**

- SIR/logistic：观测覆盖增长段 ≥30 个时间点，才有可能辨识 β 与 γ；只有累计确诊时要先转成日增。
- 早期指数段估 R0（对 log(I) 做线性回归），全段拟合会被后期饱和拉低。
- 网络/ABM：节点 >10^4 时先跑均值场近似，再决定是否值得上个体模型。
- 自由参数 ≤3 个；超过 3 个时必须有外部数据约束，否则参数不可辨识。

**求解器与关键参数**

- 初值 `I0` 固定为题面首日报告数，不要与 β、γ 一起自由估计。
- `least_squares(res, x0, bounds=([0.01, 0.01], [2, 1]))`；`res` 返回模型轨迹减观测。
- R0 = β/γ；区间用 `fit.jac` 的协方差 `(JᵀJ)⁻¹·s²` 或 bootstrap 给，不要只报点估计。
- 报告拟合残差的自相关：残差有结构说明模型形式不对，不是参数没调好。

```python
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
def sir(t, y, b, g, N):
    S, I, R = y
    return [-b * S * I / N, b * S * I / N - g * I, g * I]
N, tb, tg = 1e4, 0.45, 0.15
t = np.arange(60)
obs = solve_ivp(sir, [0, 59], [N - 10, 10, 0], args=(tb, tg, N), t_eval=t).y[1]
obs = obs * (1 + np.random.default_rng(0).normal(0, 0.05, 60))
res = lambda p: solve_ivp(sir, [0, 59], [N - 10, 10, 0],
                          args=(p[0], p[1], N), t_eval=t).y[1] - obs
fit = least_squares(res, [0.3, 0.2], bounds=([0.01, 0.01], [2, 1]))
print('R0 = %.3f (true %.3f)' % (fit.x[0] / fit.x[1], tb / tg))
```

示例输出：`R0 = 3.005 (true 3.000)`

**已知坑（3 条）**

1. 拟合累计曲线而不是日增曲线：残差高度自相关，参数看似完美但预测滞后一个流行期。
2. 把总人口 N 当自由参数：N 与 β 强相关，同时估计会得到"无限人口 + 极小 β"的解，R0 却仍落在合理区间。
3. 把一条确定性轨迹当预测：随机模型要给分位数带，确定性模型要给参数敏感性，否则结论无法支撑决策。

### F7 classify or extract patterns · 分类与模式提取

**适用规模阈值**

- 每类样本 ≥50 才有 5 折 CV 的意义；n <200 时优先 logistic / 随机森林，不要上深度学习。
- 特征数 > n/10 先降维或加 L2 正则，否则线性模型直接过拟合。
- 类别不平衡超过 5:1 时看 recall/F1/AUC，不看 accuracy。
- 时间序列数据不能用随机 K 折，必须用 `TimeSeriesSplit`。

**求解器与关键参数**

- `StratifiedKFold(n_splits=5, shuffle=True, random_state=0)`；所有预处理放进 `Pipeline`，在折内 fit。
- `LogisticRegression(max_iter=1000, class_weight='balanced')`：默认 `max_iter=100` 常不收敛。
- 必报混淆矩阵与每类 recall；只报平均 AUC 会掩盖少数类塌陷。
- 调参在训练折内再做一层 CV，测试折不参与任何选择。

```python
from sklearn.datasets import make_classification
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import recall_score
X, y = make_classification(300, 8, n_informative=4, weights=[0.8, 0.2], random_state=0)
clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000,
                                                        class_weight='balanced'))
cv = StratifiedKFold(5, shuffle=True, random_state=0)
auc = cross_val_score(clf, X, y, cv=cv, scoring='roc_auc')
pred = cross_val_predict(clf, X, y, cv=cv)
print('AUC %.3f +- %.3f | recall per class %s'
      % (auc.mean(), auc.std(), recall_score(y, pred, average=None).round(2)))
```

示例输出：`AUC 0.807 +- 0.101 | recall per class [0.8  0.71]`

**已知坑（3 条）**

1. 先全样本 `StandardScaler` 再 CV：测试折统计量泄漏进训练，小样本下 AUC 可虚高 0.1 以上；用 `Pipeline` 包住。
2. 不平衡数据下 accuracy 90% 可能只是"全猜多数类"；必须给出少数类 recall。
3. 用测试折反复调参等于把测试集变成训练集；选择偏差会让论文里的泛化结论失效。

### F8 analyze compositional or percentage-sum data · 成分数据

**适用规模阈值**

- 只要各分量之和为常数（1、100 或 10⁶ ppm），就必须做对数比变换；直接对百分比做相关/聚类会得到伪相关。
- n <20 时 CLR 的协方差估计不稳，改用 ILR 或加正则。
- 零值比例 >5% 时先报告零值比例，并做零值处理前后的敏感性对比。
- 维度 d 的 CLR 结果秩为 d-1，回归/PCA 前要去一维或加正则。

**求解器与关键参数**

- 零值替换：用检测限的 0.65 倍，或用最小非零值的一半；替换后必须记录替换规则。
- CLR：`clr(x) = log(x) - mean(log(x))`；Aitchison 距离等于 CLR 后的欧氏距离。
- 闭合检查：`|rowsum(x) - total| < 1e-6`；不闭合的数据先查录入错误，不要直接变换。
- 对照口径：同一任务同时跑原始百分比与 CLR 两版，报"结论是否改变"，不只报 CLR 版。

```python
import numpy as np
from scipy.spatial.distance import pdist
rng = np.random.default_rng(0)
X = rng.dirichlet([2, 2, 1, 1], size=100) * 100
Z = np.log(X) - np.log(X).mean(1, keepdims=True)
print('row sums', X.sum(1).round(6).min(), '| clr rowsum %.1e' % np.abs(Z.sum(1)).max(),
      '| corr(raw, clr) %.3f' % np.corrcoef(pdist(X), pdist(Z))[0, 1])
```

示例输出：`row sums 100.0 | clr rowsum 1.8e-15 | corr(raw, clr) 0.571`

**已知坑（3 条）**

1. 直接对百分比做欧氏距离聚类：闭合约束制造伪相关，实测原始距离与 CLR 距离的相关系数只有 0.571，聚类结果会明显不同。
2. `log(0)` 得到 `-inf` 会污染整行；先做零值替换，再变换。
3. CLR 之后仍用普通 PCA 且保留全部 d 个主成分：协方差矩阵奇异，最后几个主成分是数值噪声。

### F9 bearing-only or passive localization · 纯方位定位

**适用规模阈值**

- 2D 至少 3 条方位线（2 条只能求交点，无冗余、无误差评估）；3D 至少 4 条。
- 条件数 `cond(A) > 100` 或交会角 <15° 判几何不可用，位置误差会被放大一个数量级以上；实测一个正常构型 cond = 1.4。
- 误差带：至少 1000 次蒙特卡洛；角度标准差已知时直接按 σ 扰动。
- 源数未知时先做可辨识性判断（最少源数、镜面歧义），再解算。

**求解器与关键参数**

- 线性化：每条方位线满足 `(p - s) × u = 0`，展开为 `p_x·u_y - p_y·u_x = s_x·u_y - s_y·u_x`，最小二乘一次解出。
- 有粗差时用 `least_squares(..., loss='soft_l1', f_scale=σ)`，`f_scale` 取角度噪声对应的横向距离尺度。
- 残差必须是横向距离，不是角度差；角度残差会随距离放大，权重失真。
- 输出必须带 `cond(A)`（或 GDOP）与 90% 误差椭圆。

```python
import numpy as np
from scipy.optimize import least_squares
src = np.array([[0., 0.], [100., 0.], [0., 80.]])
true = np.array([40., 35.])
ang = np.arctan2(true[1] - src[:, 1], true[0] - src[:, 0])
u = np.c_[np.cos(ang), np.sin(ang)]
A = np.c_[u[:, 1], -u[:, 0]]
b = src[:, 0] * u[:, 1] - src[:, 1] * u[:, 0]
p, *_ = np.linalg.lstsq(A, b, rcond=None)
res = lambda q: (q - src)[:, 0] * u[:, 1] - (q - src)[:, 1] * u[:, 0]
rob = least_squares(res, [50., 30.], loss='soft_l1', f_scale=1.0)
print('lsq', p.round(3), '| cond %.1f' % np.linalg.cond(A), '| robust', rob.x.round(3))
```

示例输出：`lsq [40. 35.] | cond 1.4 | robust [40. 35.]`

**已知坑（3 条）**

1. 几何病态：方位线近似平行或全在同一侧时，最小二乘会给出一个"看起来合理"的远点；不报条件数就无法发现。
2. 把角度残差当线性残差：远距离目标的角度误差对应很大的横向误差，直接最小化角度会让近处观测主导。
3. 只扰动角度、不扰动传感器位置：平台位置误差往往主导总误差，误差带会被显著低估。

### F10 understand policy effect · 政策效应

**适用规模阈值**

- DID：政策前至少 4–6 期，且处理组与对照组的前趋势可检验；期数太少无法区分趋势差异。
- 合成控制：对照单元 ≥10（15 个以上更稳），政策前拟合 RMSE 应明显小于处理后效应。
- 只有一个处理单元时，必须做 placebo（in-space / in-time），否则无法排除"该单元本来就特殊"。
- 政策后样本 <5 期时，结论只能写成"短期相关"，不能写成因果效应。

**求解器与关键参数**

- 合成控制权重约束为单纯形：`w_j ≥ 0`、`Σw_j = 1`，用 SLSQP 求解。
- 必报三件事：pre-period RMSE、post-period gap、placebo 排名。实测示例 gap = 6.18、最大 placebo = 5.87、排名 1/13、pre RMSE = 0.31。
- DID 回归加个体与时间固定效应，标准误聚类到个体层面。
- 协变量只用政策前取值，政策后协变量是"坏控制"。

```python
import numpy as np
from scipy.optimize import minimize
rng = np.random.default_rng(0)
t = np.arange(40)
Y0 = 50 + rng.normal(0, 0.3, 12) * t[:, None] + rng.normal(0, 0.3, (40, 12))
y1 = 50 + 0.25 * t + rng.normal(0, 0.3, 40)
y1[30:] += 6.0                      # 第 31 期起的政策效应
pre = slice(0, 30)
def fitw(Y, y):
    k = Y.shape[1]
    return minimize(lambda v: ((Y[pre] @ v - y[pre]) ** 2).sum(),
                    np.ones(k) / k, bounds=[(0, 1)] * k,
                    constraints={'type': 'eq',
                                 'fun': lambda v: v.sum() - 1}).x
w = fitw(Y0, y1)
gap = (y1[30:] - Y0[30:] @ w).mean()
placebo = []
for j in range(12):                 # 留一法：被检验单元不进 donor pool
    Yj = np.delete(Y0, j, axis=1)
    placebo.append(abs((Y0[30:, j] - Yj[30:] @ fitw(Yj, Y0[:, j])).mean()))
print('post gap %.2f | max placebo %.2f | rank %d/13 | pre RMSE %.2f'
      % (gap, max(placebo), sum(g >= gap for g in placebo) + 1,
         np.sqrt(((Y0[pre] @ w - y1[pre]) ** 2).mean())))
```

示例输出：`post gap 6.18 | max placebo 5.87 | rank 1/13 | pre RMSE 0.31`

**已知坑（3 条）**

1. 平行趋势没检验就上 DID：处理组本来就在上升，估计量把趋势差当成政策效应。
2. 用政策后的协变量做匹配或加权：这些变量已被政策影响，属于后处理偏差。
3. 安慰剂必须留一法：把被检验单元留在 donor pool 里，权重会给自己 1，拟合恒为 0，安慰剂分布全 0、排名永远第一。

### F11 handle uncertainty · 不确定性

**适用规模阈值**

- 均值 95% 置信区间：n ≥10^4；P99/VaR 等尾部指标需要 10^5–10^6 次，或改用重要性采样。
- 参数维度 ≤10 用拉丁超立方；>10 用 Sobol 序列做方差分解。
- 单次模型运行超过 1 s 时，先做代理模型（多项式/高斯过程）再做蒙特卡洛，否则跑不完。
- 输入相关性必须显式建模（copula 或分层），不能默认独立。

**求解器与关键参数**

- `np.random.default_rng(seed)` 固定种子；`qmc.LatinHypercube(d, seed=0).random(n)` 做分层采样。
- 收敛判据：批量均值的标准误 / 均值 <1%；实测示例 se = 0.221，中位数 65.01，约 0.34%。
- 报 P5/P50/P95 与均值标准误，不只报均值。
- 抽样代码与模型代码分开，模型函数保持纯函数，便于换采样器复跑。

```python
import numpy as np
from scipy.stats import qmc
u = qmc.LatinHypercube(d=3, seed=0).random(2000)
x = np.array([10, 5, 2]) + u * np.array([4, 2, 1])
y = x[:, 0] * x[:, 1] - x[:, 2] ** 2
print('P5/P50/P95', np.percentile(y, [5, 50, 95]).round(2),
      '| MC se %.3f' % (y.std(ddof=1) / np.sqrt(len(y))))
```

示例输出：`P5/P50/P95 [50.1  65.01 82.76] | MC se 0.221`

**已知坑（3 条）**

1. n = 1000 就报 P99：尾部只有约 10 个样本，换一个种子结论就变。
2. 默认输入独立却不声明；实际正相关时，区间会被系统性低估。
3. 只报区间不报"决策是否翻转"：区间跨过阈值时，结论必须改写成条件结论，而不是继续报点估计。

### F12 manage strategic behavior · 博弈与策略行为

**适用规模阈值**

- 参与者 2–3 类、策略 2–3 个：可解析求解并配复制动态；策略数 >5 时收益矩阵参数比数据多，必须外部标定。
- 演化过程要跑到收敛（轨迹导数为 0），不能只看固定时长。
- 多均衡时必须报均衡选择准则（ESS、风险占优或初值吸引域）。
- 行为参数 ≤3 个自由参数。

**求解器与关键参数**

- 复制动态：`dx_i/dt = x_i(π_i - π̄)`；用 `solve_ivp(..., rtol=1e-8)` 保证轨迹光滑。
- 稳定性判据：在均衡点求 Jacobian 特征值，实部全负才稳定；只有"轨迹看起来收敛"不够。
- 收益矩阵先做量纲统一（全部换成同一货币/效用单位），否则均衡对尺度敏感。
- 必须给相图或多初值轨迹，单条轨迹不能说明均衡的吸引域。

```python
import numpy as np
from scipy.integrate import solve_ivp
A = np.array([[3., 0.], [5., 1.]])
def replicator(t, x):
    p1 = x[0] * A[0, 0] + (1 - x[0]) * A[0, 1]
    p2 = x[0] * A[1, 0] + (1 - x[0]) * A[1, 1]
    return [x[0] * (p1 - (x[0] * p1 + (1 - x[0]) * p2))]
sol = solve_ivp(replicator, [0, 50], [0.2], rtol=1e-8)
print('x(0)=0.2 -> x(50)=%.4f' % sol.y[0, -1])
```

示例输出：`x(0)=0.2 -> x(50)=0.0000`

**已知坑（3 条）**

1. 把一次博弈的纳什均衡直接当"人群最终状态"：演化动力学可能收敛到另一个均衡，或根本不收敛。
2. 收益矩阵量纲不一致（成本与收益混单位），换个单位均衡就变。
3. 只报一条初值轨迹：初值稍变结论就翻，必须报多初值或相图。

## Combinations That Often Work

- Forecasting + optimization: predict demand, then optimize allocation; validate decision regret under forecast errors.
- Evaluation + clustering: cluster objects first, then apply different evaluation weights per group.
- Mechanism + machine learning: use physical or domain equations to create features, then fit a predictive model.
- Network + intervention: rank nodes/edges, then simulate removal, protection, or subsidy policies.
- Simulation + robust decision: simulate scenarios, then choose policy that is stable under worst plausible cases.

## CUMCM A/B/C Method Priors

Use these only as priors. The actual statement overrides them.

- A-type problems often reward mechanism modeling, engineering physics, simulation, dimensional analysis, and parameter sensitivity. A strong A route usually needs equations, physical sanity checks, and clear plots.
- B-type problems often reward optimization, operations research, network analysis, scheduling, resource allocation, or policy simulation. A strong B route usually needs decision variables, constraints, objective functions, and solver comparisons.
- C-type problems often reward data processing, evaluation, prediction, clustering, statistical modeling, and indicator systems. A strong C route usually needs data cleaning, feature construction, baseline comparison, and rank/prediction stability.

Do not choose C only because it looks "data-driven." Do not avoid A only because it has formulas. Choose the problem with the best executable route.

## Common Misuses

- AHP when no expert comparison matrix can be justified.
- Entropy weight when indicator variance is a data artifact rather than importance.
- Neural network on tiny data.
- Metaheuristic without a baseline or convergence evidence.
- Fuzzy evaluation used to hide unclear indicators.
- Regression treated as causal proof.
- Raw Euclidean clustering or PCA on percentage-sum composition data without checking closed-sum effects.
- Bearing-only localization without identifiability, mirror-symmetry, or error-propagation checks.
- Stacking three advanced methods when one baseline plus one justified upgrade would be clearer.
- Optimizing an objective that is not connected to the deliverable asked by the problem.

## Paper-Level Method Narrative

Write method choices as:

1. "The problem requires X, so the baseline is Y."
2. "The baseline fails under Z, so the upgraded model adds W."
3. "The solver is feasible because S."
4. "We validate the upgrade by V."
5. "The final result changes decision D, not just metric M."
