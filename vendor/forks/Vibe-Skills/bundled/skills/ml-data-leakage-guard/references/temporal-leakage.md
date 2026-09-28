# Temporal Leakage in Time Series

Comprehensive guide to detecting and preventing leakage in time series and temporal data.

## Core Principle for Temporal Data

**The Causality Rule**: You can only use information from the past to predict the future. Any feature that uses future information, even indirectly, is leakage.

## 1. Future Functions

### 1.1 Centered Rolling Windows

**Problem**: Using `center=True` in rolling window calculations includes future data.

**Why It's Leakage**: At time t, you don't have access to data from t+1, t+2, etc.

**Examples**:

```python
# ❌ WRONG: Centered rolling average
df['rolling_avg'] = df['value'].rolling(window=7, center=True).mean()
# At time t, this uses values from t-3 to t+3

# ❌ WRONG: Centered rolling std
df['rolling_std'] = df['value'].rolling(window=7, center=True).std()

# ✅ CORRECT: Backward-looking rolling window
df['rolling_avg'] = df['value'].rolling(window=7, min_periods=1).mean()
# At time t, this uses values from t-6 to t (only past data)

# ✅ CORRECT: Explicit backward window
df['rolling_avg'] = df['value'].shift(1).rolling(window=7).mean()
# Shift by 1 to ensure we don't include current value
```

**Impact**: CRITICAL - Model uses future to predict present.

### 1.2 Global Aggregations Across Time

**Problem**: Computing statistics that aggregate across all time periods.

**Why It's Leakage**: At prediction time t, you don't have access to data from t+1 onwards.

**Examples**:

```python
# ❌ WRONG: Global daily average (includes future days)
df['daily_avg'] = df.groupby('date')['value'].transform('mean')
# This computes average for entire day, including future hours

# ❌ WRONG: User lifetime statistics (includes future)
df['user_total_purchases'] = df.groupby('user_id')['purchase'].transform('sum')
# This includes all future purchases

# ❌ WRONG: Seasonal averages (includes future seasons)
df['seasonal_avg'] = df.groupby('season')['value'].transform('mean')

# ✅ CORRECT: Expanding window (cumulative statistics)
df = df.sort_values(['user_id', 'timestamp'])
df['user_cumulative_purchases'] = df.groupby('user_id')['purchase'].cumsum()
# Only includes past purchases

# ✅ CORRECT: Time-aware aggregation
df = df.sort_values('timestamp')
df['cumulative_avg'] = df['value'].expanding().mean()
# Only uses data up to current point
```

**Impact**: CRITICAL - Severe temporal leakage.

### 1.3 Lag Features with Incorrect Shifts

**Problem**: Creating lag features that don't properly shift data.

**Why It's Leakage**: Incorrect shifts can include current or future values.

**Examples**:

```python
# ❌ WRONG: No shift (includes current value)
df['value_lag1'] = df['value']  # This is just the current value!

# ❌ WRONG: Negative shift (uses future)
df['value_lag1'] = df['value'].shift(-1)  # This is the NEXT value

# ❌ WRONG: Lag without sorting
df['value_lag1'] = df['value'].shift(1)  # If not sorted by time, this is meaningless

# ✅ CORRECT: Proper lag features
df = df.sort_values(['entity_id', 'timestamp'])
df['value_lag1'] = df.groupby('entity_id')['value'].shift(1)
df['value_lag7'] = df.groupby('entity_id')['value'].shift(7)
# Properly shifted past values
```

**Impact**: CRITICAL if using future values, HIGH if using current value.

## 2. Incorrect Time-Based Splits

### 2.1 Random Split on Temporal Data

**Problem**: Using random train-test split on time series data.

**Why It's Leakage**: Random split means using "tomorrow's data" to predict "yesterday".

**Examples**:

```python
# ❌ WRONG: Random split on time series
X_train, X_test = train_test_split(df, test_size=0.2, random_state=42)
# Training set may contain data from 2024, test set from 2023

# ❌ WRONG: Shuffle in time series CV
from sklearn.model_selection import KFold
kfold = KFold(n_splits=5, shuffle=True)  # Shuffle=True breaks temporal order

# ✅ CORRECT: Time-based split
split_date = '2024-01-01'
train = df[df['date'] < split_date]
test = df[df['date'] >= split_date]

# ✅ CORRECT: Time series cross-validation
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X[train_idx], X[test_idx]
    # Each fold respects temporal order
```

**Impact**: CRITICAL - Completely invalidates model for production.

### 2.2 Overlapping Train-Test Periods

**Problem**: Training and test periods overlap in time.

**Why It's Leakage**: Model sees data from the same time period it's being tested on.

**Examples**:

