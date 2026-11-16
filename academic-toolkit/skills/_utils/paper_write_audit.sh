#!/usr/bin/env bash
# paper_write_audit.sh — paper-write 族共享收尾审计（单一实现，六件 SKILL.md 共用）
# 覆盖原六件尾部三段：figure embedding check + FIGURE_MANIFEST audit + universal paper audit
#
# 用法: bash paper_write_audit.sh [--mode latex|docx]
#   latex（默认）: figures/*.pdf 须被 paper/sections/*.tex 或 paper/main.tex 引用；
#                  figures/*.tex 的 \label{} 须被正文 \ref；
#                  FIGURE_MANIFEST 计划图须存在（.pdf/.png）且被 paper/sections/ 或 paper/main.tex 引用。
#   docx        : figures/*（png/pdf/jpg/svg）与 figures/TABLE_*.md 须被 paper/main.md 引用；
#                  FIGURE_MANIFEST 计划图须存在（.png/.pdf/.drawio）且被 paper/main.md 引用；
#                  另查 paper/main.md 题注（![alt](...)）长度 <= 14 词。
#
# 退出码: 0 = 无缺失且审计通过（或无可查项）; 1 = 存在缺失/审计失败。
#
# 口径说明：
#   - 有引擎 finish 时，产出结构/存在性/最低完整性以 output_contract 与 paper_write_gate
#     自动核验为准；本脚本用于无引擎合同场景的预检与人工兜底。
#   - 审计留痕由程序采集（执行会话/finish 证据），不再 tee -a AUDIT_REPORT.md 手写审计文件。
#   - 相比原六件内联版，本脚本修正了两处漂移：①universal audit 的退出码不再被管道 tee 吞掉；
#     ②docx 题注超长计入失败（原版仅提示）。
set -u

MODE="latex"
if [ "${1:-}" = "--mode" ]; then
  MODE="${2:-latex}"
  shift 2 2>/dev/null || true
fi

fail=0

