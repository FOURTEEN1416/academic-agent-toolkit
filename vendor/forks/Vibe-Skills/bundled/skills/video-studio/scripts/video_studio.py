#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _now_ms() -> int:
    return int(time.time() * 1000)


def _print_json(obj: Any) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _which(cmd: str) -> Optional[str]:
    try:
        return shutil.which(cmd)
    except Exception:
        return None


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_hex_color(value: str) -> str:
    v = (value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.lower()
    raise ValueError(f"Invalid hex color: {value!r} (expected '#RRGGBB')")


def _windows_default_fontfile_hint(spec: Dict[str, Any]) -> Optional[str]:
    hint = (
        (((spec.get("style") or {}).get("font") or {}).get("font_file_hint_windows"))
        if isinstance(spec, dict)
        else None
    )
    if hint and isinstance(hint, str):
        return hint
    return None


def _pick_fontfile(spec: Dict[str, Any]) -> Optional[str]:
    hint = _windows_default_fontfile_hint(spec)
    if hint:
        p = Path(hint)
        if p.exists():
            return str(p)
    # Best-effort fallback for common Windows fonts.
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def probe_environment() -> Dict[str, Any]:
    ffmpeg = _which("ffmpeg")
    ffprobe = _which("ffprobe")
    node = _which("node")
    npm = _which("npm")
    npx = _which("npx")

    vectcut_base_url = os.environ.get("VECTCUT_BASE_URL") or os.environ.get("VECTCUT_API_BASE_URL")
    vectcut_ok = False
    vectcut_error = None
    if vectcut_base_url:
        try:
            req = urllib.request.Request(vectcut_base_url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                _ = resp.read(256)
            vectcut_ok = True
        except Exception as e:
            vectcut_error = f"{type(e).__name__}: {e}"

    return {
        "timestamp_ms": _now_ms(),
        "ffmpeg": {"found": bool(ffmpeg), "path": ffmpeg},
        "ffprobe": {"found": bool(ffprobe), "path": ffprobe},
        "node": {"found": bool(node), "path": node},
        "npm": {"found": bool(npm), "path": npm},
        "npx": {"found": bool(npx), "path": npx},
        "vectcut": {
            "base_url": vectcut_base_url,
            "reachable": vectcut_ok,
            "error": vectcut_error,
        },
        "install_hints": {
            "ffmpeg_windows_choco": "choco install ffmpeg -y",
            "ffmpeg_windows_winget": "winget install -e --id Gyan.FFmpeg",
            "remotion_create_project": "npx create-video@latest",
        },
    }


@dataclass(frozen=True)
class OutputSpec:
    path: Path
    width: int
    height: int
    fps: int
    video_bitrate: str
    audio_bitrate: str


@dataclass(frozen=True)
class SceneSpec:
    duration_sec: float
    text: str
    subtitle: str


def _parse_output_spec(spec: Dict[str, Any]) -> OutputSpec:
    out = spec.get("output") or {}
    path = Path(out.get("path") or "outputs/video-studio/final/video.mp4")
    width = int(out.get("width") or 1080)
    height = int(out.get("height") or 1920)
    fps = int(out.get("fps") or 30)
    video_bitrate = str(out.get("video_bitrate") or "6M")
    audio_bitrate = str(out.get("audio_bitrate") or "192k")
    if width <= 0 or height <= 0:
        raise ValueError("output.width/height must be positive integers")
    if fps <= 0 or fps > 120:
        raise ValueError("output.fps must be within 1..120")
    return OutputSpec(
        path=path,
        width=width,
        height=height,
        fps=fps,
        video_bitrate=video_bitrate,
        audio_bitrate=audio_bitrate,
    )


def _parse_scenes(spec: Dict[str, Any]) -> List[SceneSpec]:
    scenes = spec.get("scenes") or []
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("spec.scenes must be a non-empty list")
    parsed: List[SceneSpec] = []
    for i, s in enumerate(scenes):
        if not isinstance(s, dict):
            raise ValueError(f"scene[{i}] must be an object")
        duration_sec = float(s.get("duration_sec") or 3.0)
        if duration_sec <= 0.05:
            raise ValueError(f"scene[{i}].duration_sec too small: {duration_sec}")
        text = str(s.get("text") or "").strip()
        subtitle = str(s.get("subtitle") or "").strip()
        if not text and not subtitle:
            raise ValueError(f"scene[{i}] must include 'text' or 'subtitle'")
        parsed.append(SceneSpec(duration_sec=duration_sec, text=text, subtitle=subtitle))
    return parsed


def _spec_style(spec: Dict[str, Any]) -> Tuple[str, str, bool, str]:
    style = spec.get("style") or {}
    bg = _normalize_hex_color(style.get("background_color") or "#0b1220")
    fg = _normalize_hex_color(style.get("text_color") or "#ffffff")
    box = style.get("text_box") or {}
    box_enabled = bool(box.get("enabled", True))
    box_color = str(box.get("color") or "black@0.45")
    return bg, fg, box_enabled, box_color


def _escape_drawtext(text: str) -> str:
    # FFmpeg drawtext escaping rules are finicky; this is a conservative subset.
    # See: https://ffmpeg.org/ffmpeg-filters.html#drawtext-1
    t = text.replace("\\", "\\\\")
    t = t.replace(":", "\\:")
    t = t.replace("'", "\\'")
    t = t.replace("\n", "\\n")
    return t


def _render_scene_ffmpeg(
    *,
    ffmpeg: str,
    out_path: Path,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    background_hex: str,
    text: str,
    subtitle: str,
    text_hex: str,
    fontfile: Optional[str],
    box_enabled: bool,
    box_color: str,
    video_bitrate: str,
) -> None:
    _ensure_parent(out_path)
    bg = background_hex.lstrip("#")
    fg = text_hex.lstrip("#")

    drawtext_common = []
    if fontfile:
        # Windows drive letters ("C:\") contain ":" which must be escaped for drawtext parsing.
        escaped_fontfile = _escape_drawtext(fontfile.replace("\\", "/"))
        drawtext_common.append(f"fontfile='{escaped_fontfile}'")
    drawtext_common.append(f"fontcolor=#{fg}")
    if box_enabled:
        drawtext_common.append("box=1")
        drawtext_common.append(f"boxcolor={box_color}")
        drawtext_common.append("boxborderw=24")
    else:
        drawtext_common.append("box=0")

    filters: List[str] = []
    if text:
        filters.append(
            "drawtext="
            + ":".join(
                drawtext_common
                + [
                    f"text='{_escape_drawtext(text)}'",
                    "fontsize=72",
                    "x=(w-text_w)/2",
                    "y=(h-text_h)/2-90",
                    "line_spacing=12",
                ]
            )
        )
    if subtitle:
        filters.append(
            "drawtext="
            + ":".join(
                drawtext_common
                + [
                    f"text='{_escape_drawtext(subtitle)}'",
                    "fontsize=42",
                    "x=(w-text_w)/2",
                    "y=(h-text_h)/2+20",
                    "line_spacing=10",
                ]
            )
        )
    vf = ",".join(filters) if filters else "null"

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#{bg}:s={width}x{height}:r={fps}:d={duration_sec}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        video_bitrate,
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg scene render failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )


def _concat_videos_ffmpeg(*, ffmpeg: str, inputs: List[Path], out_path: Path) -> None:
    if not inputs:
        raise ValueError("No inputs to concatenate")
    _ensure_parent(out_path)

    # Use concat demuxer with a file list.
    tmp_dir = Path("outputs/video-studio/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    list_path = tmp_dir / f"concat_{_now_ms()}.txt"
    with list_path.open("w", encoding="utf-8") as f:
        for p in inputs:
            # concat demuxer wants paths quoted, forward slashes help on Windows.
            posix_path = p.resolve().as_posix()
            f.write(f"file '{posix_path}'\n")

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(out_path),
    ]
    result = _run(cmd)
    try:
        list_path.unlink(missing_ok=True)
    except Exception:
        pass
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg concat failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )


