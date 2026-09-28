# Multi-Layer Security Defense Architecture

Based on Anthropic's official claude-quickstarts security design.

## Overview

Security for autonomous agents requires **defense in depth** - multiple independent layers that each provide protection. If one layer fails, others still protect the system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEFENSE IN DEPTH                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 5: Pre-Tool-Use Hooks                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Validate every tool call before execution               │    │
│  │ Block dangerous operations, log all attempts            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  Layer 4: Bash Command Allowlist                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Only whitelisted commands can execute                   │    │
│  │ Special validation for dangerous commands               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  Layer 3: File Permission Filter                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Read/Write/Edit only allowed in project directory       │    │
│  │ Explicit allow-list for each operation type             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  Layer 2: OS-Level Sandbox (Optional but Recommended)           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Containerized execution environment                      │    │
│  │ Network isolation, resource limits                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  Layer 1: User Confirmation (For dangerous operations)          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Explicit approval for:                                   │    │
│  │ - Operations outside workspace                           │    │
│  │ - Destructive operations                                 │    │
│  │ - System configuration changes                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Layer 1: OS-Level Sandbox

### Docker-based Isolation

```yaml
# docker-compose.yml for sandboxed execution
version: '3.8'
services:
  claude-agent:
    image: claude-agent-sandbox
    build: .
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - ./project:/workspace:rw
    networks:
      - isolated
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

networks:
  isolated:
    driver: bridge
    internal: true  # No external network access
```

### Sandbox Configuration

```python
SANDBOX_CONFIG = {
    "enabled": True,
    "autoAllowBashIfSandboxed": True,
    "network_isolated": True,
    "resource_limits": {
        "memory": "2g",
        "cpu": "2",
        "disk": "10g"
    }
}
```

## Layer 2: File Permission Filter

### Permission Model

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass
class PermissionRule:
    pattern: str          # Glob pattern
    mode: Literal["read", "write", "edit", "execute"]

DEFAULT_PERMISSIONS = {
    "defaultMode": "deny",  # Default deny
    "allow": [
        # Read permissions
        "Read(./**)",           # Project files
        "Read(../.git/**)",     # Parent git (for monorepos)

        # Write permissions
        "Write(./src/**)",      # Source code
        "Write(./tests/**)",    # Test files
        "Write(./docs/**)",     # Documentation
        "Write(./.builder/**)", # Builder state

        # Edit permissions
        "Edit(./**)",           # All project files

        # Bash permissions (validated separately)
        "Bash(*)",              # Allowed if command passes validation
    ],
    "deny": [
        # Never allow these
        "Read(/etc/**)",
        "Read(~/.ssh/**)",
        "Read(~/.gnupg/**)",
        "Write(/etc/**)",
        "Write(~/**)",
    ]
}

def check_permission(operation: str, path: str, rules: dict) -> bool:
    """Check if operation is permitted on path."""
    for rule in rules.get("deny", []):
        if matches_permission_rule(operation, path, rule):
            return False

    for rule in rules.get("allow", []):
        if matches_permission_rule(operation, path, rule):
            return True

    return rules.get("defaultMode", "deny") == "allow"
```

## Layer 3: Bash Command Allowlist

### Command Whitelist

```python
# Whitelisted commands that are always safe
ALLOWED_COMMANDS = {
    # File inspection (safe, read-only)
    "ls", "cat", "head", "tail", "wc", "grep", "find", "file",

    # File operations (safe within project)
    "cp", "mkdir", "chmod", "touch", "rm", "mv",

    # Development tools
    "npm", "node", "npx", "yarn", "pnpm",
    "pip", "python", "python3", "poetry",
    "cargo", "rustc",
    "go",

    # Version control
    "git",

    # Process management (limited)
    "ps", "lsof", "sleep", "pkill", "kill",

    # System info
    "pwd", "whoami", "echo", "env", "which",
}

# Commands requiring special validation
RESTRICTED_COMMANDS = {
    "rm": validate_rm_command,
    "chmod": validate_chmod_command,
    "pkill": validate_pkill_command,
    "kill": validate_kill_command,
    "curl": validate_curl_command,
    "wget": validate_wget_command,
}
```

### Command Validation Functions

```python
import re
from typing import Tuple

