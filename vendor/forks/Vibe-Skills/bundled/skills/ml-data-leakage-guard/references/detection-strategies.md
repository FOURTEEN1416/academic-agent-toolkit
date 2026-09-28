# Detection Strategies for Data Leakage

Practical strategies and tools for detecting data leakage in existing ML code and workflows.

## 1. Code Review Checklist

### 1.1 Preprocessing Order Check

**What to look for**: Any preprocessing before train-test split.

**Search patterns**:
```python
# Search for these patterns in code:
- "fit_transform" before "train_test_split"
- ".mean()" or ".std()" before "train_test_split"
- "fillna" before "train_test_split"
- "StandardScaler()" before "train_test_split"
- "PCA(" before "train_test_split"
```

**Red flags**:
```python
# ❌ RED FLAG: Preprocessing before split
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
X_train, X_test = train_test_split(X_scaled, y)

# ❌ RED FLAG: Imputation before split
df['age'].fillna(df['age'].mean(), inplace=True)
X_train, X_test = train_test_split(df, y)
```

**Green flags**:
```python
# ✅ GOOD: Split first, then preprocess
X_train, X_test, y_train, y_test = train_test_split(X, y)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

### 1.2 Feature Engineering Check

**What to look for**: Features that use target information or future data.

**Questions to ask**:
1. Does this feature use the target variable?
2. Does this feature use test set information?
3. For time series: Does this feature use future data?
4. Can this feature be computed at prediction time?

**Red flags**:
```python
# ❌ RED FLAG: Target encoding with full dataset
df['category_encoded'] = df.groupby('category')['target'].transform('mean')

# ❌ RED FLAG: Feature selection on full dataset
selector = SelectKBest(k=10)
X_selected = selector.fit_transform(X, y)
X_train, X_test = train_test_split(X_selected, y)

# ❌ RED FLAG: Future data in time series
df['next_value'] = df['value'].shift(-1)
```

### 1.3 Cross-Validation Check

**What to look for**: Preprocessing outside of CV pipeline.

**Red flags**:
```python
# ❌ RED FLAG: Preprocessing before CV
X_scaled = StandardScaler().fit_transform(X)
scores = cross_val_score(model, X_scaled, y, cv=5)

# ❌ RED FLAG: Feature selection before CV
X_selected = SelectKBest(k=10).fit_transform(X, y)
scores = cross_val_score(model, X_selected, y, cv=5)
```

**Green flags**:
```python
# ✅ GOOD: Pipeline for CV
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('model', LogisticRegression())
])
scores = cross_val_score(pipeline, X, y, cv=5)
```

### 1.4 Temporal Data Check

**What to look for**: Random splits on time series, future functions.

**Red flags**:
```python
# ❌ RED FLAG: Random split on time series
X_train, X_test = train_test_split(df, test_size=0.2, random_state=42)

# ❌ RED FLAG: Centered rolling window
df['rolling_avg'] = df['value'].rolling(7, center=True).mean()

# ❌ RED FLAG: Global time aggregation
df['daily_avg'] = df.groupby('date')['value'].transform('mean')
```

## 2. Automated Detection Tools

### 2.1 Leakage Detection Script

```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

