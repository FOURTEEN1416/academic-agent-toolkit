# physical.md — 物理/几何类自检（碰撞检测/动力学/ODE/SAT/空间布局）

> 目标：物理仿真"能跑"不等于"物理正确"。重点：量纲、守恒、收敛、几何判定的边界情形。
> 配套手册：`skills/_utils/error_prevention.md` 二章（微分方程/动力学/物理仿真类）+ 六章（几何/空间优化/布局类）。

## 1. 量纲与单位一致性

- [ ] 所有物理量单位声明（m/s vs km/h、kg vs g、rad vs deg），模型内部统一单位制；
- [ ] 常数取值核对：重力加速度、摩擦系数、密度等查表值与题面给定值一致（题面给的值优先于通用值）；
- [ ] 三角函数角度制/弧度制核对（np.sin 默认弧度——题面给角度必须换算）。

## 2. 动力学/ODE 正确性

- [ ] 方程组与建模报告一致：逐项核对状态变量阶数（n 个状态变量 n 个方程）、正负号（阻力/重力方向）；
- [ ] 步长收敛性验证：步长减半，关键结果（末状态/峰值/周期）变化 < 设定容差；不收敛时禁止用大步长结果写稿；
- [ ] 刚性问题识别：使用刚性求解器（如 LSODA/Radau）或声明步长自适应；能量不守恒的快速漂移 = 步长或方程错误的信号；
- [ ] 守恒律检查（如适用）：封闭系统总能量/总动量漂移量 << 系统特征量（漂移率写进自检报告）。

## 3. 碰撞/几何判定

- [ ] 判定几何与题面一致：外接圆近似 vs 真实形状、2D 简化 vs 3D 已声明；
- [ ] 边界情形：恰好相切（distance == sum_radii）、共线、重叠初始态——程序行为已定义且有测试；
- [ ] 误检率/漏检率抽检：随机抽 N 对构型用独立方法（解析解或高精度数值）交叉验证，不一致率写进自检报告；
- [ ] SAT/分离轴：投影轴完备性（凸多边形所有边法向）、接触法向方向一致性。

## 4. 数值安全

- [ ] 除零保护：速度接近零的比值项、归一化的零向量；arccos 定义域夹取（clip 到 [-1,1]）；
- [ ] 事件检测：碰撞时刻用事件定位（solve_ivp events/二分细化），不靠步长粒度硬凑；
- [ ] 随机仿真（蒙特卡洛）设 seed 并写 RESULTS.md；样本量与结论精度匹配（给出标准误）。

## 5. 凭证

- [ ] validate_capability() 通过（如：能量漂移率 < 阈值、收敛性断言、碰撞抽检一致率达标）；
- [ ] RESULTS.md 有 AUDIT_OK 凭证（按本题约束口径）。

## 输出

`_tmp/problem_N_check.md` 逐条 ✅/⚠️/❌；❌ 修复后重跑本问全部脚本。


---

## modex-3 增补块（2026-09-10 同源对照吸收）

> 来源：Modex v3 技能包 comp-code/references/checks/physical.md（溯源见 skills/shared-scripts/UPSTREAM.md）。
> 以下为本仓原版未覆盖的检查条目与可执行代码模板；条目与本仓上方重叠时，以本仓上方（含 validate_capability / AUDIT_OK 契约衔接）为准。

## 红旗信号

| 现象 | 可能原因 |
|------|---------|
| 状态变量单调增长不收敛 | 开环积分漂移 / 缺反馈 |
| ODE 求解结果发散 | 步长太大 / 缺阻尼 / 模型不稳定 |
| 碰撞检测从不触发 | SAT 写错 / 用了中心距代替轮廓距 |
| 间隙值出现负数 | 接触约束未加 / 已经穿模 |
| 能量/动量不守恒（孤立系统） | 数值积分误差累积 / 模型缺项 |

## 几何参数引用规则（最高优先级）

代码中涉及碰撞检测、约束校验、目标函数计算时：

**必须使用 MODELING_REPORT.md 中定义的完整物理参数**（如板凳全长220cm、矩形宽30cm、车身长4.5m）, 
**禁止直接复用上游步骤为其他目的计算的中间量**（如孔中心距165cm、把手坐标间距、质心偏移量）作为物理实体的几何代理。

**典型错误示例**：
- 板凳碰撞检测用"孔中心距165cm"代替"板凳全长220cm" → 错误（少算了两端各27.5cm）
- 矩形放置约束用"中心坐标差"代替"边缘到边缘距离" → 错误（忽略了物体宽度）
- 车辆避障用"质心距离"代替"车身外轮廓最近点距离" → 错误（可能已经碰撞）

**正确做法**：

```python
# ⛔ 物理参数定义（来源：MODELING_REPORT.md 第X节）
BENCH_TOTAL_LENGTH = 2.20  # 板凳全长 220cm（题目原文）
BENCH_WIDTH = 0.30          # 板凳宽度 30cm（题目原文）

def check_collision(bench_a, bench_b):
    """检测两个板凳是否碰撞。

    物理参数来源：MODELING_REPORT.md 符号说明表
    - 板凳全长: BENCH_TOTAL_LENGTH = 2.20m
    - 板凳宽度: BENCH_WIDTH = 0.30m
    使用完整外轮廓（矩形四角）判断, 非中心点距离。
    """
    # 使用完整矩形碰撞检测（SAT 分离轴定理）
    ...
```

## SAT 碰撞检测自检

如果用了 SAT（分离轴定理）：

