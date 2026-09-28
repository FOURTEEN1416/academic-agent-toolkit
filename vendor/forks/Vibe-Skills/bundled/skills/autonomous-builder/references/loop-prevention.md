# Loop Prevention & Resource Management

Comprehensive guide to prevent infinite loops and manage token consumption in autonomous operations.

## Overview

When running autonomously without user supervision, the system must detect and break out of repetitive patterns that waste tokens and make no progress. This document defines the detection mechanisms and escalation protocols.

## Detection Thresholds

| Condition | Threshold | Severity | Action |
|-----------|-----------|----------|--------|
| Same error message | 3 occurrences | CRITICAL | Immediate escalation |
| Same file edited | 5 times | HIGH | Review and try alternative |
| Same command run | 3 times | HIGH | Try different approach |
| No feature progress | 10 operations | MEDIUM | Pause and reassess |
| Session duration | 50 turns | MEDIUM | Checkpoint and pause |
| Same fix attempt | 2 times | HIGH | Skip to alternative |

## Loop Detection System

### Error Signature Matching

```python
import hashlib

def compute_error_signature(error_message: str) -> str:
    """Create a hash of normalized error message for comparison."""
    # Normalize: remove file paths, line numbers, timestamps
    normalized = normalize_error(error_message)
    return hashlib.md5(normalized.encode()).hexdigest()[:8]

def normalize_error(error: str) -> str:
    """Remove variable parts from error message."""
    import re
    # Remove file paths
    error = re.sub(r'/[\w/.-]+', '<PATH>', error)
    # Remove line numbers
    error = re.sub(r':\d+', ':<LINE>', error)
    # Remove timestamps
    error = re.sub(r'\d{4}-\d{2}-\d{2}T[\d:]+', '<TIME>', error)
    # Remove variable names (keep error type)
    return error.strip()
```

### Loop Detection State

```python
@dataclass
class LoopDetectionState:
    # Error tracking
    error_signatures: Dict[str, ErrorRecord] = field(default_factory=dict)

    # File edit tracking
    file_edit_counts: Dict[str, int] = field(default_factory=dict)
    recent_edits: List[str] = field(default_factory=list)

    # Command tracking
    command_counts: Dict[str, int] = field(default_factory=dict)
    recent_commands: List[str] = field(default_factory=list)

    # Progress tracking
    operations_since_progress: int = 0
    last_completed_feature: Optional[str] = None

    # Session tracking
    session_start: datetime = field(default_factory=datetime.now)
    turn_count: int = 0
    tokens_used_estimate: int = 0

@dataclass
class ErrorRecord:
    signature: str
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    attempted_fixes: List[str] = field(default_factory=list)
```

### Detection Logic