class LeakageDetector:
    """Automated data leakage detection."""

    def __init__(self, X_train, X_test, y_train, y_test):
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test
        self.warnings = []
        self.errors = []

    def check_duplicate_samples(self):
        """Check for duplicate samples between train and test."""
        if isinstance(self.X_train, pd.DataFrame):
            train_hashes = set(pd.util.hash_pandas_object(self.X_train))
            test_hashes = set(pd.util.hash_pandas_object(self.X_test))
            overlap = train_hashes.intersection(test_hashes)

            if overlap:
                self.errors.append(
                    f"❌ CRITICAL: {len(overlap)} duplicate samples in train and test"
                )
                return False
        return True

    def check_statistical_similarity(self, threshold=0.01):
        """Check if train and test statistics are suspiciously similar."""
        if isinstance(self.X_train, pd.DataFrame):
            for col in self.X_train.columns:
                if self.X_train[col].dtype in ['float64', 'int64']:
                    train_mean = self.X_train[col].mean()
                    test_mean = self.X_test[col].mean()
                    train_std = self.X_train[col].std()
                    test_std = self.X_test[col].std()

                    # Check if means are too similar
                    if abs(train_mean - test_mean) / (train_std + 1e-10) < threshold:
                        self.warnings.append(
                            f"⚠️ WARNING: Column '{col}' has suspiciously similar "
                            f"train/test means (possible preprocessing leakage)"
                        )

    def check_temporal_order(self, date_column=None):
        """Check temporal order for time series data."""
        if date_column and date_column in self.X_train.columns:
            train_max_date = self.X_train[date_column].max()
            test_min_date = self.X_test[date_column].min()

            if train_max_date > test_min_date:
                self.errors.append(
                    f"❌ CRITICAL: Training data contains dates ({train_max_date}) "
                    f"after test data ({test_min_date}). Use time-based split!"
                )
                return False
        return True

    def check_target_correlation(self, threshold=0.95):
        """Check if any feature is too correlated with target (possible target leakage)."""
        if isinstance(self.X_train, pd.DataFrame):
            train_df = self.X_train.copy()
            train_df['target'] = self.y_train

            for col in self.X_train.columns:
                if train_df[col].dtype in ['float64', 'int64']:
                    corr = abs(train_df[col].corr(train_df['target']))
                    if corr > threshold:
                        self.errors.append(
                            f"❌ CRITICAL: Feature '{col}' has correlation {corr:.3f} "
                            f"with target (possible target leakage)"
                        )

    def check_missing_value_patterns(self):
        """Check if missing value patterns are identical (possible global imputation)."""
        if isinstance(self.X_train, pd.DataFrame):
            train_missing = self.X_train.isnull().sum()
            test_missing = self.X_test.isnull().sum()

            # If no missing values in either set, might indicate global imputation
            if (train_missing == 0).all() and (test_missing == 0).all():
                self.warnings.append(
                    "⚠️ WARNING: No missing values in train or test. "
                    "If original data had missing values, check for global imputation."
                )

    def run_all_checks(self, date_column=None):
        """Run all leakage detection checks."""
        print("Running Data Leakage Detection...")
        print("=" * 60)

        self.check_duplicate_samples()
        self.check_statistical_similarity()
        self.check_temporal_order(date_column)
        self.check_target_correlation()
        self.check_missing_value_patterns()

        # Print results
        if self.errors:
            print("\n🚨 ERRORS DETECTED:")
            for error in self.errors:
                print(error)

        if self.warnings:
            print("\n⚠️ WARNINGS:")
            for warning in self.warnings:
                print(warning)

        if not self.errors and not self.warnings:
            print("\n✅ No obvious leakage detected")
            print("Note: This doesn't guarantee no leakage. Manual review still needed.")

        return len(self.errors) == 0

# Usage example:
# X_train, X_test, y_train, y_test = train_test_split(X, y)
# detector = LeakageDetector(X_train, X_test, y_train, y_test)
# detector.run_all_checks(date_column='date')
```

### 2.2 Pipeline Validator

```python
def validate_pipeline(pipeline, X, y):
    """
    Validate that pipeline doesn't have leakage issues.
    Checks that all preprocessing is inside the pipeline.
    """
    from sklearn.pipeline import Pipeline

    if not isinstance(pipeline, Pipeline):
        print("⚠️ WARNING: Not using Pipeline. Preprocessing may leak into CV.")
        return False

    # Check that pipeline includes preprocessing steps
    step_names = [name for name, _ in pipeline.steps]

    preprocessing_steps = ['scaler', 'imputer', 'selector', 'pca', 'encoder']
    has_preprocessing = any(step in step_names for step in preprocessing_steps)

    if has_preprocessing:
        print("✅ Pipeline includes preprocessing steps")
    else:
        print("⚠️ WARNING: Pipeline has no preprocessing. "
              "Ensure preprocessing isn't done outside pipeline.")

    return True
