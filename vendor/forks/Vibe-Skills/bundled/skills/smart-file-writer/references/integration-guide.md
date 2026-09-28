# Integration Guide

How to integrate smart-file-writer with Claude Code tools and workflows.

## Overview

The smart-file-writer skill can be used in two modes:
1. **Reactive**: Triggered automatically when file write errors occur
2. **Proactive**: Called before critical file operations to prevent errors

## Integration with Claude Code Tools

### Write Tool Integration

**Before using Write tool:**

```python
import os
import shutil

def validate_write_conditions(filepath):
    """Pre-flight check before Write tool"""
    issues = []

    # 1. Path length check
    if len(filepath) > 260 and os.name == 'nt':
        issues.append({
            'type': 'path_length',
            'message': f'Path too long: {len(filepath)} chars',
            'fix': 'Use shorter path or enable long paths'
        })

    # 2. Parent directory check
    parent = os.path.dirname(filepath) or '.'
    if not os.path.exists(parent):
        issues.append({
            'type': 'missing_parent',
            'message': f'Parent directory does not exist: {parent}',
            'fix': f'Create directory: os.makedirs("{parent}", exist_ok=True)'
        })
    elif not os.access(parent, os.W_OK):
        issues.append({
            'type': 'permission',
            'message': f'No write permission for directory: {parent}',
            'fix': 'Check directory permissions'
        })

    # 3. Disk space check
    try:
        stat = shutil.disk_usage(parent)
        free_mb = stat.free / (1024 ** 2)
        if free_mb < 100:
            issues.append({
                'type': 'disk_space',
                'message': f'Low disk space: {free_mb:.1f} MB free',
                'fix': 'Free up disk space or use alternative location'
            })
    except Exception as e:
        issues.append({
            'type': 'disk_check_failed',
            'message': f'Could not check disk space: {e}',
            'fix': 'Verify path is valid'
        })

    # 4. Existing file check
    if os.path.exists(filepath):
        if not os.access(filepath, os.W_OK):
            issues.append({
                'type': 'readonly',
                'message': f'File is read-only: {filepath}',
                'fix': 'Remove read-only attribute'
            })

    return issues

# Usage in Claude Code workflow
issues = validate_write_conditions(target_path)
if issues:
    print("⚠️  Pre-write validation found issues:")
    for issue in issues:
        print(f"  [{issue['type']}] {issue['message']}")
        print(f"    Fix: {issue['fix']}")

    # Auto-fix if possible
    for issue in issues:
        if issue['type'] == 'missing_parent':
            parent = os.path.dirname(target_path)
            os.makedirs(parent, exist_ok=True)
            print(f"  ✓ Created directory: {parent}")

    # Re-validate
    issues = validate_write_conditions(target_path)

if not issues:
    # Proceed with Write tool
    print(f"✓ Pre-write validation passed for: {target_path}")
```

### Edit Tool Integration

**Before using Edit tool:**

```python
def validate_edit_conditions(filepath):
    """Pre-flight check before Edit tool"""
    issues = []

    # 1. File must exist
    if not os.path.exists(filepath):
        issues.append({
            'type': 'not_found',
            'message': f'File does not exist: {filepath}',
            'fix': 'Use Write tool instead of Edit'
        })
        return issues  # No point checking further

    # 2. File must be readable
    if not os.access(filepath, os.R_OK):
        issues.append({
            'type': 'not_readable',
            'message': f'Cannot read file: {filepath}',
            'fix': 'Check file permissions'
        })

    # 3. File must be writable
    if not os.access(filepath, os.W_OK):
        issues.append({
            'type': 'not_writable',
            'message': f'File is read-only: {filepath}',
            'fix': 'Remove read-only attribute'
        })

    # 4. Check if file is locked
    try:
        with open(filepath, 'a') as f:
            pass
    except (PermissionError, IOError):
        issues.append({
            'type': 'locked',
            'message': f'File is locked by another process: {filepath}',
            'fix': 'Close other programs using this file'
        })

    return issues

# Usage
issues = validate_edit_conditions(target_path)
if issues:
    print("⚠️  Cannot edit file:")
    for issue in issues:
        print(f"  [{issue['type']}] {issue['message']}")
        print(f"    Fix: {issue['fix']}")
else:
    # Proceed with Edit tool
    print(f"✓ File is editable: {target_path}")
```

