# Review Tracing Protocol

<!-- modex-3 同源吸收 P3（2026-09-22）：自上游共享参考收编为本技能 references/，补齐 SKILL.md 悬空指针；调用名已中性化。 -->

## Purpose

Save full prompt/response pairs for every cross-model reviewer call, enabling:
- **Reviewer-independence audit**: verify the executor only passed file paths, not summaries
- **Reproducibility**: threadId preservation allows conversation continuation
- **Meta-optimize input**: richer data for harness improvement analysis

## When to Trace

After **every** external reviewer/critique call that serves a reviewer
function — whatever bridge the driving agent provides (native sub-agent task,
agent-native review tool, or CLI reviewer client such as
`tools/reviewer_client.py`). This includes review scoring, experiment
auditing, claim verification, idea critique, and patch gating.

Do NOT trace: purely informational LLM calls (e.g., an external CLI call for code generation that is not a review).

## Trace Directory

```
<workspace>/traces/<skill-name>/<YYYY-MM-DD>_run<NN>/
  ├── run.meta.json                      # Run-level metadata
  ├── 001-<purpose>.request.json         # Request snapshot
  ├── 001-<purpose>.response.md          # Full response text
  ├── 001-<purpose>.meta.json            # Response metadata
  ├── 002-<purpose>.request.json         # Second call (e.g., reply)
  └── ...
```

- `<skill-name>`: the owning skill that triggered this call (e.g., `auto-review-loop`)
- `<YYYY-MM-DD>_run<NN>`: date + sequential run number (start from `01`)
- `<purpose>`: short kebab-case label (e.g., `round-1-review`, `critique`, `ideation`, `audit`, `patch-gate`)

## How to Trace

After each reviewer call — including every FAILED attempt in a
capability-fallback chain (one trace entry per attempt: `--status error` +
`--fallback-reason`; the successful entry records the RESOLVED pair) — write the trace files **directly** per the "File Schemas" section
below, into:

```
<workspace>/traces/<skill-name>/<YYYY-MM-DD>_run<NN>/
  ├── run.meta.json
  ├── 001-<purpose>.request.json
  ├── 001-<purpose>.response.md
  ├── 001-<purpose>.meta.json
  └── ...
```

No helper script is bundled: the trace files themselves are the
contract. A workspace may provide its own `save_trace` helper as an
optimization, never as a dependency. Do NOT silently skip —
trace_path is load-bearing for any mandatory audit emitting
`trace_path` in its artifact (see assurance-contract
§"Required Audit Artifact Schema"). Every FAILED attempt in a round
gets its own numbered pair, same as successes.

The helper, when present, handles directory creation, run numbering, file
writing, and provenance classification. For a successful native call, it first
revalidates `--native-evidence`, overrides caller model/response fields with the
session-bound values, and records the evidence ID/path; missing or invalid
evidence is an error. A native dispatch that failed before evidence could exist
may be traced only with `--status error` and no `--native-evidence`; that record
has no verified model provenance or independence and can never enter the stop
gate. For other backends it derives families from model strings
(`reported_reviewer_model`, otherwise `requested_reviewer_model`, otherwise
`model`) and ignores contradictory caller family/independence claims. It also
records that `--executor-model` is `caller-declared`; a different family pair is
`family_relation: "different"` but remains `independence_verified: "unverified"`.
Validated native evidence instead records both sources as
`agent-session-event`, `family_relation: "different"`, and
`independence_verified: true`.

### Native session evidence

The native-specific required pair for a completed review is:

```bash
bash "$TRACE_HELPER" ... --backend native \
  --native-evidence "review-stage/NATIVE_${RUN_ID}_ROUND_${ROUND}_REVIEW.evidence.json"
```