```python
# ❌ WRONG: Overlapping periods
train = df[(df['date'] >= '2023-01-01') & (df['date'] <= '2024-01-01')]
test = df[(df['date'] >= '2023-06-01') & (df['date'] <= '2024-06-01')]
# 6 months of overlap!

# ❌ WRONG: No gap between train and test
train = df[df['date'] < '2024-01-01']
test = df[df['date'] >= '2024-01-01']
# If you're predicting 7 days ahead, you need a gap

# ✅ CORRECT: Non-overlapping periods with gap
train = df[df['date'] < '2023-12-01']
test = df[(df['date'] >= '2024-01-01') & (df['date'] < '2024-02-01')]
# 1-month gap between train and test

# ✅ CORRECT: Gap for prediction horizon
prediction_horizon = 7  # days
train_end = '2024-01-01'
test_start = pd.to_datetime(train_end) + pd.Timedelta(days=prediction_horizon)
train = df[df['date'] < train_end]
test = df[df['date'] >= test_start]
```

**Impact**: HIGH - Test performance doesn't reflect production reality.

## 3. Feature Engineering Temporal Leakage

### 3.1 Ratio Features with Future Data

**Problem**: Computing ratios or differences that include future information.

**Why It's Leakage**: At time t, you don't know future values.

**Examples**:

```python
# ❌ WRONG: Ratio to future value
df['price_change_ratio'] = df['price'] / df['price'].shift(-1)
# Uses next period's price

# ❌ WRONG: Difference to future
df['sales_growth'] = df['sales'].shift(-1) - df['sales']
# Uses next period's sales

# ✅ CORRECT: Ratio to past value
df = df.sort_values('date')
df['price_change_ratio'] = df['price'] / df['price'].shift(1)
# Uses previous period's price

# ✅ CORRECT: Growth from past
df['sales_growth'] = df['sales'] - df['sales'].shift(1)
# Current minus previous
```

**Impact**: CRITICAL - Direct use of future information.

### 3.2 Time-Based Aggregations Without Cutoff

**Problem**: Aggregating data without respecting the prediction time cutoff.

**Why It's Leakage**: At prediction time t, you only have data up to t.

**Examples**:

```python
# ❌ WRONG: Monthly average without time cutoff
df['monthly_avg'] = df.groupby(['user_id', 'month'])['value'].transform('mean')
# If predicting mid-month, this includes rest of month

# ❌ WRONG: Weekly statistics without cutoff
df['weekly_sum'] = df.groupby(['user_id', 'week'])['value'].transform('sum')

# ✅ CORRECT: Expanding window by time
df = df.sort_values(['user_id', 'timestamp'])
df['cumulative_monthly_avg'] = df.groupby(['user_id', 'month'])['value'].expanding().mean().reset_index(0, drop=True)

# ✅ CORRECT: Use only past complete periods
df['prev_month_avg'] = df.groupby('user_id')['value'].shift(30).rolling(30).mean()
# Average of previous 30 days, not including current day
```

**Impact**: HIGH - Subtle but significant leakage.

### 3.3 Sequence Features with Look-Ahead

**Problem**: Creating sequence features that look ahead in time.

**Why It's Leakage**: At time t, you can't see future sequence elements.

**Examples**:

```python
# ❌ WRONG: Next N events
df['next_3_events'] = df.groupby('user_id')['event'].shift(-3)

# ❌ WRONG: Time until next event (requires knowing when next event occurs)
df['time_to_next_event'] = df.groupby('user_id')['timestamp'].shift(-1) - df['timestamp']

# ✅ CORRECT: Previous N events
df = df.sort_values(['user_id', 'timestamp'])
df['prev_3_events'] = df.groupby('user_id')['event'].shift(3)

# ✅ CORRECT: Time since last event
df['time_since_last_event'] = df['timestamp'] - df.groupby('user_id')['timestamp'].shift(1)
```

**Impact**: CRITICAL - Uses future information.

## 4. Domain-Specific Temporal Leakage

### 4.1 Financial Data

**Problem**: Using future prices, returns, or market information.

**Examples**:

```python
# ❌ WRONG: Future returns
df['next_day_return'] = (df['close'].shift(-1) - df['close']) / df['close']

# ❌ WRONG: Forward-looking volatility
df['future_volatility'] = df['returns'].shift(-20).rolling(20).std()

# ✅ CORRECT: Historical returns
df['prev_day_return'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1)

# ✅ CORRECT: Historical volatility
df['historical_volatility'] = df['returns'].rolling(20).std()
```

### 4.2 Healthcare/Medical Data

**Problem**: Using information only available after diagnosis or treatment.

**Examples**:

