# MCP Auto-Integration & Intelligent Service Discovery

Complete guide for automatic MCP service discovery, creation, and invocation to enable human-like computer control.

## Overview

The autonomous-builder can automatically:
1. **Discover** existing MCP servers and their capabilities
2. **Install** missing MCP servers when needed
3. **Create** custom MCP servers for specific tasks
4. **Invoke** MCP tools seamlessly during execution
5. **Chain** multiple MCP tools for complex workflows

## MCP Capabilities Matrix

### Browser Automation (Web Interaction)

| Capability | MCP Server | Tools Available |
|------------|------------|-----------------|
| Navigate URLs | puppeteer | `mcp__puppeteer_navigate` |
| Click elements | puppeteer | `mcp__puppeteer_click` |
| Type text | puppeteer | `mcp__puppeteer_type` |
| Take screenshots | puppeteer | `mcp__puppeteer_screenshot` |
| Execute JavaScript | puppeteer | `mcp__puppeteer_evaluate` |
| Get page content | puppeteer | `mcp__puppeteer_content` |
| Fill forms | puppeteer | `mcp__puppeteer_fill` |
| Scroll pages | puppeteer | `mcp__puppeteer_scroll` |
| Wait for elements | puppeteer | `mcp__puppeteer_wait` |

### File System Control

| Capability | MCP Server | Tools Available |
|------------|------------|-----------------|
| Read files | filesystem | `mcp__filesystem_read` |
| Write files | filesystem | `mcp__filesystem_write` |
| List directories | filesystem | `mcp__filesystem_list` |
| Create directories | filesystem | `mcp__filesystem_mkdir` |
| Delete files | filesystem | `mcp__filesystem_delete` |
| Search files | filesystem | `mcp__filesystem_search` |

### Code Execution

| Capability | MCP Server | Tools Available |
|------------|------------|-----------------|
| Execute Python | ide | `mcp__ide__executeCode` |
| Get diagnostics | ide | `mcp__ide__getDiagnostics` |
| Run shell commands | terminal | `mcp__terminal_execute` |

### Database Operations

| Capability | MCP Server | Tools Available |
|------------|------------|-----------------|
| Query SQL | sqlite/postgres | `mcp__db_query` |
| Execute SQL | sqlite/postgres | `mcp__db_execute` |
| List tables | sqlite/postgres | `mcp__db_list_tables` |

### Desktop Automation

| Capability | MCP Server | Tools Available |
|------------|------------|-----------------|
| Mouse control | desktop | `mcp__desktop_mouse_move`, `mcp__desktop_click` |
| Keyboard input | desktop | `mcp__desktop_type`, `mcp__desktop_hotkey` |
| Screen capture | desktop | `mcp__desktop_screenshot` |
| Window management | desktop | `mcp__desktop_window_list`, `mcp__desktop_window_focus` |

## Auto-Discovery Protocol

### Step 1: Check Available MCP Servers

```markdown
ON SESSION START:

1. Run /mcp to list configured servers
2. Parse available tools from each server
3. Build capability map:
   {
     "browser_automation": true,  // puppeteer available
     "file_system": true,         // filesystem available
     "code_execution": true,      // ide available
     "desktop_control": false,    // not configured
     "database": false            // not configured
   }
4. Store in state.json → mcp_integration.capabilities
```

### Step 2: Install Missing MCP Servers

```python
def ensure_mcp_server(server_type: str):
    """Auto-install missing MCP servers."""

    install_commands = {
        "puppeteer": "claude mcp add puppeteer -- npx -y @anthropic-ai/mcp-server-puppeteer",
        "filesystem": "claude mcp add filesystem -- npx -y @anthropic-ai/mcp-server-filesystem",
        "desktop": "claude mcp add desktop -- npx -y @anthropic-ai/mcp-server-desktop",
        "sqlite": "claude mcp add sqlite -- npx -y @anthropic-ai/mcp-server-sqlite",
    }

    if server_type not in get_available_mcp_servers():
        log(f"Installing MCP server: {server_type}")
        run_command(install_commands[server_type])
```

### Step 3: Capability-Based Task Routing

```python
def route_task_to_mcp(task_description: str, capabilities: dict) -> MCPToolCall:
    """Route task to appropriate MCP tool based on requirements."""

    # Task pattern matching
    patterns = {
        r"open (?:website|url|page)": "mcp__puppeteer_navigate",
        r"click (?:button|link|element)": "mcp__puppeteer_click",
        r"type|fill|enter": "mcp__puppeteer_type",
        r"screenshot|capture|snapshot": "mcp__puppeteer_screenshot",
        r"execute (?:python|code)": "mcp__ide__executeCode",
        r"run (?:command|shell)": "Bash",  # Use Bash tool
    }

    for pattern, tool in patterns.items():
        if re.search(pattern, task_description, re.IGNORECASE):
            return MCPToolCall(tool=tool, task=task_description)

    return None
```

