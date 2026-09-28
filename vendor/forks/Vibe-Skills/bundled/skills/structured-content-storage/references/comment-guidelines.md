# Code Comment Guidelines

Best practices for documenting code with comprehensive comments.

## Core Principles

1. **Explain WHY, not WHAT**: Code shows what it does; comments explain why
2. **Comment complex logic**: If it takes more than 5 seconds to understand, add a comment
3. **Document assumptions**: Make implicit assumptions explicit
4. **Keep comments synchronized**: Update comments when code changes
5. **Be concise but complete**: Every comment should add value

## File Headers

Every source file must have a header comment:

```python
"""
Module: data_processor.py
Purpose: Process and transform raw sensor data into analysis-ready format

Main components:
- DataLoader: Reads raw CSV files from multiple sources
- DataCleaner: Handles missing values, outliers, and data quality issues
- DataTransformer: Applies normalization and feature engineering
- DataValidator: Ensures output meets quality standards

Dependencies:
- pandas >= 1.3.0
- numpy >= 1.20.0
- scikit-learn >= 0.24.0

Author: [Optional]
Created: 2026-01-19
Last modified: 2026-01-19
"""
```

### Minimal File Header
```python
"""
Module: utils.py
Purpose: Utility functions for data manipulation and validation
"""
```

## Function Documentation

### Standard Function Docstring

```python
def calculate_moving_average(data, window_size=7, min_periods=None):
    """
    Calculate moving average with configurable window size.

    Args:
        data (pd.Series): Time series data to smooth
        window_size (int): Number of periods in moving average window (default: 7)
        min_periods (int, optional): Minimum observations required for calculation.
                                     If None, uses window_size. (default: None)

    Returns:
        pd.Series: Smoothed time series with same index as input

    Raises:
        ValueError: If window_size < 1 or min_periods > window_size

    Example:
        >>> data = pd.Series([1, 2, 3, 4, 5])
        >>> calculate_moving_average(data, window_size=3)
        0    NaN
        1    NaN
        2    2.0
        3    3.0
        4    4.0
        dtype: float64

    Notes:
        - Uses pandas rolling window implementation
        - NaN values at the beginning depend on min_periods setting
        - For time series with irregular intervals, consider time-based windows
    """
    if window_size < 1:
        raise ValueError("window_size must be at least 1")

    if min_periods is None:
        min_periods = window_size

    if min_periods > window_size:
        raise ValueError("min_periods cannot exceed window_size")

    return data.rolling(window=window_size, min_periods=min_periods).mean()
```

### Minimal Function Docstring (for simple functions)

```python
def normalize_column_names(df):
    """
    Convert DataFrame column names to lowercase with underscores.

    Args:
        df (pd.DataFrame): Input DataFrame

    Returns:
        pd.DataFrame: DataFrame with normalized column names
    """
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    return df
```

### Complex Function with Detailed Process Documentation

```python
def detect_anomalies(data, method='iqr', threshold=1.5, window=None):
    """
    Detect anomalies in time series data using multiple methods.

    This function implements several anomaly detection algorithms and returns
    a boolean mask indicating anomalous points. The choice of method depends
    on data characteristics and use case requirements.

    Args:
        data (pd.Series): Time series data to analyze
        method (str): Detection method - 'iqr', 'zscore', or 'isolation_forest'
                     (default: 'iqr')
        threshold (float): Sensitivity threshold. Meaning varies by method:
                          - 'iqr': IQR multiplier (typical: 1.5 for outliers, 3.0 for extreme)
                          - 'zscore': Number of standard deviations (typical: 3.0)
                          - 'isolation_forest': Contamination parameter (typical: 0.1)
        window (int, optional): Rolling window size for local anomaly detection.
                               If None, uses global statistics. (default: None)

    Returns:
        pd.Series: Boolean mask where True indicates anomaly

    Raises:
        ValueError: If method is not recognized or threshold is invalid

    Example:
        >>> data = pd.Series([1, 2, 3, 100, 4, 5])
        >>> detect_anomalies(data, method='iqr', threshold=1.5)
        0    False
        1    False
        2    False
        3     True
        4    False
        5    False
        dtype: bool

    Notes:
        Method selection guidelines:
        - 'iqr': Best for symmetric distributions, robust to outliers
        - 'zscore': Assumes normal distribution, sensitive to outliers
        - 'isolation_forest': Best for high-dimensional data, no distribution assumptions

        Performance considerations:
        - IQR and Z-score: O(n) time complexity
        - Isolation Forest: O(n log n) time complexity

    References:
        - IQR method: Tukey, J. W. (1977). Exploratory Data Analysis.
        - Isolation Forest: Liu, F. T., et al. (2008). ICDM.
    """
    if method not in ['iqr', 'zscore', 'isolation_forest']:
        raise ValueError(f"Unknown method: {method}")

    if method == 'iqr':
        # IQR method: detect outliers using interquartile range
        # Threshold of 1.5 is standard for outliers, 3.0 for extreme outliers
        if window is None:
            Q1 = data.quantile(0.25)
            Q3 = data.quantile(0.75)
        else:
            # Use rolling window for local anomaly detection
            Q1 = data.rolling(window=window).quantile(0.25)
            Q3 = data.rolling(window=window).quantile(0.75)

        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR

        # Points outside bounds are anomalies
        anomalies = (data < lower_bound) | (data > upper_bound)

    elif method == 'zscore':
        # Z-score method: detect outliers using standard deviations
        # Assumes data is approximately normally distributed
        if window is None:
            mean = data.mean()
            std = data.std()
        else:
            mean = data.rolling(window=window).mean()
            std = data.rolling(window=window).std()

        # Calculate z-scores
        z_scores = np.abs((data - mean) / std)

        # Points with |z-score| > threshold are anomalies
        anomalies = z_scores > threshold

    else:  # isolation_forest
        # Isolation Forest: ensemble method for anomaly detection
        # Works by isolating anomalies in random decision trees
        from sklearn.ensemble import IsolationForest

        # Reshape for sklearn (expects 2D array)
        X = data.values.reshape(-1, 1)

        # threshold parameter becomes contamination (expected proportion of anomalies)
        clf = IsolationForest(contamination=threshold, random_state=42)
        predictions = clf.fit_predict(X)

        # -1 indicates anomaly, 1 indicates normal
        anomalies = pd.Series(predictions == -1, index=data.index)

    return anomalies
```

