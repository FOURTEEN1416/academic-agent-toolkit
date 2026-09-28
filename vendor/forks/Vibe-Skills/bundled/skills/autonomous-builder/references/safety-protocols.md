# Safety Protocols Reference

Comprehensive guide for safe autonomous operations with system protection.

## Overview

This document defines the safety protocols that govern all autonomous-builder operations. These rules are designed to protect:
1. **System integrity** - Prevent damage to operating system and system files
2. **Data safety** - Prevent accidental data loss
3. **User control** - Ensure user has final say on risky operations

## Safety Classification

### Risk Levels

| Level | Description | Action Required |
|-------|-------------|-----------------|
| GREEN | Safe operation within workspace | Proceed automatically |
| YELLOW | Potentially risky but reversible | Warn user, proceed with caution |
| RED | Dangerous or irreversible | STOP, require explicit approval |

### Operation Categories

```yaml
GREEN (Safe):
  - Create new files in workspace
  - Modify project source code
  - Read any file
  - Run project tests
  - Install project-local dependencies

YELLOW (Caution):
  - Overwrite existing project files
  - Delete project files
  - Run npm install / pip install (project-local)
  - Modify project configuration files
  - Network operations (API calls, downloads)

RED (Dangerous - Require Approval):
  - Access files outside workspace
  - System configuration changes
  - Global package installations
  - Database operations (DROP, TRUNCATE)
  - Network binding / port operations
  - Any operation with "rm -rf" or similar
```

## Protected Paths

### System Directories (Never Modify)

```
Windows:
  - C:\Windows\
  - C:\Program Files\
  - C:\Program Files (x86)\
  - C:\Users\{other_users}\
  - C:\ProgramData\

Linux:
  - /etc/
  - /usr/
  - /var/
  - /root/
  - /home/{other_users}/
  - /bin/
  - /sbin/

macOS:
  - /System/
  - /Library/
  - /Applications/
  - /Users/{other_users}/
```

### User Data (Confirm Before Accessing)

```
- Desktop (outside project)
- Documents (outside project)
- Downloads (outside project)
- Pictures, Videos, Music folders
- Any folder named: backup, archive, important, private, confidential
- Database files (.db, .sqlite, .mdb)
- Configuration files (.env, config.json outside project)
```

## Pre-Execution Safety Checks

### Checklist Before Any File Operation

```markdown
□ Is the target path inside the workspace?
  ├─ YES: Proceed to next check
  └─ NO: STOP → Display warning → Get user approval

□ Is the operation destructive?
  ├─ NO: Proceed
  └─ YES (delete/overwrite):
      ├─ Is there a backup?
      │   ├─ YES: Proceed with warning
      │   └─ NO: Create backup first

□ Is this a system-wide operation?
  ├─ NO (project-local): Proceed
  └─ YES: STOP → Explain scope → Get user approval

□ Could data be lost if operation fails?
  ├─ NO: Proceed
  └─ YES: Ensure rollback is possible
```

### Path Validation Algorithm

```python
def validate_path_safety(path: str, workspace: str) -> SafetyResult:
    """Validate if a path operation is safe."""

    # Normalize paths
    path = os.path.realpath(path)
    workspace = os.path.realpath(workspace)

    # Check 1: Inside workspace
    if not path.startswith(workspace):
        return SafetyResult(
            level="RED",
            reason="Path is outside workspace",
            action="STOP and request approval"
        )

    # Check 2: Protected system paths
    protected = get_protected_paths()
    for protected_path in protected:
        if path.startswith(protected_path):
            return SafetyResult(
                level="RED",
                reason="Path is in protected system directory",
                action="STOP and request approval"
            )

    # Check 3: Sensitive file patterns
    sensitive_patterns = ['.env', 'credentials', 'secrets', 'private']
    for pattern in sensitive_patterns:
        if pattern in path.lower():
            return SafetyResult(
                level="YELLOW",
                reason="Path may contain sensitive data",
                action="Warn user before proceeding"
            )

    return SafetyResult(
        level="GREEN",
        reason="Path is safe",
        action="Proceed"
    )
```

