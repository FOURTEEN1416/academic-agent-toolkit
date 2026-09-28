# smart-file-writer References

Navigation index for detailed documentation.

## Core Documentation

### [diagnostic-procedures.md](diagnostic-procedures.md)
Detailed step-by-step diagnostic workflows for each error type:
- Permission errors
- Disk space issues
- Path length problems
- File locking
- File system limitations

### [platform-specific.md](platform-specific.md)
Platform-specific issues and solutions:
- Windows: Path length limits, file attributes, handle.exe usage
- Linux: Permission models, inode limits, filesystem types
- macOS: Extended attributes, Gatekeeper interference

### [integration-guide.md](integration-guide.md)
How to integrate smart-file-writer with Claude Code tools:
- Wrapping Write tool calls
- Wrapping Edit tool calls
- Wrapping Bash file operations
- Proactive validation patterns

### [error-catalog.md](error-catalog.md)
Comprehensive catalog of file write errors:
- Error messages by platform
- Root cause mapping
- Resolution strategies
- Prevention techniques

## Quick Links

- **Most Common Issue**: Permission denied → See diagnostic-procedures.md § Permission Errors
- **Windows Path Limits**: → See platform-specific.md § Windows Path Length
- **File Locks**: → See diagnostic-procedures.md § File Locking Detection
- **Proactive Validation**: → See integration-guide.md § Pre-Write Validation

## External Resources

- [Python os module](https://docs.python.org/3/library/os.html)
- [Python shutil module](https://docs.python.org/3/library/shutil.html)
- [Windows File System Limits](https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)
- [POSIX File Permissions](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_stat.h.html)
