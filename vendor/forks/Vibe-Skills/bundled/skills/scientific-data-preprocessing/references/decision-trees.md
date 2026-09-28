# Decision Trees for Preprocessing Choices

Complete decision trees for all major preprocessing decisions in grouped time-series data.

---

## Master Decision Tree

```
START: Raw grouped time-series data
│
├─ Step 1: Classify each feature
│  ├─ Binary (0/1)? → Keep as-is, go to Step 5
│  ├─ Categorical (finite discrete)? → One-hot encode, go to Step 5
│  ├─ Ordinal (ordered categories)? → Keep as numeric or ordinal encode, go to Step 2
│  └─ Continuous (infinite values)? → Go to Step 2
│
├─ Step 2: Check for missing values
│  ├─ None? → Go to Step 3
│  └─ Yes? → Choose interpolation strategy (see § Missing Value Strategy)
│
├─ Step 3: Validate data quality
│  ├─ Physical ranges OK? → Go to Step 4
│  └─ Issues found? → Clean data (see § Data Quality Validation), then Step 4
│
├─ Step 4: Choose standardization strategy
│  ├─ Is data grouped? → Go to § Standardization Scope Decision
│  └─ No groups? → Global standardization, go to Step 5
│
└─ Step 5: Feature engineering
   ├─ Need momentum features? → Go to § Time-Series Feature Engineering
   └─ Done? → Validate output (see § Validation Checklist)
```

---

## § Missing Value Strategy Decision Tree

```
Missing values detected in continuous feature
│
├─ Q1: Is data grouped (e.g., by match_id, patient_id)?
│  │
│  ├─ YES: Within-group interpolation
│  │  │
│  │  ├─ Q2: How many valid points within groups?
│  │  │  ├─ ≥4 points → Cubic spline interpolation
│  │  │  ├─ 2-3 points → Linear interpolation
│  │  │  └─ <2 points → Drop feature or impute with group mean
│  │  │
│  │  └─ Code:
│  │     for group_id in df['group_col'].unique():
│  │         mask = df['group_col'] == group_id
│  │         # Interpolate only within this group
│  │         df.loc[mask, 'feature'] = interpolate_within(df.loc[mask, 'feature'])
│  │
│  └─ NO: Global interpolation
│     │
│     ├─ Q3: Is data time-ordered?
│     │  ├─ YES → Cubic spline or linear interpolation
│     │  └─ NO → Mean/median imputation or KNN imputation
│     │
│     └─ Code:
│        df['feature'] = df['feature'].interpolate(method='cubic')
```

**When to use each method:**

| Method | Best For | Requires | Pros | Cons |
|--------|----------|----------|------|------|
| Cubic spline | Smooth continuous data | ≥4 points | Smooth, respects trends | Can overshoot |
| Linear | Fewer data points | ≥2 points | Simple, fast | Less smooth |
| Group mean | Very sparse data | ≥1 point | Safe, no overshoot | Loses variance |
| Forward fill | Time-series | Ordered data | Preserves last value | Can propagate errors |

---

## § Standardization Scope Decision Tree

```
Continuous feature ready for standardization
│
├─ Q1: Is data grouped?
│  │
│  ├─ NO → Global standardization
│  │  └─ Code:
│  │     scaler = StandardScaler()
│  │     df['feature_std'] = scaler.fit_transform(df[['feature']])
│  │
│  └─ YES → Q2: What is your analysis goal?
│     │
│     ├─ RELATIVE (within-group comparison)
│     │  Example: "Was this tennis point intense FOR THIS MATCH?"
│     │  │
│     │  └─ Within-group standardization
│     │     Code:
│     │     for group_id in df['group_col'].unique():
│     │         mask = df['group_col'] == group_id
│     │         scaler = StandardScaler()
│     │         df.loc[mask, 'feature_std'] = scaler.fit_transform(
│     │             df.loc[mask, [['feature']]
│     │         )
│     │
│     │     Interpretation: z=+2 means "2σ above average IN THIS GROUP"
│     │
│     └─ ABSOLUTE (cross-group comparison)
│        Example: "Which matches overall had the most intense points?"
│        │
│        └─ Global standardization
│           Code:
│           scaler = StandardScaler()
│           df['feature_std'] = scaler.fit_transform(df[['feature']])
│
│           Interpretation: z=+2 means "2σ above average ACROSS ALL GROUPS"
```

**Decision helper: Intraclass Correlation (ICC)**