## Class Documentation

```python
class DataPipeline:
    """
    End-to-end data processing pipeline for sensor data.

    This class orchestrates the complete data processing workflow from raw
    sensor readings to analysis-ready datasets. It handles data loading,
    validation, cleaning, transformation, and quality assurance.

    Attributes:
        config (dict): Pipeline configuration parameters
        data_loader (DataLoader): Component for loading raw data
        cleaner (DataCleaner): Component for data cleaning
        transformer (DataTransformer): Component for feature engineering
        validator (DataValidator): Component for quality checks

    Example:
        >>> config = {'input_path': 'data/raw/', 'output_path': 'data/processed/'}
        >>> pipeline = DataPipeline(config)
        >>> pipeline.run()
        >>> print(pipeline.get_quality_report())

    Notes:
        - Pipeline stages are executed sequentially
        - Each stage logs progress and errors
        - Failed quality checks raise DataQualityError
    """

    def __init__(self, config):
        """
        Initialize pipeline with configuration.

        Args:
            config (dict): Configuration dictionary with keys:
                          - 'input_path': Path to raw data
                          - 'output_path': Path for processed data
                          - 'quality_threshold': Minimum quality score (0-1)
        """
        self.config = config
        self.data_loader = DataLoader(config['input_path'])
        self.cleaner = DataCleaner()
        self.transformer = DataTransformer()
        self.validator = DataValidator(config['quality_threshold'])

    def run(self):
        """
        Execute complete pipeline workflow.

        Process:
            1. Load raw data from input_path
            2. Validate data schema and completeness
            3. Clean data (handle missing values, outliers)
            4. Transform data (normalize, engineer features)
            5. Validate output quality
            6. Save processed data to output_path

        Raises:
            DataLoadError: If raw data cannot be loaded
            DataQualityError: If quality checks fail

        Returns:
            dict: Pipeline execution summary with metrics
        """
        # Implementation with detailed inline comments
        pass
```

## Inline Comments

### When to Add Inline Comments

**DO comment**:
- Complex algorithms or logic
- Non-obvious optimizations
- Workarounds for bugs or limitations
- Important assumptions
- Magic numbers or constants
- Regex patterns
- Business logic rationale

**DON'T comment**:
- Obvious code (e.g., `x = x + 1  # increment x`)
- Code that is self-explanatory
- Redundant information already in function docstring

### Good Inline Comments

```python
# Remove sensors with insufficient data coverage
# Threshold of 0.95 means sensor must have 95% valid readings to be included
completeness = df.groupby('sensor_id')['value'].count() / len(df)
valid_sensors = completeness[completeness >= 0.95].index

# Use IQR method for outlier detection (more robust than z-score for skewed data)
Q1 = df['value'].quantile(0.25)
Q3 = df['value'].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR  # 1.5 is standard multiplier for outliers
upper_bound = Q3 + 1.5 * IQR

# Forward fill missing values (assumes temporal continuity in sensor readings)
df['value'] = df.groupby('sensor_id')['value'].fillna(method='ffill')

# Regex pattern: match ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SS)
datetime_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'

# Batch size of 32 chosen empirically for optimal GPU memory usage
batch_size = 32

# Workaround: pandas rolling() doesn't handle NaN at boundaries correctly
# Manual implementation ensures consistent behavior
for i in range(window_size, len(data)):
    window_data = data[i-window_size:i]
    result[i] = window_data.mean()
```

