# vibe-think Protocol

> **What this protocol does -- plain language overview**
>
> This is the planning and analysis protocol. It governs how VibeSkills clarifies
> requirements, designs architecture, and writes execution plans -- primarily during
> Stages 2-4 of the runtime.
>
> You do not need to read this to use VibeSkills. It is reference material for those
> who want to understand how the system thinks before it acts.
>
> **Key terms used below:**
> - **Phase A / Phase B**: Internal protocol phases. Phase A = pre-execution analysis (classify the task); Phase B = planning and design execution (write the plan).
> - **Proxy-goal drift**: When the system optimizes a visible metric instead of the actual goal. Planning is the cheapest place to prevent this.
> - **GSD-Lite Preflight Hook**: An optional planning enhancement that adds a brownfield context snapshot and assumption verification step before writing the plan.
> - **Brownfield context**: An existing codebase that already has its own architecture and conventions -- as opposed to a blank-slate new project.
> - **Dialectic mode**: A structured multi-perspective design analysis: two groups of agents argue different viewpoints, then a coordinator synthesizes the best ideas from both.


Pre-routing analysis and post-routing planning/design/research protocol.

## Governed Runtime Position

This protocol is not a standalone user entrypoint.
It is the planning and analysis surface used inside the governed `vibe` runtime defined by `protocols/runtime.md`.

The user-facing runtime path remains fixed:

1. `skeleton_check`
2. `deep_interview`
3. `requirement_doc`
4. `xl_plan`
5. `plan_execute`
6. `phase_cleanup`

`think.md` primarily owns stages 2 through 4:

- `deep_interview`: clarify intent or infer assumptions
- `requirement_doc`: freeze the requirement contract
- `xl_plan`: generate the executable plan

`M`, `L`, and `XL` are still one runtime strategy surface rather than separate
entry branches. In `interactive_governed` runs, L/XL selection is also a
user-visible workflow-level confirmation before requirement and plan freeze.

## Runtime Mode Behavior

### `interactive_governed`

The governed planning mode.

- ask high-value questions when ambiguity blocks planning quality
- require a user-visible requirement freeze before execution
- allow approval pauses before execution begins

This protocol must leave execution with a frozen requirement artifact and a plan artifact.

## Anti-Drift Planning Guardrails

Planning is the first place where proxy-goal drift can be prevented cheaply.

When anti-drift policy is active:
- freeze the primary objective before discussing implementation convenience,
- name non-objective proxy signals explicitly,
- keep validation material in a validation role rather than letting examples become the requirement,
- declare the intended scope and completion state honestly,
- preserve bounded specialization as a valid outcome when generalization is not yet proven.

This planning guidance is advisory support for better requirement quality.
It does not create a hidden hard gate beyond the already-approved requirement and plan contracts.

## Closure-First Preflight (2 Probes + 1 Verify)

Even in planning/research, the primary failure mode is **stalling** (dead-air).
So we run a minimal closed loop early: probe context → locate evidence → verify assumptions.

### Contract (No Code Writing)
Within the first 3 actions, do:
1. **Probe #1 (glob, fast):** inspect repo shape / available docs.
   - Example: `Get-ChildItem -Force | Select-Object Name`
2. **Probe #2 (rg, targeted):** search for the most relevant keyword(s) and existing plans/specs.
   - Example: `rg -n -F -e '<keyword>' docs .`
3. **Verify #1:** before final recommendations, validate at least 1 key assumption against an artifact:
   - Repo evidence (README/config/code), or
   - 2 independent external sources for factual claims (research).

### Router Hints (When Available)
If VCO router output includes:
- `closure_advice`: follow `closure_advice.contract.probes` + `closure_advice.contract.verify` (prefer verbatim).
- `exploration_advice`: use `exploration_advice.recommended_execution_mode` to pace analysis, but **still do probes early**.

## Scope

### Phase A: Pre-Execution Analysis (L grade, before implementation)

Activated when L-grade task needs structured analysis before execution:
- Task could be classified as multiple types → clarify via analysis
- User explicitly asks to "analyze", "think through", or "evaluate"
- Compound task requiring decomposition into phases

### Phase B: Planning & Design Execution (L grade)

Activated for L-grade planning, design, and research tasks:
- Requirements analysis and discovery
- Architecture and system design
- Research and investigation
- Option evaluation and comparison

## Phase A: Pre-Execution Analysis

### A1: Problem Framing
Tool: None (Claude native reasoning)
- What exactly is being asked? What are the constraints?
- Is this a single task or compound task?

### A2: Structured Analysis (by estimated grade)

| Estimated Grade | Native Vibe Method | Stage |
|----------------|--------------------|-------|
| M | concise risk and objective check | `deep_interview` |
| L | structured options, constraints, and acceptance criteria | `deep_interview` -> `requirement_doc` |
| XL | Socratic clarification plus explicit tradeoff comparison | `deep_interview` -> `xl_plan` |
| Any code-heavy case | repository evidence probe before plan text | `skeleton_check` -> `xl_plan` |

### A3: Classification Decision
Based on analysis output, determine:
- Final grade (may differ from initial estimate)
- Task type (plan/code/review/debug/research)
- Compound task? -> decompose (see below)
- Runtime mode fit:
  - `interactive_governed` for governed planning and execution

### Compound Task Decomposition

| Grade | Native Vibe Method | Stage |
|-------|--------------------|-------|
| M | short serial checklist | `xl_plan` |
| L | phase plan with owners, verification, and rollback notes | `xl_plan` |
| XL | wave-sequential plan with bounded parallel windows | `xl_plan` -> `plan_execute` |