## MCP Tool Invocation Patterns

### Pattern 1: Web Testing (E2E)

```markdown
## Automated Web Testing Flow

1. NAVIGATE to target URL
   Tool: mcp__puppeteer_navigate
   Args: {"url": "https://example.com"}

2. WAIT for page load
   Tool: mcp__puppeteer_wait
   Args: {"selector": "body", "timeout": 5000}

3. TAKE screenshot (before)
   Tool: mcp__puppeteer_screenshot
   Args: {"name": "before_test"}

4. INTERACT with elements
   Tool: mcp__puppeteer_click
   Args: {"selector": "#submit-button"}

   Tool: mcp__puppeteer_type
   Args: {"selector": "#username", "text": "testuser"}

5. VERIFY result
   Tool: mcp__puppeteer_evaluate
   Args: {"script": "document.querySelector('.result').textContent"}

6. TAKE screenshot (after)
   Tool: mcp__puppeteer_screenshot
   Args: {"name": "after_test"}
```

### Pattern 2: Desktop Automation

```markdown
## Desktop Control Flow

1. CAPTURE current screen
   Tool: mcp__desktop_screenshot
   Args: {}

2. ANALYZE screen content (via vision)

3. MOVE mouse to target
   Tool: mcp__desktop_mouse_move
   Args: {"x": 500, "y": 300}

4. CLICK
   Tool: mcp__desktop_click
   Args: {"button": "left"}

5. TYPE text
   Tool: mcp__desktop_type
   Args: {"text": "Hello World"}

6. USE hotkey
   Tool: mcp__desktop_hotkey
   Args: {"keys": ["ctrl", "s"]}
```

### Pattern 3: Database Operations

```markdown
## Database Query Flow

1. LIST tables
   Tool: mcp__db_list_tables
   Args: {}

2. QUERY data
   Tool: mcp__db_query
   Args: {"sql": "SELECT * FROM users WHERE active = 1"}

3. INSERT data
   Tool: mcp__db_execute
   Args: {"sql": "INSERT INTO logs (message) VALUES ('test')"}
```

## Custom MCP Server Creation

### When to Create Custom MCP Server

1. **No existing MCP server** for required capability
2. **Need specialized tool** for project-specific task
3. **Need API wrapper** for external service
4. **Need automation** for proprietary software

### Template: Simple MCP Server

```python
# custom_mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("custom-tool-server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="custom_operation",
            description="Perform custom operation",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "number"}
                },
                "required": ["param1"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "custom_operation":
        result = do_custom_operation(arguments)
        return [TextContent(type="text", text=result)]

def do_custom_operation(args):
    # Custom logic here
    return f"Operation completed with {args}"

if __name__ == "__main__":
    server.run()
```

### Auto-Create MCP Server Protocol

```markdown
WHEN custom MCP server is needed:

1. IDENTIFY requirement:
   - Task cannot be completed with existing tools
   - Need specialized API or automation

2. DESIGN server:
   - Define tool names and parameters
   - Implement core logic
   - Add error handling

3. CREATE files:
   - .builder/mcp-servers/{server_name}.py
   - .builder/mcp-servers/{server_name}_config.json

4. REGISTER server:
   Run: claude mcp add {server_name} -- python .builder/mcp-servers/{server_name}.py

5. TEST server:
   Invoke tool and verify output
```

## MCP Integration State Tracking

### State Schema

```json
{
  "mcp_integration": {
    "discovery_completed": true,
    "last_discovery": "2026-02-13T10:00:00Z",

    "available_servers": [
      "puppeteer",
      "filesystem",
      "ide"
    ],

    "capabilities": {
      "browser_automation": true,
      "file_system": true,
      "code_execution": true,
      "desktop_control": false,
      "database": false,
      "screenshot": true,
      "form_filling": true,
      "javascript_execution": true
    },

    "custom_servers": [
      {
        "name": "project-api-wrapper",
        "path": ".builder/mcp-servers/api_wrapper.py",
        "tools": ["api_call", "api_batch"]
      }
    ],

    "tool_invocations": [
      {
        "tool": "mcp__puppeteer_navigate",
        "args": {"url": "https://example.com"},
        "timestamp": "2026-02-13T10:30:00Z",
        "result": "success"
      }
    ]
  }
}
```

## Workflow Integration

### During Initialization Phase

```markdown
1. DISCOVER MCP servers
   - Run /mcp command
   - Parse available tools
   - Store capabilities

2. CHECK critical capabilities
   - browser_automation: needed for web testing
   - code_execution: needed for debugging
   - file_system: needed for file operations

3. INSTALL missing servers
   - For web projects: ensure puppeteer
   - For data projects: ensure database connectors
   - For desktop apps: ensure desktop control

4. UPDATE state.json
```

