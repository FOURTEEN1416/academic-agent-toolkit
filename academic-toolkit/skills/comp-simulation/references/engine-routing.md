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

### 本机实装状态（2026-10-16 实测）

| 引擎 | 状态 | 备注 |
|---|---|---|
| **mesa 3.5.1** | ✅ **已装** | 装于 `C:\Program Files\Python312`（本仓门禁基线解释器）；实测**只新增 mesa 一个包、零升级**科学栈；ABM 骨架已按 3.5.1 实跑校准 |
| numpy / pandas / scipy / matplotlib / networkx / altair / tqdm | ✅ 已装 | Mesa 运行时链齐备（**networkx 必须**，否则 `import mesa` 直接报错） |
| torch 2.8.0+cu128 / scikit-learn / statsmodels / sympy / notebook + ipykernel / plotly / seaborn | ✅ 已装 | C 赛道基线 + Jupyter 推演演示链路现成 |
| simpy / salabim / pysd / pymoo / pymc / SALib / pyDOE3 / mesa-geo | ⬜ 未装 | 开赛后按选定赛道补；命令见上表「一行安装」 |
| ⚠️ Python 版本门槛 | — | `mesa`/`pymc` 均要求 **≥3.12**；仓内 `.venv311`(3.11) **装不上** |
| ⚠️ 安全 | — | **pin `mesa==3.5.1`**：CVE-2026-29075 影响 3.5.0（CI 供应链问题，非运行时） |

## 二、最小可用骨架（照抄可跑）

### ABM（Mesa · 骨架已按 3.5.1 实测校准）

```python
# ⚠️ 2026-10-16 在本机 mesa 3.5.1 实跑校准（不是抄文档）：
#   · Model.__init__ 签名 = (self, *args, seed=None, rng=None, scenario=None, **kwargs)
#     → **推荐 rng=**（传 np.random.default_rng(seed)）；`seed=` 已 deprecated
#       （传 seed= 会发 FutureWarning: "The use of the `seed` keyword argument is deprecated, use `rng` instead"）。
#   · mesa.AgentSet 顶层**不可用**（hasattr(mesa,'AgentSet')=False）；实例上 model.agents 是 AgentSet 派生类，有 do/shuffle_do。
#   · 顶层 mesa.time 提供 Event / EventList / Schedule / Priority / EventGenerator（事件调度 API）。
#   · Model.run_for / run_until 可用；mesa.DataCollector 可用；mesa.space 提供 ContinuousSpace 等。
import numpy as np
import mesa

class Actor(mesa.Agent):
    def __init__(self, model, pos, rule="greedy"):
        super().__init__(model); self.pos = pos; self.rule = rule
    def step(self):
        ...  # 决策 + 交互 + 状态转移（每条规则必须可溯源）

class World(mesa.Model):
    def __init__(self, n=40, seed=1):
        super().__init__(rng=np.random.default_rng(seed))   # ← 用 rng，不用 seed
        for _ in range(n):
            Actor(self, int(self.random.integers(0, 10)))
        self.log: list[float] = []
    def step(self):
        self.agents.do("step")          # AgentSet API（打乱顺序用 shuffle_do）
        self.log.append(float(self.random.random()))   # 记录观测量

# 自检两件事（写完全局必跑）：
#   1) 同种子复现：两次 World(seed=1) 跑同样步数，log 必须逐位一致
#   2) 零告警：`python -W error::FutureWarning` 下不得报错（能抓出 deprecated 形态）
```

> **随机源纪律**：`rng=np.random.default_rng(seed)` 是唯一推荐形式；`self.random`（实例属性）由 mesa 从该 rng 派生，
> 可用但**不要**另建全局 `np.random`。种子表写进 `SIM_MANIFEST.json.randomness.seeds`。

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
