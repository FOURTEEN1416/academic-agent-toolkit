# scientific-data-preprocessing Skill 更新日志

**更新日期**: 2026-01-18
**版本**: V1.1

---

## 更新内容概述

在原有的 scientific-data-preprocessing skill 基础上，新增了对 **AI常见预处理错误** 的检测和防范机制，涵盖数据泄露、语义错误、分布盲区等6大类致命问题。

---

## 新增内容

### 1. 新增参考文档

**文件**: `references/ai-common-pitfalls.md` (约3000行)

包含6大类AI常犯错误的详细说明：

#### Category 1: 数据泄露 (🔴🔴🔴 致命级)

- **时间穿越泄露**: 使用未来信息处理过去数据
  - 全局插值在时间序列中的错误
  - 在train/test split前进行全局缩放
  - 检测方法和修复代码

- **因果倒置泄露**: 使用目标变量的结果作为特征
  - 示例: 预测流失时使用"最后通话时长"
  - 检测问题: "这个特征在预测时是否可用？"

- **高基数ID泄露**: 将唯一标识符用作特征
  - 错误: One-hot编码 user_id (10万+列)
  - 错误: 将ID当作数值处理
  - 正确: 仅用于分组聚合

#### Category 2: 语义-数值映射谬误 (🔴🔴 严重级)

- **无意义的数值运算**
  - 邮编/区号的算术运算 (平均邮编 = 50105.5?)
  - 日期作为Unix时间戳的问题
  - 检测代码和正确处理方法

- **序数变量的错误处理**
  - 错误A: One-hot编码 → 丢失顺序信息
  - 错误B: 天真的数值映射 → 间距不相等
  - 决策树: 何时用ordinal encoding vs one-hot

#### Category 3: 分布盲目的暴力归一化 (🔴 中等级)

- **盲目应用StandardScaler**
  - 问题: 假设所有数据都是正态分布
  - 长尾分布的压缩问题 (收入数据示例)
  - 智能缩放器选择算法 (基于偏度和峰度)

- **缩放器选择指南**:
  - 正态分布 → StandardScaler
  - 长尾分布 → Log transform + StandardScaler
  - 重度异常值 → RobustScaler
  - 计数数据 → √(x) 或 log(x+1)

#### Category 4: 天真插值 (🔴 中等级)

- **无条件均值/中位数填充**
  - 问题: 忽略关系、减少方差
  - 更好方法: 条件插值、预测插值、指示缺失

- **盲目删除**
  - dropna() 导致70%数据损失
  - 可能引入选择偏差
  - 何时可接受删除的条件

#### Category 5: 特征构建混乱 (🔴 中等级)

- **暴力多项式爆炸**
  - PolynomialFeatures(degree=3): 10特征 → 220特征
  - 维度诅咒、多重共线性、过拟合
  - 特征构建清单 (物理意义、可解释性、信息增益)

- **无意义算术**
  - 纬度 + 经度 = ???
  - user_id × age = ???
  - 单位检查、语义检查、领域检查

#### Category 6: 特征选择短视 (🔴 中等级)

- **线性相关性盲区**
  - Pearson相关系数无法检测非线性关系
  - y=x² 的 Pearson ≈ 0 (如果x对称)
  - 综合特征选择: Pearson + Spearman + Mutual Information

- **P值迷信**
  - 大样本下一切都"显著"
  - 忽略效应量
  - 智能选择: 同时检查显著性和效应量

---

### 2. 更新主技能文件

**文件**: `SKILL.md`

#### 新增触发条件:
- 审计现有预处理是否存在数据泄露或语义错误
- 审查AI生成的预处理代码常见陷阱

#### 新增Pattern 9: 数据泄露检测

```python
def detect_data_leakage(df, target_col, feature_cols, id_cols):
    """
    Critical checks for data leakage and AI common pitfalls
    """
    # 1. ID泄露: 高基数变量
    # 2. 因果倒置: 与目标完美相关
    # 3. 无意义数值: 代码被当作数字
```

**功能**:
- 检测ID列是否被误用为特征 (>50%唯一值)
- 检测因果倒置 (correlation > 0.95)
- 检测代码列被数值化 (邮编、电话号码等)

#### 新增Pattern 10: 分布感知缩放

```python
def smart_scaler_selection(df, col):
    """
    Choose scaler based on distribution characteristics
    """
    # 检查偏度和峰度
    # 正态 → StandardScaler
    # 右偏 → Log + StandardScaler
    # 异常值 → RobustScaler
```

**功能**:
- 自动检测数据分布特性 (skewness, kurtosis)
- 根据分布选择合适的缩放器
- 必要时自动应用对数变换

---

### 3. 更新导航索引

**文件**: `references/index.md`

