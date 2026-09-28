# AI Common Pitfalls in Data Preprocessing

**Critical errors that AI agents (and humans) frequently make in data preprocessing, causing data leakage, semantic destruction, and model failure.**

---

## Overview

This document catalogs systematic errors that occur when preprocessing is done mechanically without domain understanding. These pitfalls often go undetected until models fail in production.

**Severity levels:**
- 🔴🔴🔴 **Fatal**: Data leakage, causes complete model failure
- 🔴🔴 **Severe**: Semantic destruction, results invalid
- 🔴 **Moderate**: Performance degradation, interpretation issues

---

## Category 1: Data Leakage (🔴🔴🔴 Fatal)

### 1.1 Time Travel Leakage

**Error**: Using future information to process past data.

**Common manifestations:**

#### A. Global Imputation in Time Series
```python
# ❌ WRONG: Uses future data to fill past
df['value'] = df['value'].fillna(df['value'].mean())
# Problem: mean() includes all data (past + future)

# ✅ CORRECT: Forward-fill or group-wise
df['value'] = df.groupby('group_id')['value'].fillna(method='ffill')
```

#### B. Global Scaling Before Train/Test Split
```python
# ❌ WRONG: Test set statistics leak into training
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df)  # Uses entire dataset!
train, test = train_test_split(df_scaled)

# ✅ CORRECT: Fit on training only
train, test = train_test_split(df)
scaler = StandardScaler()
train_scaled = scaler.fit_transform(train)
test_scaled = scaler.transform(test)  # Use training statistics
```

**Impact:**
- Overly optimistic training performance
- Catastrophic failure in production (model expects future information)
- Results not reproducible in real-time scenarios

**Detection:**
```python
def detect_time_travel(df, timestamp_col, target_col):
    """
    Check if preprocessing used future information
    """
    # Sort by time
    df = df.sort_values(timestamp_col)

    # Check if any operation used global statistics
    # Example: Check if imputation values match future means
    for col in df.select_dtypes(include=[np.number]).columns:
        if col == target_col:
            continue

        # For each time point, calculate statistics using only past data
        for i in range(len(df)):
            past_data = df[col].iloc[:i+1]
            if past_data.isna().any():
                past_mean = past_data.mean()
                global_mean = df[col].mean()

                if abs(past_mean - global_mean) > 0.01:
                    print(f"⚠️ {col} at row {i}: past mean != global mean")
                    print(f"   Possible time travel leakage!")
```

### 1.2 Causal Inversion Leakage

**Error**: Using variables that are **consequences** of the target as predictive features.

**Examples:**

| Task | Target | Leakage Feature | Why It's Wrong |
|------|--------|-----------------|----------------|
| Predict customer churn | is_churned | last_call_duration | Duration is 0 BECAUSE they churned |
| Predict loan default | will_default | final_payment_amount | Payment amount is low BECAUSE they defaulted |
| Predict disease | has_disease | num_prescriptions | Prescriptions are result of diagnosis |

**Detection questions:**
1. "Can this feature be known BEFORE the target occurs?"
2. "Is this feature a result of the target, or a cause?"
3. "In production, will this feature be available at prediction time?"

```python
def check_causal_inversion(df, feature_col, target_col, timestamp_col):
    """
    Check if feature appears AFTER target in time
    """
    # For events with timestamps
    feature_time = df[f'{feature_col}_timestamp']
    target_time = df[f'{target_col}_timestamp']

    # Feature should occur BEFORE target
    if (feature_time > target_time).any():
        print(f"❌ {feature_col} occurs after {target_col}")
        print(f"   This is causal inversion leakage!")
        return True

    return False
```

### 1.3 High-Cardinality ID Leakage

**Error**: Treating unique identifiers as predictive features.

**Common mistakes:**

