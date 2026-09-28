"""User guidance handoff files for internal text/image loops."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from .constants import GUIDANCE_STEPS, STEP_OUTPUT_DIRS
from .errors import StateError
from .paths import normalize_relative_path, safe_join, utc_now


SAFE_GUIDANCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
TEXT_ONLY_GUARD_CN = (
    "本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入与校验；"
    "不要生成、创建、编辑、重绘、渲染、附加、调用或请求任何图像。"
)
IMAGE_ONLY_MARKERS = (
    "IMAGE_GENERATE",
        "此轮是 IMAGE",
    "此轮只执行 IMAGE",
    "直接调用图像生成",
)
TEXT_ONLY_MARKERS = (
    "text prepare substage",
    "text review substage",
    "embedded audit",
    "embedded aggregate",
    "本轮纯文字",
    "不要生成图片",
    "不要生成图像",
    "不要生图",
)
EXPECTED_PATH_SECTION_RE = re.compile(
    r"(expected\s+active\s+image\s+paths|expected\s+image\s+paths|generated\s+image\s+default\s+locations|"
    r"预期.*路径|待登记.*路径)",
    re.I,
)
PATH_LIST_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:C\d{2}\s*[:：]\s*)?outputs/.*\.(?:png|jpg|jpeg|webp)\s*$",
    re.I,
)


def guidance_output_dir(step: str) -> str:
    if step not in GUIDANCE_STEPS:
        raise StateError(f"guidance is supported only for {sorted(GUIDANCE_STEPS)}")
    return f"{STEP_OUTPUT_DIRS[step]}/substage-guides"


def normalize_guidance_id(value: str) -> str:
    if not value or not SAFE_GUIDANCE_ID_RE.fullmatch(value):
        raise StateError("substage guidance id must contain only letters, digits, dot, underscore, and hyphen")
    return value


def optional_rel_path(run_dir: Path, label: str, value: str | None) -> str | None:
    if not value:
        return None
    rel = normalize_relative_path(value)
    safe_join(run_dir, rel)
    return rel


def is_image_only_prompt(step: str, substage_id: str, prompt: str) -> bool:
    text = f"{step}\n{substage_id}\n{prompt}"
    upper = text.upper()
    return any(marker in text or marker in upper for marker in IMAGE_ONLY_MARKERS)


def is_text_only_prompt(step: str, substage_id: str, prompt: str) -> bool:
    if is_image_only_prompt(step, substage_id, prompt):
        return False
    text = f"{step}\n{substage_id}\n{prompt}"
    upper = text.upper()
    substage_lower = substage_id.lower()
    if "text" in substage_lower:
        return True
    if step in {"S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"}:
        return any(marker in text or marker in upper for marker in TEXT_ONLY_MARKERS)
    return True


def strip_expected_path_sections(prompt: str) -> str:
    lines = prompt.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if EXPECTED_PATH_SECTION_RE.search(line):
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate or PATH_LIST_LINE_RE.match(candidate):
                    index += 1
                    continue
                break
            continue
        output.append(line)
        index += 1
    return "\n".join(output).strip()


def normalize_next_prompt(step: str, substage_id: str, prompt: str) -> str:
    normalized = strip_expected_path_sections(prompt)
    if is_text_only_prompt(step, substage_id, normalized) and not normalized.endswith(TEXT_ONLY_GUARD_CN):
        normalized = f"{normalized.rstrip()}\n{TEXT_ONLY_GUARD_CN}"
    return normalized.strip()


def guidance_markdown(args: argparse.Namespace, created_at: str) -> str:
    lines = [
        f"# Next User Prompt: {args.step} / {args.substage_id}",
        "",
        f"- step: `{args.step}`",
        f"- substage_id: `{args.substage_id}`",
        f"- created_at: `{created_at}`",
    ]
    if args.summary:
        lines.extend(["", "## Summary", "", args.summary.strip()])
    lines.extend(["", "## Copyable Prompt", "", "```text", args.next_prompt.strip(), "```"])
    if args.checkpoint_path:
        lines.extend(["", "## Checkpoint", "", f"- checkpoint: `{args.checkpoint_path}`"])
    if args.source_user_request:
        lines.extend(["", "## Source User Request", "", args.source_user_request.strip()])
    lines.append("")
    return "\n".join(lines)


def cmd_write_guidance(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    if not args.next_prompt or not args.next_prompt.strip():
        raise StateError("--next-prompt is required and cannot be empty")
    substage_id = normalize_guidance_id(args.substage_id)
    next_prompt = normalize_next_prompt(args.step, substage_id, args.next_prompt)
    guide_dir_rel = guidance_output_dir(args.step)
    guide_rel = f"{guide_dir_rel}/{substage_id}-next-user-prompt.md"
    guide_path = safe_join(run_dir, guide_rel)
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_rel = optional_rel_path(run_dir, "checkpoint_path", args.checkpoint_path)
    created_at = utc_now()
    original_next_prompt = args.next_prompt
    args.next_prompt = next_prompt
    guide_path.write_text(guidance_markdown(args, created_at), encoding="utf-8")
    row = {
        "step": args.step,
        "substage_id": substage_id,
        "relative_path": guide_rel,
        "summary": args.summary or "",
        "next_prompt": next_prompt,
        "checkpoint_path": checkpoint_rel,
        "created_at": created_at,
        "updated_at": created_at,
        "source_user_request": args.source_user_request or "",
        "prompt_normalization": {
            "text_only_guard_appended": next_prompt != strip_expected_path_sections(original_next_prompt).strip()
            and next_prompt.endswith(TEXT_ONLY_GUARD_CN),
            "expected_path_section_removed": strip_expected_path_sections(original_next_prompt).strip()
            != original_next_prompt.strip(),
        },
    }
    state.setdefault("substage_guidance_registry", {}).setdefault(args.step, {})[substage_id] = row
    state.setdefault("next_prompt_registry", {})[args.step] = {
        "substage_id": substage_id,
        "relative_path": guide_rel,
        "next_prompt": next_prompt,
        "updated_at": created_at,
    }
    state["updated_at"] = created_at
    return row
