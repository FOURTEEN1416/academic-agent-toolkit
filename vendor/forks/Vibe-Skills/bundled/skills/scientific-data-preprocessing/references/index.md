# References Index

## Navigation

This skill's reference materials are organized as:

1. **error-case-studies.md** - Real-world preprocessing disasters and lessons learned
2. **decision-trees.md** - Complete decision trees for all preprocessing choices
3. **validation-checklist.md** - Pre-processing validation checklist
4. **ai-common-pitfalls.md** - AI-specific errors: data leakage, semantic fallacies, distribution blindness (NEW)

## Quick Links by Topic

### Error Prevention
- **Avoiding cross-group contamination** → error-case-studies.md § Cross-Group Interpolation Error
- **Feature type misclassification** → error-case-studies.md § Binary Variable Standardization Error
- **Data quality issues** → validation-checklist.md § Data Quality Validation
- **Data leakage detection** → ai-common-pitfalls.md § Category 1: Data Leakage (NEW)
- **Semantic-numeric mapping errors** → ai-common-pitfalls.md § Category 2: Semantic-Numeric Mapping Fallacy (NEW)

### Processing Strategies
- **Choosing standardization scope** → decision-trees.md § Standardization Scope Decision
- **Handling missing values** → decision-trees.md § Missing Value Strategy
- **Feature engineering for time-series** → decision-trees.md § Time-Series Feature Engineering
- **Distribution-aware scaling** → ai-common-pitfalls.md § Category 3: Distribution-Blind Scaling (NEW)

### Validation
- **Pre-processing checklist** → validation-checklist.md
- **Detecting processing errors** → error-case-studies.md § How to Detect
- **Comprehensive audit** → ai-common-pitfalls.md § Comprehensive Validation Checklist (NEW)

## Source Material

This skill was derived from:
- 2024 MCM Problem C (Tennis Momentum Analysis)
- Real preprocessing pipeline failures (V1.0, V2.0) and corrections
- Statistical best practices for panel/grouped data

## Maintenance

Last updated: 2026-01-18