```python
# ❌ WRONG: One-hot encoding high-cardinality IDs
df_encoded = pd.get_dummies(df, columns=['user_id'])
# Problem: Creates 100,000+ columns for 100,000 users
# Model memorizes training user IDs, fails on new users

# ❌ WRONG: Using ID as numeric feature
df['user_id_numeric'] = df['user_id'].astype(int)
# Problem: Assumes user_id=123 is "between" user_id=100 and user_id=150

# ✅ CORRECT: Use ID for grouping, not as feature
user_features = df.groupby('user_id').agg({
    'purchase_amount': ['mean', 'std', 'count'],
    'days_since_signup': 'first'
})
```

**Detection:**
```python
def detect_id_leakage(df, potential_id_cols):
    """
    Identify columns that are likely IDs and shouldn't be features
    """
    for col in potential_id_cols:
        n_unique = df[col].nunique()
        n_rows = len(df)

        # High cardinality (>50% unique values)
        if n_unique / n_rows > 0.5:
            print(f"⚠️ {col}: {n_unique}/{n_rows} unique ({n_unique/n_rows*100:.1f}%)")
            print(f"   Likely an ID - should NOT be used as feature")

            # Check if it's in feature list
            if col in feature_columns:
                print(f"   ❌ ERROR: {col} is being used as feature!")
```

**Rules for ID columns:**
- ✅ Use for grouping (GROUP BY)
- ✅ Use for joins (MERGE/JOIN)
- ❌ Never one-hot encode
- ❌ Never treat as numeric
- ❌ Never use directly as model input

---

## Category 2: Semantic-Numeric Mapping Fallacy (🔴🔴 Severe)

### 2.1 Meaningless Numeric Operations

**Error**: Treating coded numbers as if they have mathematical meaning.

**Common mistakes:**

#### A. Postal Code / Area Code Arithmetic
```python
# ❌ WRONG: Treating zip codes as numbers
df['avg_zipcode'] = df['zipcode'].mean()
# Problem: Average of 10001 and 90210 is 50105.5 (meaningless!)

# ❌ WRONG: Standardizing zip codes
scaler = StandardScaler()
df['zipcode_std'] = scaler.fit_transform(df[['zipcode']])
# Problem: Creates false distance relationships

# ✅ CORRECT: Treat as categorical
df = pd.get_dummies(df, columns=['zipcode'])
# Or: Extract meaningful features
df['zipcode_region'] = df['zipcode'].astype(str).str[:3]
```

**Detection:**
```python
def detect_meaningless_numeric(df, col):
    """
    Check if numeric column should actually be categorical
    """
    # Check if column looks like a code
    if df[col].dtype in ['int64', 'float64']:
        n_unique = df[col].nunique()

        # Check patterns
        is_code = False

        # Pattern 1: High number of unique values but discrete
        if n_unique > 50 and (df[col] % 1 == 0).all():
            is_code = True

        # Pattern 2: Values in specific ranges (like zip codes)
        if df[col].min() > 1000 and df[col].max() < 100000:
            is_code = True

        # Pattern 3: No meaningful order (shuffling doesn't change meaning)
        # Calculate correlation with target before/after shuffle

        if is_code:
            print(f"⚠️ {col} looks like a code (ID/zipcode/phone)")
            print(f"   Should be treated as categorical, not numeric")
```

#### B. Dates/Times as Unix Timestamps
```python
# ❌ WRONG: Using raw timestamp
df['timestamp_numeric'] = pd.to_datetime(df['date']).astype(int)
# Problem: Distance between 2020-01-01 and 2020-01-02
#          same as 2020-12-31 and 2021-01-01 (but different meaning!)

# ✅ CORRECT: Extract meaningful features
df['year'] = df['date'].dt.year
df['month'] = df['date'].dt.month
df['day_of_week'] = df['date'].dt.dayofweek
df['is_weekend'] = df['date'].dt.dayofweek >= 5
df['is_holiday'] = df['date'].isin(holiday_dates)
```

### 2.2 Ordinal Variable Mishandling

**Error**: Treating ordered categories incorrectly.

**Two common mistakes:**

