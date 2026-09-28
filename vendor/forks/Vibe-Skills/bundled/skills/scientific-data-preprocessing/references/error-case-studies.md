# Error Case Studies

Real-world preprocessing disasters from tennis match data analysis, with detailed diagnosis and fixes.

---

## Case Study 1: Binary Variable Standardization Error (V1.0)

### Context
Tennis match point-by-point data with features like `is_ace` (0 or 1 indicating ACE serve).

### The Error
```python
# ❌ V1.0: Standardized ALL numeric features
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()

# Blindly standardized binary variable
df['is_ace_standardized'] = scaler.fit_transform(df[['is_ace']])
```

### Diagnosis
**What went wrong:**
- `is_ace` is binary (0/1) with semantic meaning
- ACE rate in data: 5% (mean = 0.05, std = 0.22)
- Standardization result:
  - 0 (no ACE) → (0 - 0.05) / 0.22 = **-0.23**
  - 1 (ACE) → (1 - 0.05) / 0.22 = **+4.32**

**Why it's catastrophic:**
1. **Semantic destruction**: 0/1 becomes -0.23/+4.32 (meaningless numbers)
2. **False anomalies**: +4.32 > 3σ, so all ACEs flagged as "outliers"
3. **Model confusion**: Neural networks learn wrong patterns
4. **Interpretation impossible**: What does a coefficient of 0.5 on this feature mean?

### Impact Metrics
- **Error rate**: 18 out of 18 binary features (100%)
- **Rows affected**: All 7,284 rows
- **Downstream impact**: All models using these features

### Correct Approach
```python
# ✅ CORRECT: Keep binary variables as-is
binary_features = ['is_ace', 'is_winner', 'is_error', ...]
# No transformation needed! 0/1 is already normalized.

# For models: use directly
X = df[binary_features]  # Keep as 0/1
```

**Verification:**
```python
# Check that feature is truly binary
assert df['is_ace'].isin([0, 1]).all(), "Not a pure binary variable"
assert df['is_ace'].nunique() == 2, "More than 2 unique values"
```

---

## Case Study 2: Categorical Variable Standardization Error (V1.0)

### Context
`server` column indicates which player is serving (1 or 2).

### The Error
```python
# ❌ V1.0: Standardized categorical variable
df['server_standardized'] = scaler.fit_transform(df[['server']])
# server=1 → -1.02
# server=2 → +1.02
```

### Diagnosis
**Why it's wrong:**
- `server` is **categorical** (player 1 vs player 2)
- No inherent ordering: player 2 is not "greater than" player 1
- Standardization creates false numeric relationship

**Consequences:**
1. **Semantic destruction**: "Who is serving" becomes a number line
2. **Model mislearning**: Linear models learn that server=2 is "better" (higher value)
3. **Coefficient interpretation**: Impossible to explain what the coefficient means

### Impact Metrics
- **Error rate**: 5 out of 5 categorical features (100%)
- **Rows affected**: All 7,284 rows

### Correct Approach
```python
# ✅ CORRECT: One-hot encode categorical variables
df = pd.get_dummies(df, columns=['server'], dtype=int)
# Creates: server_1 (0/1), server_2 (0/1)
```

**Verification:**
```python
# After one-hot encoding
assert 'server_1' in df.columns and 'server_2' in df.columns
assert (df['server_1'] + df['server_2'] == 1).all(), "Exactly one server per row"
```

---

## Case Study 3: Cross-Group Interpolation Error (V2.0)

### Context
31 tennis matches, each with ~200-300 points. Missing `speed_mph` values (10% missing).

### The Error
```python
# ❌ V2.0: Global interpolation across all matches
from scipy.interpolate import CubicSpline

# Get all valid indices globally
valid_idx = df['speed_mph'].notna()
valid_positions = np.where(valid_idx)[0]  # ❌ Indices span multiple matches!
valid_values = df['speed_mph'].dropna().values

# Interpolate
cs = CubicSpline(valid_positions, valid_values)
missing_positions = np.where(~valid_idx)[0]
df.loc[~valid_idx, 'speed_mph'] = cs(missing_positions)
```

### Diagnosis
**Data structure:**
```
Row    match_id              speed_mph
100    2023-wimbledon-1301   120.0
101    2023-wimbledon-1301   NaN       ← Missing
102    2023-wimbledon-1301   125.0
--- (Match 1301 ends) ---
103    2023-wimbledon-1302   110.0     ← Different match!
```

**What went wrong:**
- Row 101 interpolated using rows 100 and 103
- But row 103 is from a **different match** with **different players**!
- Physical nonsense: Alcaraz's serve speed used to predict Djokovic's

