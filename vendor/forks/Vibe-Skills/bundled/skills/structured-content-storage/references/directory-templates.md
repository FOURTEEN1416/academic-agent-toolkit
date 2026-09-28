# Directory Templates

Standard directory structures for different project types.

## Machine Learning Training Project

```
ml-project-name/
├── README.md                      # Project overview and setup
├── requirements.txt               # Python dependencies
├── .gitignore                     # Git ignore patterns
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── train.py                   # Main training script
│   ├── model.py                   # Model architecture definition
│   ├── data_loader.py             # Data loading and preprocessing
│   ├── evaluate.py                # Evaluation metrics and testing
│   └── utils.py                   # Utility functions
│
├── data/                          # Data files
│   ├── raw/                       # Original, immutable data
│   │   ├── train.csv
│   │   └── test.csv
│   ├── processed/                 # Cleaned and preprocessed data
│   │   ├── train_processed.csv
│   │   └── test_processed.csv
│   └── DATA_DICTIONARY.md         # Data field descriptions
│
├── models/                        # Saved model checkpoints
│   ├── best_model.pth
│   └── checkpoint_epoch_10.pth
│
├── logs/                          # Training logs and metrics
│   ├── training_log.txt
│   └── tensorboard/
│
├── outputs/                       # Results and visualizations
│   ├── predictions.csv
│   ├── confusion_matrix.png
│   └── metrics_summary.json
│
├── notebooks/                     # Jupyter notebooks (optional)
│   ├── exploratory_analysis.ipynb
│   └── model_evaluation.ipynb
│
├── configs/                       # Configuration files
│   ├── train_config.yaml
│   └── model_config.yaml
│
└── docs/                          # Documentation
    ├── TRAINING_PROCESS.md        # Training methodology
    ├── MODEL_ARCHITECTURE.md      # Model design decisions
    ├── EXPERIMENTS.md             # Experiment tracking
    └── CHANGELOG.md               # Modification history
```

### Key Files

**src/train.py**: Main training script with comprehensive comments
```python
"""
Training script for [model name] on [dataset name].

This script handles:
- Data loading and preprocessing
- Model initialization
- Training loop with validation
- Checkpoint saving
- Logging and metrics tracking
"""
```

**docs/TRAINING_PROCESS.md**: Detailed training methodology
- Data preprocessing steps
- Model architecture rationale
- Hyperparameter selection
- Training procedure
- Evaluation metrics

**docs/MODEL_ARCHITECTURE.md**: Model design documentation
- Architecture diagram (text-based acceptable)
- Layer specifications
- Design decisions and rationale
- Comparison with alternatives

## Data Processing / Cleaning Project

```
data-processing-project/
├── README.md                      # Project overview
├── requirements.txt               # Dependencies
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── clean.py                   # Main cleaning script
│   ├── validators.py              # Data validation functions
│   ├── transformers.py            # Data transformation utilities
│   └── quality_checks.py          # Data quality assessment
│
├── data/                          # Data files
│   ├── raw/                       # Original data (read-only)
│   │   └── input_data.csv
│   ├── intermediate/              # Intermediate processing steps
│   │   ├── validated.csv
│   │   └── cleaned.csv
│   ├── processed/                 # Final cleaned data
│   │   └── output_data.csv
│   ├── DATA_DICTIONARY.md         # Field descriptions
│   └── QUALITY_REPORT.md          # Data quality metrics
│
├── outputs/                       # Reports and visualizations
│   ├── quality_report.html
│   ├── distribution_plots.png
│   └── cleaning_summary.json
│
├── configs/                       # Configuration files
│   └── cleaning_config.yaml
│
└── docs/                          # Documentation
    ├── CLEANING_PROCESS.md        # Step-by-step cleaning methodology
    ├── VALIDATION_RULES.md        # Data validation criteria
    └── CHANGELOG.md               # Modification history
```

### Key Files

**src/clean.py**: Main cleaning script
```python
"""
Data cleaning pipeline for [dataset name].

Pipeline stages:
1. Load and validate raw data
2. Handle missing values
3. Remove duplicates
4. Detect and handle outliers
5. Standardize formats
6. Export cleaned data

Each stage is logged and can be configured via cleaning_config.yaml
"""
```

