#!/usr/bin/env bash
# Unified rc_copilot (autoclaw + auto-derived HITL) runner for ARC-Bench T01-T25.
#
# Pre-requisite: rc_full results must exist for at least each target topic so
# `hitl_suggestor.py` can derive interventions; the script auto-runs the
# suggestor for any topic missing baseline/interventions/<Txx>.json.
#
# Usage:
#   bash scripts/run_rc_copilot.sh                       # all 25 topics
#   bash scripts/run_rc_copilot.sh --topics "T01 T02"    # subset

set -u

: "${OPENAI_BASE_URL:?Set OPENAI_BASE_URL before running}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before running}"

export OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.3-codex}"
export OPENAI_SMALL_FAST_MODEL="${OPENAI_SMALL_FAST_MODEL:-gpt-4o}"
export OPENAI_WIRE_API="${OPENAI_WIRE_API:-responses}"
export ARC_JUDGE_MODEL="${ARC_JUDGE_MODEL:-gpt-5.3-codex}"
export ARC_WIRE_API="${ARC_WIRE_API:-responses}"

TOPICS_DEFAULT="T01 T02 T03 T04 T05 T06 T07 T08 T09 T10 T11 T12 T13 T14 T15 T16 T17 T18 T19 T20 T21 T22 T23 T24 T25"
TOPICS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --topics) TOPICS="$2"; shift 2 ;;
        *)        echo "unknown arg: $1"; exit 2 ;;
    esac
done
[ -z "$TOPICS" ] && TOPICS="$TOPICS_DEFAULT"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AB_ROOT="$REPO_ROOT/experiments/arc_bench"
LOG_ROOT="$AB_ROOT/results/legacy/log/rc_copilot"
INTERVENTIONS_DIR="$AB_ROOT/baseline/interventions"
mkdir -p "$LOG_ROOT"
cd "$REPO_ROOT"

echo "=== ARC-Bench rc_copilot sweep ==="
echo "started_at: $(date -Iseconds)"
echo "topics:     $TOPICS"
echo ""

for tid in $TOPICS; do
    if ls "$AB_ROOT/results/rc_copilot/$tid"/*/judge_result.json >/dev/null 2>&1; then
        echo "[$tid] already complete — skipping"
        continue
    fi

    # Ensure intervention file exists; otherwise derive from rc_full
    if [ ! -f "$INTERVENTIONS_DIR/$tid.json" ]; then
        echo "[$tid] deriving HITL intervention from rc_full..."
        python -u "$AB_ROOT/scripts/hitl_suggestor.py" --topic "$tid" \
            >"$LOG_ROOT/${tid}-suggest.log" 2>&1 || \
            { echo "[$tid] suggestor failed"; continue; }
    fi

    ts=$(date -u +%Y%m%d-%H%M%S)
    log_path="$LOG_ROOT/${tid}-${ts}.log"
    echo "[$tid] START at $(date -Iseconds)  log=$log_path"
    python -u "$AB_ROOT/scripts/run_bench.py" --mode rc_copilot --topic "$tid" \
        >"$log_path" 2>&1
    echo "[$tid] DONE rc=$?"
done

echo ""
echo "=== rc_copilot sweep DONE  finished_at=$(date -Iseconds) ==="