```python
def recommend_standardization_scope(df, group_col, feature_col):
    """
    Automatically recommend scope based on variance decomposition
    """
    # Variance within groups
    within_var = df.groupby(group_col)[feature_col].var().mean()

    # Total variance
    total_var = df[feature_col].var()

    # Variance between groups
    between_var = total_var - within_var

    # Intraclass correlation
    icc = between_var / total_var

    if icc > 0.5:
        print(f"✅ HIGH between-group variance (ICC={icc:.2f})")
        print("   Recommendation: Within-group standardization")
        print("   Reason: Groups are very different from each other")
        return 'within_group'

    else:
        print(f"✅ LOW between-group variance (ICC={icc:.2f})")
        print("   Recommendation: Global standardization")
        print("   Reason: Groups are similar to each other")
        return 'global'

# Usage
scope = recommend_standardization_scope(df, 'match_id', 'distance_run')
```

**Interpretation:**
- **ICC > 0.5**: Groups are very different → Use within-group standardization
- **ICC < 0.5**: Groups are similar → Global standardization is acceptable

---

## § Time-Series Feature Engineering Decision Tree

```
Need features for momentum/trend analysis
│
├─ Q1: What temporal pattern do you want to capture?
│  │
│  ├─ RECENT TREND (last N observations)
│  │  Example: "Win rate in last 10 points"
│  │  │
│  │  └─ Sliding window aggregation
│  │     Code:
│  │     window = 10
│  │     df['recent_mean'] = df.groupby('group_col')['target'].transform(
│  │         lambda x: x.rolling(window, min_periods=1).mean()
│  │     )
│  │
│  │     Options: .mean(), .sum(), .std(), .max(), .min()
│  │
│  ├─ CUMULATIVE TOTAL (all observations up to now)
│  │  Example: "Total points won so far"
│  │  │
│  │  ⚠️  WARNING: Usually not recommended for momentum analysis!
│  │  │  (See § Cumulative vs Sliding Window)
│  │  │
│  │  └─ Cumulative sum
│  │     Code:
│  │     df['cumulative'] = df.groupby('group_col')['target'].cumsum()
│  │
│  ├─ STREAK (consecutive wins/losses)
│  │  Example: "Currently on 3-point winning streak"
│  │  │
│  │  └─ Streak calculator
│  │     Code:
│  │     def calculate_streak(series):
│  │         streaks = []
│  │         current = 0
│  │         for val in series:
│  │             if val == 1:
│  │                 current = current + 1 if current >= 0 else 1
│  │             else:
│  │                 current = current - 1 if current <= 0 else -1
│  │             streaks.append(current)
│  │         return streaks
│  │
│  │     df['streak'] = df.groupby('group_col')['won'].transform(
│  │         lambda x: calculate_streak(x)
│  │     )
│  │
│  └─ CHANGE/DELTA (difference from previous)
│     Example: "Change in distance from last point"
│     │
│     └─ Difference calculation
│        Code:
│        df['delta'] = df.groupby('group_col')['feature'].diff()
```

---

## § Cumulative vs Sliding Window Decision

```
Choosing between cumulative and sliding window
│
├─ Q: What is your goal?
│  │
│  ├─ Track TOTAL accumulated (e.g., "total points won")
│  │  └─ Use cumulative sum
│  │     ✅ Good for: Total scores, cumulative progress
│  │     ❌ Bad for: Momentum, recent performance
│  │
│  └─ Detect RECENT TREND (e.g., "hot/cold streak")
│     └─ Use sliding window
│        ✅ Good for: Momentum, recent form, trend detection
│        ❌ Bad for: Total scores, progress tracking
```

**Visual comparison:**

```
Point:    10   20   30   40   50   60   70   80   90  100
Won?:      1    1    0    1    1    0    0    1    1    1

Cumulative:
wins:      6   12   16   22   29   32   35   42   49   58
trend:     ↗    ↗    ↗    ↗    ↗    ↗    ↗    ↗    ↗    ↗   (always increasing)

Sliding (N=10):
win_rate: 0.6  0.6  0.5  0.6  0.6  0.5  0.4  0.5  0.6  0.7
trend:     →    →    ↘    ↗    →    ↘    ↘    ↗    ↗    ↗   (fluctuates!)
```

**Key difference:**
- Cumulative is **monotonic** (always increases or stays same)
- Sliding window **fluctuates** (captures local changes)

---

## § Data Quality Validation Decision Tree

