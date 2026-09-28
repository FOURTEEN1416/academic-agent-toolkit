# Full Workflow Guide: From Problem to Deployment

This guide provides a comprehensive, step-by-step workflow for machine learning projects, contrasting novice and expert approaches at each phase.

## Phase 1: Problem Formulation

### Novice Approach
```
Receive task → Assume ML is needed → Find SOTA model → Start coding
```

### Expert Approach

**Step 1: Convert Business Problem to Mathematical Formulation**

```python
# Business problem: "Predict customer churn"
# Mathematical formulation:
# - Type: Binary classification
# - Input: X = customer features (usage, demographics, support tickets)
# - Output: y ∈ {0, 1} where 1 = churn
# - Objective: Maximize P(y|X) accuracy while minimizing false negatives
#   (losing a customer is more costly than retention effort)
```

**Step 2: Question Necessity of ML**

Ask: Can this be solved without ML?
- Simple rules? "If no login in 30 days → likely churn"
- Heuristics? "If support tickets > 3 → likely churn"
- Lookup table? "Historical churn rate by segment"

**Only proceed with ML if simpler approaches are insufficient**

**Step 3: Define Success Metrics Beyond Accuracy**

```python
# Novice: "Maximize accuracy"
# Expert: Consider business context

# For imbalanced churn (5% churn rate):
# - Accuracy is misleading (95% by predicting "no churn" always)
# - Use: Precision, Recall, F1, AUC-ROC
# - Business metric: Cost of false negative vs false positive

# Cost matrix
cost_fn = 100  # Lost customer value
cost_fp = 10   # Cost of retention campaign

# Custom loss function
def business_loss(y_true, y_pred):
    fn = ((y_true == 1) & (y_pred == 0)).sum() * cost_fn
    fp = ((y_true == 0) & (y_pred == 1)).sum() * cost_fp
    return fn + fp
```

**Step 4: Consider Negative Consequences**

- Optimizing click-through rate → Clickbait headlines
- Optimizing engagement time → Addictive features
- Optimizing approval rate → Discriminatory lending

**Expert always asks:** "What bad behavior does this metric incentivize?"

## Phase 2: Data Engineering

### Novice Approach
```
Load CSV → df.fillna(0) → Train model
```

### Expert Approach

**Step 1: Data Archaeology - Understand Generation Mechanism**

```python
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('data.csv')

# Expert questions:
# 1. How was this data collected?
# 2. What do missing values mean?
# 3. Are there temporal dependencies?
# 4. What are the data quality issues?

# Check missing value patterns
missing_analysis = pd.DataFrame({
    'column': df.columns,
    'missing_count': df.isnull().sum(),
    'missing_pct': df.isnull().sum() / len(df) * 100
})
print(missing_analysis[missing_analysis['missing_count'] > 0])

# Informative missingness check
# Example: Income missing might indicate unemployment
df['income_missing'] = df['income'].isna().astype(int)

# Check correlation with target
from scipy.stats import chi2_contingency
contingency = pd.crosstab(df['income_missing'], df['target'])
chi2, p_value, _, _ = chi2_contingency(contingency)
print(f"Income missingness vs target: p-value = {p_value:.4f}")
# If p < 0.05, missingness is informative → keep as feature!
```

**Step 2: Temporal Data Isolation (Prevent Data Leakage)**

```python
# WRONG: Random split (causes data leakage if temporal data)
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# RIGHT: Time-based split
df = df.sort_values('date')
split_date = '2023-01-01'
train_df = df[df['date'] < split_date]
test_df = df[df['date'] >= split_date]

X_train, y_train = train_df.drop('target', axis=1), train_df['target']
X_test, y_test = test_df.drop('target', axis=1), test_df['target']

# Expert checks: No future information in training data
assert X_train['date'].max() < X_test['date'].min(), "Data leakage detected!"
```

**Step 3: Feature Engineering - Causality Over Correlation**

