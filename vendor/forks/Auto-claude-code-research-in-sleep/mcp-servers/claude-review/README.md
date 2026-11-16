# Claude Review MCP

Bridge Codex-first ARIS workflows to the local Claude Code CLI.

## What it does

- Keeps **Codex** as the executor
- Uses **Claude Code CLI** as the external reviewer
- Exposes synchronous MCP tools:
  - `review`
  - `review_reply`
- Exposes asynchronous MCP tools for long reviewer prompts:
  - `review_start`
  - `review_reply_start`
  - `review_status`

The synchronous tools return a JSON string containing `threadId` and `response`.
The asynchronous start tools return a JSON string containing `jobId` and `status`, and `review_status` later returns the final `threadId` and `response`.

Claude Code is the CLI transport. The reviewer uses its configured provider,
which may be Anthropic or an API-compatible provider such as DeepSeek. Do not
classify the reviewer's model family from the bridge name alone.

## Install into Codex

```bash
mkdir -p ~/.codex/mcp-servers/claude-review
cp mcp-servers/claude-review/server.py ~/.codex/mcp-servers/claude-review/server.py
codex mcp add claude-review -- python3 ~/.codex/mcp-servers/claude-review/server.py
```

Alternatively, register the absolute path to `server.py` in an existing ARIS
checkout so repository updates also update the bridge. If Codex cannot find
`claude` on PATH, pass `--env CLAUDE_BIN=/absolute/path/to/claude` before `--`.
The bridge uses Claude Code's existing provider settings and authentication;
there is no need to copy credentials into the MCP configuration. Leaving
`CLAUDE_REVIEW_MODEL` unset follows the CLI's configured model.

Reopen the Codex session after registering a new server and check its MCP tool
list. An existing interactive Claude Code window can remain open: this bridge
starts a separate non-interactive session and resumes only the supplied
`threadId`, never the most recent interactive conversation.

If your Claude Code login depends on a shell function such as `claude-aws`, use the wrapper instead:

```bash
mkdir -p ~/.codex/mcp-servers/claude-review
cp mcp-servers/claude-review/server.py ~/.codex/mcp-servers/claude-review/server.py
cp mcp-servers/claude-review/run_with_claude_aws.sh ~/.codex/mcp-servers/claude-review/run_with_claude_aws.sh
chmod +x ~/.codex/mcp-servers/claude-review/run_with_claude_aws.sh
codex mcp add claude-review -- ~/.codex/mcp-servers/claude-review/run_with_claude_aws.sh
```

## Environment Variables

- `CLAUDE_BIN`: Claude CLI path, defaults to `claude`
- `CLAUDE_REVIEW_MODEL`: optional reviewer model override
- `CLAUDE_REVIEW_SYSTEM`: optional default system prompt
- `CLAUDE_REVIEW_TOOLS`: Claude tools override, defaults to empty string
- `CLAUDE_REVIEW_TIMEOUT_SEC`: subprocess timeout, defaults to `600`
- `CLAUDE_REVIEW_STATE_DIR`: async job storage, defaults to `~/.codex/state/claude-review`
- `CLAUDE_REVIEW_DEBUG_LOG`: local protocol/debug log path; logs include prompts and responses

## Notes

- The bridge runs Claude in non-interactive `-p` mode.
- It passes `--strict-mcp-config` with an empty MCP configuration, so the
  reviewer does not inherit MCP servers such as Codex and delegate back to the
  executor. Provider settings remain available. CLI tools and plan permissions
  are not an operating-system sandbox.
- By default the reviewer gets **no tools**. This matches the original ARIS pattern where the external reviewer only sees the prompt context prepared by the executor.
- A prompt that hands the reviewer **artifact paths** instead of pasted context must therefore opt in per call, e.g. `"tools": "Read,Grep,Glob"`. Without it the reviewer is asked to read files it has no tool to open, and it answers from your framing alone — exactly what artifact-grounded review is meant to avoid. The `skills-codex-claude-review` overlay passes this on its artifact-grounded review blocks; the server default stays tool-free, so prompt-only reviews are unchanged.
- The opt-in is **per call, not per thread**: every call re-sends `--tools`, so a `review_reply` / `review_reply_start` continuing an artifact-grounded thread has to repeat it.
- All four review tools accept `cwd`. Set it to the project directory when
  passing artifact paths, and repeat the same value on replies. Without it,
  the CLI inherits the MCP server's directory; `threadId` does not select a
  working directory. Async jobs save the resolved absolute directory before
  launching their worker.
- Keep the opt-in read-only. The bridge already runs Claude with `--permission-mode plan`, and a reviewer has no reason to hold `Bash`, `Edit`, or `Write`.
- `threadId` is the native Claude session id and can be passed directly to `review_reply`.
- `jobId` is a bridge-local background task id stored on disk under `~/.codex/state/claude-review/jobs/` by default, so status can be resumed across MCP server restarts.

Example file review:

```json
{
  "name": "review",
  "arguments": {
    "prompt": "Read draft.md and identify unsupported claims.",
    "cwd": "/absolute/path/to/project",
    "tools": "Read,Grep,Glob"
  }
}
```

Results include `requestedModel` (explicit argument or bridge default, otherwise
`null`) separately from `model`. The latter comes from the CLI result's `model`
field or a single `modelUsage` entry, with `modelSource` identifying the source.
`reportedModels` lists the usage entries when present. If the CLI does not
identify one model unambiguously, `model` is `null`; the requested alias is never
substituted as evidence. These are CLI reports, not independent server identity
verification. No context-window size or reasoning effort is inferred from the
model name.

Empty reviews, nonterminal output, CLI errors and explicit unfinished stop
reasons are returned as errors, with no automatic retry. Existing synchronous
calls block the protocol reader until the CLI returns or times out; MCP
cancellation is not a process-tree cancellation guarantee. Use async jobs for
long reviews and poll their status after reconnecting.

## When to use sync vs async

- Use `review` / `review_reply` for short prompts that comfortably finish within the host MCP tool timeout.
- Use `review_start` / `review_reply_start` + `review_status` for long paper or project reviews. This avoids the observed `Codex -> tools/call` timeout around 120 seconds.

## Async flow

Start a long review:

```json
{
  "name": "review_start",
  "arguments": {
    "prompt": "Review this paper draft..."
  }
}
```

Example response:

```json
{
  "jobId": "5d8d0a9c5a2f4f42ae44f6f0c2d73f6f",
  "status": "queued",
  "done": false
}
```

Poll later:

```json
{
  "name": "review_status",
  "arguments": {
    "jobId": "5d8d0a9c5a2f4f42ae44f6f0c2d73f6f",
    "waitSeconds": 20
  }
}
```

When complete, `review_status` returns the same reviewer payload fields as the synchronous tools, including `threadId`, `response`, `model`, and `stop_reason`.