**docs/CLEANING_PROCESS.md**: Detailed cleaning methodology
- Data quality assessment
- Cleaning rules and rationale
- Transformation steps
- Quality metrics before/after

**data/QUALITY_REPORT.md**: Data quality documentation
- Completeness metrics
- Validity checks
- Outlier detection results
- Distribution statistics

## Analysis / Research Project

```
analysis-project/
├── README.md                      # Project overview
├── requirements.txt               # Dependencies
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── analyze.py                 # Main analysis script
│   ├── statistics.py              # Statistical functions
│   └── visualizations.py          # Plotting utilities
│
├── data/                          # Data files
│   ├── raw/                       # Original data
│   ├── processed/                 # Processed data
│   └── DATA_DICTIONARY.md         # Data descriptions
│
├── outputs/                       # Results
│   ├── figures/                   # Generated plots
│   ├── tables/                    # Result tables
│   └── reports/                   # Analysis reports
│
├── notebooks/                     # Jupyter notebooks
│   ├── 01_exploratory_analysis.ipynb
│   ├── 02_statistical_tests.ipynb
│   └── 03_visualization.ipynb
│
└── docs/                          # Documentation
    ├── ANALYSIS_PROCESS.md        # Analysis methodology
    ├── FINDINGS.md                # Key findings and insights
    └── CHANGELOG.md               # Modification history
```

## General Software Project

```
software-project/
├── README.md                      # Project overview
├── requirements.txt               # Dependencies
├── setup.py                       # Package setup (if applicable)
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── core/                      # Core functionality
│   │   ├── __init__.py
│   │   └── module.py
│   └── utils/                     # Utilities
│       ├── __init__.py
│       └── helpers.py
│
├── tests/                         # Test files
│   ├── __init__.py
│   ├── test_core.py
│   └── test_utils.py
│
├── data/                          # Data files (if applicable)
│   └── DATA_DICTIONARY.md
│
├── configs/                       # Configuration files
│   └── config.yaml
│
├── outputs/                       # Generated outputs
│
└── docs/                          # Documentation
    ├── ARCHITECTURE.md            # System architecture
    ├── API.md                     # API documentation
    └── CHANGELOG.md               # Modification history
```

## ETL / Data Pipeline Project

```
etl-pipeline/
├── README.md                      # Project overview
├── requirements.txt               # Dependencies
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── extract.py                 # Data extraction
│   ├── transform.py               # Data transformation
│   ├── load.py                    # Data loading
│   └── pipeline.py                # Orchestration
│
├── data/                          # Data files
│   ├── raw/                       # Extracted data
│   ├── staging/                   # Intermediate data
│   ├── processed/                 # Transformed data
│   └── DATA_DICTIONARY.md         # Schema documentation
│
├── configs/                       # Configuration
│   ├── sources.yaml               # Data source configs
│   └── pipeline_config.yaml       # Pipeline settings
│
├── logs/                          # Pipeline logs
│   └── pipeline_run_YYYYMMDD.log
│
└── docs/                          # Documentation
    ├── PIPELINE_PROCESS.md        # Pipeline workflow
    ├── DATA_SOURCES.md            # Source documentation
    └── CHANGELOG.md               # Modification history
```

## Directory Naming Conventions

### Standard Directory Names
- `src/` or `source/`: Source code
- `data/`: Data files
- `docs/`: Documentation
- `tests/`: Test files
- `outputs/` or `results/`: Generated outputs
- `configs/` or `config/`: Configuration files
- `logs/`: Log files
- `models/`: Saved models (ML projects)
- `notebooks/`: Jupyter notebooks

### Data Subdirectories
- `raw/`: Original, immutable data
- `intermediate/` or `staging/`: Intermediate processing steps
- `processed/` or `clean/`: Final processed data

### Best Practices
1. Use lowercase with underscores for directory names
2. Keep directory structure shallow (max 3-4 levels)
3. Group related files together
4. Separate code, data, and outputs
5. Make the structure self-documenting
