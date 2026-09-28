# Comprehensive Leakage Patterns Catalog

Detailed documentation of all common data leakage patterns in machine learning.

## 1. Preprocessing Leakage

### 1.1 Normalization and Standardization

**Problem**: Fitting scalers on the entire dataset before train-test split.

**Why It's Leakage**: The scaler learns statistics (mean, std, min, max) from the test set, which won't be available at prediction time.

**Examples**:

```python
# ❌ WRONG: StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # Learns from entire dataset
X_train, X_test = train_test_split(X_scaled, y)

# ❌ WRONG: MinMaxScaler
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)  # Learns min/max from test set
X_train, X_test = train_test_split(X_scaled, y)

# ❌ WRONG: RobustScaler
scaler = RobustScaler()
X_scaled = scaler.fit_transform(X)  # Learns quantiles from test set
X_train, X_test = train_test_split(X_scaled, y)

# ✅ CORRECT: Fit on training data only
X_train, X_test, y_train, y_test = train_test_split(X, y)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

**Impact**: Test performance is artificially inflated by 2-10% depending on dataset.

### 1.2 Missing Value Imputation

**Problem**: Computing imputation statistics (mean, median, mode) from the entire dataset.

**Why It's Leakage**: At prediction time, you won't have access to test set values to compute these statistics.

**Examples**:

```python
# ❌ WRONG: Global mean imputation
df['age'].fillna(df['age'].mean(), inplace=True)

# ❌ WRONG: Global median imputation
df['income'].fillna(df['income'].median(), inplace=True)

# ❌ WRONG: Global mode imputation
df['category'].fillna(df['category'].mode()[0], inplace=True)

# ❌ WRONG: SimpleImputer on full dataset
from sklearn.impute import SimpleImputer
imputer = SimpleImputer(strategy='mean')
X_imputed = imputer.fit_transform(X)
X_train, X_test = train_test_split(X_imputed, y)

# ✅ CORRECT: Compute statistics from training data only
X_train, X_test, y_train, y_test = train_test_split(df, y)
train_mean = X_train['age'].mean()
X_train['age'].fillna(train_mean, inplace=True)
X_test['age'].fillna(train_mean, inplace=True)

# ✅ CORRECT: SimpleImputer fit on training data
imputer = SimpleImputer(strategy='mean')
X_train_imputed = imputer.fit_transform(X_train)
X_test_imputed = imputer.transform(X_test)
```

**Impact**: Moderate performance inflation, especially when missing rate is high.

### 1.3 Outlier Detection and Removal

**Problem**: Detecting outliers using statistics from the entire dataset.

**Why It's Leakage**: Outlier thresholds computed from test set won't be available at prediction time.

**Examples**:

```python
# ❌ WRONG: IQR-based outlier removal on full dataset
Q1 = df['value'].quantile(0.25)
Q3 = df['value'].quantile(0.75)
IQR = Q3 - Q1
df_clean = df[(df['value'] >= Q1 - 1.5*IQR) & (df['value'] <= Q3 + 1.5*IQR)]
X_train, X_test = train_test_split(df_clean, y)

# ❌ WRONG: Z-score outlier removal on full dataset
z_scores = np.abs((df['value'] - df['value'].mean()) / df['value'].std())
df_clean = df[z_scores < 3]
X_train, X_test = train_test_split(df_clean, y)

# ✅ CORRECT: Compute outlier thresholds from training data
X_train, X_test, y_train, y_test = train_test_split(df, y)
Q1 = X_train['value'].quantile(0.25)
Q3 = X_train['value'].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5*IQR
upper_bound = Q3 + 1.5*IQR

# Remove outliers from training data
X_train_clean = X_train[(X_train['value'] >= lower_bound) & (X_train['value'] <= upper_bound)]
# Clip outliers in test data (don't remove, as you can't remove in production)
X_test['value'] = X_test['value'].clip(lower_bound, upper_bound)
```

**Impact**: Can significantly inflate performance if outliers are correlated with target.

## 2. Feature Engineering Leakage

### 2.1 Target Encoding

**Problem**: Using target values from the entire dataset to encode categorical features.

**Why It's Leakage**: This directly uses the answer (target) from test set as a feature.

**Examples**:

```python
# ❌ WRONG: Target encoding with full dataset
category_means = df.groupby('category')['target'].mean()
df['category_encoded'] = df['category'].map(category_means)
X_train, X_test = train_test_split(df, y)