```python
class LoopDetector:
    """Detects infinite loops and repetitive patterns."""

    def __init__(self, state: LoopDetectionState):
        self.state = state
        self.thresholds = {
            'same_error': 3,
            'same_file_edit': 5,
            'same_command': 3,
            'no_progress': 10,
            'session_turns': 50,
        }

    def record_error(self, error: str, attempted_fix: str = None):
        """Record an error occurrence and check for loops."""
        signature = compute_error_signature(error)

        if signature in self.state.error_signatures:
            record = self.state.error_signatures[signature]
            record.count += 1
            record.last_seen = datetime.now()
            if attempted_fix:
                record.attempted_fixes.append(attempted_fix)
        else:
            self.state.error_signatures[signature] = ErrorRecord(
                signature=signature,
                first_seen=datetime.now(),
                last_seen=datetime.now()
            )

        return self.check_loop()

    def record_file_edit(self, file_path: str):
        """Record a file edit and check for loops."""
        self.state.file_edit_counts[file_path] = \
            self.state.file_edit_counts.get(file_path, 0) + 1
        self.state.recent_edits.append(file_path)

        # Keep only last 20 edits
        self.state.recent_edits = self.state.recent_edits[-20:]

        return self.check_loop()

    def record_command(self, command: str):
        """Record a command execution and check for loops."""
        self.state.command_counts[command] = \
            self.state.command_counts.get(command, 0) + 1
        self.state.recent_commands.append(command)

        # Keep only last 20 commands
        self.state.recent_commands = self.state.recent_commands[-20:]

        return self.check_loop()

    def record_progress(self, feature_id: str):
        """Record that a feature was completed."""
        self.state.operations_since_progress = 0
        self.state.last_completed_feature = feature_id
        # Reset counters on progress
        self.state.error_signatures.clear()
        self.state.file_edit_counts.clear()
        self.state.command_counts.clear()

    def record_operation(self):
        """Record a general operation without progress."""
        self.state.operations_since_progress += 1
        self.state.turn_count += 1
        return self.check_loop()

    def check_loop(self) -> Optional[LoopAlert]:
        """Check all loop conditions and return alert if detected."""

        # Check 1: Same error repeated
        for sig, record in self.state.error_signatures.items():
            if record.count >= self.thresholds['same_error']:
                return LoopAlert(
                    type='SAME_ERROR_LOOP',
                    severity='CRITICAL',
                    details=f"Error signature {sig} occurred {record.count} times",
                    fixes_attempted=record.attempted_fixes,
                    action='ESCALATE'
                )

        # Check 2: Same file edited too many times
        for file, count in self.state.file_edit_counts.items():
            if count >= self.thresholds['same_file_edit']:
                return LoopAlert(
                    type='FILE_EDIT_LOOP',
                    severity='HIGH',
                    details=f"File {file} edited {count} times",
                    action='REVIEW_APPROACH'
                )

        # Check 3: Same command repeated
        for cmd, count in self.state.command_counts.items():
            if count >= self.thresholds['same_command']:
                return LoopAlert(
                    type='COMMAND_LOOP',
                    severity='HIGH',
                    details=f"Command '{cmd}' executed {count} times",
                    action='TRY_ALTERNATIVE'
                )

        # Check 4: No progress
        if self.state.operations_since_progress >= self.thresholds['no_progress']:
            return LoopAlert(
                type='NO_PROGRESS',
                severity='MEDIUM',
                details=f"{self.state.operations_since_progress} operations without feature completion",
                action='PAUSE_REASSESS'
            )

        # Check 5: Session too long
        if self.state.turn_count >= self.thresholds['session_turns']:
            return LoopAlert(
                type='SESSION_LIMIT',
                severity='MEDIUM',
                details=f"Session reached {self.state.turn_count} turns",
                action='CHECKPOINT_PAUSE'
            )

        return None
```

## Escalation Protocol

### Alert Levels

```python
class AlertSeverity(Enum):
    LOW = "low"           # Log and continue
    MEDIUM = "medium"     # Pause for review
    HIGH = "high"         # Try alternative immediately
    CRITICAL = "critical" # Stop and escalate to user

class LoopAlert:
    def __init__(self, type: str, severity: str, details: str, action: str, **kwargs):
        self.type = type
        self.severity = severity
        self.details = details
        self.action = action
        self.timestamp = datetime.now()
        self.context = kwargs

    def to_user_message(self) -> str:
        """Generate user-facing alert message."""
        return f"""
## ⚠️ LOOP DETECTED: {self.type}

**Severity**: {self.severity}
**Details**: {self.details}
**Time**: {self.timestamp.isoformat()}

**Action Required**: {self.action}

**Your Options**:
1. **Skip** - Move to next feature, mark this as blocked
2. **Partial** - Accept current partial implementation
3. **Guide** - Provide additional context to help resolve
4. **Abort** - Stop and generate summary report

Please respond with your choice (1-4) or provide specific guidance.
"""
```

### Response Actions

```python
def handle_loop_alert(alert: LoopAlert, state: ProjectState) -> ActionResult:
    """Handle loop alert based on severity and type."""

    # Always save checkpoint first
    checkpoint_id = create_checkpoint(state, reason=f"loop_detected:{alert.type}")

    # Log the loop
    log_loop_event(alert, state)

    if alert.severity == 'CRITICAL':
        # Immediate stop, require user input
        return ActionResult(
            status='PAUSED',
            message=alert.to_user_message(),
            requires_user_input=True,
            checkpoint=checkpoint_id
        )

    elif alert.severity == 'HIGH':
        # Try alternative approach automatically
        alternative = get_alternative_approach(alert, state)
        if alternative:
            return ActionResult(
                status='CONTINUE',
                message=f"Trying alternative: {alternative.description}",
                new_approach=alternative
            )
        else:
            return ActionResult(
                status='PAUSED',
                message=alert.to_user_message(),
                requires_user_input=True,
                checkpoint=checkpoint_id
            )

    elif alert.severity == 'MEDIUM':
        # Log warning, continue with caution
        return ActionResult(
            status='CONTINUE_WITH_WARNING',
            message=f"Warning: {alert.details}. Proceeding with monitoring.",
            monitoring_level='increased'
        )

    else:  # LOW
        return ActionResult(
            status='CONTINUE',
            message=f"Note: {alert.details}"
        )
```

