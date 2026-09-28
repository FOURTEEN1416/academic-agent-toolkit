---
name: smart-file-writer
description: "Intelligent file write error handler: diagnoses permissions, disk space, path length, file locks before retrying. Use when you encounter 'Error writing file', 'Permission denied', 'Access denied', 'No space left', or related file write failures."
---

# smart-file-writer Skill

Automatically diagnoses and resolves file write errors through systematic investigation rather than blind retries. Prevents common write failures proactively.

## When to Use This Skill

Use this skill when any of these occurs:
- "Error writing file" messages
- "Permission denied" or "Access denied" errors
- "No space left on device" errors
- "File exists" conflicts
- "Path too long" errors (Windows)
- "Read-only file system" errors
- Any file write operation failure (Python, CLI, any language)
- Before critical file writes (proactive mode)

## Not For / Boundaries

This skill does NOT:
- Handle network file system issues (NFS, SMB) beyond basic diagnostics
- Modify system-level permissions without user confirmation
- Bypass security policies or antivirus software
- Handle database write operations (different error domain)

Required inputs:
- Target file path
- Intended operation (write, append, create, etc.)
- Error message (if reactive mode)

## Quick Reference

### Diagnostic Checklist (Run Before Retry)

**1. Path Validation**
```python
import os
# Check path length (Windows: 260 char limit)
if len(filepath) > 260 and os.name == 'nt':
    print(f"Path too long: {len(filepath)} chars")

# Check parent directory exists
parent = os.path.dirname(filepath)
if not os.path.exists(parent):
    print(f"Parent directory missing: {parent}")
```

**2. Permission Check**
```python
import os
# Check directory write permission
parent = os.path.dirname(filepath) or '.'
if not os.access(parent, os.W_OK):
    print(f"No write permission: {parent}")

# Check file permissions if exists
if os.path.exists(filepath):
    if not os.access(filepath, os.W_OK):
        print(f"File not writable: {filepath}")
```

**3. Disk Space Check**
```python
import shutil
# Check available disk space
stat = shutil.disk_usage(os.path.dirname(filepath) or '.')
free_gb = stat.free / (1024**3)
if free_gb < 0.1:  # Less than 100MB
    print(f"Low disk space: {free_gb:.2f} GB free")
```

**4. File Lock Detection**
```python
import os
# Try to open with exclusive access
try:
    with open(filepath, 'a') as f:
        pass
except PermissionError:
    print(f"File locked by another process: {filepath}")
```

**5. Windows-Specific Checks**
```bash
# Check if file is in use (Windows)
handle.exe -a "filepath"

# Check file attributes
attrib "filepath"
```

### Resolution Patterns

**Pattern 1: Create Missing Directories**
```python
import os
os.makedirs(os.path.dirname(filepath), exist_ok=True)
```

**Pattern 2: Atomic Write (Temp + Rename)**
```python
import os
import tempfile

# Write to temp file first
temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filepath))
try:
    with os.fdopen(temp_fd, 'w') as f:
        f.write(content)
    # Atomic rename
    os.replace(temp_path, filepath)
except Exception as e:
    os.unlink(temp_path)
    raise
```

**Pattern 3: Exponential Backoff for Transient Issues**
```python
import time

def write_with_retry(filepath, content, max_retries=3):
    for attempt in range(max_retries):
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return True
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)
            else:
                raise
```

**Pattern 4: Alternative Path (Shorten Long Paths)**
```python
import os
import hashlib

def shorten_path(long_path):
    """Use hash for long filenames"""
    dir_path = os.path.dirname(long_path)
    filename = os.path.basename(long_path)

    if len(long_path) > 260:
        # Hash the filename
        name, ext = os.path.splitext(filename)
        hash_name = hashlib.md5(name.encode()).hexdigest()[:16]
        return os.path.join(dir_path, f"{hash_name}{ext}")
    return long_path
```

**Pattern 5: Permission Fix Suggestions**
```bash
# Linux/Mac: Add write permission
chmod u+w filepath

# Windows: Remove read-only attribute
attrib -r filepath

# Windows: Take ownership (admin required)
takeown /f filepath
icacls filepath /grant %username%:F
```

**Pattern 6: Detect Antivirus Interference**
```python
import time
import os

def is_antivirus_blocking(filepath):
    """Detect if antivirus is scanning file"""
    try:
        # Try to open exclusively
        with open(filepath, 'r+b') as f:
            pass
        return False
    except PermissionError:
        # Wait and retry
        time.sleep(0.5)
        try:
            with open(filepath, 'r+b') as f:
                pass
            return True  # Was temporarily blocked
        except:
            return False  # Persistent block
```

### Proactive Pre-Write Validation

**Before Any Critical Write**
```python
def validate_write_conditions(filepath):
    """Run before writing important files"""
    issues = []

    # 1. Path length
    if len(filepath) > 260 and os.name == 'nt':
        issues.append(f"Path too long: {len(filepath)} chars")

    # 2. Parent directory
    parent = os.path.dirname(filepath) or '.'
    if not os.path.exists(parent):
        issues.append(f"Parent missing: {parent}")
    elif not os.access(parent, os.W_OK):
        issues.append(f"No write permission: {parent}")

    # 3. Disk space
    stat = shutil.disk_usage(parent)
    if stat.free < 100 * 1024 * 1024:  # 100MB
        issues.append(f"Low disk space: {stat.free / 1024**2:.1f} MB")

    # 4. File exists and writable
    if os.path.exists(filepath):
        if not os.access(filepath, os.W_OK):
            issues.append(f"File not writable: {filepath}")

    return issues
```