```python
# 验证 SAT 实现是否正确
def sat_collide(rect_a, rect_b, *, touching_is_collision=True, atol=0.0):
    """凸四边形按边界顺序给点；接触定义与绝对长度容差必须来自本题。"""
    import math
    if not math.isfinite(atol) or atol < 0:
        raise ValueError("invalid collision tolerance")
    axes = []
    for poly in (rect_a, rect_b):
        if len(poly) != 4 or any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in poly):
            raise ValueError("expected four finite 2D vertices")
        turns = []
        for i in range(len(poly)):
            edge = (poly[(i+1)%len(poly)][0]-poly[i][0], poly[(i+1)%len(poly)][1]-poly[i][1])
            nxt = (poly[(i+2)%4][0]-poly[(i+1)%4][0], poly[(i+2)%4][1]-poly[(i+1)%4][1])
            turns.append(edge[0]*nxt[1] - edge[1]*nxt[0])
            normal = (-edge[1], edge[0])  # 法向量
            length = math.hypot(*normal)
            if length == 0:
                raise ValueError("zero length edge")
            axes.append((normal[0]/length, normal[1]/length))
        if not (all(x > 0 for x in turns) or all(x < 0 for x in turns)):
            raise ValueError("unordered, non-convex or degenerate polygon")

    for axis in axes:
        proj_a = [p[0]*axis[0] + p[1]*axis[1] for p in rect_a]
        proj_b = [p[0]*axis[0] + p[1]*axis[1] for p in rect_b]
        overlap = min(max(proj_a), max(proj_b)) - max(min(proj_a), min(proj_b))
        separated = overlap < -atol if touching_is_collision else overlap <= atol
        if separated:
            return False  # 找到分离轴, 不碰撞
    return True  # 所有轴都重叠, 碰撞
```

⛔ **SAT 自检 unit test**：

```python
# 首次实现/修改碰撞器后运行；不为每个算例重复读规则。
# 1) 不重叠
assert sat_collide(
    [(0,0),(1,0),(1,1),(0,1)],
    [(2,0),(3,0),(3,1),(2,1)]
) == False
# 2) 部分重叠
assert sat_collide(
    [(0,0),(2,0),(2,1),(0,1)],
    [(1,0.5),(3,0.5),(3,1.5),(1,1.5)]
) == True
# 3) 旋转后恰好接触：(1,1) 在双方边界上，默认算碰撞
assert sat_collide(
    [(0,0),(1,0),(1,1),(0,1)],
    [(1.5,0.5),(2.5,1.5),(1.5,2.5),(0.5,1.5)]  # 45° 菱形
) == True
assert sat_collide(
    [(0,0),(1,0),(1,1),(0,1)],
    [(1.5,0.5),(2.5,1.5),(1.5,2.5),(0.5,1.5)],
    touching_is_collision=False,
) == False
print("✅ SAT 自检通过")
```

## ODE / 动力学

### 数值积分参数

采用建模报告已经论证的精度设置，例如 `rtol=1e-8`；绝对容差按各状态的单位与尺度设定，
不能从例子统一复制 `atol=1e-10`。更换积分器或步长需同精度对比证据，不能只为快而降精度。

### 漂移检测

```python
# 长时间积分必做 — 检查是否漂移
import numpy as np
def check_drift(t, state, expected_bound):
    """state 形状为 (时间点,) 或 (时间点, 状态数)，solve_ivp.y 先转置。"""
    t, state, bound = np.asarray(t), np.asarray(state), np.asarray(expected_bound)
    if t.ndim != 1 or state.ndim not in (1, 2) or len(state) != len(t) or not len(t):
        raise ValueError("invalid time/state dimensions")
    if not all(np.all(np.isfinite(x)) for x in (t, state, bound)) or np.any(bound < 0):
        raise ValueError("nonfinite state/time or invalid bound")
    violation = np.abs(state) > bound
    if violation.shape != state.shape:
        raise ValueError("bound must broadcast to state shape")
    bad_time = violation if state.ndim == 1 else violation.any(axis=1)
    if np.any(bad_time):
        i = np.flatnonzero(bad_time)[0]
        print(f"⚠ 状态在 t={t[i]:.3f}s 时超出预期边界 {expected_bound}")
        return False
    return True
```

### 守恒量验证

只对模型确实守恒的系统检查对应量；受迫/耗散系统核能量收支而非强制能量不变。
容差来自离散误差与物理尺度，不统一用 1%。检查完整轨迹，不能只比首尾而漏掉中间漂移：

```python
def check_conserved_energy(energies, *, atol, rtol, reference_scale):
    import numpy as np
    e = np.asarray(energies, dtype=float)
    settings = np.asarray([atol, rtol, reference_scale], dtype=float)
    if e.ndim != 1 or not len(e) or not np.isfinite(e).all():
        raise ValueError("invalid energy series")
    if not np.isfinite(settings).all() or (settings < 0).any():
        raise ValueError("invalid energy tolerances")
    error = float(np.max(np.abs(e - e[0])))
    limit = atol + rtol * max(abs(float(e[0])), reference_scale)
    return error <= limit, error, limit  # E0=0 时也不会除零
```

## 接触约束 / 饱和限幅

只有本题确有接触/饱和条件时才加入；通过事件定位、约束积分或有依据的接触模型处理。
不要通用地裁剪位移、把速度归零来“修复”穿透，这可能掩盖错误并破坏能量与动量。
冲击前后变化必须符合本题恢复系数/耗散模型；自由运动 ODE 不凭空加接触条件。

## 必产数据

下例是字段示意，只记录本题实际使用与实际计算的项；没有接触或能量模型时不填假数。

```json
{
  "model": "ODE / RK4 / solve_ivp",
  "rtol": 1e-8,
  "atol": 1e-10,
  "duration_s": 100,
  "drift_pct": 0.5,
  "energy_conservation_pct": 0.3,
  "constraints_active": ["gap_lower_bound", "velocity_saturation"],
  "max_gap": 0.058,
  "max_velocity": 3.2
}
```
