# Validation Checklist for Scientific Data Preprocessing

Use this checklist before and after preprocessing to ensure data integrity.

---

## Pre-Processing Validation

### ✅ 1. Data Structure Understanding

- [ ] Confirmed data has natural groupings (match_id, patient_id, session_id, etc.)
- [ ] Identified group column name: `________________`
- [ ] Number of groups: `________________`
- [ ] Average observations per group: `________________`
- [ ] Data is time-ordered: Yes / No
- [ ] Time column name (if applicable): `________________`

### ✅ 2. Feature Classification

For each numeric feature, classify:

| Feature | Type | Action | Notes |
|---------|------|--------|-------|
| _______ | Binary/Categorical/Continuous | Keep/One-hot/Standardize | |
| _______ | Binary/Categorical/Continuous | Keep/One-hot/Standardize | |
| _______ | Binary/Categorical/Continuous | Keep/One-hot/Standardize | |

**Classification code:**
```python
for col in df.select_dtypes(include=['int64', 'float64']).columns:
    n_unique = df[col].nunique()
    print(f"{col}: {n_unique} unique values")

    if n_unique == 2:
        print(f"  → Binary: Keep as-is")
    elif n_unique <= 10:
        print(f"  → Categorical or ordinal: One-hot encode or keep")
    else:
        print(f"  → Continuous: Standardize")
```

### ✅ 3. Data Quality Checks

- [ ] **Physical range validation**: All continuous features within reasonable bounds
  ```python
  # Example
  assert df['speed_mph'].max() < 170, "Speed exceeds world record"
  assert df['distance_meters'].min() >= 0, "Negative distance"
  ```

- [ ] **Unit consistency**: Values in expected units (not km/h when expecting mph, etc.)
  ```python
  # Check median is in expected range
  print(f"Speed median: {df['speed_mph'].median()}")  # Should be ~110-120 for tennis
  ```

- [ ] **No extreme outliers**: Check for data errors (>5σ from mean)
  ```python
  for col in continuous_features:
      mean = df[col].mean()
      std = df[col].std()
      extreme = df[abs(df[col] - mean) > 5 * std]
      if len(extreme) > 0:
          print(f"⚠️  {col}: {len(extreme)} extreme outliers")
  ```

- [ ] **Missing value pattern**: Is missingness random or systematic?
  ```python
  # Check by group
  missing_by_group = df.groupby('group_col').apply(
      lambda g: g.isna().sum() / len(g) * 100
  )
  print(missing_by_group.describe())
  ```

### ✅ 4. Analysis Goal Definition

- [ ] Goal is **within-group (relative)** comparison → Use within-group standardization
  - Example: "Was this point intense FOR THIS MATCH?"

- [ ] Goal is **cross-group (absolute)** comparison → Use global standardization
  - Example: "Which matches had the most intense points overall?"

- [ ] Goal is **momentum/trend detection** → Use sliding window features
  - Window size: `________________`

---

## During Processing Validation

### ✅ 5. Interpolation Validation

- [ ] **Interpolation scope**: Within-group only (not cross-group)
  ```python
  # Verify: interpolated values within observed group range
  for group_id in df['group_col'].unique():
      group_data = df[df['group_col'] == group_id]
      obs_min = group_data['feature'].quantile(0.01)
      obs_max = group_data['feature'].quantile(0.99)

      # Check interpolated values
      suspicious = group_data[
          (group_data['feature'] < obs_min * 0.8) |
          (group_data['feature'] > obs_max * 1.2)
      ]
      assert len(suspicious) == 0, f"Group {group_id}: suspicious interpolation"
  ```

- [ ] **No extrapolation**: Interpolated values between observed points, not beyond

### ✅ 6. Standardization Validation

- [ ] **Within-group standardization** (if applicable):
  ```python
  # Each group should have mean≈0, std≈1
  group_stats = df.groupby('group_col')['feature_std'].agg(['mean', 'std'])

  assert (group_stats['mean'].abs() < 0.1).all(), "Means not centered per group"
  assert (group_stats['std'].between(0.9, 1.1)).all(), "Stds not scaled per group"
  ```

- [ ] **Global standardization** (if applicable):
  ```python
  # Overall should have mean≈0, std≈1
  assert abs(df['feature_std'].mean()) < 0.01, "Mean not centered globally"
  assert abs(df['feature_std'].std() - 1.0) < 0.01, "Std not scaled globally"
  ```

### ✅ 7. Feature Type Preservation

