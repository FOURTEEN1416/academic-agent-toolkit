# Two-Agent Architecture Pattern

Based on Anthropic's official claude-quickstarts architecture design.

## Overview

The Two-Agent pattern is the **core architecture** for long-running autonomous tasks, solving the fundamental problem of limited context windows.

## The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT WINDOW LIMITATION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Single Session Approach (PROBLEMATIC):                         │
│                                                                 │
│  Session 1:                                                      │
│  ├─ Initialize project                                          │
│  ├─ Feature 1 (done)                                            │
│  ├─ Feature 2 (done)                                            │
│  ├─ Feature 3 (in progress...)                                  │
│  └─ ⚠️ Context exhausted, session must end                       │
│                                                                 │
│  Result: Project incomplete, no automatic continuation          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## The Solution: Two-Agent Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    TWO-AGENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SESSION 1: INITIALIZER AGENT                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. Read app_spec.txt / requirements                     │    │
│  │ 2. Create project structure                             │    │
│  │ 3. Generate feature_list.json (200+ tests)              │    │
│  │ 4. Create init.sh (startup script)                      │    │
│  │ 5. Initialize Git repository                            │    │
│  │ 6. ✨ Prompt for GitHub repository URL                  │    │
│  │ 7. ✨ Create README.md & PLANNING.md                    │    │
│  │ 8. Commit initial state                                 │    │
│  │ 9. ✨ Push to GitHub                                    │    │
│  │ 10. ✨ Create GitHub issues for features               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│                   feature_list.json                              │
│                   (Single Source of Truth)                       │
│                              │                                   │
│                              ▼                                   │
│  SESSIONS 2+: BUILDER AGENT (repeated until complete)           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 1: Get Context                                     │    │
│  │         pwd && ls -la                                   │    │
│  │         cat app_spec.txt                                │    │
│  │         cat feature_list.json | head -50                │    │
│  │         cat progress.txt                                │    │
│  │         git log --oneline -20                           │    │
│  │                                                         │    │
│  │ Step 2: Start Server                                    │    │
│  │         ./init.sh                                       │    │
│  │                                                         │    │
│  │ Step 3: Verify Previous Tests                           │    │
│  │         Run all passing tests (regression check)        │    │
│  │                                                         │    │
│  │ Step 4: Select Next Feature                             │    │
│  │         Find highest priority "passes": false           │    │
│  │                                                         │    │
│  │ Step 5: Implement Feature                               │    │
│  │         Write code                                      │    │
│  │                                                         │    │
│  │ Step 6: Browser Automation Test                         │    │
│  │         Navigate, click, type, verify                   │    │
│  │         Take screenshots                                │    │
│  │                                                         │    │
│  │ Step 7: Update feature_list.json                        │    │
│  │         Only modify "passes" field!                     │    │
│  │                                                         │    │
│  │ Step 8: Git Commit + GitHub Push                       │    │
│  │         git add -A && git commit                        │    │
│  │         ✨ git push origin main                         │    │
│  │         ✨ Update GitHub issue status                   │    │
│  │         ✨ Check milestone & create release tag         │    │
│  │                                                         │    │
│  │ Step 9: Update Progress Notes                           │    │
│  │         echo "progress" >> progress.txt                 │    │
│  │                                                         │    │
│  │ Step 10: Clean Exit                                     │    │
│  │         All tests passing, no console errors            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│                    Auto-continue (3s delay)                      │
│                              │                                   │
│                              ▼                                   │
│                    NEW SESSION (fresh context)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Design Principles

### 1. Fresh Context Per Session

```python
# Each session starts with a BRAND NEW context window
# This is CRITICAL for long-running tasks

class BuilderAgent:
    async def run_session(self, project_dir: Path):
        # Session 1: Full 180k tokens available
        # Session 2: Full 180k tokens available
        # Session N: Full 180k tokens available

        # Progress is persisted via FILES, not context
        context = await self.get_context_from_files(project_dir)
        # ...
```

### 2. Single Source of Truth

