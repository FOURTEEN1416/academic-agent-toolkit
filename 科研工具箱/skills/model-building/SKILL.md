# Model Building Skill

## 用途
根据子问题，选模型、写代码、跑出结果、验证合理性。

## 触发时机
- 数据清洗完毕之后
- 距离比赛结束 60-72h（建模核心时段）

## 输入
1. 清洗后数据（`work/data/clean/*.csv`）
2. 题型 + 推荐模型（`work/analysis.md`）
3. 3 个子问题（Q1/Q2/Q3）

## 输出
1. **模型代码**（`work/models/*.py`，每子问题一文件）
2. **结果数据**（`work/results/*.csv`）
3. **模型说明**（`work/models/README.md`）

## 强制建模流程
```
Q1：基线模型（保底能跑通）→ 改进模型 1 → 改进模型 2 → 对比 → 选最优
Q2：同上
Q3：综合 / 灵敏度分析
```

## 6 类题型推荐模型
| 题型 | 基线模型 | 改进 1 | 改进 2 |
|------|----------|--------|--------|
| 优化 | LP/IP | 启发式（GA/SA） | 强化学习 |
| 预测 | 线性回归 / ARIMA | XGBoost / LSTM | 集成学习 |
| 评价 | AHP / TOPSIS | 熵权法 + 灰色关联 | 主成分分析 |
| 统计 | 多元回归 | Lasso / Ridge | 贝叶斯回归 |
| 机理 | Euler 数值解 | Runge-Kutta | 有限元 |
| 图论 | Dijkstra / Floyd | 启发式（ACO/PSO） | 复杂网络 |

## 核心原则
1. **基线优先**：先跑通最简单的，再优化（避免 60h 还跑不出数）
2. **可解释性 > 准确率**：评委看的是"为什么这么做"
3. **可复现性**：设 `random_state=42`，记录所有超参数
4. **评价指标 ≥ 2 个**：RMSE + MAE、R² + MAPE、AUC + F1
5. **灵敏度分析**：关键参数 ±20% 验证模型稳定性

## 常用代码片段
```python
# 时间序列预测（ARIMA）
from statsmodels.tsa.arima.model import ARIMA
model = ARIMA(train, order=(p, d, q))
fit = model.fit()
pred = fit.forecast(steps=len(test))

# 机器学习（XGBoost）
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score
model = xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42)
model.fit(X_train, y_train)
pred = model.predict(X_test)
print(f'RMSE: {mean_squared_error(y_test, pred, squared=False):.4f}')
print(f'R²: {r2_score(y_test, pred):.4f}')

# 优化（pulp）
import pulp
prob = pulp.LpProblem('xxx', pulp.LpMinimize)
x = pulp.LpVariable('x', lowBound=0)
prob += x
prob += x >= 10
prob.solve()

# 图论（networkx）
import networkx as nx
G = nx.Graph()
G.add_edge(1, 2, weight=3)
path = nx.shortest_path(G, 1, 2, weight='weight')
```

## 灵敏度分析模板
```python
# 参数 ±20% 验证
for param in ['learning_rate', 'n_estimators', 'max_depth']:
    for ratio in [0.8, 0.9, 1.0, 1.1, 1.2]:
        value = baseline[param] * ratio
        # 训练 + 评价
        # 记录结果
```

## 必填交付物
- `work/models/q1_model.py` / `q2_model.py` / `q3_model.py`
- `work/results/q1_results.csv` / `q2_results.csv` / `q3_results.csv`
- `work/models/README.md`（每个模型的：原理 + 公式 + 超参数 + 评价指标 + 灵敏度分析）

## 后续 Skill
- `model-innovation`：找创新点
- `visualization`：把结果画成图
- `paper-writing`：把模型说明写进论文