#### A. One-Hot Encoding Ordinal Variables (Loses Order)
```python
# ❌ WRONG: One-hot encoding ordinal
# Original: ["Poor", "Fair", "Good", "Excellent"]
df = pd.get_dummies(df, columns=['rating'])
# Result: rating_Poor, rating_Fair, rating_Good, rating_Excellent
# Problem: Lost the ordering information!

# ✅ CORRECT: Ordinal encoding
rating_map = {'Poor': 1, 'Fair': 2, 'Good': 3, 'Excellent': 4}
df['rating_ordinal'] = df['rating'].map(rating_map)
```

#### B. Naive Numeric Mapping (Wrong Intervals)
```python
# ❌ POTENTIALLY WRONG: Assuming equal intervals
education_map = {
    'None': 0,
    'High School': 1,
    'Bachelor': 2,
    'Master': 3,
    'PhD': 4
}
# Problem: Gap between None→HS != gap between Master→PhD

# ✅ CORRECT: Consider real-world intervals
education_map = {
    'None': 0,
    'High School': 12,    # 12 years
    'Bachelor': 16,       # 16 years
    'Master': 18,         # 18 years
    'PhD': 22             # 22 years (approximate)
}
# Or use domain knowledge to set appropriate intervals
```

**Decision tree for categorical variables:**

```
Is variable categorical?
│
├─ Does it have a natural order?
│  │
│  ├─ YES (Ordinal)
│  │  │
│  │  ├─ Are intervals equal/known?
│  │  │  ├─ YES → Numeric encoding with correct intervals
│  │  │  └─ NO → Ordinal encoding (1,2,3,...) + note in documentation
│  │  │
│  │  └─ Use: OrdinalEncoder or manual mapping
│  │
│  └─ NO (Nominal)
│     │
│     ├─ How many categories?
│     │  ├─ Few (<10) → One-hot encoding
│     │  ├─ Many (10-50) → Target encoding or embedding
│     │  └─ Very many (>50) → Feature hashing or entity embedding
│     │
│     └─ Never: Numeric encoding (creates false order)
```

---

## Category 3: Distribution-Blind Scaling (🔴 Moderate)

### 3.1 Blind StandardScaler Application

**Error**: Assuming all data is normally distributed.

**Problem:**
```python
# Real-world data (e.g., income)
# Distribution: Long-tailed (most people: $30k-$80k, few: $1M+)

# ❌ WRONG: Blind Z-score standardization
scaler = StandardScaler()
df['income_std'] = scaler.fit_transform(df[['income']])

# Result: Mean=$100k, Std=$500k (due to outliers)
# Most data compressed to [-0.1, 0.1] range
# Outliers at z=+20 dominate model learning
```

**Correct approach:**
```python
def smart_scaling(df, col):
    """
    Choose scaler based on distribution
    """
    from scipy.stats import skew, kurtosis

    # Check distribution
    skewness = skew(df[col].dropna())
    kurt = kurtosis(df[col].dropna())

    print(f"{col}: skewness={skewness:.2f}, kurtosis={kurt:.2f}")

    if abs(skewness) < 0.5 and abs(kurt) < 3:
        # Roughly normal
        print("→ Use StandardScaler")
        return StandardScaler()

    elif skewness > 1:
        # Right-skewed (long tail)
        print("→ Apply log transform first, then StandardScaler")
        df[f'{col}_log'] = np.log1p(df[col])
        return StandardScaler()

    else:
        # Heavy outliers
        print("→ Use RobustScaler (median/IQR)")
        return RobustScaler()
```

**Scaler selection guide:**

| Distribution | Recommended Scaler | Reason |
|--------------|-------------------|--------|
| Normal | StandardScaler | Mean/std are stable |
| Long-tailed | Log transform + StandardScaler | Reduces skewness first |
| Heavy outliers | RobustScaler | Uses median/IQR (robust) |
| Bounded [0,1] | No scaling needed | Already normalized |
| Count data | √(x) or log(x+1) first | Variance stabilization |

---

## Category 4: Naive Imputation (🔴 Moderate)

### 4.1 Unconditional Mean/Median Filling

**Error**: Filling missing values without considering context.