新增章节链接:
- 数据泄露检测 → ai-common-pitfalls.md § Category 1
- 语义-数值映射错误 → ai-common-pitfalls.md § Category 2
- 分布感知缩放 → ai-common-pitfalls.md § Category 3
- 综合审计 → ai-common-pitfalls.md § Comprehensive Validation Checklist

---

## 关键特性

### 1. 全面的错误检测

**6大类错误覆盖**:
- 数据泄露 (时间穿越、因果倒置、ID泄露)
- 语义错误 (邮编算术、序数→one-hot)
- 分布盲区 (盲目StandardScaler)
- 天真插值 (无条件填充)
- 特征混乱 (暴力多项式)
- 选择短视 (Pearson盲区)

### 2. 可执行的检测代码

每种错误类型都提供:
- ✅ 检测函数 (自动识别问题)
- ❌ 错误示例代码
- ✅ 正确实现代码
- 📊 影响分析和严重程度

### 3. 综合验证清单

**新增全面审计函数**:
```python
comprehensive_preprocessing_audit(
    df,
    target_col,
    id_cols,
    timestamp_col
)
```

**检查项目**:
- [ ] 数据泄露检查 (6项)
- [ ] 语义检查 (4项)
- [ ] 分布检查 (3项)
- [ ] 插值检查 (4项)
- [ ] 特征工程检查 (5项)
- [ ] 特征选择检查 (6项)

---

## 使用示例

### 场景1: 审计现有预处理管道

```python
# 加载已处理的数据
df_processed = pd.read_csv('processed_data.csv')

# 运行综合审计
issues = comprehensive_preprocessing_audit(
    df_processed,
    target_col='churn',
    id_cols=['user_id', 'order_id'],
    timestamp_col='date'
)

# 查看问题
for issue in issues:
    print(issue)
```

**典型输出**:
```
❌ user_id: High cardinality ID - remove from features
⚠️ zipcode: Looks like code (zipcode/phone) - check encoding
❌ final_payment: Near-perfect correlation (0.987) - likely leakage!
⚠️ income: Highly skewed (3.21) - consider log transform
```

### 场景2: 选择合适的缩放器

```python
# 自动选择缩放器
for col in continuous_features:
    scaler, transform = smart_scaler_selection(df, col)

    if transform == 'log':
        df[f'{col}_log'] = np.log1p(df[col])
        df[f'{col}_scaled'] = scaler.fit_transform(df[[f'{col}_log']])
    else:
        df[f'{col}_scaled'] = scaler.fit_transform(df[[col]])
```

**典型输出**:
```
income: skewness=2.45, kurtosis=8.32
  → Log transform + StandardScaler (right-skewed)

age: skewness=0.12, kurtosis=2.87
  → StandardScaler (data is roughly normal)

num_purchases: skewness=4.21, kurtosis=25.67
  → RobustScaler (heavy outliers)
```

### 场景3: 检测数据泄露

```python
# 在建模前检查
issues = detect_data_leakage(
    df,
    target_col='will_default',
    feature_cols=df.columns.tolist(),
    id_cols=['loan_id', 'customer_id']
)
```

**典型输出**:
```
============================================================
DATA LEAKAGE AUDIT
============================================================
❌ FATAL: loan_id is an ID - NEVER use as feature
❌ FATAL: final_payment_amount correlation=0.987 - likely consequence of target!
⚠️ customer_zipcode: Looks like code (zipcode/ID) - should be categorical
============================================================
```

---

## 防范的具体错误

### 错误1: 时间穿越 (V2.0曾犯此错)

**错误代码**:
```python
# ❌ 使用全局统计量
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df)  # 测试集信息泄露!
train, test = train_test_split(df_scaled)
```

**新增检测**: Pattern 9会警告此类错误

**正确代码**:
```python
# ✅ 先分割再缩放
train, test = train_test_split(df)
scaler = StandardScaler()
train_scaled = scaler.fit_transform(train)
test_scaled = scaler.transform(test)
```

### 错误2: 邮编算术 (AI常犯)

**错误代码**:
```python
# ❌ 平均邮编 = ???
df['avg_zipcode'] = df['zipcode'].mean()  # 100001和90210的平均?
```

**新增检测**: Pattern 9会识别邮编类特征 (>1000的值，>100个unique)

**正确代码**:
```python
# ✅ 当作分类
df = pd.get_dummies(df, columns=['zipcode'])
# 或: 提取有意义特征
df['zipcode_region'] = df['zipcode'].astype(str).str[:3]
```

### 错误3: ID泄露 (V1.0教训)

**错误代码**:
```python
# ❌ One-hot编码用户ID
df = pd.get_dummies(df, columns=['user_id'])  # 10万列!
```

**新增检测**: Pattern 9会标记高基数列 (>50% unique)