Omit `--native-evidence` for every other backend.
For a failed native dispatch, instead use `--backend native --status
error --fallback-reason "<agent error>"` without evidence, then write a separate
trace for any fallback backend that actually reviews the artifacts.
The fallback branch above documents what to do
when the helper is unreachable — the trace is forensic evidence, so
"helper missing" never means "skip the trace." A direct fallback writer MUST
apply the same model-string derivation and evidence-source rules; it may not
copy caller family labels or promote caller-declared identity to verification.

## File Schemas

### `run.meta.json`
```json
{
  "skill": "auto-review-loop",
  "run_id": "2026-04-15_run01",
  "started_at": "2026-04-15T14:30:00+08:00",
  "executor": "<driving-agent>",
  "executor_model": "<executor-model>",
  "executor_model_source": "caller-declared",
  "executor_family": "vendor-a",
  "reviewer_model_source": "requested",
  "reviewer_family": "vendor-b",
  "reviewer_backend": "cli",
  "native_evidence_id": null,
  "native_evidence_path": null,
  "family_relation": "different",
  "independence_verified": "unverified",
  "project_dir": "/path/to/project"
}
```

- `executor`: the name of the running executor (from `--executor`; dynamic, set by the caller, not hardcoded).
- `executor_model`: the declared model running this invocation (from `--executor-model` when available; otherwise `null`).
- `executor_model_source`: `"agent-session-event"` for validated native evidence,
  `"caller-declared"` when a non-native caller passes `--executor-model`, or
  `"unavailable"`.
- `executor_family`: derived from `executor_model` (a caller-supplied family label or `unknown`).
- `reviewer_model_source`: `"agent-session-event"`, `"backend-reported"`,
  `"requested"`, or `"unavailable"`.
- `reviewer_family`: derived from the backend-reported model when available, otherwise the requested model.
- `family_relation`: `different`, `same`, or `unknown`, derived from model strings.
- `independence_verified`: `true` only for a revalidated native cross-family
  event chain, `false` for known same-family identities, otherwise
  `"unverified"`.
- `native_evidence_id` / `native_evidence_path`: set only for
  `native`; `null` for other backends.
- `reviewer_backend`: `native` / `cli` / `manual`, or any identifier supplied by the caller.

### `NNN-<purpose>.request.json`
```json
{
  "call_number": 1,
  "purpose": "round-1-review",
  "timestamp": "2026-04-15T14:31:00+08:00",
  "tool": "<agent reviewer bridge name>",
  "backend": "cli",
  "model": "<reviewer-model>",
  "config": {"model_reasoning_effort": "xhigh"},
  "reviewer_profile": null,
  "files_referenced": ["paper/sections/3_method.tex", "results/table1.csv"],
  "prompt": "<full prompt text>"
}
```

For native backend (no reviewer override in a bound agent session):
```json
{
  "call_number": 1,
  "purpose": "round-1-review",
  "tool": "task(agent_type=<native-reviewer>)",
  "backend": "native",
  "model": "<reviewer-model>",
  "executor_model": "<executor-model>",
  "executor_model_source": "agent-session-event",
  "executor_family": "vendor-a",
  "reported_reviewer_model": "<reviewer-model>",
  "reviewer_model_source": "agent-session-event",
  "reviewer_family": "vendor-b",
  "family_relation": "different",
  "independence_verified": true,
  "native_evidence_id": "ne_0123456789abcdef0123456789abcdef",
  "native_evidence_path": "/project/review-stage/NATIVE_run_20260715_a1b2c3d4_ROUND_1_REVIEW.evidence.json",
  "prompt": "<full nonce-bound native task prompt>"
}
```

For CLI backend (`--reviewer: cli`):
```json
{
  "call_number": 1,
  "purpose": "round-1-review",
  "timestamp": "2026-04-15T14:31:00+08:00",
  "tool": "<reviewer-cli> --agent",
  "backend": "cli",
  "model": "<reviewer-model>",
  "effort": "xhigh",
  "effort_unpinned": false,
  "reviewer_profile": "profile-reviewer",
  "requested_reviewer_model": "<reviewer-model>",
  "reported_reviewer_model": null,
  "executor_model": "<executor-model>",
  "executor_model_source": "caller-declared",
  "executor_family": "vendor-a",
  "reviewer_model_source": "requested",
  "reviewer_family": "vendor-b",
  "family_relation": "different",
  "independence_verified": "unverified",
  "files_referenced": ["paper/sections/3_method.tex", "results/table1.csv"],
  "prompt": "<full prompt text>"
}
```