**Problems:**

```python
# ❌ WRONG: Global mean imputation
df['age'].fillna(df['age'].mean(), inplace=True)

# Problems:
# 1. Reduces variance (all missing → same value)
# 2. Ignores relationships (age varies by gender, occupation, etc.)
# 3. Can create impossible values (mean age = 35.7 years for children dataset)
```

**Better approaches:**

```python
# ✅ CONDITIONAL IMPUTATION
# Use related variables
df['age'] = df.groupby(['gender', 'occupation'])['age'].transform(
    lambda x: x.fillna(x.median())
)

# ✅ PREDICTIVE IMPUTATION
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer

imputer = IterativeImputer(random_state=0)
df_imputed = imputer.fit_transform(df)

# ✅ INDICATE MISSINGNESS
df['age_was_missing'] = df['age'].isna().astype(int)
df['age'].fillna(df['age'].median(), inplace=True)
# Now model can learn that missingness itself is informative
```

**Imputation strategy decision tree:**

```
Missing values detected
│
├─ Q1: Is missingness informative? (MCAR, MAR, MNAR)
│  │
│  ├─ YES (MAR/MNAR) → Add missingness indicator
│  └─ NO (MCAR) → Proceed to Q2
│
├─ Q2: What % is missing?
│  │
│  ├─ <5% → Simple imputation (mean/median)
│  ├─ 5-30% → Conditional or predictive imputation
│  └─ >30% → Consider dropping feature or sophisticated methods
│
└─ Q3: What type of feature?
   │
   ├─ Categorical → Mode or create "Missing" category
   ├─ Continuous (grouped data) → Group-wise median
   └─ Time series → Forward fill or interpolation (within group!)
```

### 4.2 Blind Deletion (Listwise/Pairwise)

**Error**: Dropping all rows with any missing value.

```python
# ❌ WRONG: Drop all incomplete rows
df_clean = df.dropna()

# Problems:
# - Original: 10,000 rows → After dropna(): 3,000 rows
# - Lost 70% of data!
# - Remaining data may be biased (e.g., only rich people fill all fields)
```

**When deletion is acceptable:**
- Missing completely at random (MCAR)
- <5% of rows affected
- Sample size remains adequate
- No systematic bias introduced

---

## Category 5: Feature Construction Chaos (🔴 Moderate)

### 5.1 Brute-Force Polynomial Explosion

**Error**: Creating all possible feature interactions without thought.

```python
from sklearn.preprocessing import PolynomialFeatures

# ❌ WRONG: Blind polynomial expansion
poly = PolynomialFeatures(degree=3, include_bias=False)
X_poly = poly.fit_transform(X)  # 10 features → 220 features!

# Problems:
# 1. Curse of dimensionality (n^d features)
# 2. Most interactions meaningless (temperature × customer_id?)
# 3. Severe multicollinearity
# 4. Overfitting
```

**Better approach:**

```python
# ✅ DOMAIN-DRIVEN FEATURE ENGINEERING
# Only create features with physical meaning

# Example: E-commerce
df['price_per_unit'] = df['total_price'] / df['quantity']
df['discount_rate'] = df['discount'] / df['original_price']
df['is_bulk_order'] = (df['quantity'] > 10).astype(int)

# NOT: df['user_id'] * df['timestamp']  # Meaningless!
```

**Feature construction checklist:**

- [ ] Does this interaction have **physical meaning**?
- [ ] Can you **explain** this feature to a domain expert?
- [ ] Does it **add information** beyond original features?
- [ ] Have you checked for **multicollinearity**?
- [ ] Does performance **improve** on validation set?

### 5.2 Meaningless Arithmetic

**Error**: Combining features without considering units or semantics.