```
Validating data quality before processing
│
├─ Check 1: Physical range validation
│  │
│  ├─ Q: Does feature have known physical limits?
│  │  Example: speed_mph should be < 170 (world record)
│  │
│  ├─ YES → Define range and check
│  │  Code:
│  │  def validate_range(df, feature, min_val, max_val):
│  │      out_of_range = df[
│  │          (df[feature] < min_val) | (df[feature] > max_val)
│  │      ]
│  │      if len(out_of_range) > 0:
│  │          print(f"❌ {len(out_of_range)} values outside [{min_val}, {max_val}]")
│  │          return False
│  │      return True
│  │
│  │  validate_range(df, 'speed_mph', 50, 170)
│  │
│  └─ NO → Go to Check 2
│
├─ Check 2: Statistical outlier detection
│  │
│  ├─ Calculate: mean, std, min, max
│  │  Code:
│  │  stats = df[feature].describe()
│  │  print(stats)
│  │
│  ├─ Q: Is std > mean?
│  │  ├─ YES → ⚠️  Highly skewed or data errors
│  │  │         Investigate: print(df[feature].value_counts())
│  │  └─ NO → Probably OK
│  │
│  └─ Q: Are there extreme outliers (>5σ)?
│     Code:
│     mean = df[feature].mean()
│     std = df[feature].std()
│     extreme = df[abs(df[feature] - mean) > 5 * std]
│     if len(extreme) > 0:
│         print(f"⚠️  {len(extreme)} extreme outliers (>5σ)")
│
├─ Check 3: Missing value patterns
│  │
│  ├─ Q: Is missing data random or systematic?
│  │
│  ├─ By group:
│  │  Code:
│  │  missing_by_group = df.groupby('group_col')[feature].apply(
│  │      lambda x: x.isna().sum() / len(x) * 100
│  │  )
│  │  print(missing_by_group)
│  │
│  │  ├─ Uniform across groups? → Random missing (OK)
│  │  └─ Some groups >50% missing? → Systematic issue (investigate)
│  │
│  └─ By time:
│     Code:
│     df['missing_flag'] = df[feature].isna().astype(int)
│     plt.plot(df.groupby('time_col')['missing_flag'].mean())
│
└─ Check 4: Unit consistency
   │
   └─ Q: Are values in expected units?
      Example: speed in mph vs km/h?
      │
      Code:
      # Check if values cluster around expected range
      median = df[feature].median()
      if feature == 'speed_mph':
          if median < 50:
              print("⚠️  Median too low - might be in different units")
          elif median > 200:
              print("⚠️  Median too high - might be in different units")
```

---

## § Feature Type Classification Decision Tree

```
Given a numeric column, determine its true type
│
├─ Q1: How many unique values?
│  │
│  ├─ 2 values → Binary variable
│  │  └─ Q2: Are values 0 and 1?
│  │     ├─ YES → ✅ Pure binary (keep as-is)
│  │     └─ NO (e.g., 1 and 2) → Recode to 0/1, then keep as-is
│  │
│  ├─ 3-10 values → Likely categorical or ordinal
│  │  └─ Q3: Do values have meaningful order?
│  │     ├─ YES → Ordinal (e.g., low/med/high = 1/2/3)
│  │     │         Keep as numeric or use ordinal encoding
│  │     └─ NO → Categorical (e.g., player_id = 1/2/3/...)
│  │              One-hot encode
│  │
│  └─ >10 values → Likely continuous
│     └─ Q4: Are values discrete counts or truly continuous?
│        ├─ Discrete counts (e.g., rally_count = 1,2,3,...)
│        │  └─ Treat as continuous for standardization
│        │     (or keep as-is for tree models)
│        └─ Continuous (e.g., distance_run = 5.376, 21.384, ...)
│           └─ ✅ Standardize (within-group or global)
```

**Code implementation:**

```python
def classify_feature(series):
    """
    Automatically classify feature type
    """
    n_unique = series.nunique()

    if n_unique == 2:
        return 'binary', "Keep as 0/1"

    elif n_unique <= 10:
        # Check if values are sequential (ordinal) or arbitrary (categorical)
        unique_vals = sorted(series.unique())
        if unique_vals == list(range(min(unique_vals), max(unique_vals) + 1)):
            return 'ordinal', "Sequential values - check if ordered"
        else:
            return 'categorical', "One-hot encode"

    else:
        # Check if integer counts or continuous
        if series.dtype == 'int64':
            return 'discrete_count', "Treat as continuous or keep as-is"
        else:
            return 'continuous', "Standardize (within-group or global)"

# Usage
for col in df.select_dtypes(include=['int64', 'float64']).columns:
    ftype, action = classify_feature(df[col])
    print(f"{col}: {ftype} → {action}")
```

---

## Summary: Quick Decision Lookup

| Situation | Decision | Code Pattern |
|-----------|----------|--------------|
| Binary feature (0/1) | Keep as-is | `# No transformation` |
| Categorical feature | One-hot encode | `pd.get_dummies(df, columns=[...])` |
| Continuous + grouped + momentum analysis | Within-group standardize | `for group: scaler.fit_transform(group)` |
| Continuous + grouped + cross-match comparison | Global standardize | `scaler.fit_transform(all_data)` |
| Missing values + grouped | Within-group interpolate | `for group: interpolate(group)` |
| Momentum feature | Sliding window | `.rolling(N).mean()` |
| Total/cumulative feature | Cumulative sum | `.cumsum()` |

---

*Source: Lessons from 2024 MCM Problem C tennis data preprocessing*
*Last updated: 2026-01-18*
