# DATA_DICTIONARY Template

Comprehensive documentation of all data fields and schemas.

## Overview

- **Dataset Name**: [Name of dataset]
- **Source**: [Where the data comes from]
- **Update Frequency**: [How often data is updated]
- **Date Range**: [Start date] to [End date]
- **Total Records**: [Number of records]

---

## Raw Data

### File: [filename.csv]

**Location**: `data/raw/[filename.csv]`

**Description**: [Brief description of what this file contains]

**Schema**:

| Field Name | Type | Description | Valid Range / Values | Constraints | Notes |
|------------|------|-------------|---------------------|-------------|-------|
| id | string | Unique identifier | UUID format | NOT NULL, PRIMARY KEY | Auto-generated |
| timestamp | datetime | Record timestamp | 2020-01-01 to present | NOT NULL | ISO 8601 format |
| value | float | Measurement value | -999.99 to 999.99 | NOT NULL | Rounded to 2 decimals |
| category | string | Category label | ['A', 'B', 'C'] | NOT NULL | Enum type |
| status | string | Record status | ['active', 'inactive'] | NOT NULL | Default: 'active' |
| metadata | json | Additional metadata | Valid JSON | NULLABLE | Optional field |

**Example Record**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-19T10:30:00Z",
  "value": 123.45,
  "category": "A",
  "status": "active",
  "metadata": {"source": "sensor_01", "quality": "high"}
}
```

**Data Quality**:
- Completeness: 98.5%
- Missing values: 1.5% (primarily in metadata field)
- Duplicates: 0.2% (based on id field)

---

## Processed Data

### File: [filename_processed.csv]

**Location**: `data/processed/[filename_processed.csv]`

**Description**: [Brief description of processed data]

**Schema**:

| Field Name | Type | Description | Valid Range / Values | Constraints | Notes |
|------------|------|-------------|---------------------|-------------|-------|
| id | string | Unique identifier | UUID format | NOT NULL, PRIMARY KEY | From raw data |
| timestamp | datetime | Record timestamp | 2020-01-01 to present | NOT NULL | ISO 8601 format |
| value | float | Measurement value | -999.99 to 999.99 | NOT NULL | From raw data |
| value_normalized | float | Normalized value | 0.0 to 1.0 | NOT NULL | **NEW**: Min-max normalized |
| category | string | Category label | ['A', 'B', 'C'] | NOT NULL | From raw data |
| category_encoded | int | Encoded category | 0, 1, 2 | NOT NULL | **NEW**: Label encoded |
| status | string | Record status | ['active', 'inactive'] | NOT NULL | From raw data |
| is_outlier | boolean | Outlier flag | true/false | NOT NULL | **NEW**: IQR-based detection |

**Transformations Applied**:

1. **value_normalized**: Min-max normalization
   - Formula: `(value - min) / (max - min)`
   - Min: -999.99
   - Max: 999.99

2. **category_encoded**: Label encoding
   - 'A' → 0
   - 'B' → 1
   - 'C' → 2

3. **is_outlier**: Outlier detection using IQR method
   - Threshold: 1.5 * IQR
   - Outliers flagged but not removed

**Data Quality**:
- Completeness: 100% (missing values handled)
- Records removed: 1,234 (duplicates and invalid entries)
- Outliers detected: 567 (0.5%)

---

## Field Definitions

### Common Fields

**id (Identifier)**
- **Purpose**: Unique identifier for each record
- **Format**: UUID v4 (e.g., 550e8400-e29b-41d4-a716-446655440000)
- **Generation**: Auto-generated at data collection
- **Uniqueness**: Guaranteed unique across all records

**timestamp (Datetime)**
- **Purpose**: When the record was created or event occurred
- **Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- **Timezone**: UTC
- **Precision**: Seconds
- **Example**: 2026-01-19T10:30:00Z

**value (Numeric)**
- **Purpose**: Primary measurement or metric
- **Unit**: [Specify unit, e.g., USD, meters, etc.]
- **Precision**: 2 decimal places
- **Range**: -999.99 to 999.99
- **Special values**: None (no NaN or Inf)

**category (Categorical)**
- **Purpose**: Classification or grouping
- **Type**: Enum
- **Values**:
  - 'A': [Description of category A]
  - 'B': [Description of category B]
  - 'C': [Description of category C]
- **Default**: None (must be specified)

---

## Data Sources

### Source 1: [Source Name]
- **Type**: [Database, API, File, etc.]
- **Location**: [URL or path]
- **Access**: [How to access]
- **Update frequency**: [Daily, hourly, etc.]
- **Reliability**: [High, medium, low]

### Source 2: [Source Name]
- **Type**: [Database, API, File, etc.]
- **Location**: [URL or path]
- **Access**: [How to access]
- **Update frequency**: [Daily, hourly, etc.]
- **Reliability**: [High, medium, low]

---

## Data Collection Process

1. **Extraction**: [How data is extracted from source]
2. **Validation**: [What validation checks are performed]
3. **Storage**: [Where and how data is stored]
4. **Update**: [How and when data is updated]

---

## Data Quality Rules

### Completeness
- All NOT NULL fields must have values
- Missing values in optional fields are acceptable

### Validity
- Numeric fields must be within specified ranges
- Categorical fields must match allowed values
- Datetime fields must be valid ISO 8601 format

### Consistency
- id must be unique across all records
- timestamp must be chronologically valid
- Related fields must be logically consistent

### Accuracy
- Values must match source data
- Transformations must be correctly applied
- No data corruption during processing

---

## Known Issues and Limitations

1. **Issue**: [Description of known data quality issue]
   - **Impact**: [How it affects analysis]
   - **Workaround**: [How to handle it]

2. **Limitation**: [Description of data limitation]
   - **Impact**: [What analyses are not possible]
   - **Future**: [Plans to address]

---

## Change History

### 2026-01-19
- Added `value_normalized` field to processed data
- Added `is_outlier` flag for outlier detection
- Updated data quality metrics

### 2026-01-15
- Initial data dictionary created
- Documented raw and processed schemas

---

## Contact

For questions about this data dictionary:
- **Maintainer**: [Name]
- **Email**: [Email]
- **Last Updated**: [Date]
