# 编码阶段防错手册（按题型索引）

## 使用方法

编码开始前，读取 MODELING_REPORT.md 末尾的题型标注，然后查阅对应章节。
每个子问题代码写完后，对照"必须验证"条目逐项检查。

---

## 一、优化类

### 必须验证
- [ ] `minimize` vs `maximize` 方向是否与建模报告一致（scipy 只有 minimize，最大化要取负）
- [ ] 所有约束是否都加入了求解器（逐条对照 MODELING_REPORT.md 的约束列表）
- [ ] 不等式约束方向是否正确（scipy: `ineq` 要求 f(x)≥0，`eq` 要求 f(x)=0）
- [ ] 决策变量 bounds 是否设置（特别是非负约束 x≥0）
- [ ] 整数变量是否做了取整？取整后是否仍然可行？
- [ ] 多起点验证：换 3-5 组随机初始点，结果是否一致？（不一致说明陷入局部最优）
- [ ] 求解器是否报告收敛？（检查 result.success / result.message）
- [ ] 最优解是否满足所有约束？（代入约束函数验证，不能只信求解器）

### 常见 Bug
```python
# ❌ 错误：忘记取负号
result = minimize(profit_function, x0)  # 应该是 minimize(lambda x: -profit_function(x), x0)

# ❌ 错误：约束方向写反
constraints = {'type': 'ineq', 'fun': lambda x: capacity - x[0]}  # 这是 capacity >= x[0]
# 如果要 x[0] >= min_val，应该写 lambda x: x[0] - min_val

# ❌ 错误：没设 bounds 导致出现负值
result = minimize(f, x0)  # 应该加 bounds=[(0, None)] * n

# ❌ 错误：整数松弛后不取整
x_opt = result.x  # x_opt = [2.7, 1.3] → 必须取整并验证可行性
```

### ⛔ 算法有效性验证（通用，必须通过）

```python
# ===== 建模与优化有效性检查（优化类必做）=====

# 1. 资源单调性检查
# 后续问题拥有更多决策资源时，结果必须严格更优
for i in range(1, len(problem_results)):
    if has_more_resources(i, i-1) and problem_results[i] <= problem_results[i-1]:
        print(f"⛔ 资源单调性违反: P{i+1}={problem_results[i]} ≤ P{i}={problem_results[i-1]}")
        print("  → 更多资源但结果未改善，建模降维失败，必须重新分解")

# 2. 解析基准下界对标
# 先用几何/贪心/物理推导得到一个可行解作为下界
baseline = compute_analytical_baseline(...)  # 几何解析/贪心/均匀分布
if optimized_result <= baseline:
    print(f"⛔ 优化解 {optimized_result} ≤ 解析基准 {baseline}")
    print("  → 算法失败，检查编码/约束/罚函数/初始化")

# 3. 搜索空间健康度（维度≥6时必做）
if n_dimensions >= 6:
    sample_points = generate_random_points(n=100, bounds=bounds)
    valid_ratio = sum(1 for x in sample_points if fitness(x) > trivial_fitness) / 100
    if valid_ratio < 0.3:
        print(f"⛔ 搜索空间过稀疏: 有效解比例 {valid_ratio:.0%} < 30%")
        print("  → 必须降维/分层/启发式播种后再优化")

# 4. 维度分层检查（维度≥10时必做）
if n_dimensions >= 10:
    print(f"⛔ 决策变量 {n_dimensions} 维 ≥ 10，禁止单层黑箱优化")
    print("  → 必须分层分解（每层≤6维），在建模报告中给出分层依据")

# 5. 离散取整可行性验证
if has_integer_variables:
    x_rounded = np.round(x_continuous)  # 或 np.floor/np.ceil
    for constraint_fn in all_constraints:
        if constraint_fn(x_rounded) < 0:
            print(f"⛔ 取整后约束违反: {constraint_fn.__name__}")
            print("  → 必须用修复启发式（贪心减少/邻域搜索），禁止使用不可行解")

# 6. 多目标归一化验证
if is_multi_objective:
    # 检查各目标的量级
    obj_magnitudes = [abs(obj_i(x)) for obj_i in objectives]
    if max(obj_magnitudes) / min(obj_magnitudes) > 100:
        print(f"⛔ 目标函数量级差异 > 100倍: {obj_magnitudes}")
        print("  → 必须先归一化到[0,1]再加权，否则小量级目标被淹没")

# 7. 步长收敛性验证（时间/空间离散化）
if uses_discretization:
    result_dt = solve(dt=dt)
    result_dt_half = solve(dt=dt/2)
    relative_change = abs(result_dt - result_dt_half) / abs(result_dt_half)
    if relative_change > 0.01:
        print(f"⛔ 步长未收敛: 减半后结果变化 {relative_change:.1%} > 1%")
        print("  → 必须继续减小步长直到变化<1%")
```