def render_from_spec(spec_path: Path) -> Dict[str, Any]:
    spec = _read_json(spec_path)
    env = probe_environment()

    ffmpeg = env["ffmpeg"]["path"]
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install it first, then re-run.\n"
            f"Hint (Windows): {env['install_hints']['ffmpeg_windows_choco']}"
        )

    out = _parse_output_spec(spec)
    scenes = _parse_scenes(spec)
    bg_hex, fg_hex, box_enabled, box_color = _spec_style(spec)
    fontfile = _pick_fontfile(spec)

    tmp_dir = Path("outputs/video-studio/tmp") / f"render_{_now_ms()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    scene_paths: List[Path] = []
    for i, s in enumerate(scenes):
        scene_out = tmp_dir / f"scene_{i:02d}.mp4"
        _render_scene_ffmpeg(
            ffmpeg=ffmpeg,
            out_path=scene_out,
            width=out.width,
            height=out.height,
            fps=out.fps,
            duration_sec=s.duration_sec,
            background_hex=bg_hex,
            text=s.text,
            subtitle=s.subtitle,
            text_hex=fg_hex,
            fontfile=fontfile,
            box_enabled=box_enabled,
            box_color=box_color,
            video_bitrate=out.video_bitrate,
        )
        scene_paths.append(scene_out)

    _ensure_parent(out.path)
    _concat_videos_ffmpeg(ffmpeg=ffmpeg, inputs=scene_paths, out_path=out.path)

    return {
        "ok": True,
        "spec_path": str(spec_path),
        "output": {
            "path": str(out.path),
            "width": out.width,
            "height": out.height,
            "fps": out.fps,
        },
        "tmp_dir": str(tmp_dir),
        "notes": {
            "fontfile": fontfile,
            "backend": "ffmpeg",
        },
    }


