# Think Tool Pattern

Based on Anthropic's official claude-quickstarts architecture.

## Overview

The Think Tool is a **critical pattern** for complex reasoning scenarios. It allows the model to perform internal reasoning without affecting external state, improving decision quality for complex tasks.

## Why Think Tool?

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE PROBLEM                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Without Think Tool:                                            │
│                                                                 │
│  User: "Implement authentication with rate limiting"            │
│                                                                 │
│  Model immediately starts:                                      │
│  - Write code                                                   │
│  - Create files                                                 │
│  - Make changes                                                 │
│                                                                 │
│  Problem: No time to plan, consider alternatives,               │
│           identify edge cases, or think through security        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    THE SOLUTION                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  With Think Tool:                                               │
│                                                                 │
│  User: "Implement authentication with rate limiting"            │
│                                                                 │
│  Model first calls: think({                                     │
│    thought: "Let me analyze this task...                        │
│    1. Authentication types: JWT, session, OAuth?                │
│    2. Rate limiting: IP-based? User-based? Sliding window?      │
│    3. Security: Password hashing, token rotation?               │
│    4. Edge cases: Concurrent logins, token expiry?              │
│    Decision: JWT + sliding window rate limiter..."              │
│  })                                                             │
│                                                                 │
│  Then executes with better plan                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation

### Tool Definition

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ThinkTool(Tool):
    name: str = "think"
    description: str = """
Use this tool to think about something. It will not obtain new information
or make any changes to the project, but just log the thought. Use it when
complex reasoning or cache memory is needed.

When to use:
- Planning multi-step implementation
- Analyzing trade-offs between approaches
- Identifying potential edge cases
- Debugging complex issues
- Security analysis
- Architecture decisions
"""
    input_schema: dict = {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "A thought to think about."
            }
        },
        "required": ["thought"]
    }

    async def execute(self, thought: str) -> str:
        # The thought is logged but doesn't affect external state
        # The value is in the act of structured reasoning
        return "Thinking complete. You can now proceed with your plan."
```

### Integration into Agent

```python
class Agent:
    def __init__(self, tools: list[Tool]):
        # Add ThinkTool by default
        self.tools = [ThinkTool()] + tools

    async def run(self, input: str):
        # ThinkTool is always available for complex reasoning
        pass
```

## Usage Patterns

### Pattern 1: Pre-Implementation Planning

```markdown
Before implementing a feature:

1. CALL think tool:
   think({
     thought: "Analyzing feature requirements...
     - What files need to be created?
     - What dependencies exist?
     - What are the edge cases?
     - What's the minimal implementation?"
   })

2. RECEIVE confirmation

3. PROCEED with implementation
```

### Pattern 2: Debugging Strategy

```markdown
When encountering an error:

1. CALL think tool:
   think({
     thought: "Error analysis...
     - What is the root cause?
     - What are possible fixes?
     - Which fix is least risky?
     - How to verify the fix?"
   })

2. RECEIVE confirmation

3. APPLY selected fix
```

### Pattern 3: Security Analysis

```markdown
Before security-sensitive operations:

1. CALL think tool:
   think({
     thought: "Security checklist...
     - Is this operation safe?
     - Are there injection risks?
     - Is user input sanitized?
     - Are credentials handled safely?
     - What are the blast radius if this fails?"
   })

2. RECEIVE confirmation

3. PROCEED only if safe
```

### Pattern 4: Architecture Decision

```markdown
When making architectural choices:

1. CALL think tool:
   think({
     thought: "Architecture analysis...
     Option A: Monolithic
     - Pros: Simple deployment, easier debugging
     - Cons: Harder to scale, tight coupling

     Option B: Microservices
     - Pros: Independent scaling, loose coupling
     - Cons: Complexity, distributed issues

     Decision: For this project size, Option A..."
   })

2. RECEIVE confirmation

3. IMPLEMENT chosen architecture
```

## Think Tool vs Direct Action

| Scenario | Without Think Tool | With Think Tool |
|----------|-------------------|-----------------|
| Complex feature | Immediate code → rework | Plan → implement once |
| Debugging | Trial and error | Systematic analysis |
| Security | Miss vulnerabilities | Check before act |
| Architecture | Inconsistent decisions | Reasoned choices |
| Multi-step tasks | Lose track | Stay organized |

## Best Practices

### DO

```markdown
✅ Use think tool for:
- Multi-step implementations
- Complex debugging
- Security-sensitive operations
- Architecture decisions
- Trade-off analysis
- Planning before action
```

### DON'T

```markdown
❌ Don't use think tool for:
- Simple file reads
- Straightforward writes
- Routine operations
- When action is immediately clear
```

## Example Workflow

```python
# Example: Implementing user authentication

# Step 1: Think about the approach
await agent.invoke_tool("think", {
    "thought": """
Authentication Implementation Plan:

1. CHOICE: JWT-based auth
   - Stateless, scalable
   - Works well with our microservices

2. COMPONENTS needed:
   - Password hashing (bcrypt)
   - Token generation (jwt library)
   - Middleware for verification
   - Refresh token mechanism

3. SECURITY considerations:
   - Password: min 8 chars, hash with salt
   - Token: 1hr expiry, secure storage
   - Refresh: 7 day expiry, rotate on use

4. FILES to create:
   - /auth/service.py
   - /auth/middleware.py
   - /auth/models.py

5. ORDER of implementation:
   - Models → Service → Middleware → Routes
"""
})

# Step 2: Execute the plan
# ... implementation follows
```

## Integration with autonomous-builder

```markdown
## Automatic Think Tool Invocation

The autonomous-builder skill should automatically invoke think tool:

1. BEFORE complex features:
   - If feature has >3 steps
   - If feature involves security
   - If feature affects architecture

2. DURING debugging:
   - On error occurrence
   - Before retry attempts
   - For root cause analysis

3. AFTER significant changes:
   - Before commit
   - For verification planning
```

## Think Log

```json
// .builder/think-log.json - Track reasoning history
{
  "thoughts": [
    {
      "timestamp": "2026-02-13T10:30:00Z",
      "feature": "feat-003",
      "thought": "Authentication approach analysis...",
      "decision": "JWT-based with refresh tokens"
    },
    {
      "timestamp": "2026-02-13T11:15:00Z",
      "feature": "feat-003",
      "thought": "Debugging login error...",
      "decision": "Root cause: missing token expiry"
    }
  ]
}
```

## Summary

The Think Tool is a simple but powerful pattern that:
1. **Improves decision quality** - Forces structured reasoning
2. **Reduces errors** - Catches issues before execution
3. **Enables self-correction** - Visible reasoning trail
4. **Costs nothing** - No external effects

This is especially valuable for autonomous agents that operate without human supervision.
