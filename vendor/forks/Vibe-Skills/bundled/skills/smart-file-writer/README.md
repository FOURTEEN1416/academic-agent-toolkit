# smart-file-writer Skill

Intelligent file write error handler that diagnoses and resolves file write issues automatically.

## Quick Start

This skill **auto-activates** when file write errors occur. You don't need to call it manually - it will trigger automatically when Claude Code encounters:

- "Error writing file"
- "Permission denied"
- "Access denied"
- "No space left on device"
- "Path too long"
- Any file write operation failure

## What It Does

Instead of blindly retrying failed writes, smart-file-writer:

1. **Diagnoses** the root cause:
   - Permission issues
   - Disk space problems
   - Path length limits (Windows)
   - File locks
   - Missing directories
   - File system limitations

2. **Resolves** automatically when possible:
   - Creates missing parent directories
   - Suggests permission fixes
   - Proposes alternative paths
   - Uses atomic write operations
   - Implements exponential backoff

3. **Reports** clearly:
   - Root cause analysis
   - Attempted solutions
   - Success/failure status
   - Recommendations for permanent fixes

## Examples

### Example 1: Missing Directory

**Before:**
```
Error writing file: results/model_checkpoint.pth
```

**With smart-file-writer:**
```
Diagnosis: Parent directory 'results' does not exist
Resolution: Created directory 'results'
Retry: Write succeeded
```

### Example 2: Path Too Long (Windows)

**Before:**
```
Error: Path too long (285 characters)
```

**With smart-file-writer:**
```
Warning: Path length 285 chars exceeds Windows limit (260)
Alternative: D:\project\a3f5e8b2c1d4.csv
Mapping saved to: path_mappings.json
Write succeeded to alternative path
```

### Example 3: Read-Only File

**Before:**
```
PermissionError: [Errno 13] Permission denied: 'data.csv'
```

**With smart-file-writer:**
```
Diagnosis: File 'data.csv' has read-only attribute
Resolution: Run 'attrib -r data.csv' to remove read-only flag
[After confirmation] Attribute removed. Retry succeeded.
```

## Proactive Mode

You can also use smart-file-writer proactively to prevent errors before they happen:

```python
# Validate before critical write
issues = validate_write_conditions('important_file.txt')
if not issues:
    # Safe to proceed
    write_file()
```

## Documentation

- **SKILL.md**: Complete skill reference with all patterns
- **references/diagnostic-procedures.md**: Detailed diagnostic workflows
- **references/platform-specific.md**: Windows/Linux/Mac specific issues
- **references/integration-guide.md**: Integration with Claude Code tools

## Validation

Run the validation script to test the skill:

```bash
cd scripts
python validate.py
```

All tests should pass on your platform.

## Installation

This skill is already installed in your Claude Code skills directory:
```
C:\Users\羽裳\.claude\skills\smart-file-writer\
```

It will auto-activate when needed. No manual configuration required.

## Supported Platforms

- ✓ Windows (10/11)
- ✓ Linux (all distributions)
- ✓ macOS

Platform-specific features:
- Windows: Path length detection, file attribute handling
- Linux: Permission model, inode limits, SELinux
- macOS: Gatekeeper, SIP, extended attributes

## License

Part of Claude Code skills collection.