### Bad Inline Comments (Avoid These)

```python
# Bad: States the obvious
x = x + 1  # increment x

# Bad: Redundant with variable name
user_count = len(users)  # count the users

# Bad: Outdated comment (code changed but comment didn't)
# Calculate average  (but code now calculates median)
result = np.median(data)

# Bad: Vague and unhelpful
# Do some processing
result = complex_function(data)

# Bad: Comment instead of fixing code
# This is a hack
result = data[0] if len(data) > 0 else None  # Use: result = data[0] if data else None
```

## Special Comment Types

### TODO Comments

```python
# TODO: Implement caching to improve performance (Issue #123)
# TODO: Add support for additional file formats (CSV, Parquet)
# TODO: Refactor this function to reduce complexity (cyclomatic complexity = 15)
```

### FIXME Comments

```python
# FIXME: This breaks when input contains Unicode characters
# FIXME: Memory leak when processing large files (>1GB)
# FIXME: Race condition in multi-threaded mode
```

### NOTE Comments

```python
# NOTE: This function modifies the input DataFrame in-place
# NOTE: Assumes data is sorted by timestamp
# NOTE: Performance degrades significantly for n > 10000
```

### WARNING Comments

```python
# WARNING: Changing this value will break backward compatibility
# WARNING: This operation is expensive (O(n²) time complexity)
# WARNING: Not thread-safe - use locks in concurrent environments
```

## Documentation for Different Code Complexity Levels

### Simple Function (Minimal Documentation)
```python
def get_file_extension(filename):
    """Return file extension from filename."""
    return filename.split('.')[-1]
```

### Medium Complexity (Standard Documentation)
```python
def load_csv_with_validation(filepath, required_columns):
    """
    Load CSV file and validate required columns exist.

    Args:
        filepath (str): Path to CSV file
        required_columns (list): Column names that must be present

    Returns:
        pd.DataFrame: Loaded and validated data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required columns are missing
    """
    df = pd.read_csv(filepath)

    # Check for required columns
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df
```

### High Complexity (Comprehensive Documentation)
```python
def train_model_with_cross_validation(X, y, model_class, param_grid, cv_folds=5):
    """
    Train model using grid search with cross-validation.

    This function performs exhaustive search over specified parameter values
    using k-fold cross-validation to find optimal hyperparameters. It handles
    class imbalance through stratified sampling and provides detailed metrics.

    Args:
        X (np.ndarray or pd.DataFrame): Feature matrix of shape (n_samples, n_features)
        y (np.ndarray or pd.Series): Target vector of shape (n_samples,)
        model_class (class): Scikit-learn estimator class (e.g., RandomForestClassifier)
        param_grid (dict): Parameter grid for grid search
                          Example: {'n_estimators': [100, 200], 'max_depth': [10, 20]}
        cv_folds (int): Number of cross-validation folds (default: 5)

    Returns:
        tuple: (best_model, cv_results)
            - best_model: Trained model with optimal parameters
            - cv_results: Dict with keys 'best_params', 'best_score', 'all_scores'

    Raises:
        ValueError: If X and y have incompatible shapes
        ValueError: If cv_folds < 2

    Example:
        >>> from sklearn.ensemble import RandomForestClassifier
        >>> param_grid = {'n_estimators': [100, 200], 'max_depth': [10, 20]}
        >>> model, results = train_model_with_cross_validation(
        ...     X_train, y_train, RandomForestClassifier, param_grid
        ... )
        >>> print(f"Best params: {results['best_params']}")
        >>> print(f"Best score: {results['best_score']:.3f}")

    Notes:
        - Uses stratified k-fold to maintain class distribution in each fold
        - Scoring metric is accuracy for classification, R² for regression
        - Grid search uses all available CPU cores (n_jobs=-1)
        - Random state is fixed (42) for reproducibility

    Performance:
        - Time complexity: O(n_params * n_folds * model_training_time)
        - Space complexity: O(n_samples * n_features)
        - For large datasets (>100k samples), consider RandomizedSearchCV

    See Also:
        - sklearn.model_selection.GridSearchCV
        - sklearn.model_selection.StratifiedKFold
    """
    # Validation and implementation with detailed inline comments
    pass
```

## Best Practices Summary

1. **File headers**: Always include module purpose and main components
2. **Function docstrings**: Include Args, Returns, Raises, and Examples for non-trivial functions
3. **Inline comments**: Explain WHY, not WHAT; focus on complex logic and assumptions
4. **Keep synchronized**: Update comments when code changes
5. **Be concise**: Every comment should add value
6. **Use consistent format**: Follow the templates provided
7. **Document edge cases**: Explain how code handles special situations
8. **Include examples**: Show typical usage in docstrings
9. **Explain trade-offs**: Document why you chose one approach over alternatives
10. **Link to references**: Cite papers, documentation, or issues when relevant