def _ffprobe_duration_seconds(*, ffprobe: str, input_path: Path) -> Optional[float]:
    probe = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
    )
    if probe.returncode != 0:
        return None
    try:
        return float((probe.stdout or "").strip())
    except Exception:
        return None


def _ffprobe_has_audio(*, ffprobe: str, input_path: Path) -> bool:
    probe = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(input_path),
        ]
    )
    return probe.returncode == 0 and bool((probe.stdout or "").strip())


def _detect_silence_intervals(
    *,
    ffmpeg: str,
    input_path: Path,
    duration_sec: Optional[float],
    silence_threshold_db: float,
    min_silence_sec: float,
) -> List[Tuple[float, float]]:
    # silencedetect logs to stderr; we parse it to find silent ranges.
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        f"silencedetect=n={silence_threshold_db}dB:d={min_silence_sec}",
        "-f",
        "null",
        "-",
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg silencedetect failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )

    intervals: List[Tuple[float, float]] = []
    current_start: Optional[float] = None
    for line in (result.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*(?P<start>[0-9.]+)", line)
        if m:
            try:
                current_start = float(m.group("start"))
            except Exception:
                current_start = None
            continue

        m = re.search(r"silence_end:\s*(?P<end>[0-9.]+)", line)
        if m and current_start is not None:
            try:
                end = float(m.group("end"))
            except Exception:
                end = None
            if end is not None and end >= current_start:
                intervals.append((current_start, end))
            current_start = None

    # If the file ends during a silence_start, treat it as silence until end.
    if current_start is not None and duration_sec and duration_sec >= current_start:
        intervals.append((current_start, duration_sec))

    return intervals


def _compute_keep_segments(
    *,
    duration_sec: float,
    silences: List[Tuple[float, float]],
    pad_sec: float,
    min_keep_sec: float,
) -> List[Tuple[float, float]]:
    if duration_sec <= 0:
        return []

    keep: List[Tuple[float, float]] = []
    cur = 0.0
    for s_start, s_end in silences:
        # We cut the middle of the silent interval, leaving a tiny padding around it.
        cut_start = min(duration_sec, max(0.0, s_start + pad_sec))
        cut_end = min(duration_sec, max(0.0, s_end - pad_sec))
        if cut_end <= cut_start:
            continue
        if cut_start - cur >= min_keep_sec:
            keep.append((cur, cut_start))
        cur = max(cur, cut_end)

    if duration_sec - cur >= min_keep_sec:
        keep.append((cur, duration_sec))

    return keep


def jumpcut_video(
    *,
    input_path: Path,
    output_path: Path,
    silence_threshold_db: float,
    min_silence_sec: float,
    pad_sec: float,
    min_keep_sec: float,
    preset: str,
    crf: int,
    audio_bitrate: str,
) -> Dict[str, Any]:
    env = probe_environment()
    ffmpeg = env["ffmpeg"]["path"]
    ffprobe = env["ffprobe"]["path"]
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install it first, then re-run.\n"
            f"Hint (Windows): {env['install_hints']['ffmpeg_windows_choco']}"
        )
    if not ffprobe:
        raise RuntimeError("ffprobe not found (required for jumpcut)")

    if not input_path.exists():
        raise FileNotFoundError(str(input_path))
    _ensure_parent(output_path)

    if not _ffprobe_has_audio(ffprobe=ffprobe, input_path=input_path):
        raise RuntimeError("Input has no audio stream; jumpcut needs audio to detect silence.")

    duration = _ffprobe_duration_seconds(ffprobe=ffprobe, input_path=input_path)
    if not duration:
        raise RuntimeError("Failed to probe input duration via ffprobe.")

    silences = _detect_silence_intervals(
        ffmpeg=ffmpeg,
        input_path=input_path,
        duration_sec=duration,
        silence_threshold_db=silence_threshold_db,
        min_silence_sec=min_silence_sec,
    )
    keep_segments = _compute_keep_segments(
        duration_sec=duration,
        silences=silences,
        pad_sec=pad_sec,
        min_keep_sec=min_keep_sec,
    )
    if not keep_segments:
        raise RuntimeError("No keep segments found; adjust silence threshold/min duration/pad.")

    tmp_dir = Path("outputs/video-studio/tmp") / f"jumpcut_{_now_ms()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: List[Path] = []
    for i, (start, end) in enumerate(keep_segments):
        seg_dur = max(0.0, end - start)
        seg_out = tmp_dir / f"seg_{i:03d}.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{seg_dur:.3f}",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            preset,
            "-crf",
            str(int(crf)),
            "-c:a",
            "aac",
            "-b:a",
            str(audio_bitrate),
            "-movflags",
            "+faststart",
            str(seg_out),
        ]
        result = _run(cmd)
        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg segment render failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
            )
        segment_paths.append(seg_out)

    _concat_videos_ffmpeg(ffmpeg=ffmpeg, inputs=segment_paths, out_path=output_path)

    return {
        "ok": True,
        "in": str(input_path),
        "out": str(output_path),
        "duration_sec": duration,
        "silences_detected": len(silences),
        "segments_kept": len(keep_segments),
        "tmp_dir": str(tmp_dir),
    }


