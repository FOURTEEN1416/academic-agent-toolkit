#!/usr/bin/env bash
# =============================================================================
# Manual paper-quality grader — launches Claude Code on a completed run dir
# and uses config/_meta_paper_quality.json as the reference rubric text.
# -----------------------------------------------------------------------------
# This is INTENTIONALLY not invoked by the bench pipeline.  You run it manually
# when you want a paper-quality verdict on a finished run.  Why manual:
#   - Paper-quality judgments benefit from a human (or a long-context agent
#     with vision) reading the actual deliverable, not from a fast LLM call
#     summarising a JSON dump.
#   - Grading cost: ~one Claude Code session per run (5-15 min, ~$0.5 in
#     credits).  Don't burn this on every CI run.
#
# What it does:
#   1. Resolves a run directory (latest under results/e2e/<topic>/ by default,
#      or whatever path you pass).
#   2. Builds a single Markdown prompt at <run_dir>/judge_paper_prompt.md
#      containing the full _meta_paper_quality.json as reference text, plus
#      a directory tree of the deliverables, plus explicit scoring instructions.
#   3. Invokes `claude -p` with --dangerously-skip-permissions so the agent
#      can Read, View images, and Grep across the run dir.
#   4. The agent writes <run_dir>/paper_quality_verdict.json with per-leaf
#      scores, evidence quotes, and an overall weighted score.
#
# Usage:
#   experiments/arc_bench/scripts/judge_paper_manual.sh <run_dir>
#   experiments/arc_bench/scripts/judge_paper_manual.sh --topic B01
#   experiments/arc_bench/scripts/judge_paper_manual.sh --topic ML07 --dry-run
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BENCH_ROOT="$REPO_ROOT/experiments/arc_bench"
META_RUBRIC="$BENCH_ROOT/config/_meta_paper_quality.json"

DRY_RUN=false
RUN_DIR=""
TOPIC=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --topic) TOPIC="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help)
            sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            if [[ -z "$RUN_DIR" ]]; then RUN_DIR="$1"
            else echo "unexpected arg: $1" >&2; exit 2; fi
            shift
            ;;
    esac
done

if [[ -z "$RUN_DIR" && -n "$TOPIC" ]]; then
    RUN_DIR=$(ls -td "$BENCH_ROOT/results/e2e/$TOPIC/e2e-$TOPIC-"*/ 2>/dev/null | head -1 || true)
    if [[ -z "$RUN_DIR" ]]; then
        echo "ERROR: no run dir found for topic $TOPIC under $BENCH_ROOT/results/e2e/$TOPIC/" >&2
        exit 1
    fi
    RUN_DIR="${RUN_DIR%/}"
fi

if [[ -z "$RUN_DIR" || ! -d "$RUN_DIR" ]]; then
    echo "ERROR: run dir not given or not found: $RUN_DIR" >&2
    echo "Usage: $0 [<run_dir>|--topic <id>] [--dry-run]" >&2
    exit 1
fi

PAPER_FINAL=$(find "$RUN_DIR" -maxdepth 4 -name "paper_final.md" -print -quit 2>/dev/null || true)
PAPER_REVISED=$(find "$RUN_DIR" -maxdepth 4 -name "paper_revised.md" -print -quit 2>/dev/null || true)
PAPER_DRAFT=$(find "$RUN_DIR" -maxdepth 4 -name "paper_draft.md" -print -quit 2>/dev/null || true)
SUBMISSION_README=$(find "$RUN_DIR" -maxdepth 4 -path "*/submission/README.md" -print -quit 2>/dev/null || true)
CHARTS_DIR=$(find "$RUN_DIR" -maxdepth 4 -type d -name "charts" -print -quit 2>/dev/null || true)
DELIVERABLES_DIR="$RUN_DIR/deliverables"
CODE_DIR=$(find "$RUN_DIR" -maxdepth 4 -type d \( -name "code" -o -name "experiment_final" \) -print -quit 2>/dev/null || true)
EXP_SUMMARY=$(find "$RUN_DIR" -maxdepth 4 -name "experiment_summary.json" -print -quit 2>/dev/null || true)

echo "==========================================================================="
echo "  Manual paper-quality grading"
echo "  Run dir:       $RUN_DIR"
echo "  paper_final:   ${PAPER_FINAL:-<missing>}"
echo "  paper_revised: ${PAPER_REVISED:-<missing>}"
echo "  charts dir:    ${CHARTS_DIR:-<missing>}"
echo "  code dir:      ${CODE_DIR:-<missing>}"
echo "  exp_summary:   ${EXP_SUMMARY:-<missing>}"
echo "  meta-rubric:   $META_RUBRIC"
echo "==========================================================================="

PROMPT_FILE="$RUN_DIR/judge_paper_prompt.md"
VERDICT_FILE="$RUN_DIR/paper_quality_verdict.json"