---

## 二、微分方程/动力学类

### 必须验证
- [ ] 物理约束是否在 ODE 中实现（事件检测 / 状态钳位 / 条件判断）
- [ ] 求解器选择是否合适（刚性系统用 `Radau`/`BDF`，非刚性用 `RK45`）
- [ ] 步长精度是否足够（rtol=1e-8, atol=1e-10 对物理问题）
- [ ] 守恒量是否守恒（计算前后能量/质量差异 < 0.1%）
- [ ] 结果是否在物理范围内（validate_constraints 必须调用）
- [ ] 长时间积分是否有漂移（检查最后时刻的状态是否合理）

### 常见 Bug
```python
# ❌ 错误：没有接触约束，位移超出物理极限
sol = solve_ivp(ode_func, t_span, y0)  # 结果可能 gap > 0.06m

# ✅ 正确：加入事件检测
def contact_event(t, y):
    return y[0]  # z_f = 0 时触发（接触轨道）
contact_event.terminal = True
contact_event.direction = -1
sol = solve_ivp(ode_func, t_span, y0, events=contact_event)

# ❌ 错误：刚性系统用 RK45
sol = solve_ivp(stiff_ode, t_span, y0, method='RK45')  # 极慢或发散
# ✅ 正确：
sol = solve_ivp(stiff_ode, t_span, y0, method='Radau')
```

---

## 三、统计/回归/预测类

### 必须验证
- [ ] 数据划分是否正确（时序按时间，非时序可随机但要设 random_state）
- [ ] 归一化/标准化是否只用训练集统计量（fit on train, transform on test）
- [ ] R² 是否合理（物理/工程 >0.8，社科 >0.3，<0.5 必须改进）
- [ ] 残差是否有模式（画残差图，不能有明显弯曲/扇形）
- [ ] 预测值是否在合理范围内（不能出现负价格、超100%概率等）
- [ ] 多重共线性是否处理（VIF>10 的变量需剔除或 PCA）

### 常见 Bug
```python
# ❌ 错误：数据泄露
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # 用了全部数据
X_train, X_test = train_test_split(X_scaled)

# ✅ 正确：
X_train, X_test = train_test_split(X)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)  # 只 transform，不 fit

# ❌ 错误：时序用随机划分
X_train, X_test = train_test_split(df, test_size=0.2, shuffle=True)  # 未来预测过去！
# ✅ 正确：
split_idx = int(len(df) * 0.8)
train, test = df[:split_idx], df[split_idx:]
```

---

## 四、评价/决策类

### 必须验证
- [ ] 正负向指标处理是否正确（负向指标取倒数或 max-x）
- [ ] 权重之和是否精确等于1（abs(sum(w) - 1) < 0.001）
- [ ] AHP 一致性比率 CR < 0.1
- [ ] 最终得分是否有区分度（最大-最小 > 5%）
- [ ] 排名是否符合常识（明显好的方案排名应该靠前）

### 常见 Bug
```python
# ❌ 错误：负向指标没处理
scores = w1 * cost + w2 * quality  # cost 越大越差，不能直接加权！
# ✅ 正确：
scores = w1 * (1 / cost) + w2 * quality  # 或 w1 * (max_cost - cost)

# ❌ 错误：权重不归一
weights = [0.3, 0.3, 0.3]  # sum = 0.9 ≠ 1
```

---

## 五、图论/网络流类

### 必须验证
- [ ] 图的构建是否正确（节点数、边数与题目一致）
- [ ] 有向/无向是否正确
- [ ] 负权边是否存在？存在则不能用 Dijkstra
- [ ] 网络流的流量守恒是否满足（每个中间节点：流入=流出）
- [ ] 最短路/最大流结果是否合理（不能为负、不能超过容量）

### 常见 Bug
```python
# ❌ 错误：有负权边用 Dijkstra
dist = dijkstra(graph, source)  # 负权边会导致错误结果
# ✅ 正确：
dist = bellman_ford(graph, source)

# ❌ 错误：忘记加反向边（最大流）
graph.add_edge(u, v, capacity=c)
# ✅ 正确：
graph.add_edge(u, v, capacity=c)
graph.add_edge(v, u, capacity=0)  # 反向边容量为0
```

---

## 六、几何/空间优化类