```json
// feature_list.json - THE ONLY STATE THAT MATTERS
[
  {
    "category": "functional",
    "description": "User can log in with valid credentials",
    "steps": [
      "Navigate to login page",
      "Enter username 'testuser'",
      "Enter password 'password123'",
      "Click login button",
      "Verify redirect to dashboard"
    ],
    "passes": false  // ONLY THIS FIELD CAN BE MODIFIED
  },
  {
    "category": "style",
    "description": "Login button has correct styling",
    "steps": [
      "Navigate to login page",
      "Verify button color is #3B82F6",
      "Verify button has rounded corners"
    ],
    "passes": true   // This test passes
  }
]
```

### 3. Git Commit as State Anchor

```markdown
Every feature completion = 1 Git commit

This provides:
- Atomic progress units
- Easy rollback
- Clear history
- State recovery point
```

### 4. Browser Automation for Verification

```markdown
## Testing Philosophy

NEVER use curl or JS evaluation to bypass UI

ALWAYS:
1. Navigate to page
2. Click elements like a human
3. Type text like a human
4. Take screenshots
5. Check console for errors
```

## Implementation

### Initializer Agent

```python
class InitializerAgent:
    """First session: Set up project structure"""

    SYSTEM_PROMPT = """
You are the Initializer Agent. Your job is to set up a project for long-running development.

Your outputs:
1. Project structure with all necessary files
2. feature_list.json with 200+ test cases
3. init.sh startup script
4. Git repository with initial commit

Rules:
- Create comprehensive test cases (mix of simple and complex)
- All tests start with "passes": false
- Include both "functional" and "style" categories
- Exit cleanly when done
"""

    async def run(self, spec: str, project_dir: Path):
        # Read spec
        # Create project structure
        # Generate feature_list.json
        # Create init.sh
        # Initialize git
        # Prompt for GitHub URL (optional)
        # Create README.md and PLANNING.md
        # Commit
        # Push to GitHub (if enabled)
        # Create GitHub issues (if enabled)
        pass
```

#### GitHub Integration in Initializer

```python
async def setup_github_integration(self, project_dir: Path, state: dict):
    """Set up GitHub integration during initialization"""

    # 1. Prompt for repository URL
    print("\n=== GitHub Integration (Optional) ===")
    print("Enter GitHub repository URL to enable remote push and issue tracking.")
    print("Leave empty to skip GitHub integration.\n")

    repo_url = input("GitHub repository URL: ").strip()

    if not repo_url:
        state['github']['enabled'] = False
        print("GitHub integration disabled. Local git commits will continue.")
        return

    # 2. Verify authentication
    try:
        subprocess.run(['gh', 'auth', 'status'], check=True, capture_output=True)
    except:
        print("⚠️ GitHub CLI not authenticated. Run: gh auth login")
        state['github']['enabled'] = False
        return

    # 3. Set up remote
    subprocess.run(['git', 'remote', 'add', 'origin', repo_url])

    # 4. Update state
    owner, repo_name = self.extract_repo_info(repo_url)
    state['github'].update({
        'enabled': True,
        'repository_url': repo_url,
        'repository_owner': owner,
        'repository_name': repo_name
    })

    # 5. Create initial documentation
    self.create_readme(project_dir, state)
    self.create_planning_doc(project_dir, state)

    # 6. Initial push
    subprocess.run(['git', 'add', '.'])
    subprocess.run(['git', 'commit', '-m', 'chore: Initialize project with autonomous-builder'])
    subprocess.run(['git', 'push', '-u', 'origin', 'main'])

    # 7. Create GitHub issues
    features = json.loads((project_dir / 'features.json').read_text())
    for feature in features['features']:
        issue_number = self.create_github_issue(feature, state)
        feature['github_issue'] = issue_number
        state['github']['issues'][feature['id']] = issue_number

    # Save updated state
    (project_dir / '.builder' / 'state.json').write_text(json.dumps(state, indent=2))
    (project_dir / 'features.json').write_text(json.dumps(features, indent=2))
```

### Builder Agent