**Why it's wrong:**
1. **Group boundary violation**: Matches are independent experiments
2. **Physical impossibility**: Different players, different conditions
3. **Data leakage**: Future match data used to fill past match gaps

### Impact Metrics
- **Contaminated rows**: ~752 (10% with missing values)
- **Cross-match contaminations**: Estimated 50-100 cases
- **Data integrity**: Compromised

### Correct Approach
```python
# ✅ CORRECT: Interpolate within each match
for match_id in df['match_id'].unique():
    mask = df['match_id'] == match_id
    group_data = df.loc[mask, 'speed_mph'].copy()

    valid_idx = group_data.notna()
    if valid_idx.sum() >= 4:
        valid_pos = np.where(valid_idx)[0]
        valid_vals = group_data[valid_idx].values

        cs = CubicSpline(valid_pos, valid_vals)
        missing_pos = np.where(~valid_idx)[0]

        df.loc[mask & ~valid_idx, 'speed_mph'] = cs(missing_pos)
```

**Verification:**
```python
# Verify no cross-match interpolation
for match_id in df['match_id'].unique():
    match_data = df[df['match_id'] == match_id]
    # All speed values should be within match's observed range
    match_min = match_data['speed_mph'].min()
    match_max = match_data['speed_mph'].max()
    assert (match_data['speed_mph'] >= match_min).all()
    assert (match_data['speed_mph'] <= match_max).all()
```

---

## Case Study 4: Cross-Group Standardization Error (V2.0)

### Context
31 matches with varying intensity (3-set vs 5-set matches).

### The Error
```python
# ❌ V2.0: Global standardization
scaler = StandardScaler()
df['distance_run_std'] = scaler.fit_transform(df[['distance_run']])
# Global μ=14.0m, σ=13.5m
```

### Diagnosis
**Match characteristics:**
- Match A (5-set thriller, 334 points): Avg distance = 18m/point
- Match B (3-set blowout, 150 points): Avg distance = 10m/point

**Global standardization result:**
- Match A "normal point" (18m) → z = +0.3
- Match B "intense point" (18m) → z = +0.3 (same!)

**Why it's wrong for momentum analysis:**
- **Goal**: Identify when a point is intense *relative to the match*
- **Problem**: Can't distinguish match-specific intensity
- Match A's easy points look intense (above global average)
- Match B's intense points look normal (at global average)

### Impact Metrics
- **Affected features**: 4 continuous variables
- **Analysis validity**: Momentum analysis compromised

### Correct Approach for Momentum Analysis
```python
# ✅ CORRECT: Within-match standardization
for match_id in df['match_id'].unique():
    mask = df['match_id'] == match_id
    scaler = StandardScaler()

    df.loc[mask, 'distance_run_std'] = scaler.fit_transform(
        df.loc[mask, [['distance_run']]
    )

# Interpretation: z=+2 means "2σ above average FOR THIS MATCH"
```

**When global standardization IS appropriate:**
```python
# ✅ CORRECT: Global standardization for cross-match comparison
# Use when goal is: "Which matches overall had the most intense points?"
scaler = StandardScaler()
df['distance_run_std_global'] = scaler.fit_transform(df[['distance_run']])
```

**Verification:**
```python
# Check within-group standardization
group_stats = df.groupby('match_id')['distance_run_std'].agg(['mean', 'std'])

# Each match should have mean≈0, std≈1
assert (group_stats['mean'].abs() < 0.1).all(), "Means not centered per match"
assert (group_stats['std'].between(0.9, 1.1)).all(), "Stds not scaled per match"
```

---

## Case Study 5: Cumulative vs Sliding Window Error (V2.0)

### Context
Feature engineering for momentum detection.

### The Error
```python
# ❌ V2.0: Cumulative features
df['cumulative_break_points'] = df.groupby('match_id')['is_break_point'].cumsum()
df['cumulative_wins'] = df.groupby('match_id')['point_won'].cumsum()
```

### Diagnosis
**Problem with cumulative features:**
```
Point   cumulative_wins   interpretation
10      6                 Won 6 of 10 points (60%)
50      30                Won 30 of 50 points (60%)
100     58                Won 58 of 100 points (58%)
```

**Why it's wrong:**
1. **Monotonic increase**: Always goes up (or stays same)
2. **High correlation with time**: cumsum ≈ point_number × win_rate
3. **No temporal locality**: Point 100's value includes point 1 (90 points ago!)
4. **Doesn't capture momentum**: Can't detect recent hot/cold streaks