**正确代码**:
```python
# ✅ 用于聚合
user_features = df.groupby('user_id').agg({
    'purchase_amount': ['mean', 'std', 'count']
})
```

---

## 文件结构

```
C:\Users\羽裳\.claude\skills\scientific-data-preprocessing\
├── SKILL.md                                    # 主技能文件 (已更新)
│   ├── Pattern 9: Data Leakage Detection       # 新增
│   └── Pattern 10: Distribution-Aware Scaling  # 新增
│
└── references/
    ├── index.md                                # 导航索引 (已更新)
    ├── error-case-studies.md                  # 真实案例
    ├── decision-trees.md                       # 决策树
    ├── validation-checklist.md                 # 验证清单
    └── ai-common-pitfalls.md                   # AI常见错误 (新增)
        ├── Category 1: Data Leakage            # 数据泄露
        ├── Category 2: Semantic-Numeric Fallacy# 语义错误
        ├── Category 3: Distribution-Blind      # 分布盲区
        ├── Category 4: Naive Imputation        # 天真插值
        ├── Category 5: Feature Construction    # 特征混乱
        ├── Category 6: Feature Selection       # 选择短视
        └── Comprehensive Validation Checklist  # 综合清单
```

---

## 与现有内容的整合

### 与error-case-studies.md的关系

**互补关系**:
- `error-case-studies.md`: 真实项目中发生的错误 (V1.0, V2.0)
  - 专注于分组时间序列数据
  - 基于网球数据的具体案例

- `ai-common-pitfalls.md`: AI系统性错误模式
  - 适用于所有类型的数据
  - 更广泛的错误类型覆盖

### 与decision-trees.md的关系

**决策树扩展**:
- `decision-trees.md`: 正确处理的决策流程
  - 如何选择插值方法
  - 如何选择标准化范围

- `ai-common-pitfalls.md`: 错误决策的识别
  - 如何检测已经发生的错误
  - 如何防止常见陷阱

### 与validation-checklist.md的关系

**验证增强**:
- `validation-checklist.md`: 处理后的验证
  - 检查输出数据质量
  - 验证转换正确性

- `ai-common-pitfalls.md`: 处理前的审计
  - 检测输入数据的潜在问题
  - 预防性错误识别

---

## 影响范围

### 受益场景

1. **AI代码审查**: 检测AI生成的预处理代码中的常见错误
2. **遗留系统审计**: 审查现有预处理管道的数据泄露风险
3. **教学培训**: 向新手展示常见错误和正确做法
4. **生产部署前**: 最后一道防线，确保没有致命错误

### 不受影响的部分

- 原有的8个Pattern (Pattern 1-8) 保持不变
- 3个示例 (Example 1-3) 保持不变
- 分组时间序列的核心原则不变

---

## 验证和测试

### 已验证的场景

✅ **数据泄露检测**:
- 识别高基数ID列 (>50% unique)
- 识别目标变量代理 (correlation > 0.95)
- 识别代码列 (邮编、电话号码)

✅ **分布感知缩放**:
- 正态分布 → StandardScaler
- 右偏分布 → Log transform
- 重度异常值 → RobustScaler

✅ **综合审计**:
- 6大类错误的自动检测
- 清晰的错误报告格式
- 可操作的修复建议

---

## 未来改进方向

### 潜在扩展

1. **时间泄露检测**: 更精细的时间穿越检测
   - 需要特征时间戳信息
   - 自动检测特征是否在目标之后

2. **因果图分析**: 基于领域知识的因果关系检测
   - 需要用户提供因果先验
   - 自动识别因果倒置

3. **交互式审计报告**: HTML格式的详细报告
   - 可视化错误分布
   - 交互式修复建议

4. **自动修复**: 不仅检测，还能自动修复部分错误
   - 自动移除ID列
   - 自动转换代码列为分类
   - 自动选择缩放器

---

## 总结

### 核心价值

1. **全面性**: 覆盖6大类AI常犯错误
2. **实用性**: 提供可执行的检测和修复代码
3. **系统性**: 与现有skill完美整合
4. **可扩展性**: 易于添加新的错误类型

### 关键改进

| 方面 | 改进前 | 改进后 |
|------|--------|--------|
| **错误覆盖** | 仅分组时间序列错误 | +6大类通用错误 |
| **检测能力** | 手动识别 | 自动审计函数 |
| **错误类型** | 3种 (V1/V2错误) | 15+种常见错误 |
| **适用范围** | 分组数据 | 所有类型数据 |

### 最终目标

让 scientific-data-preprocessing skill 成为:
- ✅ 预处理的**完整指南** (正确做法)
- ✅ 错误的**检测工具** (识别问题)
- ✅ AI的**安全网** (防止常见陷阱)

---

**更新完成**: 2026-01-18
**版本**: V1.1
**状态**: ✅ 生产就绪

---

*End of Update Log*
