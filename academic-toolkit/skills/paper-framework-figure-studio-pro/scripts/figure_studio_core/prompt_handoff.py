"""Generic file-reference prompt handoff helpers for v3.2.15f.

Full image prompts are persisted as files. User-visible next prompts should
reference prompt indexes rather than inline long multi-candidate prompts. The
candidate id written into the prompt-index is the source of truth for prompt,
image, registry, artifact, and checkpoint paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .constants import S5_REFERENCE_IMAGE_INPUT_POLICY
from .identity import (
    assert_path_candidate_id,
    default_candidate_paths,
    normalize_candidate_id,
    normalize_prompt_index,
)


def _as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def save_candidate_prompt(candidate_id: str, prompt_text: str, stage_root: str | Path, *, filename: str = "prompt-v01.md") -> str:
    cid = normalize_candidate_id(candidate_id)
    candidate_dir = _as_path(stage_root) / "candidates" / cid
    candidate_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = candidate_dir / filename
    assert_path_candidate_id(prompt_path.as_posix(), cid, label="candidate prompt path")
    prompt_path.write_text(prompt_text.rstrip() + "\n", encoding="utf-8")
    return prompt_path.as_posix()


def create_prompt_index(
    stage_root: str | Path,
    candidate_ids: Iterable[str],
    *,
    stage: str | None = None,
    substage: str = "IMAGE_GENERATE",
    prompt_filename: str = "prompt-v01.md",
    target_filename: str = "image-v01.png",
    extra_candidate_metadata: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    stage_root_path = _as_path(stage_root)
    stage_root_path.mkdir(parents=True, exist_ok=True)
    ids = [normalize_candidate_id(cid) for cid in candidate_ids]
    rows: list[dict[str, Any]] = []
    for cid in ids:
        prompt_path = stage_root_path / "candidates" / cid / prompt_filename
        target_image_path = stage_root_path / "candidates" / cid / target_filename
        row: dict[str, Any] = {
            "candidate_id": cid,
            "prompt_path": assert_path_candidate_id(prompt_path.as_posix(), cid, label=f"{cid}.prompt_path"),
            "target_image_path": assert_path_candidate_id(target_image_path.as_posix(), cid, label=f"{cid}.target_image_path"),
        }
        if extra_candidate_metadata and cid in extra_candidate_metadata:
            row.update(dict(extra_candidate_metadata[cid]))
        rows.append(row)
    index_payload: dict[str, Any] = {
        "schema_version": 2,
        "stage": stage,
        "substage": substage,
        "prompt_mode": "file_reference_handoff",
        "candidate_ids": ids,
        "candidates": rows,
        "image_route_policy": "Codex must use image_gen; ChatGPT web must use Create Image / ChatGPT Images 2.0; other runtimes require a named approved image-generation API. Do not use SVG, Python/PIL, Matplotlib, Graphviz, TikZ, Mermaid, canvas, PPT/PDF rendering, screenshots, or any local raster substitute.",
        "user_visible_policy": "Visible handoff prompts should reference this index and should not inline full prompt bodies.",
        "candidate_id_source_of_truth": "candidate_id in this prompt-index; do not renumber or reinterpret IDs during image generation or registration.",
    }
    if stage == "S5-CANDIDATE-IMAGE":
        index_payload["s5_reference_image_input_policy"] = S5_REFERENCE_IMAGE_INPUT_POLICY
    index: dict[str, Any] = normalize_prompt_index(
        index_payload,
        stage=stage,
    )
    index_path = stage_root_path / "prompt-index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index_path.as_posix()


def user_visible_handoff(index_path: str | Path, *, mode: str = "IMAGE_GENERATE") -> str:
    index = _as_path(index_path).as_posix()
    return (
        f"进入相应的 {mode} 子阶段。请读取并使用已保存的 prompt-index：\n\n"
        f"{index}\n\n"
        "逐一读取 prompt-index 中每个 selected / non-skipped candidate 的 prompt_path，并按同一行 candidate_id 生成对应 target_image_path。"
        "必须采用 row-atomic 队列：一次图像生成只激活一个 candidate_id、一个 prompt_path、一个 target_image_path；不得用一次宽泛/批量提示词满足多个 rows。"
        "若当前 prompt-index 有 N 个 selected / non-skipped rows，则必须完成 N 次独立图像生成与 N 个 target_image_path 镜像/注册后，S2/S5 才算完成。"
        "若这是 S5-CANDIDATE-IMAGE 且行内存在 reference_image_paths，请先读取这些 S2 参考图路径；当前图像路线支持参考图输入时附加使用，不支持时自动忽略并继续。"
        "不得改写、重排、重命名或猜测 candidate_id；图像、状态、artifact、checkpoint 中的 ID 必须与 prompt-index 完全一致。"
        "孤立生成图、未镜像到 target_image_path 的图、未绑定同一 candidate_id 的图、或把多个 sibling rows 合成一张的图，都不得视为候选产出。"
        "必须使用当前 runtime 锁定的图像生成路线：Codex=image_gen；ChatGPT web=Create Image / ChatGPT Images 2.0；其他 runtime=已登记的 approved image-generation API。"
        "禁止用 SVG、Python/PIL、Matplotlib、Graphviz、TikZ、Mermaid、canvas、PPT/PDF 渲染、截图或本地程序化 PNG/WebP 代替生图。"
        "本轮为 image-only：只逐行生成/附加并注册图像；不要写解释、审核、排序、修改建议或下一步提示词。"
    )