```python
# ❌ WRONG: Meaningless combinations
df['lat_plus_lon'] = df['latitude'] + df['longitude']
# Problem: Latitude + Longitude = ??? (no physical meaning)

df['user_id_times_age'] = df['user_id'] * df['age']
# Problem: Why would this ever be useful?

# ✅ CORRECT: Meaningful combinations
df['distance_from_center'] = np.sqrt(
    (df['latitude'] - city_center_lat)**2 +
    (df['longitude'] - city_center_lon)**2
)
# Has meaning: Distance in degrees

df['bmi'] = df['weight_kg'] / (df['height_m'] ** 2)
# Has meaning: Body mass index (standard medical metric)
```

**Rules:**
1. **Check units**: Can these units be combined? (m + s = nonsense)
2. **Check semantics**: Does the result have meaning?
3. **Check domain**: Would an expert create this feature?

---

## Category 6: Feature Selection Myopia (🔴 Moderate)

### 6.1 Linear Correlation Blindness

**Error**: Using Pearson correlation to select features for non-linear relationships.

```python
# ❌ WRONG: Remove low-correlation features
corr = df.corr()['target'].abs()
features_to_keep = corr[corr > 0.3].index
# Problem: Misses non-linear relationships!

# Example: y = x^2 (perfect quadratic relationship)
# Pearson correlation ≈ 0 if x is symmetric around 0
```

**Demonstration:**
```python
import numpy as np
import matplotlib.pyplot as plt

# Generate non-linear relationship
x = np.linspace(-10, 10, 1000)
y = x**2

# Pearson correlation
pearson = np.corrcoef(x, y)[0, 1]
print(f"Pearson correlation: {pearson:.3f}")  # ≈ 0.0 !

# But they're perfectly related!
```

**Better approaches:**

```python
# ✅ USE MULTIPLE METRICS

from sklearn.feature_selection import mutual_info_regression
from scipy.stats import spearmanr

def comprehensive_feature_selection(X, y):
    results = pd.DataFrame(index=X.columns)

    # 1. Pearson (linear)
    results['pearson'] = X.corrwith(y).abs()

    # 2. Spearman (monotonic)
    results['spearman'] = X.apply(lambda col: abs(spearmanr(col, y)[0]))

    # 3. Mutual Information (any relationship)
    results['mutual_info'] = mutual_info_regression(X, y)

    # 4. Rank by multiple criteria
    results['rank_sum'] = results.rank().sum(axis=1)

    return results.sort_values('rank_sum', ascending=False)
```

### 6.2 P-Value Obsession

**Error**: Relying solely on statistical significance (p<0.05).

**Problem:**
```python
# ❌ WRONG: Select features by p-value only
from sklearn.feature_selection import SelectKBest, f_regression

selector = SelectKBest(f_regression, k=10)
X_selected = selector.fit_transform(X, y)

# Problems:
# 1. With large n, everything is "significant" (p → 0)
# 2. Ignores effect size (tiny correlation can have p<0.001)
# 3. Assumes linear relationships
# 4. Doesn't account for interactions
```

**Better approach:**
```python
def smart_feature_selection(X, y, threshold_effect_size=0.1):
    """
    Select features by BOTH significance AND effect size
    """
    from sklearn.feature_selection import f_regression
    from scipy.stats import pearsonr

    results = []
    for col in X.columns:
        # Statistical test
        f_stat, p_value = f_regression(X[[col]], y)

        # Effect size (correlation)
        effect_size = abs(pearsonr(X[col], y)[0])

        results.append({
            'feature': col,
            'p_value': p_value[0],
            'effect_size': effect_size,
            'keep': (p_value[0] < 0.05) and (effect_size > threshold_effect_size)
        })

    return pd.DataFrame(results).sort_values('effect_size', ascending=False)
```

---

## Comprehensive Validation Checklist

Before finalizing preprocessing:

### Data Leakage Checks
- [ ] No future information used in past predictions
- [ ] Train/test split done BEFORE any transformations
- [ ] No target variable proxies in features
- [ ] All IDs removed from feature set
- [ ] Time-series ordering preserved

### Semantic Checks
- [ ] All numeric features have mathematical meaning
- [ ] Categorical variables properly encoded
- [ ] Ordinal variables preserve order
- [ ] No meaningless arithmetic operations
- [ ] Units are compatible in combined features