- [ ] **Binary features unchanged**:
  ```python
  for col in binary_features:
      assert df[col].isin([0, 1]).all(), f"{col} not binary!"
  ```

- [ ] **Categorical features one-hot encoded**:
  ```python
  # Check for new one-hot columns
  original_cats = ['server', 'serve_number']
  for cat in original_cats:
      onehot_cols = [c for c in df.columns if c.startswith(f"{cat}_")]
      assert len(onehot_cols) > 0, f"{cat} not one-hot encoded"
      # Exactly one should be 1 per row
      assert (df[onehot_cols].sum(axis=1) == 1).all(), f"{cat} one-hot sum != 1"
  ```

---

## Post-Processing Validation

### ✅ 8. Output Data Quality

- [ ] **No missing values** (after interpolation):
  ```python
  assert df[continuous_features].isna().sum().sum() == 0, "Still have missing values"
  ```

- [ ] **Column count**:
  - Original columns: `________________`
  - New columns added: `________________`
  - Expected total: `________________`
  - Actual total: `________________`

- [ ] **Row count unchanged**:
  ```python
  assert len(df) == original_row_count, "Rows were dropped!"
  ```

### ✅ 9. Feature Distribution Sanity

- [ ] **Continuous features have reasonable distributions**:
  ```python
  for col in continuous_features:
      std_col = f"{col}_std"
      if std_col in df.columns:
          # Standardized should be roughly normal(-3, 3)
          assert df[std_col].min() > -10, f"{col}: extreme negative z-score"
          assert df[std_col].max() < 10, f"{col}: extreme positive z-score"

          # Should have values across range
          assert df[std_col].std() > 0.5, f"{col}: standardized but no variance"
  ```

- [ ] **Binary features still binary**:
  ```python
  for col in binary_features:
      unique_vals = df[col].unique()
      assert set(unique_vals).issubset({0, 1}), f"{col} not binary anymore!"
  ```

### ✅ 10. Feature Engineering Validation

- [ ] **Sliding window features vary** (not monotonic):
  ```python
  for col in sliding_window_features:
      # Should have substantial variation
      std = df.groupby('group_col')[col].std().mean()
      assert std > 0.1, f"{col}: sliding window not varying"
  ```

- [ ] **Cumulative features monotonic** (if any):
  ```python
  for col in cumulative_features:
      # Diffs should be non-negative
      diffs = df.groupby('group_col')[col].diff()
      assert (diffs[diffs.notna()] >= 0).all(), f"{col}: cumulative not monotonic"
  ```

### ✅ 11. Group Boundary Validation

- [ ] **No cross-group leakage**:
  ```python
  # For sliding windows, first N values in each group should use min_periods
  for group_id in df['group_col'].unique():
      group_data = df[df['group_col'] == group_id]

      # First value should exist (min_periods=1)
      first_val = group_data.iloc[0]['rolling_feature']
      assert not pd.isna(first_val), f"Group {group_id}: first rolling value is NaN"

      # First value should NOT equal last value from previous group
      # (would indicate cross-group contamination)
  ```

---

## Common Error Detection

### ⚠️ Error Pattern 1: Binary Variable Transformation

```python
# Detect if binary features were incorrectly transformed
for col in ['is_ace', 'is_winner', 'is_error']:
    if col in df.columns:
        unique_vals = df[col].unique()
        if not set(unique_vals).issubset({0, 1}):
            print(f"❌ ERROR: {col} was transformed!")
            print(f"   Values: {unique_vals}")
            print(f"   Expected: [0, 1]")
```

### ⚠️ Error Pattern 2: Cross-Group Standardization

```python
# Detect if standardization was done cross-group
for std_col in [c for c in df.columns if c.endswith('_std')]:
    group_means = df.groupby('group_col')[std_col].mean()

    if (group_means.abs() < 0.1).all():
        print(f"✅ {std_col}: Within-group standardization")
    else:
        print(f"❌ {std_col}: Cross-group standardization detected!")
        print(f"   Group means range: [{group_means.min():.2f}, {group_means.max():.2f}]")
        print(f"   Expected: All ≈ 0")
```

### ⚠️ Error Pattern 3: Cross-Group Interpolation