def burn_subtitles(
    *,
    input_path: Path,
    srt_path: Path,
    output_path: Path,
    font_name: str,
    font_size: int,
    margin_v: int,
    outline: int,
    shadow: int,
    preset: str,
    crf: int,
) -> Dict[str, Any]:
    env = probe_environment()
    ffmpeg = env["ffmpeg"]["path"]
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install it first, then re-run.\n"
            f"Hint (Windows): {env['install_hints']['ffmpeg_windows_choco']}"
        )
    if not input_path.exists():
        raise FileNotFoundError(str(input_path))
    if not srt_path.exists():
        raise FileNotFoundError(str(srt_path))
    _ensure_parent(output_path)

    # subtitles filter uses ":"-separated options; escape Windows drive letters ("C:/...") colons.
    srt_filter_path = _escape_drawtext(srt_path.resolve().as_posix())
    force_style = (
        f"FontName={font_name},FontSize={int(font_size)},"
        f"Alignment=2,MarginV={int(margin_v)},Outline={int(outline)},Shadow={int(shadow)}"
    )
    style_escaped = _escape_drawtext(force_style)
    vf = f"subtitles='{srt_filter_path}':force_style='{style_escaped}'"

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        preset,
        "-crf",
        str(int(crf)),
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg subtitles burn-in failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )

    return {"ok": True, "in": str(input_path), "srt": str(srt_path), "out": str(output_path)}