Fields:
- `tool`: the tool name used (invocation-specific: reviewer bridge, sub-agent
  task, or CLI reviewer invocation).
- `backend`: the logical backend (`native`, `cli`, `manual`, or any
  caller-supplied identifier).
- `effort_unpinned`: applies only to compatibility `cli`; native
  complementary dispatch does not accept a model/effort pin.
- `reviewer_profile`: custom profile for compatibility `cli`; a descriptive
  reviewer label may be used for native traces; `null` otherwise.
- `requested_reviewer_model`: the model parsed from profile frontmatter and repeated through subprocess `--model`; `null` when unavailable.
- `reported_reviewer_model`: the model the tool reports actually using (for example, captured service response-model telemetry); `null` when unavailable.
- `executor_model`: native session-event value, or from `--executor-model` on
  legacy/non-native paths; `null` if unavailable.
- `executor_model_source`: `agent-session-event`, `caller-declared`, or
  `unavailable`.
- `executor_family`: derived from `executor_model`.
- `reviewer_model_source`: `backend-reported`, `requested`, or `unavailable`.
- `reviewer_family`: derived by the helper from the reported/requested/actual reviewer model, never trusted from the caller.
- `family_relation`: string-derived relation (`different` / `same` / `unknown`).
- `independence_verified`: `true` only for validated native cross-family
  evidence; `false` for known same-family; `"unverified"` for advisory pairs.
- `native_evidence_id` / `native_evidence_path`: bind a native trace to the
  revalidated session-event artifact; `null` otherwise.

### `NNN-<purpose>.response.md`
The reviewer's full response, verbatim. No truncation, no summarization.

### `NNN-<purpose>.meta.json`
```json
{
  "call_number": 1,
  "purpose": "round-1-review",
  "timestamp": "2026-04-15T14:33:00+08:00",
  "thread_id": "019d8fe0-b25d-...",
  "model": "<reviewer-model>",
  "model_family": "vendor-b",
  "executor_model": null,
  "executor_model_source": "unavailable",
  "executor_family": "unknown",
  "reviewer_model_source": "requested",
  "family_relation": "unknown",
  "independence_verified": "unverified",
  "reviewer_profile": null,
  "duration_ms": 142000,
  "status": "ok"
}
```

For CLI backend:
```json
{
  "call_number": 1,
  "purpose": "round-1-review",
  "timestamp": "2026-04-15T14:33:00+08:00",
  "thread_id": null,
  "model": "<reviewer-model>",
  "model_family": "vendor-b",
  "effort": "xhigh",
  "effort_unpinned": false,
  "executor_model": "<executor-model>",
  "executor_model_source": "caller-declared",
  "executor_family": "vendor-a",
  "requested_reviewer_model": "<reviewer-model>",
  "reported_reviewer_model": null,
  "reviewer_model_source": "requested",
  "family_relation": "different",
  "independence_verified": "unverified",
  "reviewer_profile": "profile-reviewer",
  "duration_ms": 142000,
  "status": "ok"
}
```

Fields new per this fix:
- `model_family`: a caller-supplied model-family label or `unknown` — derived from the model that actually ran.
- `effort_unpinned`: whether a compatibility CLI subprocess lacked the
  required explicit `xhigh` pin; it does not apply to native dispatch.
- `executor_model` / `executor_model_source`: native calls record the actual
  session event model/source; compatibility routing records `caller-declared`.