### Integration with Claude Code Tools

**Wrap Write Tool**
```python
# Before using Write tool, validate:
issues = validate_write_conditions(target_path)
if issues:
    print("Pre-write validation failed:")
    for issue in issues:
        print(f"  - {issue}")
    # Take corrective action
else:
    # Proceed with Write tool
```

**Wrap Edit Tool**
```python
# Before editing, check file is writable
if not os.access(filepath, os.W_OK):
    print(f"Cannot edit: {filepath} is read-only")
    # Suggest: chmod u+w or attrib -r
```

**Wrap Bash File Operations**
```bash
# Before redirecting output
if [ ! -w "$(dirname "$output_file")" ]; then
    echo "Cannot write to directory"
    exit 1
fi
```

## Examples

### Example 1: Reactive - Handle "Error writing file"

**Input:**
- Error: "Error writing file: results/model_checkpoint.pth"
- Operation: torch.save(model.state_dict(), filepath)

**Steps:**
1. Run diagnostic checklist:
   - Path length: 45 chars ✓
   - Parent exists: No ✗
   - Permissions: N/A (parent missing)
   - Disk space: 50GB ✓
2. Root cause: Parent directory doesn't exist
3. Resolution: `os.makedirs('results', exist_ok=True)`
4. Retry write operation
5. Success

**Expected output:**
```
Diagnosis: Parent directory 'results' does not exist
Resolution: Created directory 'results'
Retry: torch.save() succeeded
```

### Example 2: Proactive - Prevent Long Path Error

**Input:**
- Target: `D:\very\long\path\with\many\subdirectories\...\extremely_long_filename_that_exceeds_windows_limit.csv`
- Operation: pandas.to_csv()

**Steps:**
1. Pre-write validation detects path length: 285 chars
2. Suggest shortened path using hash
3. Create mapping file for reference
4. Write to shortened path
5. Log original -> shortened mapping

**Expected output:**
```
Warning: Path length 285 chars exceeds Windows limit (260)
Alternative: D:\very\long\path\...\a3f5e8b2c1d4.csv
Mapping saved to: path_mappings.json
Write succeeded to alternative path
```

### Example 3: Reactive - Permission Denied on Windows

**Input:**
- Error: "PermissionError: [Errno 13] Permission denied: 'data.csv'"
- Operation: Writing CSV file

**Steps:**
1. Run diagnostic checklist:
   - File exists: Yes
   - File attributes: Read-only ✗
   - File lock: Not locked
   - Permissions: Read-only attribute set
2. Root cause: File has read-only attribute
3. Resolution: Suggest `attrib -r data.csv`
4. After user confirms, remove attribute
5. Retry write

**Expected output:**
```
Diagnosis: File 'data.csv' has read-only attribute
Resolution: Run 'attrib -r data.csv' to remove read-only flag
[After user confirmation]
Attribute removed. Retry succeeded.
```

### Example 4: Reactive - File Locked by Another Process

**Input:**
- Error: "PermissionError: [Errno 13] Permission denied: 'report.xlsx'"
- Operation: Writing Excel file

**Steps:**
1. Run diagnostic checklist:
   - File exists: Yes
   - Permissions: Writable
   - File lock test: Locked ✗
2. Root cause: File open in Excel
3. Resolution: Cannot proceed, inform user
4. Suggest: Close Excel or write to alternative filename

**Expected output:**
```
Diagnosis: File 'report.xlsx' is locked by another process
Likely cause: File is open in Microsoft Excel
Resolution options:
  1. Close Excel and retry
  2. Write to alternative: 'report_new.xlsx'
  3. Use atomic write with temp file
Cannot proceed automatically. User action required.
```

### Example 5: Proactive - Low Disk Space

**Input:**
- Target: Large model checkpoint (2GB)
- Operation: torch.save()

**Steps:**
1. Pre-write validation checks disk space
2. Detects only 500MB free
3. Warns before attempting write
4. Suggests cleanup or alternative location

**Expected output:**
```
Warning: Insufficient disk space
Required: ~2.0 GB
Available: 0.5 GB
Recommendations:
  1. Clean up temporary files
  2. Write to alternative drive: E:\
  3. Compress checkpoint before saving
Write operation blocked to prevent failure.
```

## References

- `references/diagnostic-procedures.md`: Detailed diagnostic workflows
- `references/platform-specific.md`: Windows/Linux/Mac specific issues
- `references/integration-guide.md`: Integrating with Claude Code tools
- `references/error-catalog.md`: Common error messages and solutions

## Maintenance

- Sources: Python os/shutil docs, Windows file system limits, POSIX standards
- Last updated: 2026-01-20
- Known limits:
  - Network file systems (NFS/SMB) require specialized handling
  - Some antivirus software cannot be reliably detected
  - System-level permission changes require admin rights