```python
# Novice: Add all possible features
# Expert: Add features with causal story

# Example: House price prediction

# GOOD: Causal features
df['price_per_sqft'] = df['price'] / df['sqft']  # Price depends on size
df['house_age'] = 2024 - df['year_built']  # Age affects depreciation
df['rooms_per_sqft'] = df['bedrooms'] / df['sqft']  # Density indicator

# BAD: Spurious correlations
# df['random_product'] = df['bedrooms'] * df['bathrooms']  # No causal story

# Feature validation: Check importance
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance

model = RandomForestRegressor()
model.fit(X_train, y_train)

# Permutation importance (more reliable than feature_importances_)
perm_importance = permutation_importance(model, X_test, y_test, n_repeats=10)

feature_importance_df = pd.DataFrame({
    'feature': X_train.columns,
    'importance': perm_importance.importances_mean,
    'std': perm_importance.importances_std
}).sort_values('importance', ascending=False)

print(feature_importance_df)

# Remove features with importance < 0.01
important_features = feature_importance_df[feature_importance_df['importance'] > 0.01]['feature'].tolist()
X_train_filtered = X_train[important_features]
X_test_filtered = X_test[important_features]
```

**Step 4: Data Quality Checks**

```python
# Check for duplicates
duplicates = df.duplicated().sum()
print(f"Duplicate rows: {duplicates}")

# Check for label leakage (features that perfectly predict target)
for col in X_train.columns:
    if X_train[col].dtype in ['int64', 'float64']:
        correlation = X_train[col].corr(y_train)
        if abs(correlation) > 0.95:
            print(f"WARNING: {col} has correlation {correlation:.3f} with target - possible leakage!")

# Check class balance
print(f"Class distribution:\n{y_train.value_counts(normalize=True)}")
```

## Phase 3: Modeling and Algorithm Selection

### Novice Approach
```
Use latest SOTA model → Grid search all hyperparameters → Pick highest accuracy
```

### Expert Approach

**Step 1: Match Inductive Bias to Data Structure**

```python
# Expert decision tree:

# Tabular data (structured features)
# → Start with: Gradient Boosting (XGBoost, LightGBM, CatBoost)
# → Alternative: Random Forest (more robust, less tuning)

# Image data
# → CNN (translation invariance)
# → Pre-trained models (ResNet, EfficientNet) for transfer learning

# Text data
# → Transformer (BERT, GPT) for context
# → TF-IDF + Linear model for simple tasks

# Time series
# → ARIMA, Prophet for univariate
# → LSTM, Transformer for multivariate

# Graph data
# → GNN (Graph Neural Network)

# Example: Tabular data
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

# Start simple
simple_model = LogisticRegression(max_iter=1000)
simple_model.fit(X_train, y_train)
simple_score = simple_model.score(X_test, y_test)

# Medium complexity
medium_model = RandomForestClassifier(n_estimators=100, max_depth=10)
medium_model.fit(X_train, y_train)
medium_score = medium_model.score(X_test, y_test)

# High complexity
complex_model = XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1)
complex_model.fit(X_train, y_train)
complex_score = complex_model.score(X_test, y_test)

print(f"Simple: {simple_score:.3f}")
print(f"Medium: {medium_score:.3f}")
print(f"Complex: {complex_score:.3f}")

# Decision: Use simplest model with acceptable performance
```

**Step 2: Analyze Residuals (Errors), Not Just Metrics**

```python
# Get predictions
y_pred = model.predict(X_test)

# Analyze errors
errors = y_test - y_pred  # For regression
error_mask = (y_pred != y_test)  # For classification

# Plot residuals (regression)
import matplotlib.pyplot as plt
plt.scatter(y_pred, errors)
plt.axhline(y=0, color='r', linestyle='--')
plt.xlabel('Predicted')
plt.ylabel('Residual')
plt.title('Residual Plot')
plt.show()

# Look for patterns:
# - Heteroscedasticity (fan shape) → Need transformation
# - Systematic bias (curve) → Missing nonlinear features
# - Outliers → Data quality issues or rare events

# Error analysis by feature ranges
error_df = pd.DataFrame({
    'error': errors,
    'feature1': X_test['feature1'],
    'feature2': X_test['feature2']
})

# Where does model fail?
high_error_mask = abs(errors) > errors.std() * 2
print("High error cases:")
print(error_df[high_error_mask].describe())
```