```

## 3. Performance-Based Detection

### 3.1 Too-Good-To-Be-True Check

```python
def check_performance_realism(train_score, test_score, problem_difficulty='medium'):
    """
    Check if performance is unrealistically high (suggests leakage).

    problem_difficulty: 'easy', 'medium', 'hard'
    """
    thresholds = {
        'easy': 0.90,
        'medium': 0.85,
        'hard': 0.75
    }

    threshold = thresholds.get(problem_difficulty, 0.85)

    if test_score > threshold:
        print(f"⚠️ WARNING: Test score ({test_score:.3f}) is very high for "
              f"a {problem_difficulty} problem. Check for leakage.")

    # Check train-test gap
    gap = abs(train_score - test_score)
    if gap < 0.01:
        print(f"⚠️ WARNING: Train ({train_score:.3f}) and test ({test_score:.3f}) "
              f"scores are suspiciously similar. Possible leakage.")

    # Check if test > train (red flag)
    if test_score > train_score:
        print(f"❌ CRITICAL: Test score ({test_score:.3f}) > train score "
              f"({train_score:.3f}). Strong indicator of leakage.")
```

### 3.2 Cross-Validation vs. Holdout Comparison

```python
def compare_cv_holdout(model, X, y, cv=5):
    """
    Compare CV score with holdout score.
    Large discrepancy suggests leakage in CV setup.
    """
    from sklearn.model_selection import cross_val_score, train_test_split

    # CV score
    cv_scores = cross_val_score(model, X, y, cv=cv)
    cv_mean = cv_scores.mean()

    # Holdout score
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    model.fit(X_train, y_train)
    holdout_score = model.score(X_test, y_test)

    print(f"CV Score: {cv_mean:.3f}")
    print(f"Holdout Score: {holdout_score:.3f}")
    print(f"Difference: {abs(cv_mean - holdout_score):.3f}")

    if abs(cv_mean - holdout_score) > 0.1:
        print("⚠️ WARNING: Large discrepancy between CV and holdout. "
              "Check for preprocessing leakage in CV.")

    return cv_mean, holdout_score
```

### 3.3 Feature Importance Analysis

```python
def analyze_feature_importance(model, feature_names, top_n=10):
    """
    Analyze top features for potential leakage.
    Post-event features or suspiciously perfect features are red flags.
    """
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    elif hasattr(model, 'coef_'):
        importances = abs(model.coef_[0])
    else:
        print("Model doesn't support feature importance")
        return

    # Get top features
    indices = np.argsort(importances)[::-1][:top_n]

    print(f"\nTop {top_n} Most Important Features:")
    print("=" * 60)
    for i, idx in enumerate(indices):
        print(f"{i+1}. {feature_names[idx]}: {importances[idx]:.4f}")

    print("\n⚠️ MANUAL REVIEW NEEDED:")
    print("Check if any top features are:")
    print("- Post-event features (only available after outcome)")
    print("- Future information (for time series)")
    print("- Direct proxies of the target")
    print("- Suspiciously perfect predictors")
```

## 4. Production Validation

### 4.1 Production Simulation Test

```python
def simulate_production_prediction(model, scaler, feature_pipeline, new_data):
    """
    Simulate production prediction to verify no leakage.

    This function should ONLY use information that would be available
    at prediction time in production.
    """
    try:
        # Step 1: Can we compute all features with available data?
        features = feature_pipeline.transform(new_data)

        # Step 2: Can we apply preprocessing with saved statistics?
        features_scaled = scaler.transform(features)

        # Step 3: Make prediction
        prediction = model.predict(features_scaled)

        print("✅ Production simulation successful")
        return prediction

    except Exception as e:
        print(f"❌ Production simulation failed: {e}")
        print("This suggests features or preprocessing require unavailable data")
        return None