def polish_video(input_path: Path, output_path: Path, enable_loudnorm: bool, enable_fade: bool, fade_in: float, fade_out: float) -> Dict[str, Any]:
    env = probe_environment()
    ffmpeg = env["ffmpeg"]["path"]
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install it first, then re-run.\n"
            f"Hint (Windows): {env['install_hints']['ffmpeg_windows_choco']}"
        )

    if not input_path.exists():
        raise FileNotFoundError(str(input_path))
    _ensure_parent(output_path)

    vf_filters: List[str] = []
    af_filters: List[str] = []
    if enable_fade:
        # Fade in/out for both video+audio. Duration is inferred from input.
        # For audio, we use afade with st=0 for fade-in, and fade-out from (duration - fade_out).
        vf_filters.append(f"fade=t=in:st=0:d={fade_in}")
        # For fade-out, we need duration. Use a first pass via ffprobe when available.
        duration = None
        ffprobe = env["ffprobe"]["path"]
        if ffprobe:
            probe = _run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(input_path),
                ]
            )
            if probe.returncode == 0:
                try:
                    duration = float((probe.stdout or "").strip())
                except Exception:
                    duration = None
        if duration and duration > (fade_out + 0.05):
            st = max(0.0, duration - fade_out)
            vf_filters.append(f"fade=t=out:st={st}:d={fade_out}")
            af_filters.append(f"afade=t=out:st={st}:d={fade_out}")
        af_filters.append(f"afade=t=in:st=0:d={fade_in}")

    if enable_loudnorm:
        af_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

    vf = ",".join(vf_filters) if vf_filters else "null"
    af = ",".join(af_filters) if af_filters else "anull"

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-af",
        af,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg polish failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )

    return {"ok": True, "in": str(input_path), "out": str(output_path)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="video_studio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("probe", help="Probe env (ffmpeg/node/vectcut reachability) and print JSON")

    p_render = sub.add_parser("render", help="Render a simple text-based video from a JSON spec using FFmpeg")
    p_render.add_argument("--spec", required=True, help="Path to spec.json")

    p_polish = sub.add_parser("polish", help="Polish a rendered video (encode, loudnorm, fade)")
    p_polish.add_argument("--in", dest="inp", required=True, help="Input video path")
    p_polish.add_argument("--out", dest="out", required=True, help="Output video path")
    p_polish.add_argument("--no-loudnorm", action="store_true", help="Disable loudnorm")
    p_polish.add_argument("--no-fade", action="store_true", help="Disable fade in/out")
    p_polish.add_argument("--fade-in", type=float, default=0.15, help="Fade-in seconds")
    p_polish.add_argument("--fade-out", type=float, default=0.2, help="Fade-out seconds")

    p_jumpcut = sub.add_parser("jumpcut", help="Auto-cut silence from a talking-head video (jump cut)")
    p_jumpcut.add_argument("--in", dest="inp", required=True, help="Input video path")
    p_jumpcut.add_argument("--out", dest="out", required=True, help="Output video path")
    p_jumpcut.add_argument("--silence-threshold-db", type=float, default=-35.0, help="Silence threshold in dB (e.g. -35)")
    p_jumpcut.add_argument("--min-silence", type=float, default=0.4, help="Min silence duration in seconds")
    p_jumpcut.add_argument("--pad", type=float, default=0.06, help="Padding kept around silences (seconds)")
    p_jumpcut.add_argument("--min-keep", type=float, default=0.12, help="Discard keep segments shorter than this (seconds)")
    p_jumpcut.add_argument("--preset", default="veryfast", help="x264 preset")
    p_jumpcut.add_argument("--crf", type=int, default=18, help="x264 CRF (lower=better, bigger file)")
    p_jumpcut.add_argument("--audio-bitrate", default="192k", help="AAC bitrate for segments")

    p_burn = sub.add_parser("burn-subtitles", help="Burn subtitles (SRT) into a video using FFmpeg/libass")
    p_burn.add_argument("--in", dest="inp", required=True, help="Input video path")
    p_burn.add_argument("--srt", required=True, help="Subtitle .srt path")
    p_burn.add_argument("--out", dest="out", required=True, help="Output video path")
    p_burn.add_argument("--font", default="Arial", help="Subtitle font name")
    p_burn.add_argument("--font-size", type=int, default=42, help="Subtitle font size")
    p_burn.add_argument("--margin-v", type=int, default=80, help="Bottom margin (px)")
    p_burn.add_argument("--outline", type=int, default=2, help="Subtitle outline size")
    p_burn.add_argument("--shadow", type=int, default=0, help="Subtitle shadow size")
    p_burn.add_argument("--preset", default="veryfast", help="x264 preset")
    p_burn.add_argument("--crf", type=int, default=18, help="x264 CRF")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "probe":
            _print_json(probe_environment())
            return 0
        if args.cmd == "render":
            spec_path = Path(args.spec)
            result = render_from_spec(spec_path)
            _print_json(result)
            return 0
        if args.cmd == "polish":
            result = polish_video(
                input_path=Path(args.inp),
                output_path=Path(args.out),
                enable_loudnorm=not args.no_loudnorm,
                enable_fade=not args.no_fade,
                fade_in=float(args.fade_in),
                fade_out=float(args.fade_out),
            )
            _print_json(result)
            return 0
        if args.cmd == "jumpcut":
            result = jumpcut_video(
                input_path=Path(args.inp),
                output_path=Path(args.out),
                silence_threshold_db=float(args.silence_threshold_db),
                min_silence_sec=float(args.min_silence),
                pad_sec=float(args.pad),
                min_keep_sec=float(args.min_keep),
                preset=str(args.preset),
                crf=int(args.crf),
                audio_bitrate=str(args.audio_bitrate),
            )
            _print_json(result)
            return 0
        if args.cmd == "burn-subtitles":
            result = burn_subtitles(
                input_path=Path(args.inp),
                srt_path=Path(args.srt),
                output_path=Path(args.out),
                font_name=str(args.font),
                font_size=int(args.font_size),
                margin_v=int(args.margin_v),
                outline=int(args.outline),
                shadow=int(args.shadow),
                preset=str(args.preset),
                crf=int(args.crf),
            )
            _print_json(result)
            return 0
    except Exception as e:
        _print_json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        return 2

    _print_json({"ok": False, "error": "unreachable"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
