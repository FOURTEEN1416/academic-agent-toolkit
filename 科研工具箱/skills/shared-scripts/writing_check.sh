#!/bin/bash
# Source checks are independent of the compiled-PDF gate.
# --supplemental runs only checks not already owned by compile_check.sh.
PAPER_DIR="${1:-paper}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v cygpath >/dev/null 2>&1; then
    SCRIPT_DIR="$(cygpath -m "$SCRIPT_DIR")"
    PAPER_DIR="$(cygpath -m "$PAPER_DIR")"
fi
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PYTHON="${MH_PYTHON:-python}"
EXIT_CODE=0
run_check() {
    local script="$1"; shift
    if [ ! -f "$SCRIPT_DIR/$script" ]; then
        echo "[CHECK_UNAVAILABLE] Missing $script"
        EXIT_CODE=3
        return
    fi
    local output
    output=$("$PYTHON" "$SCRIPT_DIR/$script" "$@" 2>&1)
    local status=$?
    printf '%s\n' "$output"
    if [ "$status" -ne 0 ] && { [ "$status" -ne 1 ] || [[ "$output" == *"[CHECK_UNAVAILABLE]"* ]] || [[ "$output" == *"Traceback (most recent call last)"* ]]; }; then
        echo "[CHECK_UNAVAILABLE] $script exit=$status; do not rewrite the paper for a tool error"
        EXIT_CODE=3
    elif [ "$status" -eq 1 ] && [ "$EXIT_CODE" -ne 3 ]; then
        EXIT_CODE=1
    fi
}
run_check writing_source_check.py "$PAPER_DIR"
if [ "${2:-}" != "--supplemental" ]; then
    run_check figure_narrative_check.py "$PAPER_DIR"
    run_check modeling_tex_policy.py check "$PAPER_DIR"
    run_check assumption_layout_check.py "$PAPER_DIR"
    run_check symbol_layout_check.py "$PAPER_DIR"
    run_check abstract_emphasis_check.py "$PAPER_DIR"
    run_check human_paper_style_check.py "$PAPER_DIR"
    run_check ai_tell_check.py
fi
echo "=== Writing checks complete (exit=$EXIT_CODE; advisory warnings are not evidence of failure) ==="
exit "$EXIT_CODE"