### 必须验证
- [ ] 碰撞检测用完整外轮廓（不是中心点距离）
- [ ] 物理参数与 MODELING_REPORT.md 一致（逐个对照数值）
- [ ] 坐标系统一（全局坐标，不混用局部坐标）
- [ ] 角度单位统一（全部弧度或全部角度，不混用）
- [ ] 场地边界约束是否加入（物体不能超出边界）
- [ ] 旋转后的碰撞检测是否正确（用 OBB/SAT，不能用 AABB）

### 常见 Bug
```python
# ❌ 错误：用中心距代替实体碰撞
def no_collision(a, b):
    return distance(a.center, b.center) > threshold  # 忽略了实体尺寸！

# ✅ 正确：用分离轴定理（SAT）
def no_collision(rect_a, rect_b):
    """SAT 碰撞检测，使用完整矩形四角坐标。"""
    # 获取两个矩形的所有边的法向量作为分离轴
    ...

# ❌ 错误：弧度角度混用
angle = 90  # 角度
x = r * np.cos(angle)  # np.cos 需要弧度！结果完全错误
# ✅ 正确：
x = r * np.cos(np.radians(angle))

# ❌ 错误：遮蔽/覆盖判定降维为中心点
def is_occluded(smoke_center, missile_pos, target_center):
    """只检查导弹→目标中心的视线被遮蔽 — 错误！"""
    dist = point_to_line_distance(smoke_center, missile_pos, target_center)
    return dist <= smoke_radius  # 只判断了一个点！

# ✅ 正确：对目标完整几何边界做判定
def is_fully_occluded(smoke_center, smoke_radius, missile_pos, 
                     target_base_center, target_radius, target_height, N=300):
    """
    圆柱体完全遮蔽判定。
    几何参数来源：MODELING_REPORT.md 符号说明表
    判定对象：圆柱体上下底面圆周上的 N 个离散点
    等价性依据：[如果有证明 "底面圆周被遮蔽⟹整体被遮蔽"，在此说明]
    """
    for z in [0, target_height]:  # 上下两个底面
        center = target_base_center + np.array([0, 0, z])
        for i in range(N):
            theta = 2 * np.pi * i / N
            point = center + target_radius * np.array([np.cos(theta), np.sin(theta), 0])
            dist = point_to_line_distance(smoke_center, missile_pos, point)
            if dist > smoke_radius:
                return False
    return True

# ⛔ 收敛性验证（必做）
# 用 N=100, 300, 500 分别跑，结果差异 < 1% 才算采样充足
for N in [100, 300, 500]:
    result = is_fully_occluded(..., N=N)
    print(f"N={N}: {result}")
```

---

## 通用验证（所有题型必做）

1. **参数一致性**：代码中的每个物理参数值必须与 MODELING_REPORT.md 完全一致
2. **单位一致性**：检查所有计算中单位是否统一（不能混用 m/cm/mm）
3. **边界情况**：输入为 0、最大值、边界值时代码是否正常运行
4. **结果可复现**：设置 random seed，多次运行结果一致
5. **JSON 输出完整**：每个子问题的关键结果都保存到 JSON，供 paper-figure 读取


---

<!-- modex-3 同源吸收 P3（2026-09-22）：以下为上游证据化修订口径，与上文条目冲突时以本节"按需验证、不设固定重跑预算"的解释优先执行；上文清单仍作为检查项来源保留。 -->

首次读取本题所需章节。与 checks/ 使用同一份检查计划和当前版本运行证据。
该手册不另设“必须跑若干次”的预算。异常区分真实缺陷、待解释现象和检查不可用；
先核对已有数据，再修受影响代码。不要把全部题型示例强制加到每道题中。

## 一、优化类

必须验证：

- 最小化/最大化方向、目标与单位和已确认建模报告一致。
- 题设硬约束真正参与可行解选择，不能只在最后打印“通过”。
- 不等式方向与求解器 API 一致；例如 SciPy 传统 ineq 约定 f(x) >= 0。
- 整数性、边界、有限值与目标值均从最终保存的解重新核对，不只信 success。
- 连续松弛后直接四舍五入不构成整数可行解；需要整数求解或可行性修复及重新验证。
- 记录真实状态（最优、可行 incumbent、超时、未找到可行解），不把超时说成证明不可行。

最优性与开销详见 checks/optimization.md：

1. 跨问题只有同目标、同口径且可行域包含时才可比较最优值单调性；即使严格包含，最优值也可以相同。
2. 可行解对最小化是上界、对最大化是下界；与基线相等不是失败，不要求“严格优于”。
3. 随机起点差异是局部最优风险线索，不是必须一直跑到一致；按既定预算报告稳健性。
4. 不因维度 >= 6/10 或随机可行率 < 30% 就强制改模型/分层；依据结构和性能分析决定。
5. 多目标尺度与权重需解释，不强制每个目标归一化到 [0,1]；原生 Pareto、物理权重和零目标均有合法用法。
6. 离散收敛采用问题相关误差预算；复用已有粗细网格结果，不另开“直到误差 < 1%”的无限循环。

