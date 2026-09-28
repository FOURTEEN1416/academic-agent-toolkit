# Diagnostic Procedures

Systematic workflows for diagnosing file write errors.

## Permission Errors

### Symptoms
- "Permission denied"
- "Access denied"
- "Operation not permitted"
- errno 13 (EACCES)

### Diagnostic Workflow

1. **Check if file exists**
   ```python
   import os
   exists = os.path.exists(filepath)
   ```

2. **Check file permissions**
   ```python
   if exists:
       readable = os.access(filepath, os.R_OK)
       writable = os.access(filepath, os.W_OK)
       executable = os.access(filepath, os.X_OK)
   ```

3. **Check parent directory permissions**
   ```python
   parent = os.path.dirname(filepath) or '.'
   parent_writable = os.access(parent, os.W_OK)
   ```

4. **Check file attributes (Windows)**
   ```bash
   attrib "filepath"
   # Look for 'R' (read-only)
   ```

5. **Check ownership (Linux/Mac)**
   ```bash
   ls -l filepath
   # Compare owner with current user
   ```

### Resolution Strategies

**If file is read-only:**
```python
# Python
import os
import stat
os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)

# Windows CLI
attrib -r filepath

# Linux/Mac CLI
chmod u+w filepath
```

**If parent directory not writable:**
- Check if directory exists: create if missing
- Check permissions: may need sudo/admin rights
- Check disk is not mounted read-only

**If ownership issue (Linux/Mac):**
```bash
# Change owner (requires sudo)
sudo chown $USER filepath

# Or write to user-owned location
```

## Disk Space Issues

### Symptoms
- "No space left on device"
- "Disk full"
- errno 28 (ENOSPC)

### Diagnostic Workflow

1. **Check available space**
   ```python
   import shutil
   stat = shutil.disk_usage(path)
   print(f"Free: {stat.free / 1024**3:.2f} GB")
   print(f"Total: {stat.total / 1024**3:.2f} GB")
   print(f"Used: {stat.used / 1024**3:.2f} GB")
   ```

2. **Estimate required space**
   ```python
   # For in-memory data
   import sys
   size_bytes = sys.getsizeof(data)

   # For existing file (copy/move)
   size_bytes = os.path.getsize(source_file)
   ```

3. **Check for large temporary files**
   ```bash
   # Linux/Mac
   du -sh /tmp/*

   # Windows
   dir %TEMP% /s
   ```

### Resolution Strategies

**If insufficient space:**
1. Clean temporary files
2. Write to alternative location (different drive)
3. Compress data before writing
4. Stream write instead of buffering entire file

**Cleanup examples:**
```python
import tempfile
import shutil

# Clean Python temp directory
temp_dir = tempfile.gettempdir()
# Manually remove old files

# Or specify alternative temp location
os.environ['TMPDIR'] = '/path/with/more/space'
```

## Path Length Problems

### Symptoms
- "File name too long"
- "Path too long"
- errno 36 (ENAMETOOLONG)
- Windows: Paths > 260 characters fail

### Diagnostic Workflow

1. **Check path length**
   ```python
   path_length = len(os.path.abspath(filepath))
   print(f"Path length: {path_length}")

   # Windows limit
   if os.name == 'nt' and path_length > 260:
       print("Exceeds Windows MAX_PATH limit")
   ```

2. **Check filename length**
   ```python
   filename = os.path.basename(filepath)
   if len(filename) > 255:
       print("Filename exceeds 255 char limit")
   ```

### Resolution Strategies

**Shorten path:**
```python
import hashlib

def shorten_filename(filepath, max_length=200):
    """Shorten long filenames using hash"""
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)

    if len(filepath) <= max_length:
        return filepath

    # Hash the name part
    hash_name = hashlib.md5(name.encode()).hexdigest()[:16]
    new_filename = f"{hash_name}{ext}"
    return os.path.join(directory, new_filename)
```

**Enable long paths on Windows 10+:**
```powershell
# Requires admin rights and Windows 10 1607+
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**Use UNC paths (Windows):**
```python
# Prefix with \\?\ to bypass MAX_PATH
if os.name == 'nt':
    filepath = '\\\\?\\' + os.path.abspath(filepath)
```

## File Locking Detection

### Symptoms
- "Permission denied" when file exists and should be writable
- "The process cannot access the file because it is being used by another process"
- errno 13 (EACCES) on Windows

### Diagnostic Workflow

1. **Test exclusive access**
   ```python
   def is_file_locked(filepath):
       """Check if file is locked by another process"""
       if not os.path.exists(filepath):
           return False

       try:
           # Try to open with exclusive access
           with open(filepath, 'a') as f:
               pass
           return False
       except (PermissionError, IOError):
           return True
   ```

2. **Identify locking process (Windows)**
   ```bash
   # Using handle.exe from Sysinternals
   handle.exe -a filepath

   # Using PowerShell
   Get-Process | Where-Object {$_.Modules.FileName -eq "filepath"}
   ```

3. **Identify locking process (Linux)**
   ```bash
   # Using lsof
   lsof filepath

   # Using fuser
   fuser filepath
   ```

### Resolution Strategies

**Wait and retry:**
```python
import time

def wait_for_file_unlock(filepath, timeout=30, interval=1):
    """Wait for file to become available"""
    start = time.time()
    while time.time() - start < timeout:
        if not is_file_locked(filepath):
            return True
        time.sleep(interval)
    return False
```

**Write to alternative file:**
```python
def get_alternative_filename(filepath):
    """Generate alternative filename if locked"""
    name, ext = os.path.splitext(filepath)
    counter = 1
    while True:
        alt_path = f"{name}_{counter}{ext}"
        if not os.path.exists(alt_path):
            return alt_path
        counter += 1
```

**Force close (use with caution):**
```bash
# Windows: Kill process holding file
taskkill /F /PID <pid>

# Linux: Kill process
kill -9 <pid>
```

## File System Limitations

### Symptoms
- "Read-only file system"
- "Function not implemented"
- "Invalid argument"

### Diagnostic Workflow

1. **Check mount status (Linux/Mac)**
   ```bash
   mount | grep "$(df filepath | tail -1 | awk '{print $1}')"
   # Look for 'ro' (read-only)
   ```

2. **Check file system type**
   ```python
   import platform
   if platform.system() != 'Windows':
       import subprocess
       result = subprocess.run(['df', '-T', filepath],
                             capture_output=True, text=True)
       print(result.stdout)
   ```

3. **Check for special file systems**
   - Network mounts (NFS, SMB)
   - Virtual file systems (/proc, /sys)
   - CD-ROM/DVD mounts

### Resolution Strategies

**If read-only mount:**
```bash
# Remount as read-write (requires sudo)
sudo mount -o remount,rw /mount/point
```

**If network file system:**
- Check network connectivity
- Verify mount options
- Consider writing locally then copying

**If virtual file system:**
- Cannot write to /proc, /sys, etc.
- Write to appropriate location (/tmp, /var, home directory)