```python
class BuilderAgent:
    """Subsequent sessions: Build features one at a time"""

    SYSTEM_PROMPT = """
You are the Builder Agent. Your job is to implement features one at a time.

CRITICAL WORKFLOW:

Step 1: Get Context (MANDATORY)
- pwd && ls -la
- cat app_spec.txt
- cat feature_list.json | head -50
- cat progress.txt
- git log --oneline -20

Step 2: Start Server
- ./init.sh

Step 3: Verify Previous Tests
- Run all currently passing tests
- Ensure no regressions

Step 4: Select Next Feature
- Find highest priority test with "passes": false

Step 5: Implement Feature
- Write clean, maintainable code

Step 6: Browser Test
- Use Puppeteer tools
- Act like a human user
- Take screenshots

Step 7: Update feature_list.json
- ONLY change "passes": true for the test
- DO NOT add/remove/modify anything else

Step 8: Git Commit + GitHub Push
- git add -A
- git commit -m "feat: {feature description}\n\nCloses #{issue_number}"
- git push origin main (if GitHub enabled)
- Update GitHub issue status
- Check milestone and create release tag if needed

Step 9: Update Progress
- echo "$(date): Completed {feature}" >> progress.txt

Step 10: Clean Exit
- Ensure server still running
- All passing tests still pass
- No console errors
"""

    async def run(self, project_dir: Path):
        # Get context from files
        # Verify state
        # Select feature
        # Implement
        # Test
        # Commit
        # Push to GitHub (if enabled)
        # Update GitHub issue (if enabled)
        # Check milestone and create release tag (if enabled)
        # Exit
        pass
```

#### GitHub Integration in Builder

```python
async def commit_and_push_feature(self, feature: dict, state: dict):
    """Commit feature and push to GitHub"""

    # 1. Create commit message with issue reference
    issue_number = feature.get('github_issue')
    commit_msg = f"""feat: {feature['name']}

{feature['description']}

Implementation:
{self.generate_implementation_summary(feature)}

Tests: {feature['tests']['passed']}/{feature['tests']['total']} passing

Closes #{issue_number}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"""

    # 2. Commit
    subprocess.run(['git', 'add', '-A'])
    subprocess.run(['git', 'commit', '-m', commit_msg])
    commit_hash = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                 capture_output=True, text=True).stdout.strip()

    # 3. Push to GitHub (with retry)
    if state['github']['enabled']:
        success = await self.push_with_retry(state)

        if success:
            state['github']['last_push'] = datetime.now().isoformat()
            state['github']['last_push_commit'] = commit_hash

            # 4. Update GitHub issue
            if state['github']['issue_tracking'] and issue_number:
                try:
                    subprocess.run([
                        'gh', 'issue', 'comment', str(issue_number),
                        '--body', f'✅ Feature implemented in commit {commit_hash[:7]}\n\n'
                                  f'Tests: {feature["tests"]["passed"]}/{feature["tests"]["total"]} passing'
                    ])
                    feature['github_issue_state'] = 'closed'
                except Exception as e:
                    print(f"Warning: Failed to update GitHub issue: {e}")

            # 5. Check for milestone and create release tag
            if state['github']['release_tagging']:
                await self.check_and_create_release_tag(state)

    # 6. Update state
    state['git']['last_commit'] = commit_hash
    feature['github_commits'].append(commit_hash)

async def push_with_retry(self, state: dict, max_retries=3) -> bool:
    """Push to GitHub with retry logic"""
    for attempt in range(max_retries):
        try:
            subprocess.run(['git', 'push', 'origin', 'main'], check=True)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Push failed (attempt {attempt + 1}), retrying in 5s...")
                await asyncio.sleep(5)
            else:
                print(f"Push failed after {max_retries} attempts: {e}")
                state['github']['pending_pushes'].append({
                    'commit': state['git']['last_commit'],
                    'timestamp': datetime.now().isoformat(),
                    'error': str(e)
                })
                return False

async def check_and_create_release_tag(self, state: dict):
    """Check if milestone reached and create release tag"""
    completed = len(state['features']['completed'])
    total = completed + len(state['features']['pending'])
    progress = completed / total if total > 0 else 0

    milestones = {
        0.25: 'v0.1.0',
        0.50: 'v0.2.0',
        0.75: 'v0.3.0',
        1.00: 'v1.0.0'
    }

    for threshold, version in milestones.items():
        if progress >= threshold and version not in [r['version'] for r in state['github']['releases']]:
            # Create tag
            tag_msg = f"""Release {version}

Milestone: {int(threshold * 100)}% completion

Features completed: {completed}
Total features: {total}

Generated by autonomous-builder"""

            subprocess.run(['git', 'tag', '-a', version, '-m', tag_msg])
            subprocess.run(['git', 'push', 'origin', version])

            # Create GitHub release
            release_notes = self.generate_release_notes(state, version)
            subprocess.run([
                'gh', 'release', 'create', version,
                '--title', f'Release {version}',
                '--notes', release_notes
            ])

            # Update state
            state['github']['releases'].append({
                'version': version,
                'tag': version,
                'created_at': datetime.now().isoformat(),
                'commit': state['git']['last_commit'],
                'features_completed': completed
            })

            print(f"✅ Created release tag {version}")
            break
```