**Step 3: Prefer Robustness Over Fragile High Performance**

```python
# Expert prefers: Stable AUC 0.85 over Fragile AUC 0.88

# Test robustness with cross-validation
from sklearn.model_selection import cross_val_score

# Model A: High performance, high variance
model_a_scores = cross_val_score(model_a, X_train, y_train, cv=5)
print(f"Model A: {model_a_scores.mean():.3f} ± {model_a_scores.std():.3f}")

# Model B: Lower performance, low variance
model_b_scores = cross_val_score(model_b, X_train, y_train, cv=5)
print(f"Model B: {model_b_scores.mean():.3f} ± {model_b_scores.std():.3f}")

# Decision: If Model A = 0.88 ± 0.05 and Model B = 0.85 ± 0.01
# → Choose Model B (more reliable in production)
```

## Phase 4: Validation and Debugging

### The Expert's 5-Stage Deep Learning Workflow

**Stage 1: Profiling (Before Modeling)**

```python
# Don't build model yet - understand data first

import pandas as pd
import matplotlib.pyplot as plt

# Check data distribution
df.hist(bins=50, figsize=(20, 15))
plt.show()

# Check for class imbalance
print(y_train.value_counts(normalize=True))

# Check for outliers
print(df.describe())

# Establish dummy baseline
from sklearn.dummy import DummyClassifier
dummy = DummyClassifier(strategy='most_frequent')
dummy.fit(X_train, y_train)
dummy_score = dummy.score(X_test, y_test)
print(f"Dummy baseline: {dummy_score:.3f}")
```

**Stage 2: Sanity Check (Minimum Closed Loop)**

```python
# Test: Can model overfit 10 samples?
# If NO → Bug in code (not model problem)

# Take tiny dataset
tiny_X = X_train[:10]
tiny_y = y_train[:10]

# Turn off regularization
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=None,  # No depth limit
    min_samples_split=2,  # Minimum split
    min_samples_leaf=1  # Minimum leaf
)

model.fit(tiny_X, tiny_y)
train_acc = model.score(tiny_X, tiny_y)

print(f"Training accuracy on 10 samples: {train_acc:.3f}")
assert train_acc == 1.0, "BUG: Model can't overfit 10 samples!"

# If assertion fails, check:
# - Label encoding correct?
# - Feature preprocessing correct?
# - Model implementation correct?
```

**Stage 3: Capacity Expansion (Solve Underfitting)**

```python
# Goal: Get training accuracy close to 100%

# For neural networks: Add width first, then depth
# For tree models: Increase max_depth, decrease min_samples_split

# Example: Random Forest
from sklearn.ensemble import RandomForestClassifier

# Start small
model = RandomForestClassifier(n_estimators=10, max_depth=3)
model.fit(X_train, y_train)
train_score = model.score(X_train, y_train)
val_score = model.score(X_val, y_val)
print(f"Small model - Train: {train_score:.3f}, Val: {val_score:.3f}")

# Increase capacity
model = RandomForestClassifier(n_estimators=100, max_depth=10)
model.fit(X_train, y_train)
train_score = model.score(X_train, y_train)
val_score = model.score(X_val, y_val)
print(f"Large model - Train: {train_score:.3f}, Val: {val_score:.3f}")

# Keep increasing until train_score > 0.95
```

**Stage 4: Regularization (Solve Overfitting)**

```python
# Goal: Close train-val gap while maintaining train performance

# Regularization ladder (in order of effectiveness):
# 1. Data Augmentation (most effective)
# 2. Dropout (for neural networks)
# 3. L2 regularization / Tree constraints
# 4. Early stopping

# Example: Tree model regularization
from sklearn.ensemble import RandomForestClassifier

# Overfit model (train=0.99, val=0.75)
overfit_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=None,
    min_samples_split=2
)

# Regularized model
regularized_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,  # Limit depth
    min_samples_split=20,  # Require more samples to split
    min_samples_leaf=10,  # Require more samples in leaf
    max_features='sqrt'  # Limit features per tree
)

regularized_model.fit(X_train, y_train)
train_score = regularized_model.score(X_train, y_train)
val_score = regularized_model.score(X_val, y_val)
print(f"Regularized - Train: {train_score:.3f}, Val: {val_score:.3f}")

# Goal: train_score - val_score < 0.05
```