## Loop Log Format

```json
{
  "loop_log": [
    {
      "id": "loop-001",
      "timestamp": "2026-02-13T10:30:00Z",
      "type": "SAME_ERROR_LOOP",
      "severity": "CRITICAL",
      "details": {
        "error_signature": "abc123",
        "error_count": 3,
        "error_messages": [
          "TypeError: Cannot read property 'x' of undefined",
          "TypeError: Cannot read property 'x' of undefined",
          "TypeError: Cannot read property 'x' of undefined"
        ],
        "fixes_attempted": [
          "Added null check",
          "Used optional chaining",
          "Added default value"
        ],
        "files_involved": ["src/app.ts"],
        "feature": "feat-003"
      },
      "resolution": {
        "action_taken": "ESCALATE_TO_USER",
        "user_response": "SKIP_FEATURE",
        "resolved_at": "2026-02-13T10:35:00Z"
      },
      "tokens_consumed_estimate": 15000,
      "checkpoint_id": "checkpoint-20260213-103000"
    }
  ],
  "statistics": {
    "total_loops_detected": 1,
    "tokens_saved_by_early_detection": 50000,
    "most_common_loop_type": "SAME_ERROR_LOOP"
  }
}
```

## Best Practices

### 1. Progressive Fallback

```
On error:
  1st occurrence → Try direct fix
  2nd occurrence → Try alternative approach
  3rd occurrence → ESCALATE (don't continue)
```

### 2. Meaningful Progress Check

```python
def has_meaningful_progress(state: ProjectState) -> bool:
    """Check if real progress was made."""
    return (
        state.features_completed_this_session > 0 or
        state.tests_added > 0 or
        state.files_created > 0 or
        state.coverage_improved
    )
```

### 3. Resource Budgeting

```python
# Estimated token budgets
TOKEN_BUDGETS = {
    'single_feature': 20000,    # Max tokens per feature
    'error_recovery': 5000,     # Max tokens for recovery attempts
    'session_total': 100000,    # Max tokens per session
}

def check_token_budget(state: ProjectState) -> Optional[BudgetAlert]:
    """Check if token budget is exceeded."""
    if state.tokens_used > TOKEN_BUDGETS['session_total']:
        return BudgetAlert("Session budget exceeded")

    feature_tokens = state.current_feature_tokens
    if feature_tokens > TOKEN_BUDGETS['single_feature']:
        return BudgetAlert("Feature budget exceeded")

    return None
```

### 4. Circuit Breaker Pattern

```python
class CircuitBreaker:
    """Prevents repeated calls to failing operations."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = {}
        self.circuit_open = {}

    def record_failure(self, operation: str):
        self.failures[operation] = self.failures.get(operation, 0) + 1
        if self.failures[operation] >= self.failure_threshold:
            self.circuit_open[operation] = datetime.now()

    def is_available(self, operation: str) -> bool:
        if operation not in self.circuit_open:
            return True

        # Check if cooldown period has passed
        opened_at = self.circuit_open[operation]
        if (datetime.now() - opened_at).seconds > self.cooldown_seconds:
            # Reset circuit
            del self.circuit_open[operation]
            self.failures[operation] = 0
            return True

        return False  # Circuit is open, operation blocked
```

## Integration with Error Recovery

The loop detection system integrates with the 3-strike error recovery:

```
Error Recovery + Loop Detection:

STRIKE 1:
  → Try direct fix
  → Record error signature
  → Check loop (pass on 1st occurrence)

STRIKE 2:
  → Try alternative approach
  → Record error signature (count = 2)
  → Check loop (warning on 2nd occurrence)

STRIKE 3:
  → Architecture rethink
  → Record error signature (count = 3)
  → Check loop (CRITICAL alert, escalate)
```

This ensures that even within the 3-strike system, we catch loops early and prevent token waste.
