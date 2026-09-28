# Data Processing Project Template

## Project: [Project Name]

Brief description of what this data processing project does.

## Directory Structure

```
data-processing-project/
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── src/                           # Source code
│   ├── clean.py                   # Main cleaning script
│   ├── validators.py              # Validation functions
│   ├── transformers.py            # Transformation utilities
│   └── quality_checks.py          # Quality assessment
├── data/                          # Data files
│   ├── raw/                       # Original data (read-only)
│   ├── intermediate/              # Intermediate steps
│   ├── processed/                 # Final cleaned data
│   ├── DATA_DICTIONARY.md         # Field descriptions
│   └── QUALITY_REPORT.md          # Quality metrics
├── outputs/                       # Reports and visualizations
├── configs/                       # Configuration files
└── docs/                          # Documentation
    ├── CLEANING_PROCESS.md        # Cleaning methodology
    └── CHANGELOG.md               # Modification history
```

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure settings:
   - Edit `configs/cleaning_config.yaml` with your parameters

## Usage

### Basic Cleaning
```bash
python src/clean.py --input data/raw/input.csv --output data/processed/output.csv
```

### With Custom Configuration
```bash
python src/clean.py --config configs/cleaning_config.yaml
```

### Generate Quality Report
```bash
python src/quality_checks.py --data data/processed/output.csv --report outputs/quality_report.html
```

### Key Parameters
- `--input`: Path to raw data file
- `--output`: Path for cleaned data output
- `--config`: Path to configuration file
- `--validate`: Run validation checks (default: True)

## Data Processing Pipeline

1. **Load**: Read raw data from `data/raw/`
2. **Validate**: Check schema and data types
3. **Clean**: Handle missing values, duplicates, outliers
4. **Transform**: Standardize formats, normalize values
5. **Quality Check**: Verify output meets quality standards
6. **Export**: Save to `data/processed/`

See `docs/CLEANING_PROCESS.md` for detailed methodology.

## Data Quality Metrics

[Summary of data quality before and after processing]

- **Completeness**: [X%] → [Y%]
- **Validity**: [X%] → [Y%]
- **Records**: [X] → [Y]

See `data/QUALITY_REPORT.md` for complete metrics.

## Data Dictionary

See `data/DATA_DICTIONARY.md` for detailed field descriptions including:
- Field names and types
- Valid value ranges
- Transformations applied
- Data sources

## Dependencies

- Python >= 3.8
- pandas >= 1.3.0
- numpy >= 1.20.0
- scikit-learn >= 0.24.0 (for outlier detection)

See `requirements.txt` for complete list.

## Documentation

- `docs/CLEANING_PROCESS.md`: Step-by-step cleaning methodology
- `data/DATA_DICTIONARY.md`: Field descriptions and schemas
- `data/QUALITY_REPORT.md`: Data quality assessment

## Validation Rules

[Summary of key validation rules applied]

1. Required fields must be present
2. Numeric fields must be within valid ranges
3. Date fields must be in ISO 8601 format
4. No duplicate records based on primary key

See `docs/CLEANING_PROCESS.md` for complete validation rules.

## License

[License information]

## Contact

[Contact information]