### Session Coordinator

```python
class SessionCoordinator:
    """Manages the two-agent lifecycle"""

    def __init__(self, spec: str, project_dir: Path):
        self.spec = spec
        self.project_dir = project_dir
        self.initializer = InitializerAgent()
        self.builder = BuilderAgent()

    async def run_until_complete(self):
        # Check if initialized
        if not (self.project_dir / "feature_list.json").exists():
            await self.initializer.run(self.spec, self.project_dir)

        # Run builder sessions until complete
        while not self.is_complete():
            await self.builder.run(self.project_dir)
            await asyncio.sleep(3)  # Auto-continue delay

    def is_complete(self) -> bool:
        feature_list = json.loads(
            (self.project_dir / "feature_list.json").read_text()
        )
        return all(f["passes"] for f in feature_list)
```

## Context Budget Management

```python
class MessageHistory:
    """Official pattern for managing context window"""

    def __init__(
        self,
        model: str,
        context_window_tokens: int = 180000,
        enable_caching: bool = True,
    ):
        self.messages = []
        self.total_tokens = 0
        self.enable_caching = enable_caching

    async def add_message(self, role: str, content, usage=None):
        self.messages.append({"role": role, "content": content})

        if role == "assistant" and usage:
            total_input = (
                usage.input_tokens +
                getattr(usage, "cache_read_input_tokens", 0) +
                getattr(usage, "cache_creation_input_tokens", 0)
            )
            self.total_tokens += total_input + usage.output_tokens

    def truncate(self):
        """Remove oldest messages when context exceeded"""
        while self.total_tokens > self.context_window_tokens:
            self.messages.pop(0)  # Remove oldest user
            self.messages.pop(0)  # Remove oldest assistant
            # Recalculate tokens

    def format_for_api(self):
        """Format with prompt caching"""
        result = [{"role": m["role"], "content": m["content"]}
                  for m in self.messages]

        if self.enable_caching and self.messages:
            # Add cache_control to last message
            result[-1]["content"] = [
                {**block, "cache_control": {"type": "ephemeral"}}
                for block in self.messages[-1]["content"]
            ]
        return result
```

## Prompt Caching Strategy

```python
def inject_prompt_caching(messages: list):
    """
    Set cache breakpoints for last 3 user messages
    This enables cross-session prompt caching
    """
    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user":
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                message["content"][-1]["cache_control"] = {
                    "type": "ephemeral"
                }
```

## Key Metrics

```python
def count_passing_tests(project_dir: Path) -> tuple[int, int]:
    """Track progress"""
    tests = json.loads(
        (project_dir / "feature_list.json").read_text()
    )
    total = len(tests)
    passing = sum(1 for t in tests if t.get("passes", False))
    return passing, total

def calculate_completion_percentage(project_dir: Path) -> float:
    passing, total = count_passing_tests(project_dir)
    return (passing / total) * 100 if total > 0 else 0.0
```

## Best Practices

### DO

- Use fresh context per session
- Persist state via files (feature_list.json)
- Commit after each feature
- Test via browser automation
- Include regression testing

### DON'T

- Keep session running indefinitely
- Store state in context
- Skip Git commits
- Test via curl/internal APIs
- Assume previous tests still pass

## Comparison: Before vs After

| Aspect | Single Session | Two-Agent Pattern |
|--------|---------------|-------------------|
| Context limit | Blocks completion | Fresh per session |
| State persistence | Lost on exit | File-based |
| Progress tracking | Manual | Automatic |
| Recovery | Start over | Resume from commit |
| Token efficiency | Degrades over time | Constant per session |
| Cost | Increases | Predictable |