echo "=== Figure embedding check (mode=$MODE) ==="
if [ "$MODE" = "docx" ]; then
  # Markdown docx 模式：图片/表格文件须在 paper/main.md 中被引用
  for img in figures/*.png figures/*.pdf figures/*.jpg figures/*.svg; do
    [ -f "$img" ] || continue
    bn=$(basename "$img")
    [ "$bn" = "latex_includes.tex" ] && continue
    if [ -f paper/main.md ] && ! grep -q "$bn" paper/main.md; then
      echo "MISSING: $bn — produced but not embedded in paper/main.md"
      fail=$((fail + 1))
    fi
  done
  for tbl in figures/TABLE_*.md; do
    [ -f "$tbl" ] || continue
    bn=$(basename "$tbl")
    if [ -f paper/main.md ] && ! grep -q "$bn" paper/main.md; then
      echo "MISSING: $bn — table file produced but not referenced in paper/main.md"
      fail=$((fail + 1))
    fi
  done
else
  # LaTeX 模式：figures/*.pdf 须被 sections/main 引用；figures/*.tex 的 label 须被 \ref
  for pdf in figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    if ! grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null; then
      echo "MISSING: $bn — produced but not embedded in any section"
      fail=$((fail + 1))
    fi
  done
  for fig_tex in figures/*.tex; do
    [ -f "$fig_tex" ] || continue
    for lbl in $(grep -oh '\\label{[^}]*}' "$fig_tex" 2>/dev/null); do
      if ! grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null; then
        echo "MISSING: $lbl (from $(basename "$fig_tex")) — not referenced"
        fail=$((fail + 1))
      fi
    done
  done
fi
echo "Total missing embeddings: $fail"
if [ "$fail" -gt 0 ]; then
  echo "⛔ DO NOT finish until missing = 0."
fi

# docx 模式附加：题注过长检查（题注是短标签，判据/参数/结论写进正文）
if [ "$MODE" = "docx" ] && [ -f paper/main.md ]; then
  echo "=== Caption-too-long check ==="
  PY=""
  for _c in "${MH_PYTHON:-}" python python3; do
    [ -z "$_c" ] && continue
    if $_c -c "import sys" >/dev/null 2>&1; then PY="$_c"; break; fi
  done
  [ -z "$PY" ] && PY=python
  "$PY" - paper/main.md << 'PYEOF'
import re, sys
LIMIT = 14  # word cap after stripping the "Figure N:" prefix (over 14 = violation)
try:
    text = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
except FileNotFoundError:
    sys.exit(0)
m = re.search(r'(?m)^##\s*(Appendix|References)', text)
body_text = text[:m.start()] if m else text
bad = []
for alt in re.findall(r'!\[([^\]]*)\]\([^)]*\)', body_text):
    body = re.sub(r'^\s*(Figure|Fig\.?|Table|Tab\.?)\s*\d+\s*[:.．、]?\s*', '', alt, flags=re.I)
    words = re.findall(r'[A-Za-z][A-Za-z-]*', body)
    if len(words) > LIMIT:
        bad.append((len(words), ' '.join(words[:12])))
if bad:
    for n, preview in bad:
        print(f"  X caption {n} words (>{LIMIT}): {preview}...")
    print(f"  {len(bad)} caption(s) too long — keep alt text to a short label (<=14 words); move criteria/params/conclusions into the body")
    sys.exit(3)
print("  OK captions are concise")
PYEOF
  cap_rc=$?
  if [ "$cap_rc" -eq 3 ]; then
    echo "⛔ Captions too long: shorten the alt text and move detail into the body, then re-run until it prints OK"
    fail=$((fail + 1))
  fi
fi

echo "=== FIGURE_MANIFEST audit ==="
PLAN_FILE=""
for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md TOPIC_PLAN.md; do
  [ -f "$f" ] && grep -q "<!-- BEGIN FIGURE_MANIFEST -->" "$f" && { PLAN_FILE="$f"; break; }
done
manifest_missing=0
if [ -n "$PLAN_FILE" ]; then
  START=$(grep -n "<!-- BEGIN FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
  END=$(grep -n "<!-- END FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
  EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE "^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)" | sed "s/^[[:space:]]*-[[:space:]]*//")
  for name in $EXPECTED_FIGS; do
    if ! ls figures/${name}.pdf figures/${name}.png figures/${name}.drawio 2>/dev/null | head -1 | grep -q .; then
      echo "❌ MANIFEST: $name file missing"
      manifest_missing=$((manifest_missing + 1))
    elif [ "$MODE" = "docx" ]; then
      if ! grep -qE "${name}\.(png|pdf)" paper/main.md 2>/dev/null; then
        echo "❌ MANIFEST: $name exists but not embedded"
        manifest_missing=$((manifest_missing + 1))
      fi
    elif ! grep -rqE "${name}\.(pdf|png)" paper/sections/ paper/main.tex 2>/dev/null; then
      echo "❌ MANIFEST: $name exists but not referenced in paper"
      manifest_missing=$((manifest_missing + 1))
    fi
  done
  if [ "$manifest_missing" -gt 0 ]; then
    echo "⛔ FIGURE_MANIFEST audit failed ($manifest_missing missing): produce + embed every planned figure before ending"
    fail=$((fail + manifest_missing))
  else
    echo "✅ FIGURE_MANIFEST fully embedded"
  fi
else
  echo "(no FIGURE_MANIFEST in plan docs, skip audit)"
fi

echo "=== Universal paper-stage audit ==="
# [13] Conclusion consistency: paper text <-> results.json (prevent "optimal=X but paper says Y")
# [14] Event source attribution (prevent "guessing source from variable name")
# Falls back to simplified mode if no PROBLEM_FACTS.json (general academic / course / humanities).
PY=""
for _c in "${MH_PYTHON:-}" python python3; do
  [ -z "$_c" ] && continue
  if $_c -c "import sys" >/dev/null 2>&1; then PY="$_c"; break; fi
done
[ -z "$PY" ] && PY=python
if [ -f _utils/facts_audit.py ]; then
  $PY _utils/facts_audit.py --stage paper
  PRC=$?
  if [ "$PRC" = "1" ]; then
    echo "❌ Universal paper-stage audit failed — fix paper text / results.json before finishing"
    fail=$((fail + 1))
  fi
else
  echo "(facts_audit.py not found, skip universal audit)"
fi

if [ "$fail" -gt 0 ]; then
  exit 1
fi
exit 0