# ❌ WRONG: Target encoding in cross-validation
for train_idx, val_idx in kfold.split(X, y):
    category_means = df.groupby('category')['target'].mean()  # Uses all data
    df['category_encoded'] = df['category'].map(category_means)

# ✅ CORRECT: Target encoding from training data only
X_train, X_test, y_train, y_test = train_test_split(df, y)
train_df = X_train.copy()
train_df['target'] = y_train
category_means = train_df.groupby('category')['target'].mean()

X_train['category_encoded'] = X_train['category'].map(category_means)
X_test['category_encoded'] = X_test['category'].map(category_means)

# Handle unseen categories in test set
X_test['category_encoded'].fillna(y_train.mean(), inplace=True)
```

**Impact**: CRITICAL - Can inflate performance by 20-50% or more. This is severe leakage.

### 2.2 Feature Selection

**Problem**: Selecting features based on correlation or importance computed from the entire dataset.

**Why It's Leakage**: Feature selection is part of the training process and should only use training data.

**Examples**:

```python
# ❌ WRONG: Feature selection on full dataset
from sklearn.feature_selection import SelectKBest, f_classif
selector = SelectKBest(f_classif, k=10)
X_selected = selector.fit_transform(X, y)  # Uses test set
X_train, X_test = train_test_split(X_selected, y)

# ❌ WRONG: Correlation-based selection on full dataset
correlations = df.corr()['target'].abs()
top_features = correlations.nlargest(10).index.tolist()
X_selected = df[top_features]
X_train, X_test = train_test_split(X_selected, y)

# ✅ CORRECT: Feature selection on training data only
X_train, X_test, y_train, y_test = train_test_split(X, y)
selector = SelectKBest(f_classif, k=10)
X_train_selected = selector.fit_transform(X_train, y_train)
X_test_selected = selector.transform(X_test)

# ✅ CORRECT: Correlation-based selection on training data
train_df = X_train.copy()
train_df['target'] = y_train
correlations = train_df.corr()['target'].abs()
top_features = correlations.nlargest(10).index.tolist()
top_features.remove('target')
X_train_selected = X_train[top_features]
X_test_selected = X_test[top_features]
```

**Impact**: HIGH - Can inflate performance by 5-15%.

### 2.3 Dimensionality Reduction

**Problem**: Fitting PCA, SVD, or other dimensionality reduction on the entire dataset.

**Why It's Leakage**: These methods learn variance structure from test set.

**Examples**:

```python
# ❌ WRONG: PCA on full dataset
from sklearn.decomposition import PCA
pca = PCA(n_components=10)
X_reduced = pca.fit_transform(X)  # Learns variance from test set
X_train, X_test = train_test_split(X_reduced, y)

# ❌ WRONG: SVD on full dataset
from sklearn.decomposition import TruncatedSVD
svd = TruncatedSVD(n_components=10)
X_reduced = svd.fit_transform(X)
X_train, X_test = train_test_split(X_reduced, y)

# ✅ CORRECT: PCA on training data only
X_train, X_test, y_train, y_test = train_test_split(X, y)
pca = PCA(n_components=10)
X_train_reduced = pca.fit_transform(X_train)
X_test_reduced = pca.transform(X_test)
```

**Impact**: HIGH - Can inflate performance by 5-20% depending on dataset structure.

## 3. Target Leakage

### 3.1 Direct Target Leakage

**Problem**: Including features that are direct consequences of the target or contain target information.

**Examples**:

```python
# ❌ WRONG: Post-event features
# Predicting loan default using "number of collection calls"
# Collection calls only happen AFTER default

# ❌ WRONG: Proxy targets
# Predicting customer churn using "account_closed_date"
# Account closure is the churn event itself

# ❌ WRONG: Future information
# Predicting hospital readmission using "length of next stay"
# You don't know the next stay length until readmission happens

# ✅ CORRECT: Use only pre-event features
# For loan default: credit_score, income, debt_ratio, employment_status
# For churn: login_frequency, feature_usage, support_tickets, payment_delays
# For readmission: current_stay_length, diagnosis, age, comorbidities
```

**Impact**: CRITICAL - Model appears perfect but is completely useless in production.

### 3.2 Temporal Target Leakage

**Problem**: Using information from the future to predict the past.

**Examples**:

```python
# ❌ WRONG: Using next month's data to predict this month
df['next_month_sales'] = df.groupby('store')['sales'].shift(-1)
# Using next_month_sales as a feature to predict current month performance

# ❌ WRONG: Aggregating across time without respecting temporal order
df['user_lifetime_value'] = df.groupby('user_id')['purchase_amount'].sum()
# This includes future purchases when predicting early purchases