### Distribution Checks
- [ ] Scaler chosen based on distribution type
- [ ] Outliers handled appropriately
- [ ] Skewed distributions transformed if needed
- [ ] Heavy-tailed distributions use robust methods

### Imputation Checks
- [ ] Missing mechanism understood (MCAR/MAR/MNAR)
- [ ] Imputation method matches data type
- [ ] Missingness indicators added if informative
- [ ] No time-travel in imputation
- [ ] Imputation done within groups for grouped data

### Feature Engineering Checks
- [ ] All new features have physical meaning
- [ ] Domain expert would understand features
- [ ] Multicollinearity checked (VIF < 10)
- [ ] No curse of dimensionality (features << samples)
- [ ] Validation performance improves

### Feature Selection Checks
- [ ] Multiple metrics used (not just Pearson)
- [ ] Non-linear relationships considered
- [ ] Effect size checked (not just p-value)
- [ ] Interaction effects evaluated
- [ ] Domain knowledge incorporated

---

## Quick Reference: Error Detection

```python
def comprehensive_preprocessing_audit(df, target_col, id_cols, timestamp_col=None):
    """
    Audit preprocessing for common AI pitfalls
    """
    issues = []

    # 1. ID leakage check
    for col in id_cols:
        if df[col].nunique() / len(df) > 0.5:
            issues.append(f"❌ {col}: High cardinality ID - remove from features")

    # 2. Meaningless numeric check
    for col in df.select_dtypes(include=[np.number]).columns:
        if col == target_col:
            continue

        # Check if looks like a code
        if df[col].min() > 1000 and df[col].nunique() > 100:
            issues.append(f"⚠️ {col}: Looks like code (zipcode/phone) - check encoding")

    # 3. Time travel check (if time series)
    if timestamp_col:
        # Check if any feature has values after target
        # (Requires feature timestamps - simplified check here)
        pass

    # 4. Distribution check
    for col in df.select_dtypes(include=[np.number]).columns:
        if col == target_col:
            continue

        skewness = skew(df[col].dropna())
        if abs(skewness) > 2:
            issues.append(f"⚠️ {col}: Highly skewed ({skewness:.2f}) - consider log transform")

    # 5. Missing pattern check
    for col in df.columns:
        missing_pct = df[col].isna().sum() / len(df) * 100
        if missing_pct > 30:
            issues.append(f"⚠️ {col}: {missing_pct:.1f}% missing - check if informative")

    # 6. Correlation with target
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_cols = [c for c in numeric_cols if c != target_col]

    for col in numeric_cols:
        corr = df[[col, target_col]].corr().iloc[0, 1]
        if abs(corr) > 0.95:
            issues.append(f"❌ {col}: Near-perfect correlation ({corr:.3f}) - likely leakage!")

    # Print report
    print("="*60)
    print("PREPROCESSING AUDIT REPORT")
    print("="*60)

    if not issues:
        print("✅ No critical issues detected")
    else:
        for issue in issues:
            print(issue)

    return issues
```

---

## Summary: Anti-Patterns to Avoid

| Anti-Pattern | Detection | Fix |
|--------------|-----------|-----|
| **Time travel** | Test score >> production | Fit scaler on train only |
| **Causal inversion** | Perfect correlation with target | Remove consequence variables |
| **ID as feature** | High cardinality (>50% unique) | Use for grouping, not features |
| **Zipcode arithmetic** | Mean zipcode calculated | Treat as categorical |
| **Ordinal → One-hot** | Lost ordering | Use ordinal encoding |
| **Blind StandardScaler** | Skewness > 1 | Log transform first |
| **Unconditional mean** | Variance reduction | Conditional/predictive imputation |
| **Blind dropna()** | >30% data loss | Targeted imputation |
| **Polynomial explosion** | Features >> samples | Domain-driven only |
| **Pearson-only selection** | Missed non-linear | Use mutual information |

---

*Source: Common AI preprocessing errors observed across projects*
*Last updated: 2026-01-18*