```python
# ❌ WRONG: Treatment outcome as feature
# Predicting disease severity using "treatment_success" as feature
# Treatment outcome is only known AFTER treatment

# ❌ WRONG: Future lab results
# Predicting readmission using "discharge_lab_values"
# If predicting at admission, discharge values aren't available yet

# ✅ CORRECT: Use only admission data
# Predicting readmission using: admission_lab_values, vital_signs,
# medical_history, demographics
```

### 4.3 E-commerce/User Behavior

**Problem**: Using future user actions or lifetime statistics.

**Examples**:

```python
# ❌ WRONG: Future purchase behavior
df['will_purchase_next_month'] = df.groupby('user_id')['purchase'].shift(-30)

# ❌ WRONG: Lifetime value (includes future)
df['lifetime_value'] = df.groupby('user_id')['purchase_amount'].transform('sum')

# ✅ CORRECT: Historical purchase behavior
df['purchased_last_month'] = df.groupby('user_id')['purchase'].shift(30)

# ✅ CORRECT: Value to date
df = df.sort_values(['user_id', 'date'])
df['value_to_date'] = df.groupby('user_id')['purchase_amount'].cumsum()
```

## 5. Detection Strategies for Temporal Leakage

### 5.1 Temporal Consistency Check

```python
def check_temporal_consistency(df, date_col, feature_cols):
    """Check if features only use past information."""
    df = df.sort_values(date_col)

    for feature in feature_cols:
        # Check if feature values change when we add future data
        # If they do, the feature uses future information

        # Compute feature on first 80% of data
        split_idx = int(len(df) * 0.8)
        df_past = df.iloc[:split_idx].copy()

        # Recompute feature (this would need actual feature computation logic)
        # If feature values in df_past differ from df, it uses future data

        print(f"Checking {feature} for temporal consistency...")

    return True
```

### 5.2 Walk-Forward Validation

```python
def walk_forward_validation(df, date_col, target_col, model, window_size=30):
    """
    Validate model using walk-forward approach.
    If performance degrades significantly in walk-forward vs. random split,
    suspect temporal leakage.
    """
    df = df.sort_values(date_col)
    scores = []

    for i in range(window_size, len(df), window_size):
        train = df.iloc[:i]
        test = df.iloc[i:i+window_size]

        X_train = train.drop(target_col, axis=1)
        y_train = train[target_col]
        X_test = test.drop(target_col, axis=1)
        y_test = test[target_col]

        model.fit(X_train, y_train)
        score = model.score(X_test, y_test)
        scores.append(score)

    return scores
```

### 5.3 Feature Availability Audit

```python
def audit_feature_availability(features_dict):
    """
    Document when each feature becomes available.

    features_dict format:
    {
        'feature_name': {
            'available_at': 'time_description',
            'depends_on_future': True/False
        }
    }
    """
    print("Feature Availability Audit")
    print("=" * 50)

    for feature, info in features_dict.items():
        status = "❌ LEAKAGE" if info['depends_on_future'] else "✅ OK"
        print(f"{status} | {feature}")
        print(f"  Available at: {info['available_at']}")
        print()

# Example usage:
features = {
    'user_age': {
        'available_at': 'Always available from user profile',
        'depends_on_future': False
    },
    'next_purchase_amount': {
        'available_at': 'Only after next purchase occurs',
        'depends_on_future': True
    },
    'cumulative_purchases': {
        'available_at': 'At any time, computed from past purchases',
        'depends_on_future': False
    }
}

audit_feature_availability(features)
```

## 6. Best Practices for Temporal Data

1. **Always sort by time**: Before any feature engineering, sort by timestamp
2. **Use expanding windows**: For cumulative statistics, use `.expanding()` not `.transform()`
3. **Explicit lags**: Use `.shift(n)` with positive n for past data
4. **Time-based splits**: Never use random splits on temporal data
5. **Add prediction gap**: Include gap between train and test equal to prediction horizon
6. **Document feature timing**: For each feature, document when it becomes available
7. **Walk-forward validation**: Test model using walk-forward approach
8. **Production simulation**: Test feature computation with production-like data flow

## 7. Common Temporal Leakage Mistakes

| Mistake | Why It's Wrong | Correct Approach |
|---------|---------------|------------------|
| `rolling(center=True)` | Uses future data | `rolling(window=n)` (backward only) |
| `groupby().transform('mean')` | Uses all group data including future | `groupby().expanding().mean()` |
| `shift(-1)` | Gets next value | `shift(1)` (gets previous value) |
| Random train-test split | Mixes past and future | Time-based split |
| No gap between train/test | Prediction horizon overlap | Add gap equal to prediction horizon |
| Global time aggregations | Includes future periods | Cumulative/expanding aggregations |

## References

- "Time Series Cross-Validation" (scikit-learn documentation)
- "Temporal Data Mining" (Roddick & Spiliopoulou, 2002)
- "Avoiding Data Leakage in Time Series" (Kaggle Learn)