### Bash Tool Integration

**For file output operations:**

```bash
#!/bin/bash

# Function to validate write conditions
validate_write() {
    local filepath="$1"
    local parent_dir=$(dirname "$filepath")

    # Check parent directory exists
    if [ ! -d "$parent_dir" ]; then
        echo "Error: Parent directory does not exist: $parent_dir"
        return 1
    fi

    # Check parent directory is writable
    if [ ! -w "$parent_dir" ]; then
        echo "Error: No write permission for directory: $parent_dir"
        return 1
    fi

    # Check disk space (Linux/Mac)
    if command -v df &> /dev/null; then
        local free_kb=$(df "$parent_dir" | tail -1 | awk '{print $4}')
        local free_mb=$((free_kb / 1024))
        if [ $free_mb -lt 100 ]; then
            echo "Warning: Low disk space: ${free_mb} MB free"
        fi
    fi

    # Check if file exists and is writable
    if [ -f "$filepath" ] && [ ! -w "$filepath" ]; then
        echo "Error: File is read-only: $filepath"
        return 1
    fi

    return 0
}

# Usage before redirecting output
output_file="results/output.txt"
if validate_write "$output_file"; then
    echo "Data" > "$output_file"
else
    echo "Cannot write to $output_file"
    exit 1
fi
```

## Proactive Validation Patterns

### Pattern 1: Validate Before Batch Operations

```python
def validate_batch_writes(filepaths):
    """Validate multiple files before batch operation"""
    all_issues = {}

    for filepath in filepaths:
        issues = validate_write_conditions(filepath)
        if issues:
            all_issues[filepath] = issues

    if all_issues:
        print(f"⚠️  Found issues with {len(all_issues)} files:")
        for filepath, issues in all_issues.items():
            print(f"\n  {filepath}:")
            for issue in issues:
                print(f"    - {issue['message']}")

        # Auto-fix common issues
        for filepath, issues in all_issues.items():
            for issue in issues:
                if issue['type'] == 'missing_parent':
                    parent = os.path.dirname(filepath)
                    os.makedirs(parent, exist_ok=True)
                    print(f"  ✓ Created: {parent}")

        return False

    return True

# Usage
files_to_write = [
    'results/model1.pth',
    'results/model2.pth',
    'results/metrics.csv'
]

if validate_batch_writes(files_to_write):
    # Proceed with batch operation
    for filepath in files_to_write:
        # Write file...
        pass
```

### Pattern 2: Validate in Training Loops

```python
def setup_training_outputs(output_dir):
    """Validate all output paths before training starts"""
    paths = {
        'checkpoints': os.path.join(output_dir, 'checkpoints'),
        'logs': os.path.join(output_dir, 'logs'),
        'visualizations': os.path.join(output_dir, 'visualizations'),
        'reports': os.path.join(output_dir, 'reports')
    }

    print("Validating output directories...")

    for name, path in paths.items():
        # Create if missing
        os.makedirs(path, exist_ok=True)

        # Validate write access
        test_file = os.path.join(path, '.write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"  ✓ {name}: {path}")
        except Exception as e:
            print(f"  ✗ {name}: {path}")
            print(f"    Error: {e}")
            return False

    # Check disk space
    stat = shutil.disk_usage(output_dir)
    free_gb = stat.free / (1024 ** 3)
    print(f"\nDisk space: {free_gb:.2f} GB free")

    if free_gb < 1:
        print("  ⚠️  Warning: Less than 1 GB free")

    return True

# Usage before training
if setup_training_outputs('results'):
    # Start training
    train_model()
else:
    print("Cannot proceed: output validation failed")
```

### Pattern 3: Atomic Write Wrapper