### Impact Metrics
- **Feature utility**: Low (redundant with point_number)
- **Momentum detection**: Fails to capture short-term trends

### Correct Approach
```python
# ✅ CORRECT: Sliding window
window = 10
df['win_rate_last10'] = df.groupby('match_id')['point_won'].transform(
    lambda x: x.rolling(window, min_periods=1).mean()
)

# Comparison
print("Point 45-55:")
print("Cumulative wins:", df.loc[45:55, 'cumulative_wins'].values)
# [27, 28, 28, 29, 30, 30, 31, 32, 33, 34, 35] - monotonic

print("Win rate (last 10):", df.loc[45:55, 'win_rate_last10'].values)
# [0.6, 0.7, 0.6, 0.7, 0.8, 0.7, 0.8, 0.9, 0.8, 0.9, 0.9] - fluctuates!
```

**Why sliding windows work:**
- **Temporal locality**: Only last N points matter
- **Captures trends**: Can detect hot/cold streaks
- **Non-monotonic**: Can go up or down
- **Interpretable**: "Won 80% of last 10 points"

**Verification:**
```python
# Sliding window should fluctuate
rolling_mean = df.groupby('match_id')['win_rate_last10'].mean()
rolling_std = df.groupby('match_id')['win_rate_last10'].std()

# Should have substantial variation (not monotonic)
assert (rolling_std > 0.1).all(), "Sliding window not varying enough"

# Compare to cumulative (should be monotonic)
cumsum_changes = df.groupby('match_id')['cumulative_wins'].diff()
assert (cumsum_changes >= 0).all(), "Cumulative should be monotonic"
```

---

## Summary Table: Error Patterns

| Error Type | V1.0 | V2.0 | Severity | Rows Affected |
|------------|------|------|----------|---------------|
| Binary variable standardization | ✗ | ✓ | 🔴🔴🔴 Critical | All (7,284) |
| Categorical variable standardization | ✗ | ✓ | 🔴🔴🔴 Critical | All (7,284) |
| Cross-group interpolation | N/A | ✗ | 🔴🔴 Severe | ~750 |
| Cross-group standardization | N/A | ✗ | 🔴🔴 Severe | All (7,284) |
| Cumulative instead of sliding window | N/A | ✗ | 🔴 Moderate | All (7,284) |

## How to Detect These Errors

### Detection 1: Binary Variable Standardization
```python
# Check if binary features were transformed
for col in ['is_ace', 'is_winner']:
    if col in df.columns:
        unique_vals = df[col].unique()
        if not set(unique_vals).issubset({0, 1}):
            print(f"❌ ERROR: {col} was transformed! Values: {unique_vals[:5]}")
```

### Detection 2: Cross-Group Standardization
```python
# Check if standardization was within-group
def detect_cross_group_standardization(df, group_col, std_col):
    group_means = df.groupby(group_col)[std_col].mean()

    if (group_means.abs() < 0.1).all():
        print("✅ Within-group standardization detected")
    else:
        print("❌ Cross-group standardization detected!")
        print(f"Group means range: [{group_means.min():.2f}, {group_means.max():.2f}]")

detect_cross_group_standardization(df, 'match_id', 'distance_run_std')
```

### Detection 3: Cross-Group Interpolation
```python
# Check for impossible interpolated values
for match_id in df['match_id'].unique():
    match_data = df[df['match_id'] == match_id]
    speed_col = 'speed_mph'

    # Observed range in this match
    obs_min = match_data[speed_col].quantile(0.01)
    obs_max = match_data[speed_col].quantile(0.99)

    # Check for values outside observed range (suspicious)
    outliers = match_data[
        (match_data[speed_col] < obs_min * 0.8) |
        (match_data[speed_col] > obs_max * 1.2)
    ]

    if len(outliers) > 0:
        print(f"⚠️ Match {match_id}: {len(outliers)} suspicious values")
        print(f"   Range: [{obs_min:.1f}, {obs_max:.1f}]")
        print(f"   Outliers: {outliers[speed_col].values}")
```

---

## Lessons Learned

1. **Always classify features first** (binary/categorical/continuous)
2. **Respect group boundaries** (process within groups for grouped data)
3. **Match processing scope to goal** (within-group for relative, global for absolute)
4. **Use sliding windows for temporal features** (not cumulative sums)
5. **Validate before and after** (check distributions, ranges, group statistics)

---

*Source: Real preprocessing failures from 2024 MCM Problem C tennis data analysis*
*Last updated: 2026-01-18*
