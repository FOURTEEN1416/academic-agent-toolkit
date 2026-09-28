# Autonomous Builder Reference Index

Navigation for all reference documentation.

## ⚠️ Official Architecture Patterns (Anthropic claude-quickstarts)

Based on official Anthropic architecture design methodology:

- [two-agent-architecture.md](two-agent-architecture.md) - **CRITICAL**: Two-Agent pattern for long-running tasks, fresh context per session
- [think-tool.md](think-tool.md) - **CRITICAL**: Think Tool for complex reasoning before action
- [multi-layer-security.md](multi-layer-security.md) - **CRITICAL**: Defense in depth security architecture (5 layers)

## ⚠️ Safety First

- [safety-protocols.md](safety-protocols.md) - **CRITICAL**: System protection and safe operation protocols

## Skill Scheduling

- [skill-scheduling.md](skill-scheduling.md) - **CRITICAL**: Automatic skill discovery, planning, and auto-dispatch

## MCP Integration

- [mcp-auto-integration.md](mcp-auto-integration.md) - **CRITICAL**: MCP auto-discovery, installation, and human-like computer control
- [mcp-integration.md](mcp-integration.md) - MCP tool usage guide and patterns

## Architecture & Design

- [architecture-patterns.md](architecture-patterns.md) - Clean Architecture, Hexagonal, DDD patterns
- [design-decisions.md](design-decisions.md) - Common architectural decisions and trade-offs

## Development Patterns

- [multi-language.md](multi-language.md) - Language-specific patterns (Python, Node.js, Go, Rust, etc.)
- [testing-patterns.md](testing-patterns.md) - Unit, integration, E2E testing strategies
- [error-recovery.md](error-recovery.md) - Detailed error handling and 3-strike protocol
- [loop-prevention.md](loop-prevention.md) - **CRITICAL**: Anti-infinite-loop detection and token management
- [code-quality.md](code-quality.md) - Linting, formatting, best practices

## MCP Integration

- [mcp-integration.md](mcp-integration.md) - Puppeteer, IDE, Database tool usage
- [external-services.md](external-services.md) - API integrations, cloud services

## State Management

- [session-continuity.md](session-continuity.md) - **CRITICAL**: Auto-resume and continuous operation
- [state-schema.md](state-schema.md) - Complete state file schemas
- [checkpointing.md](checkpointing.md) - Recovery and resume strategies
- [session-management.md](session-management.md) - Multi-session workflows

## Workflow Guides

- [initializer-workflow.md](initializer-workflow.md) - First session setup process
- [coding-workflow.md](coding-workflow.md) - Incremental development process
- [debugging-workflow.md](debugging-workflow.md) - Error diagnosis and fix process

## Templates

- [feature-template.md](feature-template.md) - Feature definition template
- [commit-template.md](commit-template.md) - Commit message conventions
- [test-template.md](test-template.md) - Test file templates by language

## Quick Links by Task

### Starting a New Project
1. Review [safety-protocols.md](safety-protocols.md) for safe operation guidelines
2. Read [initializer-workflow.md](initializer-workflow.md)
3. Choose architecture from [architecture-patterns.md](architecture-patterns.md)
4. Set up state files per [state-schema.md](state-schema.md)

### Resuming an Interrupted Project
1. Read [session-management.md](session-management.md)
2. Load checkpoint per [checkpointing.md](checkpointing.md)
3. Continue from [coding-workflow.md](coding-workflow.md)

### Debugging an Error
1. Follow [error-recovery.md](error-recovery.md) for 3-strike protocol
2. Check language patterns in [multi-language.md](multi-language.md)
3. Use MCP tools per [mcp-integration.md](mcp-integration.md)

### Handling Safety Alerts
1. Consult [safety-protocols.md](safety-protocols.md) for risk assessment
2. Review protected paths and operation categories
3. Follow backup protocol before destructive operations
4. Log safety decisions to safety-log.json

### When Loop Detected
1. Check [loop-prevention.md](loop-prevention.md) for detection rules
2. Review error signatures and edit history
3. Choose: Skip feature / Accept partial / Provide guidance / Abort
4. Log resolution to loop-log.json

### Setting Up Self-Supervision (Unattended Operation)
1. Review [session-continuity.md](session-continuity.md) for auto-resume protocol
2. During initialization, auto-continue scripts are generated to `.builder/`:
   - **Windows**: `auto-continue.ps1`
   - **Linux/macOS**: `auto-continue.sh`
3. Run the script to start self-supervising mode:
   ```bash
   # Linux/macOS
   chmod +x .builder/auto-continue.sh
   ./builder/auto-continue.sh

   # Windows PowerShell
   powershell -ExecutionPolicy Bypass -File .builder\auto-continue.ps1
   ```
4. Monitor progress via `.builder/supervisor.log`
5. Check `.builder/supervisor.json` for configuration options

### Setting Up Skill Auto-Dispatch
1. Place `Claude_Skills_中文指南.md` in workspace root directory
2. Review [skill-scheduling.md](skill-scheduling.md) for skill matching logic
3. During initialization, skills are auto-discovered and matched to tasks
4. During implementation, relevant skills are auto-invoked
5. Check `.builder/state.json` → `skill_dispatch` section for usage logs

### Setting Up MCP Auto-Integration
1. Review [mcp-auto-integration.md](mcp-auto-integration.md) for capabilities
2. On session start, MCP servers are auto-discovered via `/mcp` command
3. Missing servers are auto-installed based on project type:
   - Web projects: puppeteer (browser automation)
   - Desktop apps: desktop (mouse/keyboard control)
   - Data projects: sqlite/postgres (database)
4. MCP tools are auto-invoked based on task patterns
5. Check `.builder/state.json` → `mcp_integration` section for status