{
cat <<'EOF_HEADER'
# Manual Paper-Quality Audit

You are a research-paper reviewer evaluating the **deliverables** of an
ARC-Bench autonomous-research run.  Your job is to read the final paper,
inspect every figure, read the experiment code, and grade each leaf of the
meta-rubric below.

## Your tools

- `Read`: read paper_final.md, paper_revised.md, paper_draft.md,
  submission/README.md, experiment_summary.json, results.json, *.py files,
  references.bib.
- Image read (built into `Read`): view PNG / PDF figures in `charts/` or
  `deliverables/charts/`.
- `Grep` / `Bash`: search the run dir for specific values, e.g. "does the
  abstract's '92.3%' appear anywhere in experiment_summary.json?".

## Procedure

1. Read the meta-rubric below in full.
2. Read the paper (prefer `paper_final.md`, fall back to revised → draft).
3. View every figure under `charts/` and `deliverables/charts/`.
4. Skim the code under `code/` or `submission/code/` for ≥5 minutes —
   enough to judge modularity, reproducibility, hygiene.
5. For each leaf, assign a score in `{0, 0.33, 0.5, 0.67, 1.0}` based on
   the leaf's `requirements` field.  Quote a short piece of evidence
   (≤200 chars) for each score.
6. Compute the weighted overall:
     overall = sum(leaf_weight * leaf_score) / sum(leaf_weight)
   over ALL leaves of the meta-rubric (across all 4 buckets).
7. Write the verdict file as JSON at the path specified at the bottom of
   this prompt.

## Scoring guidance

- Use partial credit aggressively.  Most papers are not 0 or 1 on any
  given leaf; they are 0.33, 0.5, or 0.67.
- Penalize fabrication HARSHLY: if any single key metric in the paper
  doesn't appear in the artifacts, `mca-no-fabrication` is capped at 0.5
  regardless of other findings.
- Reward honesty: a discussion section that names limitations gets a
  higher `mpq-discussion` score than one that doesn't.
- Don't penalize for length / polish if the content is correct.

## Deliverables for this audit

EOF_HEADER

echo "- Paper (final):    \`${PAPER_FINAL#$RUN_DIR/}\`"
[[ -n "$PAPER_REVISED" ]] && echo "- Paper (revised):  \`${PAPER_REVISED#$RUN_DIR/}\`"
[[ -n "$PAPER_DRAFT"  ]]  && echo "- Paper (draft):    \`${PAPER_DRAFT#$RUN_DIR/}\`"
[[ -n "$SUBMISSION_README" ]] && echo "- Submission README: \`${SUBMISSION_README#$RUN_DIR/}\`"
[[ -n "$CHARTS_DIR" ]]    && echo "- Charts dir:       \`${CHARTS_DIR#$RUN_DIR/}\`"
[[ -d "$DELIVERABLES_DIR" ]] && echo "- Deliverables dir: \`deliverables/\`"
[[ -n "$CODE_DIR"   ]]    && echo "- Code dir:         \`${CODE_DIR#$RUN_DIR/}\`"
[[ -n "$EXP_SUMMARY" ]]   && echo "- Experiment summary: \`${EXP_SUMMARY#$RUN_DIR/}\`"
echo ""
echo "## Meta-rubric (reference text — score against this)"
echo ""
echo '```json'
cat "$META_RUBRIC"
echo '```'
echo ""

cat <<EOF_FOOTER

## Output

Write your verdict to \`paper_quality_verdict.json\` in this run directory.
Schema:

\`\`\`json
{
  "run_dir": "$(basename "$RUN_DIR")",
  "graded_by": "claude-code-manual",
  "graded_at": "<ISO8601 timestamp>",
  "leaf_grades": [
    {"id": "mpq-abstract", "score": 0.67, "evidence": "...", "rationale": "..."},
    {"id": "mpq-introduction", "score": 0.5, "evidence": "...", "rationale": "..."}
  ],
  "bucket_overalls": {
    "meta-paper-content":     "<weighted avg of mpq-* leaves>",
    "meta-code-orchestration":"<weighted avg of mco-* leaves>",
    "meta-visual-layout":     "<weighted avg of mvl-* leaves>",
    "meta-content-accuracy":  "<weighted avg of mca-* leaves>"
  },
  "overall": "<weighted sum across ALL 19 leaves / total_weight>",
  "summary": "1-paragraph human-readable verdict",
  "must_revise": ["<leaf-ids whose score < 0.5>"]
}
\`\`\`

Do NOT score anything you have not actually inspected.  If a deliverable
is missing (e.g. no charts/ dir), mark the dependent leaves with
\`"score": 0, "evidence": "(artifact missing)"\` rather than guessing.

When done, also print a one-page Markdown summary to stdout for the
human reviewer.

EOF_FOOTER
} > "$PROMPT_FILE"

echo "[prompt written] $PROMPT_FILE ($(wc -l < "$PROMPT_FILE") lines)"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would invoke:"
    echo "    claude -p \"...\" --dangerously-skip-permissions --max-turns 80"
    echo "    cwd=$RUN_DIR"
    exit 0
fi

if ! command -v claude >/dev/null 2>&1; then
    echo "ERROR: claude CLI not found in PATH. Install with: npm i -g @anthropic-ai/claude-cli" >&2
    exit 3
fi

echo "[invoking claude] cwd=$RUN_DIR (this typically takes 5-15 min)"
echo "  output will be written to: $VERDICT_FILE"
echo ""

cd "$RUN_DIR"
claude -p "Read judge_paper_prompt.md and execute the audit it describes. Write paper_quality_verdict.json when done." \
    --dangerously-skip-permissions \
    --max-turns 80

if [[ -f "$VERDICT_FILE" ]]; then
    echo ""
    echo "==========================================================================="
    echo "  Verdict written: $VERDICT_FILE"
    python3 -c "
import json
d = json.load(open('$VERDICT_FILE'))
print(f'  Overall:  {d.get(\"overall\", \"?\")}')
bo = d.get('bucket_overalls', {})
for k, v in bo.items():
    print(f'    {k}: {v}')
must = d.get('must_revise', [])
if must:
    print(f'  Must revise ({len(must)} leaves):')
    for x in must: print(f'    - {x}')
" 2>/dev/null || cat "$VERDICT_FILE"
    echo "==========================================================================="
else
    echo "WARN: verdict file not written; check claude output above" >&2
    exit 4
fi