# ✅ CORRECT: Use only past information
df = df.sort_values(['user_id', 'date'])
df['cumulative_purchases'] = df.groupby('user_id')['purchase_amount'].cumsum()
# Cumulative sum only includes past purchases
```

**Impact**: CRITICAL - Model is completely invalid for production use.

## 4. Cross-Validation Leakage

### 4.1 Preprocessing Before CV

**Problem**: Applying preprocessing to the entire dataset before cross-validation.

**Why It's Leakage**: Each CV fold's validation set is influenced by its own data during preprocessing.

**Examples**:

```python
# ❌ WRONG: Scale before cross-validation
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
scores = cross_val_score(model, X_scaled, y, cv=5)

# ❌ WRONG: Feature selection before CV
selector = SelectKBest(k=10)
X_selected = selector.fit_transform(X, y)
scores = cross_val_score(model, X_selected, y, cv=5)

# ✅ CORRECT: Use Pipeline for CV
from sklearn.pipeline import Pipeline
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('selector', SelectKBest(k=10)),
    ('model', LogisticRegression())
])
scores = cross_val_score(pipeline, X, y, cv=5)
```

**Impact**: HIGH - CV scores are inflated, giving false confidence in model performance.

## 5. Data Augmentation Leakage

### 5.1 Augmentation Before Split

**Problem**: Augmenting data before train-test split.

**Why It's Leakage**: Augmented versions of test samples may end up in training set.

**Examples**:

```python
# ❌ WRONG: Augment before split
X_augmented, y_augmented = augment_data(X, y)  # Creates synthetic samples
X_train, X_test, y_train, y_test = train_test_split(X_augmented, y_augmented)
# Test set may contain original samples whose augmented versions are in train

# ✅ CORRECT: Augment after split
X_train, X_test, y_train, y_test = train_test_split(X, y)
X_train_augmented, y_train_augmented = augment_data(X_train, y_train)
# Only training data is augmented, test set remains pure
```

**Impact**: MEDIUM - Can inflate performance by 3-10% depending on augmentation strategy.

## Detection Strategies

### Code Review Checklist

1. Search for `fit_transform` calls - ensure they're only on training data
2. Search for `.mean()`, `.std()`, `.median()` - ensure computed on training data only
3. Check train_test_split order - should be BEFORE any preprocessing
4. For time series, verify time-based splits, not random splits
5. Review all features - can each be computed at prediction time?
6. Check cross-validation setup - preprocessing should be in Pipeline

### Performance Sanity Checks

1. **Too Good To Be True**: If test accuracy > 95% on a difficult problem, suspect leakage
2. **Train-Test Gap**: If train and test performance are nearly identical, suspect leakage
3. **Feature Importance**: If post-event features have high importance, that's leakage
4. **Production Failure**: If model performs well in testing but fails in production, likely leakage

### Automated Detection

```python
def check_for_leakage(X_train, X_test, y_train, y_test):
    """Basic leakage detection checks."""

    # Check 1: Are train and test statistics too similar?
    train_mean = X_train.mean()
    test_mean = X_test.mean()
    if np.allclose(train_mean, test_mean, rtol=0.01):
        print("⚠️ WARNING: Train and test means are suspiciously similar")

    # Check 2: Are there duplicate samples between train and test?
    train_hashes = set(pd.util.hash_pandas_object(X_train))
    test_hashes = set(pd.util.hash_pandas_object(X_test))
    overlap = train_hashes.intersection(test_hashes)
    if overlap:
        print(f"❌ LEAKAGE: {len(overlap)} duplicate samples in train and test")

    # Check 3: For time series, check temporal order
    if 'date' in X_train.columns:
        if X_train['date'].max() > X_test['date'].min():
            print("❌ LEAKAGE: Training data contains dates after test data")

    return True
```

## Best Practices

1. **Always split first**: `train_test_split` should be the FIRST operation
2. **Use Pipelines**: Wrap all preprocessing in sklearn Pipeline for CV
3. **Time-based splits**: For temporal data, always use time-based splits
4. **Document features**: For each feature, document when it becomes available
5. **Production simulation**: Test your pipeline with production-like data flow
6. **Code review**: Have someone else review for leakage before deployment

## References

- Kaggle: "Data Leakage in Machine Learning" (common competition mistakes)
- "Leakage in Data Mining" (Kaufman et al., 2012)
- scikit-learn documentation on Pipeline and cross-validation