## Warning Templates

### Out of Workspace Access

```markdown
⚠️ SAFETY ALERT: Out of Workspace Access

Operation: [read/write/delete]
Target: [full path]
Workspace: [workspace path]

This operation targets a file/directory OUTSIDE your project workspace.

Potential Risks:
• May affect system files or other projects
• Changes are not tracked by project version control
• Could impact other applications or user data

Do you want to proceed?
[Yes, proceed] [No, cancel] [Show me what would be affected]
```

### Destructive Operation

```markdown
⚠️ SAFETY ALERT: Destructive Operation

Operation: [delete/overwrite/drop]
Target: [full path]

This operation is IRREVERSIBLE and will permanently affect data.

What will happen:
• [Specific files affected]
• [Approximate size of data affected]
• [Dependencies that may break]

Before proceeding:
✓ A backup will be created at: .builder/backups/[timestamp]/
✓ Rollback instructions will be provided

Do you want to proceed?
[Yes, create backup and proceed] [No, cancel] [Let me backup manually first]
```

### System Configuration Change

```markdown
⚠️ SAFETY ALERT: System Configuration Change

Operation: [specific operation]
Target: [configuration file/registry key/etc.]

This operation modifies SYSTEM-LEVEL configuration.

Potential Impact:
• May affect other applications
• Could require system restart
• Changes may persist after project is deleted

Affected Scope: [local/user/system-wide]

Do you want to proceed?
[Yes, I understand the risks] [No, cancel] [Tell me more]
```

## Backup Protocol

### When to Create Backup

1. Before overwriting existing files
2. Before deleting files
3. Before modifying configuration
4. Before database schema changes
5. User requests safety measure

### Backup Structure

```
.builder/
└── backups/
    ├── 2026-02-13_10-30-00/
    │   ├── manifest.json        # What was backed up
    │   ├── files/               # File copies
    │   │   └── [original structure]
    │   └── rollback.sh          # Rollback script
    └── latest -> 2026-02-13_10-30-00/
```

### Backup Manifest

```json
{
  "backup_id": "2026-02-13_10-30-00",
  "created_at": "2026-02-13T10:30:00Z",
  "trigger": "user_request|auto_pre_destructive",
  "files_backed_up": [
    {
      "original_path": "/path/to/original",
      "backup_path": "files/path/to/original",
      "size_bytes": 1024,
      "checksum": "sha256:abc123..."
    }
  ],
  "total_size": "10KB",
  "rollback_command": "./rollback.sh"
}
```

## Safety Logging

### Log Structure

```json
{
  "timestamp": "2026-02-13T10:30:00Z",
  "session_id": "sess-001",
  "event": {
    "type": "safety_check",
    "operation": "write",
    "target": "/path/to/file",
    "risk_level": "YELLOW",
    "decision": "proceed_with_warning"
  },
  "user_interaction": {
    "warning_shown": true,
    "user_response": "approved",
    "response_time_ms": 1500
  }
}
```

## Emergency Procedures

### If Unsafe Operation Detected

```
1. IMMEDIATE STOP
   - Halt current operation
   - Do not proceed with any file changes
   - Save current state to checkpoint

2. ASSESS IMPACT
   - What was about to happen?
   - What files would be affected?
   - Is any data at risk?

3. NOTIFY USER
   - Clear explanation of what was blocked
   - Why it was considered unsafe
   - Alternatives if available

4. AWAIT INSTRUCTION
   - User must explicitly approve or cancel
   - Document decision in safety log
```

### Rollback Procedure

```bash
# If backup exists
cd .builder/backups/latest
./rollback.sh

# Or manually restore
cp -r files/* /path/to/workspace/
```

## Best Practices

1. **Better safe than sorry** - When uncertain, ask the user
2. **Default to workspace** - Keep all operations within project directory
3. **Log everything** - Maintain audit trail of safety decisions
4. **Backup liberally** - Create backups before any potentially destructive operation
5. **Clear communication** - Always explain risks in plain language