### During Implementation Phase

```markdown
BEFORE each task:

1. ANALYZE task requirements
   - Does it need browser interaction?
   - Does it need code execution?
   - Does it need desktop control?

2. CHECK capability availability
   - If capability exists: use MCP tool
   - If capability missing: install server or use alternative

3. INVOKE appropriate tool
   - Build tool arguments
   - Execute tool call
   - Handle result/error

4. LOG invocation to state
```

## Automatic MCP Server Installation

### Pre-defined Installation Commands

```json
{
  "mcp_install_commands": {
    "puppeteer": {
      "command": "claude mcp add puppeteer -- npx -y @anthropic-ai/mcp-server-puppeteer",
      "provides": ["browser_automation", "screenshot", "form_filling"],
      "priority": "high"
    },
    "filesystem": {
      "command": "claude mcp add filesystem -- npx -y @anthropic-ai/mcp-server-filesystem --path {{PROJECT_DIR}}",
      "provides": ["file_operations"],
      "priority": "critical"
    },
    "desktop": {
      "command": "claude mcp add desktop -- npx -y @anthropic-ai/mcp-server-desktop",
      "provides": ["desktop_control", "mouse_control", "keyboard_control"],
      "priority": "medium"
    },
    "sqlite": {
      "command": "claude mcp add sqlite -- npx -y @anthropic-ai/mcp-server-sqlite --db-path {{PROJECT_DIR}}/data.db",
      "provides": ["database"],
      "priority": "low"
    },
    "postgres": {
      "command": "claude mcp add postgres -- npx -y @anthropic-ai/mcp-server-postgres",
      "provides": ["database"],
      "priority": "low"
    },
    "github": {
      "command": "claude mcp add github -- npx -y @anthropic-ai/mcp-server-github",
      "provides": ["git_operations", "issue_management", "pr_management"],
      "priority": "medium"
    },
    "brave-search": {
      "command": "claude mcp add brave-search -- npx -y @anthropic-ai/mcp-server-brave-search",
      "provides": ["web_search"],
      "priority": "medium"
    }
  }
}
```

## Common MCP Workflows

### Workflow 1: Web Application Testing

```markdown
## Complete E2E Test Flow

PHASE 1: SETUP
1. mcp__puppeteer_navigate → Open application
2. mcp__puppeteer_screenshot → Capture initial state

PHASE 2: INTERACTION
3. mcp__puppeteer_fill → Fill login form
4. mcp__puppeteer_click → Submit login
5. mcp__puppeteer_wait → Wait for dashboard

PHASE 3: VERIFICATION
6. mcp__puppeteer_evaluate → Check page state
7. mcp__puppeteer_screenshot → Capture result

PHASE 4: CLEANUP
8. mcp__puppeteer_close → Close browser
```

### Workflow 2: API Testing via Browser

```markdown
## API Testing via Browser Console

1. Navigate to API endpoint or frontend
   mcp__puppeteer_navigate → "https://api.example.com/docs"

2. Execute API call in console
   mcp__puppeteer_evaluate → `
     fetch('/api/users', {method: 'GET'})
       .then(r => r.json())
       .then(data => JSON.stringify(data))
   `

3. Parse and verify response
```

### Workflow 3: Desktop App Automation

```markdown
## Desktop App Testing

1. Take initial screenshot
   mcp__desktop_screenshot → {}

2. Launch application
   Bash → "open /Applications/MyApp.app"

3. Wait for app to load
   sleep(3)

4. Capture app window
   mcp__desktop_screenshot → {}

5. Interact with app
   mcp__desktop_mouse_move → {x: 100, y: 200}
   mcp__desktop_click → {button: "left"}
   mcp__desktop_type → {text: "test input"}

6. Verify result
   mcp__desktop_screenshot → {}
```

## Error Handling

### MCP Server Not Available

```markdown
IF required MCP tool not available:
  1. Log warning: "MCP tool {name} not available"
  2. Attempt to install server
  3. If install fails:
     - Use alternative approach
     - Or skip capability and log
  4. Continue execution (DO NOT PAUSE)
```

### MCP Tool Execution Failure

```markdown
IF MCP tool execution fails:
  1. Log error details
  2. Retry with adjusted parameters
  3. If still failing:
     - Try alternative tool
     - Or use fallback method
  4. Update state with failure info
```

## Quick Reference

### Check MCP Status
```
Run: /mcp
```

### Install MCP Server
```
claude mcp add {server-name} -- {command}
```

### Invoke MCP Tool
```
Direct tool call: mcp__{server}__{tool}
Example: mcp__puppeteer_navigate
```

### View MCP Logs
```
Read: .builder/mcp-integration.log
```
