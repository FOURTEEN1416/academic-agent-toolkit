#!/usr/bin/env bash
# Unified AI Scientist v2 (Sakana) runner for ARC-Bench T01-T25.
#
# AIS-v2 is a heavyweight pipeline (~1-2h per topic on CPU). Defaults to
# 4-way parallel since each topic is process-isolated.
#
# Usage:
#   bash scripts/run_ais_v2.sh                       # all 25 topics, parallel x4
#   bash scripts/run_ais_v2.sh --topics "T01 T02"    # subset
#   bash scripts/run_ais_v2.sh --serial              # serial (cheaper on RAM)
#   bash scripts/run_ais_v2.sh --jobs 2              # 2 parallel workers

set -u

: "${OPENAI_BASE_URL:?Set OPENAI_BASE_URL before running}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before running}"

export ARC_JUDGE_MODEL="${ARC_JUDGE_MODEL:-gpt-5.3-codex}"
export ARC_WIRE_API="${ARC_WIRE_API:-responses}"

TOPICS_DEFAULT="T01 T02 T03 T04 T05 T06 T07 T08 T09 T10 T11 T12 T13 T14 T15 T16 T17 T18 T19 T20 T21 T22 T23 T24 T25"
TOPICS=""
JOBS=4
SERIAL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --topics) TOPICS="$2"; shift 2 ;;
        --jobs)   JOBS="$2"; shift 2 ;;
        --serial) SERIAL=1; shift ;;
        *)        echo "unknown arg: $1"; exit 2 ;;
    esac
done
[ -z "$TOPICS" ] && TOPICS="$TOPICS_DEFAULT"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AB_ROOT="$REPO_ROOT/experiments/arc_bench"
LOG_ROOT="$AB_ROOT/results/legacy/log/ais_v2"
mkdir -p "$LOG_ROOT"
cd "$REPO_ROOT"

echo "=== ARC-Bench AI Scientist v2 sweep ==="
echo "started_at: $(date -Iseconds)"
echo "topics:     $TOPICS"
echo "mode:       $([ $SERIAL -eq 1 ] && echo serial || echo "parallel x$JOBS")"
echo ""

PENDING=()
for tid in $TOPICS; do
    if ls "$AB_ROOT/results/ais_v2/$tid"/*/judge_result.json >/dev/null 2>&1; then
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
    python -u "$AB_ROOT/scripts/run_ais_v2.py" --topic "$tid" \
        >"$log_path" 2>&1
    echo "[$tid] DONE rc=$?"
}
export -f run_one_topic
export AB_ROOT LOG_ROOT

if [ $SERIAL -eq 1 ]; then
    for tid in "${PENDING[@]}"; do run_one_topic "$tid"; done
else
    printf '%s\n' "${PENDING[@]}" | xargs -n 1 -P "$JOBS" -I{} bash -c 'run_one_topic "$@"' _ {}
fi

echo ""
echo "=== AIS-v2 sweep DONE  finished_at=$(date -Iseconds) ==="
