# Session Continuity & Auto-Resume

Complete guide for continuous autonomous operation across multiple sessions.

## The Challenge

Claude's context window is limited. For long-running projects, the agent must:
1. Save complete state before context exhaustion
2. Resume seamlessly in a new session
3. Continue exactly where it left off
4. Never ask user for information already known

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS OPERATION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Session N                    Session N+1                      │
│   ┌─────────┐                 ┌─────────┐                       │
│   │ Start   │                 │ Start   │                       │
│   └────┬────┘                 └────┬────┘                       │
│        │                           │                            │
│        ▼                           ▼                            │
│   Load State ──────────────────▶ Load State                     │
│        │                           │                            │
│        ▼                           ▼                            │
│   Work on                    Resume from                        │
│   Features                   checkpoint                          │
│        │                           │                            │
│        ▼                           ▼                            │
│   Save Checkpoint ◀───────────▶ Continue                        │
│        │                           │                            │
│        ▼                           ▼                            │
│   Context Full?              More Features?                     │
│        │                           │                            │
│        ├─YES─▶ End Session         ├─YES─▶ Continue Working     │
│        │                           │                            │
│        └─NO──▶ Continue            └─NO──▶ Complete!            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## State Persistence Strategy

### What to Save

```json
{
  "version": "1.0",
  "timestamp": "2026-02-13T10:30:00Z",

  "project_identity": {
    "name": "my-api",
    "type": "web-api",
    "workspace_root": "/path/to/project"
  },

  "current_position": {
    "phase": "implement",
    "feature_id": "feat-003",
    "feature_name": "User Authentication",
    "step_in_feature": "Writing login endpoint",
    "progress_percent": 65
  },

  "feature_queue": {
    "completed": ["feat-001", "feat-002"],
    "in_progress": "feat-003",
    "pending": ["feat-004", "feat-005", "feat-006"],
    "blocked": []
  },

  "tech_context": {
    "language": "python",
    "framework": "fastapi",
    "database": "postgresql",
    "key_files": {
      "main": "src/main.py",
      "models": "src/models/",
      "tests": "tests/"
    }
  },

  "recent_operations": [
    {"timestamp": "...", "action": "edit", "file": "src/auth.py", "description": "Added login function"},
    {"timestamp": "...", "action": "test", "command": "pytest tests/", "result": "2 passed, 1 failed"}
  ],

  "errors_encountered": [
    {"hash": "abc123", "message": "TypeError...", "resolved": true, "solution": "Added null check"}
  ],

  "next_immediate_action": {
    "type": "implement",
    "target": "src/auth.py",
    "description": "Complete logout endpoint",
    "estimated_steps": 3
  }
}
```

### When to Save

```python
SAVE_TRIGGERS = {
    # After every significant operation
    'after_file_write': True,
    'after_file_edit': True,
    'after_test_run': True,

    # After state changes
    'after_feature_start': True,
    'after_feature_complete': True,
    'after_phase_change': True,

    # Before risky operations
    'before_destructive_op': True,
    'before_dependency_install': True,

    # Periodic
    'every_10_operations': True,
    'every_5_minutes': True,

    # Context management
    'at_80_percent_context': True,  # Before context fills
}
```

## Auto-Resume Protocol

### Session Start Sequence

```markdown
## Step 1: Check for Existing Project

ON SESSION START:
1. Run `pwd` to get current directory
2. Check if `.builder/state.json` exists
3. If exists → RESUME MODE
4. If not exists → NEW PROJECT MODE

## Step 2a: RESUME MODE

1. Read .builder/state.json
2. Display resume summary:

   "🔄 Resuming project: [project_name]
    Current: [feature_name] ([phase])
    Pending: [N] features remaining
    Auto-continuing in 3 seconds..."

3. Load checkpoint files
4. Continue from next_immediate_action

## Step 2b: NEW PROJECT MODE

1. Parse user requirements
2. Generate feature list
3. Create .builder/ directory
4. Initialize state.json
5. Begin first feature
```

### Resume Without Asking

```python
def resume_session(state_path: str) -> ResumeResult:
    """Resume from saved state WITHOUT asking user."""

    state = load_json(state_path)

    # Don't ask - just continue
    return ResumeResult(
        message=f"Resuming: {state['current_position']['feature_name']}",
        action=state['next_immediate_action'],
        auto_proceed=True  # Key: don't wait for user
    )
```

## Continuous Task Queue

### Feature Selection Algorithm

```python
def select_next_feature(pending: List[Feature], state: State) -> Feature:
    """Automatically select next feature to work on."""

    # Priority order:
    # 1. Features with completed dependencies
    # 2. Higher priority features
    # 3. Earlier in the list

    available = [f for f in pending if dependencies_met(f, state)]

    if not available:
        # All pending features have unmet dependencies
        return handle_blocked_features(pending, state)

    # Sort by priority (critical > high > medium > low)
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    available.sort(key=lambda f: priority_order.get(f.priority, 3))

    return available[0]  # Return without asking user
```

