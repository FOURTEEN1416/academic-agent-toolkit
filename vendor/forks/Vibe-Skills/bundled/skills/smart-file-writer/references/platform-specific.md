# Platform-Specific Issues

File write issues unique to each operating system.

## Windows

### Path Length Limitations

**MAX_PATH Limit (260 characters)**

Windows has a historical 260-character limit for file paths:
- 260 chars includes drive letter, path separators, filename, and null terminator
- Affects most Win32 APIs
- Can be bypassed with UNC paths or long path support

**Check if path exceeds limit:**
```python
import os
if os.name == 'nt':
    abs_path = os.path.abspath(filepath)
    if len(abs_path) > 260:
        print(f"Path too long: {len(abs_path)} chars")
```

**Solution 1: Enable Long Path Support (Windows 10 1607+)**
```powershell
# Requires administrator privileges
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# Also need to enable in Python (3.6+)
# Add to manifest or use \\?\ prefix
```

**Solution 2: Use UNC Path Prefix**
```python
def enable_long_path_windows(filepath):
    """Add \\?\ prefix to bypass MAX_PATH"""
    if os.name == 'nt' and not filepath.startswith('\\\\?\\'):
        abs_path = os.path.abspath(filepath)
        return '\\\\?\\' + abs_path
    return filepath
```

**Solution 3: Shorten Path**
- Move to shorter directory
- Use shorter filenames
- Use subst to create virtual drive

```cmd
REM Create virtual drive at shorter path
subst Z: "C:\Very\Long\Path\To\Project"
```

### File Attributes

**Read-Only Attribute**

Windows files can have read-only attribute set:

```bash
# Check attributes
attrib filepath

# Output: R = read-only, H = hidden, S = system, A = archive
```

**Remove read-only:**
```python
import os
import stat

def remove_readonly_windows(filepath):
    """Remove read-only attribute on Windows"""
    if os.name == 'nt' and os.path.exists(filepath):
        os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)
```

```cmd
REM Command line
attrib -r filepath
```

### File Locking

Windows locks files more aggressively than Unix systems:
- Files opened for reading are often locked
- Excel, Word lock files exclusively
- Antivirus software may lock files during scanning

**Detect locked files:**
```python
def is_locked_windows(filepath):
    """Check if file is locked on Windows"""
    import os
    if not os.path.exists(filepath):
        return False

    try:
        # Try to rename to itself (no-op that requires exclusive access)
        os.rename(filepath, filepath)
        return False
    except (PermissionError, OSError):
        return True
```

**Find process holding file (requires Sysinternals handle.exe):**
```cmd
handle.exe -a filepath
```

### Antivirus Interference

Antivirus software can interfere with file writes:
- Real-time scanning locks files temporarily
- Quarantine actions prevent writes
- False positives block executable writes

**Detection strategy:**
```python
import time

def detect_antivirus_interference(filepath):
    """Detect if antivirus is causing delays"""
    attempts = []

    for i in range(3):
        start = time.time()
        try:
            with open(filepath, 'w') as f:
                f.write('test')
            duration = time.time() - start
            attempts.append(duration)
        except PermissionError:
            return True  # Blocked
        time.sleep(0.5)

    # If writes take >100ms, likely AV scanning
    avg_time = sum(attempts) / len(attempts)
    return avg_time > 0.1
```

**Mitigation:**
- Add directory to antivirus exclusions
- Use temp directory (often excluded)
- Write with different extension, then rename

## Linux

### Permission Model

Linux uses POSIX permission model:
- Owner, Group, Others
- Read (r), Write (w), Execute (x)
- Numeric: 755 = rwxr-xr-x

**Check permissions:**
```bash
ls -l filepath
# Output: -rw-r--r-- 1 user group size date filepath
```

**Common permission issues:**

1. **File owned by different user:**
```bash
# Check owner
stat -c '%U %G' filepath

# Change owner (requires sudo)
sudo chown $USER:$USER filepath
```

2. **Directory not writable:**
```bash
# Check directory permissions
ls -ld directory

# Add write permission
chmod u+w directory
```

