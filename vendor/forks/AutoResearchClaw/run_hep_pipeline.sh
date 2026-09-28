#!/bin/bash
# End-to-end HEP physics pipeline run script
# Stages 1-23: from topic scoping to final paper

set -e

# ── API credentials ──────────────────────────────────────────────
# Fill these in (or export them in your shell before running). Never commit
# real keys to version control.
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-REPLACE-ME}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o}"
export OPENAI_SMALL_FAST_MODEL="${OPENAI_SMALL_FAST_MODEL:-gpt-4o-mini}"

# ── Anthropic (for claude CLI subprocess — ColliderAgent) ────────
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-REPLACE-ME}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-4-6}"
export ANTHROPIC_SMALL_FAST_MODEL="${ANTHROPIC_SMALL_FAST_MODEL:-claude-sonnet-4-6}"

# Magnus local backend (already configured in ~/.magnus/config.json)
# Frontend: localhost:3011  Backend API: localhost:8017

cd "$(dirname "$0")"

echo "============================================================"
echo "ResearchClaw HEP Physics Pipeline"
echo "Topic: Z prime boson exclusion limits from Drell-Yan dilepton search"
echo "Mode: collider_agent (stages 1-23, full-auto)"
echo "Started: $(date)"
echo "============================================================"

python -m researchclaw run \
  --config config.yaml \
  --profile hep_ph \
  --auto-approve \
  --skip-noncritical-stage \
  2>&1

echo ""
echo "Pipeline finished at: $(date)"