def validate_rm_command(command: str) -> Tuple[bool, str]:
    """Validate rm command safety."""
    # Block dangerous patterns
    dangerous_patterns = [
        r"rm\s+-rf\s+/",           # rm -rf /
        r"rm\s+-rf\s+~",           # rm -rf ~
        r"rm\s+-rf\s+\.\.",        # rm -rf ..
        r"rm\s+-rf\s+\*",          # rm -rf *
        r"rm\s+.*\.ssh",           # rm ~/.ssh
        r"rm\s+.*\.gnupg",         # rm ~/.gnupg
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            return False, f"Dangerous rm pattern detected: {pattern}"

    # Only allow within project directory
    return True, "rm command validated"

def validate_chmod_command(command: str) -> Tuple[bool, str]:
    """Only allow adding execute permission."""
    # Extract mode from command
    match = re.search(r"chmod\s+([ugoa]*)([+-])([rwxXst]+)", command)
    if not match:
        return False, "Could not parse chmod command"

    who, op, mode = match.groups()

    # Only allow +x (add execute)
    if op != "+":
        return False, "chmod only allows adding permissions (+), not removing"

    if mode not in ["x", "X", "xX", "Xx"]:
        return False, f"chmod only allows +x mode, got +{mode}"

    return True, "chmod +x validated"

def validate_pkill_command(command: str) -> Tuple[bool, str]:
    """Only allow killing development-related processes."""
    allowed_processes = {
        "node", "npm", "npx", "vite", "next", "react-scripts",
        "python", "pytest", "uvicorn", "gunicorn",
        "cargo", "rustc",
    }

    # Extract process name
    match = re.search(r"pkill\s+(-\w+\s+)*(\w+)", command)
    if not match:
        return False, "Could not parse pkill command"

    process_name = match.group(2)
    if process_name not in allowed_processes:
        return False, f"pkill only allowed for: {allowed_processes}"

    return True, "pkill validated"

def validate_curl_command(command: str) -> Tuple[bool, str]:
    """Validate curl for security."""
    # Block sensitive file access
    blocked_patterns = [
        r"file://",
        r"~/.ssh",
        r"~/.gnupg",
        r"/etc/passwd",
        r"/etc/shadow",
    ]

    for pattern in blocked_patterns:
        if re.search(pattern, command):
            return False, f"Blocked curl pattern: {pattern}"

    return True, "curl validated"
```

### Command Extraction and Validation

```python
import shlex

def extract_commands(command_string: str) -> list[str]:
    """Extract individual commands from a command string."""
    # Handle pipes, &&, ||
    separators = ["|", "&&", "||", ";"]
    result = [command_string]

    for sep in separators:
        new_result = []
        for cmd in result:
            parts = cmd.split(sep)
            new_result.extend([p.strip() for p in parts if p.strip()])
        result = new_result

    return result

def validate_bash_command(command_string: str) -> Tuple[bool, str]:
    """Validate entire bash command string."""
    commands = extract_commands(command_string)

    for cmd in commands:
        # Get the base command
        try:
            parts = shlex.split(cmd)
            if not parts:
                continue
            base_cmd = parts[0]
        except ValueError:
            return False, f"Could not parse command: {cmd}"

        # Check if allowed
        if base_cmd not in ALLOWED_COMMANDS:
            return False, f"Command '{base_cmd}' is not in allowed list"

        # Check if needs special validation
        if base_cmd in RESTRICTED_COMMANDS:
            is_valid, msg = RESTRICTED_COMMANDS[base_cmd](cmd)
            if not is_valid:
                return False, msg

    return True, "All commands validated"
```

## Layer 4: Pre-Tool-Use Hooks

### Hook Implementation

```python
from dataclasses import dataclass
from typing import Any, Callable, Literal

@dataclass
class HookResult:
    decision: Literal["allow", "block"]
    reason: str = ""
    modified_input: dict | None = None

async def pre_tool_use_hook(
    tool_name: str,
    tool_input: dict,
    context: dict
) -> HookResult:
    """
    Pre-tool-use hook that validates every tool call.

    This is called BEFORE any tool executes.
    """
    # Layer 1: File operations
    if tool_name in ["Read", "Write", "Edit"]:
        path = tool_input.get("file_path", tool_input.get("path", ""))
        if not is_within_workspace(path, context["project_dir"]):
            return HookResult(
                decision="block",
                reason=f"Path '{path}' is outside workspace"
            )

    # Layer 2: Bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        is_valid, msg = validate_bash_command(command)
        if not is_valid:
            return HookResult(
                decision="block",
                reason=f"Bash validation failed: {msg}"
            )

    # Layer 3: Sensitive operations
    if tool_name in ["Write", "Edit"]:
        path = tool_input.get("file_path", "")
        if is_sensitive_file(path):
            return HookResult(
                decision="block",
                reason=f"Cannot modify sensitive file: {path}"
            )

    # Allow by default
    return HookResult(decision="allow")

def is_within_workspace(path: str, workspace: str) -> bool:
    """Check if path is within workspace."""
    abs_path = Path(path).resolve()
    abs_workspace = Path(workspace).resolve()
    return str(abs_path).startswith(str(abs_workspace))

def is_sensitive_file(path: str) -> bool:
    """Check if file is sensitive."""
    sensitive_patterns = [
        ".env", ".env.local", ".env.production",
        ".pem", ".key", ".p12",
        ".ssh/", ".gnupg/",
        "credentials", "secrets", "password",
    ]
    return any(p in path.lower() for p in sensitive_patterns)
```

### Hook Integration

```python
class SecureAgent:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.hooks = [pre_tool_use_hook]

    async def execute_tool(self, tool_name: str, tool_input: dict):
        # Run all pre-tool-use hooks
        for hook in self.hooks:
            result = await hook(
                tool_name,
                tool_input,
                {"project_dir": str(self.project_dir)}
            )

            if result.decision == "block":
                # Log the block
                self.log_blocked_operation(tool_name, tool_input, result.reason)
                return f"BLOCKED: {result.reason}"

        # Execute the tool if all hooks pass
        return await self._execute_tool_internal(tool_name, tool_input)

    def log_blocked_operation(self, tool_name: str, tool_input: dict, reason: str):
        """Log all blocked operations for audit."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "input": tool_input,
            "reason": reason,
        }
        # Write to security log
        with open(self.project_dir / ".builder" / "security.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
```

## Layer 5: User Confirmation

### Operations Requiring Confirmation

```python
DANGEROUS_OPERATIONS = {
    # File operations outside workspace
    "external_file_access": {
        "patterns": ["/etc/*", "~/*", "/var/*"],
        "message": "This operation accesses files outside the workspace. Proceed?",
    },

    # Destructive operations
    "destructive": {
        "patterns": ["rm -rf", "DROP", "DELETE", "TRUNCATE"],
        "message": "This operation is destructive and cannot be undone. Proceed?",
    },

    # System configuration
    "system_config": {
        "patterns": ["npm install -g", "pip install --system", "apt", "yum"],
        "message": "This operation modifies system configuration. Proceed?",
    },

    # Network changes
    "network": {
        "patterns": ["iptables", "firewall", "port bind"],
        "message": "This operation changes network settings. Proceed?",
    },
}
```

### Confirmation Flow

```python
async def request_confirmation(
    operation_type: str,
    details: str,
    context: dict
) -> bool:
    """
    Request user confirmation for dangerous operations.

    In autonomous mode (--dangerously-skip-permissions), this is bypassed.
    """
    if context.get("skip_permissions", False):
        # Log the auto-approval
        log_auto_approval(operation_type, details)
        return True

    # Display warning to user
    print(f"\n{'='*60}")
    print(f"⚠️  CONFIRMATION REQUIRED: {operation_type}")
    print(f"{'='*60}")
    print(f"\n{details}")
    print(f"\nDo you want to proceed? [y/N]: ", end="")

    response = input().strip().lower()
    return response in ["y", "yes"]
```

## Security Audit Log

```json
// .builder/security.log
{
  "logs": [
    {
      "timestamp": "2026-02-13T10:30:00Z",
      "type": "blocked",
      "tool": "Bash",
      "input": {"command": "rm -rf /"},
      "reason": "Dangerous rm pattern detected",
      "layer": "command_validation"
    },
    {
      "timestamp": "2026-02-13T10:31:00Z",
      "type": "blocked",
      "tool": "Read",
      "input": {"file_path": "/etc/passwd"},
      "reason": "Path is outside workspace",
      "layer": "file_permission"
    },
    {
      "timestamp": "2026-02-13T10:32:00Z",
      "type": "auto_approved",
      "tool": "Bash",
      "input": {"command": "npm install"},
      "reason": "Autonomous mode enabled",
      "layer": "user_confirmation"
    }
  ]
}
```

## Security Checklist

```markdown
Before deploying autonomous-builder:

## Layer 1: OS Sandbox
- [ ] Docker container configured
- [ ] Network isolation enabled
- [ ] Resource limits set
- [ ] No privilege escalation

## Layer 2: File Permissions
- [ ] Workspace boundaries defined
- [ ] Sensitive paths blocked
- [ ] Allow/deny lists configured

## Layer 3: Command Validation
- [ ] Allowed commands whitelisted
- [ ] Restricted commands validated
- [ ] Command injection prevented

## Layer 4: Pre-Tool Hooks
- [ ] All tools have validation
- [ ] Blocked operations logged
- [ ] Context available to hooks

## Layer 5: User Confirmation
- [ ] Dangerous operations identified
- [ ] Confirmation flow working
- [ ] Autonomous mode documented
```

## Summary

The multi-layer security architecture provides:

1. **Defense in Depth** - Multiple independent layers
2. **Fail-Safe Defaults** - Deny by default
3. **Audit Trail** - Log all security events
4. **Flexibility** - Can enable autonomous mode when safe
5. **Transparency** - Clear what's allowed and why