3. **Parent directory missing execute permission:**
```bash
# Need execute (x) to access directory contents
chmod u+x parent_directory
```

### Inode Limits

File systems have limited inodes (file metadata entries):

**Check inode usage:**
```bash
df -i
# Shows inode usage per filesystem
```

**If inodes exhausted:**
- Delete unnecessary files (especially small files)
- Move to filesystem with more inodes
- Reformat with more inodes (destructive)

### File System Types

Different file systems have different limitations:

**ext4:**
- Max filename: 255 bytes
- Max path: 4096 bytes
- Max file size: 16 TB

**XFS:**
- Max filename: 255 bytes
- Max path: 4096 bytes
- Max file size: 8 EB

**NFS (Network File System):**
- Permissions may not match local system
- Locking behavior differs
- Latency can cause timeouts

**Check filesystem type:**
```bash
df -T filepath
```

### SELinux / AppArmor

Security modules can block file writes:

**Check SELinux status:**
```bash
getenforce
# Output: Enforcing, Permissive, or Disabled
```

**Check SELinux denials:**
```bash
ausearch -m avc -ts recent
```

**Temporary disable (testing only):**
```bash
sudo setenforce 0  # Permissive mode
```

## macOS

### Gatekeeper and Quarantine

macOS Gatekeeper can interfere with file operations:

**Check quarantine attribute:**
```bash
xattr -l filepath
# Look for com.apple.quarantine
```

**Remove quarantine:**
```bash
xattr -d com.apple.quarantine filepath
```

### System Integrity Protection (SIP)

SIP prevents writes to system directories:
- /System
- /usr (except /usr/local)
- /bin, /sbin

**Check SIP status:**
```bash
csrutil status
```

**Cannot write to protected locations even with sudo**
- Write to /usr/local instead
- Write to user directories
- Disable SIP (not recommended)

### Extended Attributes

macOS uses extended attributes extensively:

**List extended attributes:**
```bash
xattr -l filepath
```

**Remove all extended attributes:**
```bash
xattr -c filepath
```

### Case Sensitivity

macOS file system (APFS/HFS+) is case-insensitive by default:
- "File.txt" and "file.txt" are the same
- Can cause issues with case-sensitive code
- Check with: `diskutil info / | grep "Case-sensitive"`

### Permission Issues with iCloud Drive

Files in iCloud Drive may have special handling:
- Files may not be fully downloaded
- Writes may sync slowly
- Conflicts can occur

**Check if file is cloud-only:**
```bash
ls -lO filepath
# Look for 'compressed' flag
```

## Cross-Platform Best Practices

### Path Handling

```python
import os

# Always use os.path.join for cross-platform paths
filepath = os.path.join('data', 'results', 'output.csv')

# Normalize paths
filepath = os.path.normpath(filepath)

# Get absolute path
filepath = os.path.abspath(filepath)
```

### Line Endings

Different platforms use different line endings:
- Windows: CRLF (\r\n)
- Linux/Mac: LF (\n)

```python
# Use text mode for automatic conversion
with open(filepath, 'w', newline='') as f:
    # newline='' prevents automatic conversion
    f.write(content)

# Or explicitly handle
content = content.replace('\r\n', '\n')  # Normalize to LF
```

### Atomic Writes

Use atomic writes for cross-platform reliability:

```python
import os
import tempfile

def atomic_write(filepath, content):
    """Write atomically on any platform"""
    # Write to temp file in same directory
    dir_path = os.path.dirname(filepath) or '.'
    fd, temp_path = tempfile.mkstemp(dir=dir_path, text=True)

    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)

        # Atomic rename (works on all platforms)
        os.replace(temp_path, filepath)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except:
            pass
        raise
```

### Permission Handling

```python
import os
import stat

def ensure_writable(filepath):
    """Make file writable on any platform"""
    if os.path.exists(filepath):
        current = os.stat(filepath).st_mode
        os.chmod(filepath, current | stat.S_IWRITE)
```
