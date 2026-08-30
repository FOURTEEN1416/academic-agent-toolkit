#!/usr/bin/env bash
# DOI -> BibTeX（content negotiation）
# ACAT-GOVERNANCE 标注（2026-08-30）：上游 skill 原文引用本脚本但脚本从未入库（与技能库审计
# 抓过的"家族前缀改名断链"同类缺陷）。本文件为按 SKILL.md 契约重建的最小实现：
# 通过 doi.org content negotiation 请求 application/x-bibtex。非上游原样文件。
set -euo pipefail

DOI="${1:?usage: doi2bib.sh <DOI-or-URL>}"
# 剥离常见 URL 前缀
DOI="${DOI#https://doi.org/}"
DOI="${DOI#http://doi.org/}"
DOI="${DOI#https://dx.doi.org/}"
DOI="${DOI#doi:}"

exec curl -sLH "Accept: application/x-bibtex" "https://doi.org/${DOI}"
