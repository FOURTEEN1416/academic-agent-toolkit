# ML Data Leakage Guard - References

Navigation guide for detailed leakage detection documentation.

## Core Documentation

### [leakage-patterns.md](leakage-patterns.md)
Comprehensive catalog of all common data leakage patterns with examples:
- Preprocessing leakage
- Feature engineering leakage
- Target leakage
- Temporal leakage
- Cross-validation leakage

### [temporal-leakage.md](temporal-leakage.md)
Time series and temporal data specific leakage issues:
- Future functions
- Incorrect time-based splits
- Rolling window leakage
- Lag feature construction

### [detection-strategies.md](detection-strategies.md)
Practical strategies for detecting leakage in existing code:
- Code review checklist
- Automated detection approaches
- Performance sanity checks
- Production validation

## Quick Links

- **For preprocessing issues**: See leakage-patterns.md → Preprocessing Leakage
- **For time series**: See temporal-leakage.md → Future Functions
- **For feature engineering**: See leakage-patterns.md → Feature Engineering Leakage
- **For code review**: See detection-strategies.md → Code Review Checklist

## The Golden Rule

At the exact moment of prediction in production:
- Can I access this value from the database?
- Can I compute this statistic using only information available up to that point?
- Does this feature require knowing the outcome I'm trying to predict?

If any answer is "NO", you have data leakage.

## Usage

These references provide detailed specifications and examples that supplement the Quick Reference in SKILL.md. Use them when you need:
- Detailed explanations of specific leakage types
- Edge case handling
- Domain-specific leakage patterns
- Debugging existing leakage issues
