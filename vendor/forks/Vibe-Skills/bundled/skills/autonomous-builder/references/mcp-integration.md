# MCP Integration Guide

Complete guide to using MCP tools in autonomous development workflows.

## Available MCP Servers

### Puppeteer (Browser Automation)

**Purpose**: E2E testing, web scraping, screenshots

**Key Tools**:
- `mcp__puppeteer_navigate`: Navigate to URL
- `mcp__puppeteer_click`: Click element
- `mcp__puppeteer_type`: Type into input
- `mcp__puppeteer_screenshot`: Capture screenshot
- `mcp__puppeteer_evaluate`: Execute JavaScript

**Usage Patterns**:

```markdown
## E2E Login Test
1. Navigate: mcp__puppeteer_navigate("http://localhost:3000/login")
2. Type email: mcp__puppeteer_type("#email", "test@example.com")
3. Type password: mcp__puppeteer_type("#password", "password123")
4. Click submit: mcp__puppeteer_click("#submit")
5. Verify: mcp__puppeteer_evaluate("document.querySelector('.welcome')")
6. Screenshot: mcp__puppeteer_screenshot("login-success.png")
```

**Error Handling**:
```markdown
If navigation timeout:
1. Check server is running
2. Increase timeout
3. Try alternative selector

If element not found:
1. Wait for page load
2. Check selector is correct
3. Use alternative selector strategy
```

### IDE Tools (Code Execution)

**Purpose**: Execute code, get diagnostics

**Key Tools**:
- `mcp__ide__executeCode`: Run Python code in Jupyter kernel
- `mcp__ide__getDiagnostics`: Get language diagnostics

**Usage Patterns**:

```markdown
## Python Code Execution
1. Write code to file
2. Execute: mcp__ide__executeCode("import module; result = func()")
3. Check output
4. Get diagnostics: mcp__ide__getDiagnostics()
```

**For Different Languages**:
- Python: Use executeCode directly
- Node.js: Use Bash with `node script.js`
- Go: Use Bash with `go run`
- Rust: Use Bash with `cargo run`

### Filesystem MCP

**Purpose**: Advanced file operations

**Key Tools**:
- `mcp__filesystem_read_file`: Read file content
- `mcp__filesystem_write_file`: Write file content
- `mcp__filesystem_list_directory`: List directory contents
- `mcp__filesystem_search_files`: Search for files

### Database MCP

**Purpose**: Database operations

**Key Tools**:
- `mcp__database_query`: Execute SQL query
- `mcp__database_list_tables`: List all tables
- `mcp__database_describe_table`: Get table schema

**Usage Patterns**:

```markdown
## Database Migration
1. List tables: mcp__database_list_tables()
2. Check schema: mcp__database_describe_table("users")
3. Run migration: mcp__database_query("ALTER TABLE users ADD COLUMN ...")
4. Verify: mcp__database_query("SELECT * FROM users LIMIT 1")
```

## Integration Workflows

### Web Application Testing Flow

```
START
  │
  ▼
Start dev server ──▶ Wait for ready
  │
  ▼
Run unit tests ──▶ All pass? ──No──▶ Fix and retry
  │                    │
  Yes                  Yes
  │                    │
  ▼                    ▼
Run integration tests ◀─────┘
  │
  All pass?
  │
  Yes
  │
  ▼
Launch browser (Puppeteer)
  │
  ▼
Navigate to app
  │
  ▼
Run E2E scenarios
  │
  All pass?
  │
  Yes
  │
  ▼
Take screenshots
  │
  ▼
Generate test report
  │
  ▼
END
```

### Database Integration Flow

```
START
  │
  ▼
Detect database type
  │
  ▼
Read schema
  │
  ▼
Generate models
  │
  ▼
Create migrations
  │
  ▼
Test migrations
  │
  Success?
  │
  Yes
  │
  ▼
Apply migrations
  │
  ▼
Verify data integrity
  │
  ▼
END
```

## Configuration

### .mcp.json for Autonomous Builder

```json
{
  "puppeteer": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
    "env": {
      "PUPPETEER_HEADLESS": "true"
    }
  },
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/project/path"]
  },
  "database": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres"],
    "env": {
      "DATABASE_URL": "${DATABASE_URL}"
    }
  }
}
```

## Common E2E Test Scenarios

### User Registration Flow

```javascript
// 1. Navigate to registration page
await mcp__puppeteer_navigate("http://localhost:3000/register");

// 2. Fill form
await mcp__puppeteer_type("#username", "testuser");
await mcp__puppeteer_type("#email", "test@example.com");
await mcp__puppeteer_type("#password", "SecurePass123!");

// 3. Submit
await mcp__puppeteer_click("#register-button");

// 4. Verify success
const welcome = await mcp__puppeteer_evaluate(
  "document.querySelector('.welcome-message')?.textContent"
);

// 5. Screenshot for evidence
await mcp__puppeteer_screenshot("registration-success.png");
```

### CRUD Operations Test

```javascript
// Create
await mcp__puppeteer_navigate("http://localhost:3000/items/new");
await mcp__puppeteer_type("#name", "Test Item");
await mcp__puppeteer_click("#save");
await mcp__puppeteer_screenshot("item-created.png");

// Read
await mcp__puppeteer_navigate("http://localhost:3000/items");
const items = await mcp__puppeteer_evaluate(
  "document.querySelectorAll('.item').length"
);

// Update
await mcp__puppeteer_click(".item:first-child .edit");
await mcp__puppeteer_type("#name", "Updated Item");
await mcp__puppeteer_click("#save");

// Delete
await mcp__puppeteer_click(".item:first-child .delete");
await mcp__puppeteer_screenshot("item-deleted.png");
```

## Best Practices

1. **Always check tool availability** before using
2. **Handle timeouts gracefully** with retry logic
3. **Clean up resources** (close browsers, connections)
4. **Log all MCP operations** for debugging
5. **Use headless mode** for automated testing
6. **Take screenshots** at key verification points
7. **Wait for elements** before interacting
8. **Use meaningful selectors** (data-testid preferred)