## 二、微分方程/动力学类

执行 checks/physical.md 的适用检查：

- 按刚性、事件和精度需求选择积分器；RK45 遇刚性可能低效，但仅凭方法名不判失败。
- 容差依物理尺度、各状态单位和建模计划设置，不能用统一 rtol/atol 当全部题目的标准。
- 初始值、边界、完整轨迹有限性、事件顺序及相应物理条件需真实验证。
- 只有模型具有相应守恒性质才检查守恒；有外力/耗散时核能量收支。
- 接触采用有依据的事件/约束/冲击模型；不凭空加接触，不用 clip 隐藏穿透或通用地把速度归零。
- 检查全轨迹而非只比首尾；零初始能量不能用相对误差除零。

## 三、统计/回归/预测类

执行 checks/prediction.md：

- 时间序列不能用未来数据训练过去的预测；实体相关样本按组隔离，无依赖样本才可随机划分。
- 标准化、特征选择、调参均不得窥视最终测试集；交叉验证的预处理在每折内拟合。
- 标签来源、特征可用时间和评估目标有真实依据；仿真输出不冒充独立人工真值。
- 指标与适当基线、题设要求比较；负测试 R²、低 R²、高 AUC 均不单凭数值判程序错误。
- 残差结构提示假设/区间可能不适用；先诊断，不为消除模式修改真实数据。
- VIF 高提示共线性风险，不必一律删变量/PCA；结合解释/预测目标与正则化方案。
- 多重检验按假设族控制错误率，不为了显著性删不利结果。
- 已有真实划分、训练和独立验证证据可供总检复用；改变相关数据/代码后重验受影响项。

## 四、评价/决策类

执行 checks/evaluation.md：

- 指标正负向、单位、标准化与权重来源一致；倒数法须先考虑合法的零值/负值情形。
- 权重按模型要求归一并使用数值容差；AHP 采用声明的 RI/CR 标准。
- 不为“得分差至少 5%”改权重；合法并列、小差异和不稳定排名都应如实呈现。
- 扰动范围、次数、种子事先确定；复用同设置结果，不伪造稳定或无依据加试验。

## 五、图论/网络流类

- 节点、边、方向、容量和单位按题设构建，不漏孤立节点/平行边。
- 有负权边不能直接用通常的 Dijkstra；Bellman-Ford 还需处理可达负环和无路径。
- 最短路可以为负，不能套“所有结果非负”；最大流按题设非负容量、守恒和源汇平衡验证。
- 自写残量网络需反向残量边，并区分原网络真实反向边，不能把真实反向容量覆盖成 0。
- 使用最大流库时确认库是否已维护残量网络，不重复手工加边改变原题。
- 必要时用路径代价重算、流守恒、割容量等可验证证书，不强制第二求解器整题重跑。

## 六、几何/空间优化类

- 使用完整物理轮廓与正确坐标/单位，不将孔距、中心距直接当实体长度。
- 任意旋转矩形可用 OBB/SAT；AABB 可快速筛选，但不冒充精确旋转碰撞判定。
- 明确接触定义、数值容差和退化几何，执行 checks/physical.md 中的边界测试。
- 全遮蔽/覆盖题不能只测中心点；也不能把局部覆盖题强行升级成全覆盖。
- 视线按物理意义使用射线/线段及投影范围，不只用无限直线距离而忽略遮挡物在观察者背后。
- 用边界采样代替整体判定需给等价/误差依据；上下圆周采样不自动证明整个圆柱被遮蔽。
- 按既定精度验证采样收敛，不对 True/False 结果计算“1% 差异”，不强制所有题跑 100/300/500 点。

## 通用收尾

1. 原始输入、参数来源、单位及题设数量一致，清洗/采样/排除可追溯。
2. 验证新结果的必要硬条件、NaN/Inf、边界与任务能力，失败不能靠改标签变成通过。
3. 保存代码、版本、种子、实际运行状态与完整精度结果；只记录真实依赖，不强装 torch。
4. 多算例逐个保存已验证检查点。汇总/本地检查复用同版本证据，不重复求解；相关源码/数据/验证器变化则重验。
5. 缺报告补报告、缺回执等待同一任务、检查器故障修检查器，不一律从 main.py 全量重跑。
6. 达到共享返修预算后如实报未完成及剩余问题，不自动重写上游模型或降低数学标准。
