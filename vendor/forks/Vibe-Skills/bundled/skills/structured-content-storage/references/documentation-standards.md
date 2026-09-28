# Documentation Standards

Comprehensive requirements for all documentation files in structured projects.

## README.md Requirements

Every project must have a README.md at the root level containing:

### 1. Project Header
```markdown
# Project Name

Brief one-sentence description of what the project does.
```

### 2. Overview Section
- Purpose and goals (2-3 sentences)
- Key features or capabilities
- Target use case or audience

### 3. Directory Structure
```markdown
## Directory Structure

```
project-name/
├── src/           # Source code files
├── data/          # Data files (raw and processed)
├── docs/          # Additional documentation
├── outputs/       # Results and generated files
└── README.md      # This file
```
```

Explain the purpose of each major directory.

### 4. Setup and Installation
```markdown
## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure settings (if applicable)
```

### 5. Usage Instructions
```markdown
## Usage

Basic usage example:
```python
python src/main.py --input data/raw/input.csv --output outputs/results.csv
```

Key parameters:
- `--input`: Path to input data
- `--output`: Path for output results
```

### 6. Dependencies
List all major dependencies and their versions if critical.

## PROCESS.md Requirements

Document the step-by-step workflow in `docs/PROCESS.md`:

### 1. Overview
Brief description of the overall process (2-3 sentences).

### 2. Workflow Steps
```markdown
## Workflow

### Step 1: Data Loading
- Input: Raw CSV files from `data/raw/`
- Process: Read and validate data schema
- Output: Pandas DataFrame with validated structure

### Step 2: Data Cleaning
- Input: Raw DataFrame
- Process:
  1. Remove duplicates
  2. Handle missing values (forward fill for time series)
  3. Detect and remove outliers (IQR method)
- Output: Cleaned DataFrame

### Step 3: Feature Engineering
...
```

### 3. Key Decisions
Document important design decisions and rationale:
```markdown
## Key Decisions

**Decision**: Use forward fill for missing values
**Rationale**: Data is time-series with temporal continuity
**Alternative considered**: Mean imputation (rejected due to loss of temporal patterns)
```

### 4. Data Flow
Text-based diagram showing data flow:
```
Raw Data → Validation → Cleaning → Transformation → Output
   ↓           ↓           ↓            ↓            ↓
 CSV files  Schema OK  No outliers  Features    Results
```

## DATA_DICTIONARY.md Requirements

For any project involving data, create `data/DATA_DICTIONARY.md`:

### Format
```markdown
# Data Dictionary

## Raw Data (`data/raw/`)

### File: transactions.csv

| Field Name | Type | Description | Valid Range | Notes |
|------------|------|-------------|-------------|-------|
| transaction_id | string | Unique transaction identifier | UUID format | Primary key |
| timestamp | datetime | Transaction timestamp | 2020-01-01 to present | ISO 8601 format |
| amount | float | Transaction amount in USD | > 0 | Rounded to 2 decimals |
| customer_id | string | Customer identifier | UUID format | Foreign key |
| status | string | Transaction status | ['pending', 'completed', 'failed'] | Enum |

## Processed Data (`data/processed/`)

### File: transactions_clean.csv

| Field Name | Type | Description | Valid Range | Notes |
|------------|------|-------------|-------------|-------|
| transaction_id | string | Unique transaction identifier | UUID format | Primary key |
| timestamp | datetime | Transaction timestamp | 2020-01-01 to present | ISO 8601 format |
| amount | float | Transaction amount in USD | > 0 | Rounded to 2 decimals |
| customer_id | string | Customer identifier | UUID format | Foreign key |
| status | string | Transaction status | ['completed', 'failed'] | 'pending' removed |
| amount_normalized | float | Normalized amount | 0 to 1 | Min-max normalization |

### Transformations Applied
- Removed transactions with 'pending' status
- Added `amount_normalized` field using min-max normalization
- Removed duplicate transaction_ids (kept first occurrence)
```

## CHANGELOG.md Requirements

For any modifications to existing projects, maintain `docs/CHANGELOG.md`:

### Format
```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Version X.Y.Z] - YYYY-MM-DD

### Added
- New features or files added
- Specific file paths and line numbers if applicable

### Changed
- Modifications to existing functionality
- **File**: `src/module.py:45-67`
- **What**: Description of change
- **Why**: Rationale for change
- **Impact**: Expected effect on behavior

### Fixed
- Bug fixes
- **Issue**: Description of bug
- **Solution**: How it was fixed
- **File**: Specific location

### Removed
- Deprecated or removed features
- Rationale for removal

### Files Affected
- Complete list of modified files with line numbers
```

### Entry Template
```markdown
## [1.2.0] - 2026-01-19

### Changed
- Modified training loop in `src/train.py:89-145`
  - **What**: Added early stopping mechanism
  - **Why**: Prevent overfitting on validation set
  - **How**: Monitor validation loss, stop if no improvement for 10 epochs
  - **Impact**: Training may stop before max_epochs reached

### Added
- New evaluation metrics in `src/evaluate.py:67-89`
  - Precision, recall, F1-score calculations
  - Confusion matrix visualization

### Files Affected
- `src/train.py` (lines 89-145, 203-210)
- `src/evaluate.py` (lines 67-89)
- `docs/TRAINING_PROCESS.md` (updated section 3)
- `README.md` (updated usage examples)
```

## QUALITY_REPORT.md (Optional for Data Projects)

Document data quality metrics in `data/QUALITY_REPORT.md`:

```markdown
# Data Quality Report

## Summary
- **Total Records**: 1,234,567
- **Date Range**: 2020-01-01 to 2026-01-19
- **Completeness**: 98.5%
- **Validity**: 99.2%

## Completeness by Field

| Field | Missing Count | Missing % | Action Taken |
|-------|---------------|-----------|--------------|
| transaction_id | 0 | 0% | None |
| timestamp | 123 | 0.01% | Removed records |
| amount | 456 | 0.04% | Imputed with median |
| customer_id | 0 | 0% | None |

## Validity Issues

### Outliers Detected
- **Field**: amount
- **Method**: IQR (1.5 * IQR)
- **Count**: 1,234 (0.1%)
- **Action**: Removed

### Invalid Values
- **Field**: status
- **Invalid Values**: ['PENDING', 'Complete'] (wrong case)
- **Count**: 567
- **Action**: Standardized to lowercase

## Data Distribution

### Amount Distribution
- Min: $0.01
- Max: $9,999.99
- Mean: $125.43
- Median: $87.65
- Std Dev: $156.78
```

## Best Practices

1. **Keep documentation synchronized**: Update docs whenever code changes
2. **Be specific**: Include file paths, line numbers, and exact changes
3. **Explain rationale**: Document why decisions were made, not just what
4. **Use consistent formatting**: Follow the templates provided
5. **Version everything**: Use semantic versioning (MAJOR.MINOR.PATCH)
6. **Date all changes**: Use ISO 8601 format (YYYY-MM-DD)