```

### 4.2 Feature Availability Audit

```python
def audit_feature_availability(feature_list, prediction_time='T'):
    """
    Audit each feature to verify it's available at prediction time.

    For each feature, ask:
    - Can this be queried from database at time T?
    - Can this be computed using only data available before T?
    - Does this require knowing the outcome?
    """
    print(f"Feature Availability Audit (Prediction Time: {prediction_time})")
    print("=" * 60)

    for feature in feature_list:
        print(f"\nFeature: {feature}")
        print("Questions to answer:")
        print("1. Can this be queried from database at prediction time? [Y/N]")
        print("2. Can this be computed using only past data? [Y/N]")
        print("3. Does this require knowing the outcome? [Y/N]")
        print("4. For time series: Does this use future data? [Y/N]")
        print("-" * 60)

    print("\nIf any answer is 'N' for questions 1-2, or 'Y' for questions 3-4:")
    print("❌ That feature has LEAKAGE")
```

## 5. Checklist for Code Review

### Pre-Deployment Checklist

```markdown
## Data Leakage Prevention Checklist

### Data Splitting
- [ ] Train-test split is the FIRST operation (before any preprocessing)
- [ ] For time series: Using time-based split, not random split
- [ ] For time series: Added gap between train/test equal to prediction horizon
- [ ] No duplicate samples between train and test sets

### Preprocessing
- [ ] All scalers/normalizers fit ONLY on training data
- [ ] Missing value imputation uses ONLY training statistics
- [ ] Outlier detection thresholds computed from ONLY training data
- [ ] No preprocessing before train-test split

### Feature Engineering
- [ ] No features use target information from test set
- [ ] No target encoding with full dataset labels
- [ ] Feature selection done ONLY on training data
- [ ] For time series: No future functions or centered windows
- [ ] For time series: All lag features use positive shifts (past data)

### Dimensionality Reduction
- [ ] PCA/SVD/t-SNE fit ONLY on training data
- [ ] Feature selection fit ONLY on training data

### Cross-Validation
- [ ] All preprocessing inside Pipeline for CV
- [ ] No preprocessing before CV split
- [ ] For time series: Using TimeSeriesSplit, not KFold

### Feature Validation
- [ ] Each feature can be computed at prediction time
- [ ] No post-event features (features only available after outcome)
- [ ] No features that are direct proxies of target
- [ ] Feature importance analysis shows no suspicious features

### Production Readiness
- [ ] Production simulation test passes
- [ ] Feature availability audit completed
- [ ] Walk-forward validation performed (for time series)
- [ ] Model performance is realistic for problem difficulty

### Documentation
- [ ] Each feature documented with "available at" timestamp
- [ ] Preprocessing steps documented with train/test handling
- [ ] Known limitations documented
```

## 6. Common Leakage Patterns to Search For

### Code Search Patterns

Use these regex patterns to search your codebase:

```python
# Patterns that often indicate leakage:
patterns_to_search = [
    r"\.fit_transform\(X\)",  # fit_transform on full dataset
    r"\.mean\(\)",  # Global statistics
    r"\.std\(\)",
    r"\.median\(\)",
    r"fillna.*\.mean\(\)",  # Global imputation
    r"train_test_split.*\n.*fit_transform",  # Wrong order
    r"shift\(-\d+\)",  # Negative shift (future data)
    r"rolling.*center=True",  # Centered rolling window
    r"groupby.*transform",  # Global group statistics
    r"SelectKBest.*fit_transform\(X, y\)",  # Feature selection on full data
]
```

## 7. Best Practices Summary

1. **Always split first**: `train_test_split` before any preprocessing
2. **Use Pipelines**: Wrap preprocessing in sklearn Pipeline for CV
3. **Time-based splits**: For temporal data, never use random splits
4. **Document features**: For each feature, document when it's available
5. **Production simulation**: Test with production-like data flow
6. **Code review**: Have someone else review for leakage
7. **Automated checks**: Run leakage detection scripts before deployment
8. **Performance sanity**: If it's too good to be true, it probably is

## References

- scikit-learn Pipeline documentation
- "Data Leakage in Machine Learning" (Kaggle)
- "Common Pitfalls in Machine Learning" (Google ML Crash Course)
