# CHANGELOG Template

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- [List new features or files added]

### Changed
- [List modifications to existing functionality]

### Fixed
- [List bug fixes]

### Removed
- [List deprecated or removed features]

---

## [1.0.0] - YYYY-MM-DD

### Added
- Initial release
- [Feature 1]
- [Feature 2]

### Documentation
- Created README.md with project overview
- Created PROCESS.md with methodology
- Created DATA_DICTIONARY.md with field descriptions

---

## Template for New Entries

Copy this template when adding new changes:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New feature in `src/module.py:123-145`
  - **What**: Description of new feature
  - **Why**: Rationale for adding this feature
  - **Usage**: How to use the new feature

### Changed
- Modified function in `src/module.py:67-89`
  - **What**: Description of change
  - **Why**: Rationale for change
  - **Impact**: How this affects existing functionality
  - **Breaking**: Yes/No - if yes, describe migration path

### Fixed
- Fixed bug in `src/module.py:234`
  - **Issue**: Description of the bug
  - **Cause**: Root cause analysis
  - **Solution**: How it was fixed
  - **Affected versions**: Which versions had this bug

### Removed
- Removed deprecated function `old_function()` from `src/module.py`
  - **Reason**: Why it was removed
  - **Replacement**: What to use instead
  - **Migration**: How to update existing code

### Files Affected
- `src/module.py` (lines 67-89, 123-145, 234)
- `src/utils.py` (lines 45-52)
- `docs/PROCESS.md` (updated section 3)
- `README.md` (updated usage examples)
- `requirements.txt` (added new dependency: package-name==1.2.3)
```

---

## Version Numbering Guide

Use Semantic Versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (X.0.0): Incompatible API changes or major restructuring
- **MINOR** (0.X.0): New features, backward-compatible
- **PATCH** (0.0.X): Bug fixes, backward-compatible

Examples:
- `1.0.0` → `1.0.1`: Bug fix
- `1.0.1` → `1.1.0`: New feature added
- `1.1.0` → `2.0.0`: Breaking change

---

## Change Categories

### Added
- New features
- New files or modules
- New configuration options
- New documentation

### Changed
- Modifications to existing features
- Performance improvements
- Refactoring (that affects behavior)
- Updated dependencies

### Fixed
- Bug fixes
- Security patches
- Corrected documentation

### Removed
- Deprecated features
- Removed files or modules
- Removed dependencies

### Security
- Security vulnerability fixes
- Security improvements

### Deprecated
- Features marked for removal in future versions
- Include timeline for removal

---

## Best Practices

1. **Update immediately**: Add entries as you make changes, not later
2. **Be specific**: Include file paths and line numbers
3. **Explain why**: Document rationale, not just what changed
4. **Link issues**: Reference issue numbers or tickets when applicable
5. **Date format**: Use ISO 8601 (YYYY-MM-DD)
6. **Keep chronological**: Most recent changes at the top
7. **Group related changes**: Combine related changes in one version entry
8. **Describe impact**: Explain how changes affect users or other code
