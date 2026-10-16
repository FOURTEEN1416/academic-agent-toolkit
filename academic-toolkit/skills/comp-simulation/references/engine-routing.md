# 引擎路由与安装（各赛道首选库）

> **纪律**：本表只给"选哪个 + 最小可用骨架 + 探测方式"。**具体 API 以本机实测版本为准**——
> 先跑 `python skills/comp-simulation/scripts/sim_env_probe.py` 取实际版本号，再按该版本写代码。
> **缺席引擎如实记 `unavailable`，不阻断**：方法论层纯标准库可执行。

## 一、首选引擎速查

| 方向 | 包名 | 一行安装 | 定位 |
|---|---|---|---|
| 多智能体（A） | `mesa` | `pip install mesa` | Python 原生 ABM 框架（Apache-2.0） |
| 空间 ABM（A/城市） | `mesa-geo` | `pip install mesa-geo` | Mesa 的 GIS 扩展 |
| 离散事件（B/C） | `simpy` | `pip install simpy` | 描述性 DES，纯 Python（BSD/MIT 系） |
| 离散事件 + 动画（B） | `salabim` | `pip install salabim` | 自带 2D/3D 动画输出，便于做演示视频 |
| 系统动力学（B/C） | `pysd` | `pip install pysd` | 读 Vensim/SD 方程（MIT） |
| 连续系统 | `scipy` | 已随科学栈 | `scipy.integrate.solve_ivp` |
| 多目标优化（C） | `pymoo` | `pip install pymoo` | NSGA-II/III、MOEA/D、约束处理 |
| 强化学习（C） | `stable-baselines3` | `pip install stable-baselines3` | PPO/SAC/DQN 等（MIT） |
| 贝叶斯校准（C） | `pymc` | `pip install pymc` | 参数后验、不确定性量化 |
| 敏感性分析 | `SALib` | `pip install SALib` | Sobol / Morris |
| 实验设计 | `pyDOE3` | `pip install pyDOE3` | 因子/部分因子/拉丁超立方 |
| 机器学习基线 | `scikit-learn` | `pip install scikit-learn` | 回归/分类/聚类/代理模型 |
| 表格与统计 | `pandas` `statsmodels` `numpy` | 科学栈 | 账本与统计检验 |

> **不自造第四条接入通道**：引入新技能走 `vendor/forks/<repo>` + `UPSTREAM.md` + `check_provenance.py`；
> 只借库不引技能则直接 `pip install` 并在交付中声明版本。

## 二、最小可用骨架（照抄可跑）

### ABM（Mesa · 概念骨架）

```python
# 版本敏感：Mesa 3.x 用 Agent/Model 泛型与 model.agents；旧版 API 不同。
# 先跑 sim_env_probe.py 看实装版本，再按官方 examples 对齐。
import mesa

class Actor(mesa.Agent):
    def __init__(self, model, pos, rule="greedy"):
        super().__init__(model); self.pos = pos; self.rule = rule
    def step(self):
        ...  # 决策 + 交互 + 状态转移（规则必须可溯源）

class World(mesa.Model):
    def __init__(self, n=40, seed=1):
        super().__init__(seed=seed)          # 3.x 用 seed 参数管理随机源
        for _ in range(n):
            Actor(self, self.random.choice(range(10)))
    def step(self):
        self.agents.do("step")               # 3.x 的 AgentSet API
        ...  # 记录观测量
```

### DES（SimPy）

```python
import simpy   # SimPy 4.x

def job(env, res, log, jid, dur):
    t0 = env.now
    with res.request() as req:
        yield req
        t1 = env.now
        yield env.timeout(dur)
    log.append({"job": jid, "wait": t1 - t0, "t0": t0, "t1": env.now})

def run(seed, n_jobs=100):
    import random
    env, rng = simpy.Environment(), random.Random(seed)
    res, log = simpy.Resource(env, capacity=3), []
    def gen():
        for i in range(n_jobs):
            yield env.timeout(rng.expovariate(1/2))
            env.process(job(env, res, log, i, rng.expovariate(1/3)))
    env.process(gen()); env.run()
    return log
```

### 连续系统

```python
from scipy.integrate import solve_ivp
import numpy as np
def f(t, y): return [-0.1*y[0] + 0.05*y[1], 0.1*y[0] - 0.05*y[1]]   # 状态方程
sol = solve_ivp(f, (0, 100), [100, 10], t_eval=np.linspace(0, 100, 201), rtol=1e-8)
```

### 蒙特卡洛 + 置信区间

```python
import numpy as np
def est(f, n, seed=1, params=None):
    rng = np.random.default_rng(seed)
    vals = np.array([f(rng, **(params or {})) for _ in range(n)])
    m, s = vals.mean(), vals.std(ddof=1)
    half = 1.96 * s / np.sqrt(n)          # 大样本 95% CI；小样本改用 t 分位
    return m, half, vals
```

### 多目标优化（pymoo · 概念骨架）

```python
# 版本敏感：以本机实装 pymoo 的 problem/algorithm 命名空间为准。
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
class SimOpt(Problem):
    def __init__(self): super().__init__(n_var=4, n_obj=2, n_ieq_constr=1, xl=0, xu=1)
    def _evaluate(self, X, out, *a, **k):
        sim = [run_once(x, seed=int(s)) for x, s in zip(X, range(len(X)))]
        out["F"] = [[s["cost"], -s["service"]] for s in sim]
        out["G"] = [[s["risk"] - 0.1] for s in sim]
```

## 三、缺口登记（本仓实测）

| 缺口 | 影响 | 处置 |
|---|---|---|
| **三维孪生渲染**（CesiumJS / PyVista / three.js / Unity） | B 赛道"虚实联动"呈现 | 未建资产；选 B 前先确认可行，否则降级"二维态势 + 数据孪生"并声明 |
| AnyMath 商业软件 | 赛事设有 AnyMath 专项奖金 | 组委会不承担授权；不可用则放弃该奖金项，不影响主体评分 |
| 视频录制/剪辑链 | 仿真视频为必要交付件 | 见 `deliverables.md`（ffmpeg + 宿主录屏 / CDP screencast） |
| 商业仿真软件（AnyLogic / Vensim / Arena） | 图形化建模 | 非必需；Python 方案可覆盖 |

## 四、探测脚本

```bash
python skills/comp-simulation/scripts/sim_env_probe.py            # 全量探测
python skills/comp-simulation/scripts/sim_env_probe.py --json     # 机读输出
```

输出：每库 `installed / version / import_error`；**不联网、不安装**。