**Stage 5: Diagnosis (When Things Go Wrong)**

```python
# Problem: Loss oscillates
# Solution: Reduce learning rate, use warmup + cosine decay

# Problem: Model stuck at high loss
# Solution: Check for:
# - Dead ReLU (use LeakyReLU)
# - Vanishing gradients (use BatchNorm, ResNet)
# - Wrong loss function

# Problem: Val loss increases while train loss decreases
# Solution: Overfitting → Add regularization (see Stage 4)

# Problem: Both train and val loss high
# Solution: Underfitting → Add capacity (see Stage 3)
```

## Phase 5: Scientific Hyperparameter Tuning

### Novice Approach
```python
# Blind grid search
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [10, 50, 100, 200],
    'max_depth': [3, 5, 7, 10, None],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4]
}

# 4 * 5 * 3 * 3 = 180 combinations (expensive!)
grid_search = GridSearchCV(model, param_grid, cv=5)
grid_search.fit(X_train, y_train)
```

### Expert Approach

**Build Intuition for Parameter Effects**

```python
# Expert understands what each parameter does:

# n_estimators (trees): More = better, but diminishing returns after ~100
# max_depth: Controls model complexity
#   - Too low → underfitting
#   - Too high → overfitting
# min_samples_split: Regularization
#   - Higher = more regularization (simpler trees)
# learning_rate: Step size
#   - Too high → oscillation
#   - Too low → slow convergence

# Expert strategy: Tune one at a time, understand effect

import numpy as np
import matplotlib.pyplot as plt

# Tune max_depth
depths = [3, 5, 7, 10, 15, 20]
train_scores = []
val_scores = []

for depth in depths:
    model = RandomForestClassifier(n_estimators=100, max_depth=depth)
    model.fit(X_train, y_train)
    train_scores.append(model.score(X_train, y_train))
    val_scores.append(model.score(X_val, y_val))

plt.plot(depths, train_scores, label='Train')
plt.plot(depths, val_scores, label='Val')
plt.xlabel('max_depth')
plt.ylabel('Accuracy')
plt.legend()
plt.show()

# Choose depth where val score peaks (before overfitting)
```

**Bayesian Intuition**

```python
# Expert builds mental model:
# - λ (regularization) ↑ → Model smoother (variance ↓, bias ↑)
# - Batch size ↑ → Gradient estimate more accurate but flatter minima
# - Learning rate ↑ → Faster convergence but risk of oscillation

# Use this intuition to guide search, not blind grid search
```

## Traditional ML Regularization Mapping

| Deep Learning | Tree Models | Linear Models | Principle |
|---------------|-------------|---------------|-----------|
| Add layers | Increase max_depth | Polynomial features | Increase capacity |
| Dropout | colsample_bytree | - | Prevent reliance on single features |
| L2 regularization | lambda, gamma | Ridge (L2) | Penalize large weights |
| Data augmentation | subsample | SMOTE | Increase data diversity |
| Batch normalization | - | Feature scaling | Stabilize training |

## Summary: Expert Workflow Checklist

**Before Starting:**
- [ ] Can this be solved without ML?
- [ ] What is the dummy baseline?
- [ ] What are the negative consequences of this metric?

**Data Engineering:**
- [ ] Understand data generation mechanism
- [ ] Check for temporal data leakage
- [ ] Analyze missing value patterns
- [ ] Build causal features

**Modeling:**
- [ ] Start with simple model
- [ ] Establish multiple baselines
- [ ] Perform ablation studies
- [ ] Analyze errors, not just metrics

**Validation:**
- [ ] Sanity check: Overfit 10 samples
- [ ] Check train-val gap
- [ ] Stress test with adversarial inputs
- [ ] Prefer robust over fragile models

**Deployment:**
- [ ] Monitor for concept drift
- [ ] A/B test against baseline
- [ ] Set up error logging and analysis
- [ ] Plan for model retraining

The expert workflow is systematic, scientific, and always questions assumptions.
