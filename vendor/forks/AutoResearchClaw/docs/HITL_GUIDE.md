# Human-in-the-Loop Co-Pilot Guide

> **AutoResearchClaw v0.4.0** transforms the pipeline from purely autonomous to a human-AI collaborative research engine. This guide covers everything you need to know.

---

## Table of Contents

1. [Why Co-Pilot?](#1-why-co-pilot)
2. [Quick Start](#2-quick-start)
3. [Intervention Modes](#3-intervention-modes)
4. [The Co-Pilot Workflow](#4-the-co-pilot-workflow)
5. [CLI Commands](#5-cli-commands)
6. [Stage-by-Stage Intervention Guide](#6-stage-by-stage-intervention-guide)
7. [Workshops](#7-workshops)
8. [Detached Operation](#8-detached-operation)
9. [Safety & Guardrails](#9-safety--guardrails)
10. [Intelligence Layer](#10-intelligence-layer)
11. [Pipeline Branching](#11-pipeline-branching)
12. [Adapters (CLI / WebSocket / MCP)](#12-adapters)
13. [Configuration Reference](#13-configuration-reference)
14. [FAQ](#14-faq)

---

## 1. Why Co-Pilot?

Fully autonomous research pipelines produce papers fast, but testing reveals consistent quality gaps:

| Problem | Root Cause |
|---------|-----------|
| Weak research ideas | AI lacks taste for what's truly novel and impactful |
| Missing baselines | AI doesn't know which comparisons reviewers expect |
| Fragile experiment code | No human sanity check before execution |
| Thin analysis | AI draws superficial conclusions from results |
| Generic paper writing | AI produces correct-but-bland academic prose |

The HITL Co-Pilot system solves this by letting you **intervene exactly where your expertise matters most**, while the AI handles the heavy lifting everywhere else.

**The result**: papers that combine AI speed with human judgment.

---

## 2. Quick Start

### Option A: Co-Pilot Mode (Recommended)

```bash
researchclaw run --topic "Your research idea" --mode co-pilot
```

The pipeline will run automatically and pause at key decision points for your input. At each pause, you'll see an interactive prompt with available actions.

### Option B: Express Mode (Minimal Interruption)

```bash
researchclaw run --topic "Your research idea" --mode express
```

Only pauses at 3 critical gates: hypothesis approval (Stage 8), experiment design (Stage 9), and final quality check (Stage 20).

### Option C: Full Auto (Original Behavior)

```bash
researchclaw run --topic "Your research idea" --auto-approve
```

No human intervention. Identical to pre-v0.4.0 behavior.

---

## 3. Intervention Modes

| Mode | Flag | Pauses At | Best For |
|------|------|-----------|----------|
| **Full Auto** | `--auto-approve` | Never | Quick exploration, low-stakes experiments |
| **Gate Only** | `--mode gate-only` | 3 gate stages (5, 9, 20) | Light oversight |
| **Checkpoint** | `--mode checkpoint` | End of each phase (8 points) | Phase-level review |
| **Co-Pilot** | `--mode co-pilot` | Critical stages + SmartPause triggers | **Recommended for production** |
| **Step-by-Step** | `--mode step-by-step` | After every stage (23 pauses) | Learning the pipeline |
| **Express** | `--mode express` | 3 most critical gates only | Experienced users |
| **Custom** | `--mode custom` | User-defined per-stage policies | Advanced configuration |

### How to Choose

- **First time using the pipeline?** Start with `step-by-step` to understand each stage.
- **Publishing a real paper?** Use `co-pilot` for the best quality.
- **Running overnight?** Use `gate-only` or `express` — fewer interruptions.
- **Batch processing many topics?** Use `full-auto`.

---

## 4. The Co-Pilot Workflow

When the pipeline pauses, you'll see an interactive panel:

```
──────────────────────────────────────────────────────────
  HITL | Stage 08: HYPOTHESIS_GEN
  Post-stage review
──────────────────────────────────────────────────────────

  Stage 8 (HYPOTHESIS_GEN) — done

  Hypotheses generated. This is a CRITICAL decision point —
  review each hypothesis for novelty, feasibility, and significance.

  Outputs:
    hypotheses.md (1,247 bytes)
      → ## Hypothesis 1: Quantum gate noise as structured regularization
    novelty_report.json (892 bytes)

  Novelty score: 0.72 (moderate)

  Available actions:
    [a] Approve and continue
    [r] Reject and rollback
    [e] Edit stage output
    [c] Start collaborative chat
    [i] Inject guidance / direction
    [s] Skip this stage
    [q] Abort pipeline
    [v] View full stage output

Action >
```

### Available Actions at Every Pause

| Key | Action | What Happens |
|-----|--------|-------------|
| `a` | **Approve** | Accept the output and continue to the next stage |
| `r` | **Reject** | Reject the output; pipeline rolls back to an earlier stage |
| `e` | **Edit** | Opens the output file in your `$EDITOR` (vim, nano, VS Code, etc.) |
| `c` | **Collaborate** | Start a multi-turn chat with the AI to refine the output together |
| `i` | **Inject Guidance** | Provide direction that will be incorporated into subsequent stages |
| `s` | **Skip** | Skip this stage entirely (use with caution) |
| `b` | **Rollback** | Jump back to a specific earlier stage |
| `q` | **Abort** | Stop the pipeline entirely |
| `v` | **View** | Display the full contents of output files |

---

## 5. CLI Commands

### Starting a Run

```bash
# Co-Pilot mode
researchclaw run --topic "Quantum noise as neural network regularization" --mode co-pilot

# With explicit config
researchclaw run --config config.arc.yaml --topic "..." --mode co-pilot

# Resume a previous run in co-pilot mode
researchclaw run --config config.arc.yaml --resume --mode co-pilot
```

### Detached Interaction

These commands let you interact with a paused pipeline from a separate terminal:

```bash
# Check status
researchclaw status artifacts/rc-2026-0328-abc123

# Attach interactively (full TUI)
researchclaw attach artifacts/rc-2026-0328-abc123

# Quick approve (non-interactive)
researchclaw approve artifacts/rc-2026-0328-abc123 --message "Looks good"

# Quick reject
researchclaw reject artifacts/rc-2026-0328-abc123 --reason "Missing ResNet baseline"

# Inject guidance for a specific stage
researchclaw guide artifacts/rc-2026-0328-abc123 --stage 9 --message "Add Dropout as baseline"
```

---

## 6. Stage-by-Stage Intervention Guide

### Where Your Input Matters Most

| Stage | Name | Co-Pilot Behavior | Your Role |
|-------|------|-------------------|-----------|
| 1-2 | Scoping | Pause after | Confirm research direction and scope |
| 3 | Search Strategy | Pause after | Add missing search terms or sources |
| 5 | Literature Screen | **Approval required** | Verify important papers aren't filtered out |
| 7 | Synthesis | Pause after | Check if the identified gaps match your understanding |
| **8** | **Hypothesis Gen** | **Collaboration** | **Review, discuss, and refine the core research idea** |
| **9** | **Experiment Design** | **Collaboration + Approval** | **Verify baselines, benchmarks, metrics, ablations** |
| 10 | Code Generation | Pause after | Spot-check code quality |
| 12 | Experiment Run | Stream output | Monitor training metrics in real-time |
| 13 | Iterative Refine | Pause after | Decide if refinement should continue |
| **15** | **Research Decision** | **Approval required** | **Choose PROCEED, PIVOT, or REFINE** |
| 16 | Paper Outline | Pause after | Adjust section structure |
| **17** | **Paper Draft** | **Collaboration** | **Co-write key sections** |
| 18 | Peer Review | Pause after | Prioritize which review comments to address |
| **20** | **Quality Gate** | **Approval required** | **Final publication decision** |
| 23 | Citation Verify | Pause after | Review flagged citations |

### Guidance Injection

You can inject guidance for **any stage at any time**, even before it runs:

```bash
researchclaw guide artifacts/rc-xxx --stage 17 --message "Emphasize the theoretical contribution in the Introduction. Keep the Method section concise."
```

Guidance is automatically included in the LLM's context when that stage executes.

---

## 7. Workshops

Workshops are specialized collaboration tools for the most critical stages.

### Idea Workshop (Stage 7-8)

When you enter collaboration mode at Stage 8, the Idea Workshop activates:

```
You > c  (start collaboration)

AI > I generated 3 candidate hypotheses. Here's my evaluation:
     1. "Quantum gate noise as structured regularization" — Novelty: 8/10, Feasibility: 6/10
     2. "Entanglement-based feature selection" — Novelty: 7/10, Feasibility: 4/10
     3. "Quantum sampling for data augmentation" — Novelty: 5/10, Feasibility: 8/10

     Which direction interests you most?

You > Hypothesis 1 is the most promising, but we need to be more specific.
     The noise should be modeled as a stochastic regularizer, and we need
     to compare against Dropout, Label Smoothing, and MixUp.

AI > Updated hypothesis:
     "We theoretically characterize quantum gate noise as a structured
     stochastic regularizer and empirically demonstrate it outperforms
     Dropout, Label Smoothing, and MixUp on small-sample classification."

     Baselines updated: + Dropout, + Label Smoothing, + MixUp, + CutMix

     Shall I proceed with this direction?

You > Yes, approve.
```

The workshop automatically:
- Saves your refined hypothesis to `hypotheses.md`
- Records the conversation in `hitl/chat_stage_08.jsonl`
- Persists candidate evaluations in `hitl/idea_workshop.json`

### Baseline Navigator (Stage 9)

The Baseline Navigator helps you build a rigorous experiment design:

```
AI > Here are the suggested baselines:
     [AI] ResNet-50 (standard image classification baseline)
     [AI] ViT-B/16 (transformer baseline)
     [AI] Dropout (regularization baseline)

     Experiment Design Checklist:
     [+] Baselines: 3
     [ ] Benchmarks: CIFAR-10, CIFAR-100
     [ ] Metrics: accuracy, F1

You > Add Label Smoothing and MixUp as baselines. Also add STL-10.

AI > Updated. Current checklist:
     [+] Baselines: 5 (ResNet-50, ViT-B/16, Dropout, Label Smoothing, MixUp)
     [+] Benchmarks: 3 (CIFAR-10, CIFAR-100, STL-10)
     [+] Metrics: accuracy, F1

     Review questions:
     [ ] Are all standard baselines for this domain included? ✓
     [ ] Is there at least one ablation planned? — suggest: "noise magnitude sweep"
```

### Paper Co-Writer (Stage 16-17)

The Paper Co-Writer supports three workflows:

1. **AI-first** (default): AI writes the draft, you edit and refine
2. **Human-first**: You write key paragraphs, AI expands and polishes
3. **Interleaved**: You alternate — you write the Method, AI writes Related Work

```
AI > Paper draft completed (5,200 words, 7 sections).
     Which sections would you like to review or co-edit?

You > The Introduction is too generic. Let me rewrite the first paragraph.

AI > Opening your editor... (saves backup to hitl/snapshots/)

     [Editor opens with Introduction section]

You > [Saves edited file]

AI > Your edits look great. I'll polish the transitions and ensure
     the notation is consistent with the Method section.

     Updated Introduction: 420 words → 380 words (tighter, more specific).
     Change summary: +3 added, -5 deleted, ~8 changed, 22 unchanged
```

---

## 8. Detached Operation

Research runs can take hours. You don't need to sit and watch.

### How It Works

1. Pipeline pauses → writes `hitl/waiting.json`
2. Pipeline enters file-polling mode (checks every 2 seconds for `response.json`)
3. You respond whenever you're ready via `attach`, `approve`, or web dashboard
4. Pipeline picks up your response and resumes

### Scenario: Overnight Run

```bash
# Start the run at 6 PM
researchclaw run --topic "..." --mode co-pilot &

# Pipeline runs Stages 1-7, pauses at Stage 8...
# You go home

# Next morning, check status
researchclaw status artifacts/rc-2026-xxx
# Output: "WAITING for input at Stage 8 — HYPOTHESIS_GEN (since 18:42)"

# Review and approve
researchclaw attach artifacts/rc-2026-xxx
# Interactive review → approve → pipeline resumes
```

### Timeout Behavior

By default, the pipeline waits 24 hours for a response. You can configure this:

```yaml
hitl:
  timeouts:
    default_human_timeout_sec: 86400   # 24h (default)
    auto_proceed_on_timeout: false     # true = auto-approve after timeout
```

---

## 9. Safety & Guardrails

### Cost Budget

Set a spending limit to prevent runaway API costs:

```yaml
hitl:
  cost_budget_usd: 50.0   # Pipeline pauses at 50%, 80%, and 100% of budget
```

When a threshold is breached, the pipeline pauses with a cost summary:
```
Cost budget alert: Cost: $42.50 / $50.00 [████████████████░░░░] 85%
```

### Claim Verification

The Claim Verifier automatically checks AI-generated text against your collected literature:

- **Citation claims**: Are cited papers in your shortlist? Or fabricated?
- **Numerical claims**: Do reported numbers match actual experiment data?
- **Factual claims**: Are "it has been shown that..." statements grounded?

Unverified claims are flagged in the review summary, letting you decide what to keep.

### SHA256 Artifact Checksums

Every stage output gets a SHA256 manifest (`manifest.json`) for reproducibility. If an artifact is modified outside the pipeline, verification will detect it.

### Escalation Policy

For team/production use, configure tiered notification escalation:

```yaml
hitl:
  escalation:
    levels:
      - delay_sec: 0       # Immediate terminal notification
        channel: terminal
      - delay_sec: 1800    # After 30 min → Slack
        channel: slack
        message: "Pipeline needs attention"
      - delay_sec: 7200    # After 2h → email
        channel: email
      - delay_sec: 86400   # After 24h → auto-abort
        channel: terminal
        auto_action: abort
```

### Extensible Hooks

Run custom scripts before/after any stage:

```bash
# Create a hook script
cat > artifacts/rc-xxx/hooks/post_stage_10.sh << 'EOF'
#!/bin/sh
echo "Running linter on generated code..."
cd $RC_RUN_DIR/stage-10/experiment && python -m py_compile main.py
EOF
chmod +x artifacts/rc-xxx/hooks/post_stage_10.sh
```

Hooks receive environment variables: `RC_STAGE_NUM`, `RC_STAGE_NAME`, `RC_RUN_DIR`, `RC_HOOK_NAME`.

---

## 10. Intelligence Layer

### SmartPause

SmartPause goes beyond fixed gate stages. It dynamically decides whether to pause based on:

- **Quality score** (from PRM or heuristics): Low quality → pause for review
- **Stage criticality**: High-impact stages (hypotheses, experiment design) have lower thresholds
- **Historical rejection rate**: Stages you frequently reject get paused more often
- **Confidence**: When the AI is uncertain, it asks for help

You don't need to configure SmartPause — it works automatically in co-pilot mode.

### Intervention Learning (ALHF)

Every time you approve, reject, or edit, the system learns:

- Stages you always approve → future runs auto-approve them
- Stages you frequently reject → future runs pause more aggressively
- Your edit patterns → inform SmartPause thresholds

After 5+ runs, the system adapts to your review style.

### Quality Predictor

At any pause point, the system estimates the final paper quality based on current artifacts:

- Literature coverage (number and diversity of papers)
- Hypothesis specificity and falsifiability
- Experiment design completeness (baselines, ablations, metrics)
- Result strength (improvement over baselines)
- Draft quality (length, structure, section coverage)
- Citation integrity

Risk factors are highlighted so you know where to focus your attention.

---

## 11. Pipeline Branching

When you're unsure which research direction to pursue, branch the pipeline:

```
# At Stage 8, you see 3 promising hypotheses
Action > b  (branch)

# Fork to explore Hypothesis A
researchclaw branch create --run-dir artifacts/rc-xxx --name "quantum-noise" --stage 8

# Fork to explore Hypothesis B
researchclaw branch create --run-dir artifacts/rc-xxx --name "entanglement" --stage 8
```

Each branch gets its own copy of the pipeline state. Run them independently, then compare:

```bash
# Compare branches at Stage 14 (after experiments)
researchclaw branch compare --run-dir artifacts/rc-xxx --stage 14
```

```
Branch Comparison — Stage 14: RESULT_ANALYSIS

  main:
    artifacts: 3, quality: 0.72
    → Best accuracy: 78.3%

  quantum-noise:
    artifacts: 3, quality: 0.85
    → Best accuracy: 82.1%

  entanglement:
    artifacts: 2, quality: 0.61
    → Best accuracy: 74.5%
```

Merge the winner:

```bash
researchclaw branch merge --run-dir artifacts/rc-xxx --branch "quantum-noise" --from-stage 9
```

---

## 12. Adapters

The HITL system supports three interaction channels:

### CLI Adapter (Default)

Terminal-based interaction with ANSI colors, `$EDITOR` integration, and multi-line input. Works over SSH.

### WebSocket Adapter

For the web dashboard. Provides real-time updates via WebSocket:

```
Browser → WebSocket → ws_adapter.py → waiting.json / response.json → Pipeline
```

Message types: `get_status`, `approve`, `reject`, `edit`, `inject_guidance`, `chat_message`.

### MCP Adapter

External AI agents (Claude, OpenClaw) can interact with the HITL system via MCP tool calls:

- `hitl_get_status` — Check if the pipeline is waiting
- `hitl_approve_stage` — Approve the current gate
- `hitl_reject_stage` — Reject with reason
- `hitl_inject_guidance` — Provide direction
- `hitl_view_output` — Read stage artifacts

This enables **agent-in-the-loop** workflows where another AI system reviews and approves the pipeline's work.

---

## 13. Configuration Reference

```yaml
hitl:
  enabled: true                        # Master switch (default: false)
  mode: co-pilot                       # Intervention mode (see table above)
  cost_budget_usd: 0.0                 # Cost limit in USD (0 = unlimited)

  notifications:
    on_pause: true                     # Notify on pipeline pause
    on_quality_drop: true              # Notify on quality issues
    on_error: true                     # Notify on stage errors
    channels: ["terminal"]             # terminal | slack | email | webhook

  collaboration:
    llm_model: ""                      # Model for chat (default: primary model)
    max_chat_turns: 50                 # Max turns per collaboration session
    save_chat_history: true            # Persist chat logs to hitl/

  timeouts:
    default_human_timeout_sec: 86400   # Wait time for human input (24h)
    auto_proceed_on_timeout: false     # Auto-approve on timeout

  # Per-stage policies (for 'custom' mode)
  stage_policies:
    8:
      require_approval: true           # Must approve before continuing
      enable_collaboration: true       # Enable chat mode
      pause_before: false              # Pause before execution
      pause_after: true                # Pause after execution
      allow_edit_output: true          # Allow editing output files
      allow_inject_prompt: true        # Allow guidance injection
      stream_output: false             # Stream LLM output in real-time
      min_quality_score: 0.0           # Pause if quality below threshold
      max_auto_retries: 2              # Auto-retry count before pausing
      human_timeout_sec: 86400         # Per-stage timeout override
      auto_proceed_on_timeout: false   # Per-stage auto-proceed override
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `EDITOR` | Editor for file editing (default: nano on Unix, notepad on Windows) |
| `RESEARCHCLAW_SLACK_WEBHOOK` | Slack webhook URL for notifications |
| `RESEARCHCLAW_WEBHOOK_URL` | Generic webhook URL for notifications |

---

## 14. FAQ

### Does HITL slow down the pipeline?

Only at the stages where you choose to intervene. In co-pilot mode, ~15 of 23 stages run automatically. Typical human time is 30-60 minutes per run, compared to 2-4 hours of autonomous execution.

### Can I switch modes mid-run?

Not currently, but you can resume a paused run with a different mode:

```bash
researchclaw run --resume --output artifacts/rc-xxx --mode step-by-step
```

### What if I'm not sure what to do at a pause?

Press `v` to view the full output, then `c` to chat with the AI about it. The AI can explain what it did and why, and suggest what to focus on.

### Does HITL work with ACP/OpenClaw?

Yes. The MCP adapter exposes HITL tools that any ACP-compatible agent can call. OpenClaw can automatically review and approve gates.

### What data does HITL store?

Everything goes in `{run_dir}/hitl/`:
- `session.json` — Session state
- `interventions.jsonl` — All interventions (append log)
- `chat_stage_NN.jsonl` — Chat histories
- `snapshots/` — File backups before edits
- `guidance/` — Injected guidance per stage
- `notifications.jsonl` — Notification log

### Is it backward compatible?

Yes. Without `hitl.enabled: true` or `--mode`, the pipeline behaves identically to v0.3.x. The `--auto-approve` flag still works and takes precedence over HITL settings.