- `executor_family`: derived from `executor_model`; `unknown` if not known.
- `requested_reviewer_model`: the profile model also passed through subprocess `--model`; `null` when not available.
- `reported_reviewer_model` / `reviewer_model_source`: backend output when available, otherwise the requested model and source.
- `family_relation`: the model-string relation, separate from evidence assurance.
- `independence_verified`: never `true` solely because caller-declared and requested model strings differ; use `"unverified"` in that case.
- `reviewer_profile`: for compatibility `cli`, the custom agent profile;
  native may record a descriptive reviewer label; `null` for other backends.
- `native_evidence_id` / `native_evidence_path`: present only on validated
  `native` traces.
- `memory_hash`: SHA-256 of `review-stage/REVIEWER_MEMORY.md` at trace time; `null` when no memory file exists.

## Configuration

Tracing respects three modes, set via inline parameter `--- trace: off | meta | full`:
- **`full`** (default): save full prompt + full response
- **`meta`**: save metadata only (no prompt/response text), useful for sensitive projects
- **`off`**: disable tracing entirely

## Integration with events.jsonl

After writing a trace, append a compact summary event to `<workspace>/traces/meta/events.jsonl`:

```json
{"event":"review_trace","skill":"auto-review-loop","purpose":"round-1-review","thread_id":null,"trace_path":"traces/auto-review-loop/2026-04-15_run01/","backend":"native","tool":"task(agent_type=<native-reviewer>)","executor_model":"<executor-model>","executor_model_source":"agent-session-event","executor_family":"vendor-a","reviewer_model_source":"agent-session-event","reviewer_family":"vendor-b","family_relation":"different","independence_verified":true,"native_evidence_id":"ne_0123456789abcdef0123456789abcdef","native_evidence_path":"/project/review-stage/NATIVE_run_20260715_a1b2c3d4_ROUND_1_REVIEW.evidence.json","status":"ok"}
```

This allows `/meta-optimize` to discover traces without reading the full trace files.

## Debugging With Traces

Traces are not only audit evidence — they are the **first place to look when a
verdict is surprising**: a score regresses round-to-round, two reviewer backends
disagree, or `/result-to-claim` contradicts an earlier claim. Before re-invoking
the reviewer for "a better answer", read the raw transcript and find the moment
its judgment actually changed:

```bash
# Diff the raw response bodies across the two calls in question
skill=auto-review-loop run=2026-04-15_run01
diff "traces/$skill/$run/002-round-2.response.md" \
     "traces/$skill/$run/003-round-3.response.md"

# Grep for the sentence where the assessment turned
grep -En 'however|but|concern|missing|cannot' \
     "traces/$skill/$run/003-round-3.response.md"
```

The paragraph where the assessment changed **is** the causal explanation for the
divergence — cite it, don't guess. Re-running the reviewer without reading the
trace is tuning by vibe: you get a new opinion, not an explanation.

This is the same muscle this toolbox already applies to code failures (the "**Read the
error** — parse traceback, stderr, and log files" step in `/experiment-bridge`'s
auto-debug sequence, and a rescue workflow reading tracebacks before a retry) —
applied to saved AI-judgment transcripts instead of stderr. The trace is written
in English and most of it is the reviewer talking to itself; the discipline is
identical: read the primary artifact first, then act on the exact divergence
point rather than re-rolling the dice.

Practical triggers:

| Surprise | Trace move |
|---|---|
| Score dropped after a "fix" round | diff the two rounds' `.response.md`; find which criterion flipped |
| Two backends disagree (native vs cli/manual) | grep both responses for the SAME artifact path; compare what each actually read |
| Reviewer "forgot" an earlier concern | grep prior rounds for the concern keyword; if present-then-absent, cite it in the next prompt instead of restating from memory |
| Verdict contradicts a deterministic checker | read the request `.md` — was the checker's output actually in the files the reviewer was pointed at? |

## Privacy

- `traces/` should be in the workspace `.gitignore` — traces are project-local, never committed
- Traces may contain sensitive research content; treat them as confidential
- Use `--- trace: off` for projects with strict confidentiality requirements
