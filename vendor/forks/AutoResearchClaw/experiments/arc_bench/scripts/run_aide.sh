#!/usr/bin/env bash
# Unified AIDE ML runner for ARC-Bench T01-T25.
#
# Default: parallel sweep with 8 workers, 40-min/topic budget.
# Override with --serial for one-at-a-time, --topics "T01 T02" for a subset.
#
# Usage:
#   bash scripts/run_aide.sh                       # all 25 topics, parallel
#   bash scripts/run_aide.sh --topics "T01 T02"    # subset
#   bash scripts/run_aide.sh --serial              # serial
#   bash scripts/run_aide.sh --jobs 4              # 4 parallel workers
#
# Required env: OPENAI_API_KEY, OPENAI_BASE_URL.

set -u

: "${OPENAI_BASE_URL:?Set OPENAI_BASE_URL before running}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before running}"

# Defaults
TOPICS_DEFAULT="T01 T02 T03 T04 T05 T06 T07 T08 T09 T10 T11 T12 T13 T14 T15 T16 T17 T18 T19 T20 T21 T22 T23 T24 T25"
TOPICS=""
JOBS=8
SERIAL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --topics)  TOPICS="$2"; shift 2 ;;
        --jobs)    JOBS="$2"; shift 2 ;;
        --serial)  SERIAL=1; shift ;;
        *)         echo "unknown arg: $1"; exit 2 ;;
    esac
done

[ -z "$TOPICS" ] && TOPICS="$TOPICS_DEFAULT"

# AIDE wiring on the OpenAI-compatible proxy
export ARC_AIDE_CODE_MODEL="${ARC_AIDE_CODE_MODEL:-gpt-5.3-codex}"
export ARC_AIDE_FEEDBACK_MODEL="${ARC_AIDE_FEEDBACK_MODEL:-gpt-4o}"
export ARC_AIDE_REPORT_MODEL="${ARC_AIDE_REPORT_MODEL:-gpt-4o}"
export ARC_AIDE_STEPS="${ARC_AIDE_STEPS:-10}"
export ARC_AIDE_NUM_DRAFTS="${ARC_AIDE_NUM_DRAFTS:-3}"
export ARC_BASELINE_BUDGET_SEC="${ARC_BASELINE_BUDGET_SEC:-2400}"
export ARC_JUDGE_MODEL="${ARC_JUDGE_MODEL:-gpt-5.3-codex}"
export ARC_WIRE_API="${ARC_WIRE_API:-responses}"

# Thread caps so joblib doesn't oversubscribe under parallel mode
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-8}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-8}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-8}"
export TOKENIZERS_PARALLELISM=false

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AB_ROOT="$REPO_ROOT/experiments/arc_bench"
LOG_ROOT="$AB_ROOT/results/legacy/log/aide_ml"
mkdir -p "$LOG_ROOT"
cd "$REPO_ROOT"

started_at=$(date -Iseconds)
echo "=== ARC-Bench AIDE ML sweep ==="
echo "started_at: $started_at"
echo "topics:     $TOPICS"
echo "mode:       $([ $SERIAL -eq 1 ] && echo serial || echo "parallel x$JOBS")"
echo "models:     code=$ARC_AIDE_CODE_MODEL  fb=$ARC_AIDE_FEEDBACK_MODEL  rep=$ARC_AIDE_REPORT_MODEL"
echo "budget_sec: $ARC_BASELINE_BUDGET_SEC"
echo ""

# Resume-safe: skip topics with judge_result.json
PENDING=()
for tid in $TOPICS; do
    if ls "$AB_ROOT/results/aide_ml/$tid"/*/judge_result.json >/dev/null 2>&1; then
        echo "[$tid] already complete — skipping"
    else
        PENDING+=("$tid")
    fi
done
[ ${#PENDING[@]} -eq 0 ] && { echo "Nothing to run."; exit 0; }

run_one_topic() {
    local tid="$1"
    local ts log_path
    ts=$(date -u +%Y%m%d-%H%M%S)
    log_path="$LOG_ROOT/${tid}-${ts}.log"
    echo "[$tid] START at $(date -Iseconds)  log=$log_path"
    timeout $((ARC_BASELINE_BUDGET_SEC + 120)) \
        python -u "$AB_ROOT/scripts/run_baseline.py" \
            --framework aide_ml --topic "$tid" \
            >"$log_path" 2>&1
    rc=$?
    echo "[$tid] DONE rc=$rc"
}
export -f run_one_topic
export AB_ROOT LOG_ROOT ARC_BASELINE_BUDGET_SEC

if [ $SERIAL -eq 1 ]; then
    for tid in "${PENDING[@]}"; do run_one_topic "$tid"; done
else
    printf '%s\n' "${PENDING[@]}" | xargs -n 1 -P "$JOBS" -I{} bash -c 'run_one_topic "$@"' _ {}
fi

echo ""
echo "=== AIDE sweep DONE  finished_at=$(date -Iseconds) ==="