```python
import tempfile
import os

def atomic_write(filepath, content, mode='w'):
    """Write file atomically with validation"""
    # Pre-validate
    issues = validate_write_conditions(filepath)
    if issues:
        # Try to auto-fix
        for issue in issues:
            if issue['type'] == 'missing_parent':
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Re-validate
        issues = validate_write_conditions(filepath)
        if issues:
            raise IOError(f"Cannot write to {filepath}: {issues}")

    # Write to temp file first
    dir_path = os.path.dirname(filepath) or '.'
    fd, temp_path = tempfile.mkstemp(dir=dir_path, text=(mode == 'w'))

    try:
        if mode == 'w':
            with os.fdopen(fd, 'w') as f:
                f.write(content)
        else:  # binary mode
            with os.fdopen(fd, 'wb') as f:
                f.write(content)

        # Atomic rename
        os.replace(temp_path, filepath)
        return True

    except Exception as e:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass
        raise IOError(f"Failed to write {filepath}: {e}")

# Usage
try:
    atomic_write('results/model.pth', model_data, mode='wb')
    print("✓ Model saved successfully")
except IOError as e:
    print(f"✗ Failed to save model: {e}")
```

## Reactive Error Handling

### Pattern 1: Retry with Diagnosis

```python
import time

def write_with_smart_retry(filepath, content, max_retries=3):
    """Write with intelligent retry on failure"""

    for attempt in range(max_retries):
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return True

        except (PermissionError, OSError, IOError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")

            # Diagnose the issue
            print("Running diagnostics...")

            # Check if file is locked
            if "being used by another process" in str(e):
                print("  → File is locked by another process")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  → Waiting {wait_time}s for file to be released...")
                    time.sleep(wait_time)
                    continue

            # Check permissions
            parent = os.path.dirname(filepath) or '.'
            if not os.access(parent, os.W_OK):
                print(f"  → No write permission for: {parent}")
                return False

            # Check disk space
            stat = shutil.disk_usage(parent)
            if stat.free < 1024 * 1024:  # Less than 1MB
                print(f"  → Insufficient disk space: {stat.free} bytes free")
                return False

            # Check path length
            if len(filepath) > 260 and os.name == 'nt':
                print(f"  → Path too long: {len(filepath)} chars")
                return False

            # If we get here, unknown issue
            if attempt < max_retries - 1:
                print(f"  → Retrying in {2 ** attempt}s...")
                time.sleep(2 ** attempt)
            else:
                print("  → Max retries exceeded")
                return False

    return False

# Usage
if write_with_smart_retry('output.txt', data):
    print("✓ Write succeeded")
else:
    print("✗ Write failed after diagnostics and retries")
```

### Pattern 2: Fallback Strategies

```python
def write_with_fallback(filepath, content):
    """Try multiple strategies to write file"""

    strategies = [
        ('direct', lambda: direct_write(filepath, content)),
        ('atomic', lambda: atomic_write(filepath, content)),
        ('alternative_path', lambda: write_alternative(filepath, content)),
        ('temp_location', lambda: write_temp(filepath, content))
    ]

    for strategy_name, strategy_func in strategies:
        try:
            print(f"Trying strategy: {strategy_name}")
            result = strategy_func()
            print(f"✓ Success with strategy: {strategy_name}")
            return result
        except Exception as e:
            print(f"✗ Strategy '{strategy_name}' failed: {e}")
            continue

    print("✗ All strategies failed")
    return None

def direct_write(filepath, content):
    """Direct write"""
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath

def write_alternative(filepath, content):
    """Write to alternative filename"""
    name, ext = os.path.splitext(filepath)
    alt_path = f"{name}_alt{ext}"
    with open(alt_path, 'w') as f:
        f.write(content)
    return alt_path

def write_temp(filepath, content):
    """Write to temp directory"""
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, os.path.basename(filepath))
    with open(temp_path, 'w') as f:
        f.write(content)
    print(f"  → Written to temp location: {temp_path}")
    return temp_path
```

## Best Practices

1. **Always validate before critical operations**
   - Model checkpoints
   - Final results
   - Configuration files

2. **Use atomic writes for important data**
   - Prevents partial writes
   - Ensures data integrity

3. **Provide clear error messages**
   - Include root cause
   - Suggest fixes
   - Show attempted solutions

4. **Auto-fix when safe**
   - Create missing directories
   - Remove read-only attributes (with caution)
   - Wait for locked files

5. **Fail gracefully**
   - Don't lose data
   - Provide alternative paths
   - Log all attempts

6. **Test write access early**
   - Before long operations
   - Before training loops
   - Before batch processing