Output: ordered phases, each with protocol, quality gate, and handoff context.

### Example: "Design and implement user auth"

```
Phase 1: Requirements (vibe-think)
  Native method: vibe.deep_interview
  Gate: Requirements document approved by user

Phase 2: Architecture (vibe-think)
  Tool: sc:design
  Gate: Architecture diagram approved

Phase 3: Implementation (vibe-do)
  Tool: native serial execution lane (bounded delegated units only when planned)
  Gate: All tests pass, code reviewed

Phase 4: Security Review (vibe-review)
  Tool: everything-claude-code:security-reviewer
  Gate: No CRITICAL findings
```

## Phase B: Planning & Design Execution (L Grade)

### B1: Requirements Discovery
Native method: `vibe.deep_interview`
- ask one high-value clarification when ambiguity blocks requirement quality
- compare options before choosing an implementation direction
- for L/XL-capable work, first explain L versus XL in plain language and stop for the user's level choice
- after specialist skills are recommended, ask "我将会在接下来的工作中使用这些 skills，你觉得 OK 吗？" and stop before those skills become execution obligations
- output clarified requirements, assumptions, acceptance criteria, and user-visible tradeoffs

Governed runtime requirement:
- persist an intent contract that can be turned into a file under `docs/requirements/`
- do not merge workflow-level confirmation, skill-use confirmation, and requirement approval into one all-at-once prompt

### B2: Architecture Design (if needed)
Tool: sc:design
- Cognitive personas (architect, security, frontend, backend)
- Output: Architecture diagrams, component design, data flow

### B2 Self-Check (All Design Tasks)

After generating initial design through `vibe.deep_interview` or `sc:design`:
1. List 3 ways this design could fail in production
2. If any failure mode suggests a fundamentally different approach → generate alternative
3. If alternative is equally viable → present both to user with trade-off comparison
4. If no viable alternative → proceed with original + document failure modes as risks

Note: If user explicitly requested dialectic think-tank mode, skip B2 Self-Check and route to
team.md Dialectic Mode instead.

### B3: Plan Documentation
Native method: `vibe.xl_plan`
- Generates plan at docs/plans/YYYY-MM-DD-<topic>.md
- Output: Actionable implementation plan with phases

Minimum governed-runtime contents:
- internal grade decision
- confirmed user-facing workflow level
- approved selected skills, clearly separated from final material-use evidence
- wave or batch structure
- verification commands
- rollback rules
- phase cleanup expectations

### B4: Deep Research (if needed)
Tool: claude-code-settings:deep-research
- Multi-agent parallel research workflow
- Output: Research findings with sources

### B5: GSD-Lite Preflight Hook (Optional, L/XL Planning Only)
Policy source: `config/gsd-overlay.json`

Run this hook only when all conditions are met:
1. `enabled=true` and `mode != off`
2. Current task type is `planning`
3. Current grade is in `grade_allow` (default: `L`, `XL`)

Hard boundaries:
- Post-route governance only. Never re-run grade/task/pack routing.
- Do not introduce `/gsd:*` command flow.
- Do not create a second source-of-truth state tree.

Hook steps:
1. **Brownfield context snapshot** (when `brownfield_context.enabled=true`)
   - Build or refresh a light snapshot under `docs/vco-context/`:
     - `STACK.md`
     - `ARCHITECTURE.md`
     - `CONVENTIONS.md`
     - `CONCERNS.md`
   - If snapshot is missing or stale, do not silently continue. Mark the run as degraded, emit a hazard alert, and keep the result non-authoritative until the snapshot is repaired.
2. **Assumption preflight**
   - Produce a concise assumptions list before writing the final plan.
   - Persist assumptions to the active planning artifact (or `assumptions.md` when configured).
3. **Confirm policy by mode**
   - `shadow`: record advice only, no blocking.
   - `soft`: require confirm only for grades in `assumption_gate.confirm_required_for`.
   - `strict`: require confirm for all in-scope grades.
4. **Handoff**
   - Carry assumptions + brownfield context into B3 output.

On hook failure, do not silently downgrade. Follow `references/fallback-chains.md` only as an explicit degraded path, emit a standalone hazard alert, and record that the resulting planning flow is non-authoritative until the primary path is restored.

## Research Mode
When task is purely research (no implementation):
1. Skip B1 unless scope is unclear
2. Go directly to B4 (deep-research)
3. Optionally use sc:research for web research
4. Store findings in ruflo memory (or state_store if unavailable)

## Conflict Avoidance
- Do NOT write code during this protocol (respect HARD-GATE)
- Do not create a second requirement or plan surface outside the active `vibe` session
- deep analysis, option comparison, and plan writing are native methods inside `deep_interview` and `xl_plan`
- Analysis (Phase A) completes BEFORE implementation begins, not in parallel with execution
- superpowers planning/process skills remain discipline-only and must not create a second requirement or plan truth once VCO artifacts are frozen
- any planning aid that is not the governed runtime must feed the canonical `docs/requirements/` and `docs/plans/` surfaces rather than invent parallel artifacts

## Transition to Implementation
After design is approved:
1. L grade: Switch to vibe-do serial native execution (sequence-first; bounded delegation only when explicitly planned)
2. XL grade: Switch to vibe-team protocol (wave-sequential execution with step-level bounded parallel units + optional ruflo collaboration)
3. Always carry the plan document forward as context
4. Execution must hand off into runtime stage 5 `plan_execute`, not bypass directly into ad-hoc coding
5. Process-discipline helpers may influence how work is executed, but VCO remains the only governed runtime skeleton and artifact authority