### Automatic Progression

```python
class AutonomousController:
    """Controls continuous autonomous operation."""

    def run_continuous(self, state: State):
        """Main continuous loop."""

        while state.has_pending_features():

            # Check for pause conditions
            if self.should_pause(state):
                self.save_and_pause(state)
                break

            # Check for loop conditions
            if loop := self.detect_loop(state):
                if loop.severity == 'CRITICAL':
                    self.escalate_to_user(state, loop)
                    break
                else:
                    self.handle_loop(state, loop)
                    continue

            # Execute next step
            result = self.execute_next_step(state)

            # Save after every step
            self.save_state(state)

            # If feature complete, auto-continue
            if result.feature_completed:
                state = self.on_feature_complete(state, result.feature_id)
                # Does NOT ask user - continues automatically

        # All done
        return self.generate_final_report(state)
```

## Context Budget Management

### Proactive Checkpointing

```python
def manage_context_budget(state: State, context_used: int, context_limit: int):
    """Proactively manage context to prevent overflow."""

    usage_percent = (context_used / context_limit) * 100

    if usage_percent >= 80:
        # Warning zone - prepare for session end
        log("Context at 80% - preparing checkpoint")

        state.next_immediate_action = get_current_action()
        save_state(state)
        create_checkpoint(state, reason="context_80_percent")

    if usage_percent >= 90:
        # Critical zone - must end session cleanly
        log("Context at 90% - saving final checkpoint")

        save_complete_state(state)
        create_final_checkpoint(state)

        # Return instruction for next session
        return SessionEndInstruction(
            message="Session ending due to context limit. State saved.",
            resume_instruction=f"Continue with: {state.next_immediate_action}",
            estimated_remaining_features=len(state.pending_features)
        )
```

## Failure Recovery

### If Session Crashes

```markdown
ON SESSION START (after crash):

1. Detect incomplete state:
   - Last activity timestamp > 5 minutes ago
   - Current feature status = "in_progress"
   - No recent checkpoint

2. Recovery actions:
   a. Read last checkpoint
   b. Compare with current files
   c. Identify what was done
   d. Determine what remains

3. Display recovery message:
   "⚠️ Incomplete session detected
    Last activity: [timestamp]
    Recovered state from: [checkpoint]
    Resuming: [feature]"

4. Continue automatically
```

### Recovery State File

```json
{
  "crash_recovery": {
    "detected": true,
    "last_checkpoint": "checkpoint-20260213-103000",
    "last_known_state": {
      "feature": "feat-003",
      "phase": "implement",
      "progress": 65
    },
    "file_comparison": {
      "modified_since_checkpoint": ["src/auth.py"],
      "tests_status": "unknown"
    },
    "recovery_action": "Run tests to verify state, then continue"
  }
}
```

## User Intervention Points

### When User Input IS Required

Only these conditions require user input:

1. **Safety Alert** - Operation outside workspace
2. **Critical Loop** - Same error 3+ times, all fixes failed
3. **Ambiguous Requirements** - Feature description unclear
4. **User-Requested Pause** - User typed "pause" or "stop"

### When User Input is NOT Required

Everything else auto-continues:

- Feature completion → Start next feature
- Test failure → Debug and fix
- Error recovery → Try alternative approaches
- Dependency installation → Proceed
- File creation/deletion (in workspace) → Proceed

## Long-Running Operation Example

```
Session 1 (100% context used):
├─ Initialize project
├─ Complete feat-001 (Project Setup)
├─ Complete feat-002 (Database Models)
├─ Start feat-003 (Authentication) - 60%
└─ Save checkpoint, end session

Session 2 (auto-resume):
├─ Load state from .builder/
├─ Complete feat-003 (Authentication) - 100%
├─ Complete feat-004 (API Endpoints)
├─ Complete feat-005 (Tests)
├─ Start feat-006 (Documentation) - 30%
└─ Save checkpoint, end session

Session 3 (auto-resume):
├─ Load state from .builder/
├─ Complete feat-006 (Documentation) - 100%
└─ Generate final report, project complete!
```

## Monitoring Dashboard

### Progress Indicators

```markdown
## 📊 Project Progress

**Project**: my-api
**Sessions**: 3
**Total Time**: 4h 30m

**Features**:
✅ feat-001: Project Setup
✅ feat-002: Database Models
✅ feat-003: Authentication
✅ feat-004: API Endpoints
✅ feat-005: Tests
🔄 feat-006: Documentation (70%)

**Metrics**:
- Files Created: 25
- Tests Written: 45
- Tests Passing: 45
- Errors Resolved: 8
- Tokens Used: ~150,000

**Estimated Completion**: 30 minutes
```