```python
# Detect suspicious interpolated values (outside group's observed range)
for group_id in df['group_col'].unique():
    group_data = df[df['group_col'] == group_id]

    for col in continuous_features:
        # Original observed range
        obs_min = group_data[col].quantile(0.05)
        obs_max = group_data[col].quantile(0.95)

        # Check for values well outside range
        suspicious = group_data[
            (group_data[col] < obs_min * 0.7) |
            (group_data[col] > obs_max * 1.3)
        ]

        if len(suspicious) > 0:
            print(f"⚠️  Group {group_id}, {col}:")
            print(f"   Observed range: [{obs_min:.2f}, {obs_max:.2f}]")
            print(f"   Suspicious values: {suspicious[col].values}")
```

---

## Final Sign-Off Checklist

Before using preprocessed data:

- [ ] All binary features are still 0/1
- [ ] All categorical features are one-hot encoded
- [ ] Continuous features standardized appropriately (within-group or global)
- [ ] No missing values remain (or documented and acceptable)
- [ ] No cross-group contamination detected
- [ ] Sliding window features show variation (not monotonic)
- [ ] Data quality checks passed (no extreme outliers, physical ranges OK)
- [ ] Row count unchanged from original
- [ ] All processing steps documented
- [ ] Sample validation: Manually check a few groups end-to-end

---

## Automated Validation Script

Save and run this script:

```python
def validate_preprocessing(df_original, df_processed, group_col, config):
    """
    Automated validation of preprocessing pipeline

    Args:
        df_original: Original raw data
        df_processed: Processed data
        group_col: Group column name
        config: Dict with keys:
            - binary_features: List of binary feature names
            - categorical_features: List of categorical feature names
            - continuous_features: List of continuous feature names
            - standardization_scope: 'within_group' or 'global'
    """
    print("=" * 60)
    print("PREPROCESSING VALIDATION REPORT")
    print("=" * 60)

    # 1. Row count
    assert len(df_original) == len(df_processed), "❌ Row count changed!"
    print("✅ Row count preserved:", len(df_processed))

    # 2. Binary features
    print("\n--- Binary Features ---")
    for col in config['binary_features']:
        if col in df_processed.columns:
            vals = df_processed[col].unique()
            if set(vals).issubset({0, 1}):
                print(f"✅ {col}: Still binary")
            else:
                print(f"❌ {col}: NOT BINARY! Values: {vals}")

    # 3. Categorical features (one-hot)
    print("\n--- Categorical Features ---")
    for col in config['categorical_features']:
        onehot_cols = [c for c in df_processed.columns if c.startswith(f"{col}_")]
        if len(onehot_cols) > 0:
            # Check sum
            row_sums = df_processed[onehot_cols].sum(axis=1)
            if (row_sums == 1).all():
                print(f"✅ {col}: One-hot encoded ({len(onehot_cols)} categories)")
            else:
                print(f"❌ {col}: One-hot sum != 1")
        else:
            print(f"⚠️  {col}: No one-hot columns found")

    # 4. Continuous features (standardization)
    print("\n--- Continuous Features ---")
    for col in config['continuous_features']:
        std_col = f"{col}_std"
        if std_col in df_processed.columns:
            if config['standardization_scope'] == 'within_group':
                # Check within-group
                group_stats = df_processed.groupby(group_col)[std_col].agg(['mean', 'std'])
                if (group_stats['mean'].abs() < 0.1).all() and \
                   (group_stats['std'].between(0.9, 1.1)).all():
                    print(f"✅ {col}: Within-group standardization correct")
                else:
                    print(f"❌ {col}: Within-group standardization WRONG")
                    print(f"   Group means: {group_stats['mean'].describe()}")

            elif config['standardization_scope'] == 'global':
                # Check global
                mean = df_processed[std_col].mean()
                std = df_processed[std_col].std()
                if abs(mean) < 0.01 and abs(std - 1.0) < 0.01:
                    print(f"✅ {col}: Global standardization correct")
                else:
                    print(f"❌ {col}: Global standardization WRONG (mean={mean:.3f}, std={std:.3f})")

    # 5. Missing values
    print("\n--- Missing Values ---")
    missing_count = df_processed[config['continuous_features']].isna().sum().sum()
    if missing_count == 0:
        print(f"✅ No missing values")
    else:
        print(f"❌ {missing_count} missing values remain")

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)

# Usage
config = {
    'binary_features': ['is_ace', 'is_winner'],
    'categorical_features': ['server', 'serve_number'],
    'continuous_features': ['distance_run', 'speed_mph'],
    'standardization_scope': 'within_group'  # or 'global'
}

validate_preprocessing(df_original, df_processed, 'match_id', config)
```

---

*Source: Validation best practices from scientific data preprocessing*
*Last updated: 2026-01-18*
