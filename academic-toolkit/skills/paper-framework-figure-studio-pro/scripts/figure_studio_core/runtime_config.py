"""Runtime environment and hard image-generation route policy.

This module is intentionally paper-agnostic.  It validates only *how* target
paper images are produced, never *what* a particular paper should show.
"""

from __future__ import annotations

from typing import Any

from .errors import StateError

CANONICAL_CODEX_GENERATOR = "image_gen"
CANONICAL_CHATGPT_WEB_GENERATOR = "create-image"
CANONICAL_APPROVED_API_GENERATOR = "approved-image-api"

# Aliases are accepted only to normalize older state/CLI vocabulary into the
# canonical generator names used by the v3.2.5 route guard.
GENERATOR_ALIASES = {
    "imagegen": CANONICAL_CODEX_GENERATOR,
    "image-gen": CANONICAL_CODEX_GENERATOR,
    "image_gen": CANONICAL_CODEX_GENERATOR,
    "codex-imagegen": CANONICAL_CODEX_GENERATOR,
    "codex-image-gen": CANONICAL_CODEX_GENERATOR,
    "codex_imagegen": CANONICAL_CODEX_GENERATOR,
    "codex_image_gen": CANONICAL_CODEX_GENERATOR,
    "create-image": CANONICAL_CHATGPT_WEB_GENERATOR,
    "create_image": CANONICAL_CHATGPT_WEB_GENERATOR,
    "chatgpt-create-image": CANONICAL_CHATGPT_WEB_GENERATOR,
    "chatgpt_create_image": CANONICAL_CHATGPT_WEB_GENERATOR,
    "chatgpt-web-create-image": CANONICAL_CHATGPT_WEB_GENERATOR,
    "approved-image-api": CANONICAL_APPROVED_API_GENERATOR,
    "approved_image_api": CANONICAL_APPROVED_API_GENERATOR,
}

PROGRAMMATIC_GENERATOR_DENYLIST = {
    "python",
    "pil",
    "pillow",
    "matplotlib",
    "plotly",
    "graphviz",
    "tikz",
    "latex",
    "mermaid",
    "svg",
    "svg-to-png",
    "canvas",
    "html",
    "ppt",
    "pptx",
    "pdf",
    "screenshot",
    "browser-render",
    "programmatic-raster",
    "local-renderer",
}


def canonicalize_generator(generator: str | None) -> str:
    """Return the canonical target-image generator name or raise on denied routes."""
    value = (generator or "").strip()
    if not value:
        raise StateError("target-paper image generation must record a generator")
    key = value.lower().replace(" ", "-")
    key = key.replace("/", "-")
    if key in PROGRAMMATIC_GENERATOR_DENYLIST:
        raise StateError(
            f"forbidden target-image generator route: {generator!r}; use Codex image_gen, ChatGPT web Create Image, "
            "or a named approved image-generation API only in an environment where first-party routes are unavailable"
        )
    if key in GENERATOR_ALIASES:
        return GENERATOR_ALIASES[key]
    raise StateError(
        f"unknown target-image generator route: {generator!r}; allowed canonical values are "
        f"{CANONICAL_CODEX_GENERATOR}, {CANONICAL_CHATGPT_WEB_GENERATOR}, or {CANONICAL_APPROVED_API_GENERATOR}"
    )


def infer_image_generation_route(environment: str, explicit_route: str | None) -> str:
    if explicit_route:
        route = explicit_route.strip()
        if route == "codex_imagegen":
            return "codex_image_gen"
        if route == "chatgpt_create_image":
            return "chatgpt_create_image"
        if route == "approved_image_api":
            return "approved_image_api"
        return route
    if environment == "chatgpt_web":
        return "chatgpt_create_image"
    if environment == "codex":
        return "codex_image_gen"
    if environment in {"claude_code", "other"}:
        return "user_supplied_api_required"
    return "unknown"


def required_generator_for_environment(environment: str) -> str | None:
    if environment == "codex":
        return CANONICAL_CODEX_GENERATOR
    if environment == "chatgpt_web":
        return CANONICAL_CHATGPT_WEB_GENERATOR
    if environment in {"claude_code", "other"}:
        return CANONICAL_APPROVED_API_GENERATOR
    return None


def default_image_generation_note(environment: str) -> str:
    if environment == "codex":
        return (
            "Codex must call Image Gen through the codex image_gen route for every target-paper sketch and formal candidate. "
            "Generate each image separately. "
            "Python/PIL/Matplotlib/Graphviz/TikZ/Mermaid/canvas screenshots/SVG-to-PNG/PPT-rendered/programmatic raster PNGs are invalid substitutes."
        )
    if environment == "chatgpt_web":
        return (
            "ChatGPT web must use Create Image / ChatGPT Images 2.0 for every target-paper sketch and formal candidate. "
            "Generate each image separately. "
            "Do not satisfy an image unit by writing SVG/HTML/Mermaid/canvas/PPT/PDF or by rendering any local raster file."
        )
    if environment in {"claude_code", "other"}:
        return (
            "Use a named approved image-generation API only when neither Codex image_gen nor ChatGPT web Create Image is available; "
            "record the API name and unavailability reason. Programmatic drawing or renderer output is never an approved image API."
        )
    return (
        "Resolve runtime before image steps: Codex => image_gen only; ChatGPT web => Create Image / ChatGPT Images 2.0 only; "
        "other runtimes require a named approved image-generation API. Do not generate target images with code, SVG, screenshots, or local renderers."
    )


def runtime_environment_note(environment: str) -> str:
    if environment == "codex":
        return "Codex uses text replies plus direct Markdown image embeds for saved atlas boards; generated web pages are not produced."
    if environment == "chatgpt_web":
        return "ChatGPT web uses text replies plus direct Markdown image embeds for saved atlas boards; generated web pages are not produced."
    return "Use text replies plus direct atlas-board image embeds when package assets are available; generated web pages are not produced."


def validate_image_generation_route(
    *,
    environment: str | None,
    generator: str | None,
    approved_api_name: str | None = None,
    route_unavailable_reason: str | None = None,
) -> dict[str, Any]:
    """Validate the environment-locked generator for a target-paper image unit.

    Returns a small provenance payload that can be stored in state. The function
    rejects all programmatic/local renderer routes even when they produce a PNG.
    """
    env = (environment or "unknown").strip() or "unknown"
    canonical = canonicalize_generator(generator)
    required = required_generator_for_environment(env)
    if required is None:
        raise StateError(
            "runtime_environment.environment must be configured before target-paper IMAGE_* units; "
            "set it to codex, chatgpt_web, claude_code, or other before recording image generation"
        )
    if env == "codex" and canonical != CANONICAL_CODEX_GENERATOR:
        raise StateError(
            "Codex target-paper image units must call image_gen. Do not use create-image, SVG, Python/PIL, "
            "Matplotlib, Graphviz, TikZ, Mermaid, canvas, PPT/PDF, screenshots, or local raster renderers."
        )
    if env == "chatgpt_web" and canonical != CANONICAL_CHATGPT_WEB_GENERATOR:
        raise StateError(
            "ChatGPT web target-paper image units must use Create Image / ChatGPT Images 2.0. Do not output SVG, "
            "HTML, Mermaid, canvas, PPT/PDF, Python/PIL, Matplotlib, or any locally rendered raster substitute."
        )
    if env in {"claude_code", "other"}:
        if canonical != CANONICAL_APPROVED_API_GENERATOR:
            raise StateError(
                f"environment={env} must use a named approved image-generation API for target images; "
                "programmatic renderers and first-party route aliases from another runtime are invalid."
            )
        if not approved_api_name:
            raise StateError("approved_api_name is required for approved-image-api target generation")
        api_key = approved_api_name.strip().lower().replace(" ", "-")
        if api_key in PROGRAMMATIC_GENERATOR_DENYLIST:
            raise StateError(
                f"approved_api_name={approved_api_name!r} names a forbidden programmatic/local renderer, not an image-generation API"
            )
        if not route_unavailable_reason:
            raise StateError(
                "route_unavailable_reason is required when using an approved image-generation API fallback"
            )
    return {
        "environment": env,
        "generator": canonical,
        "required_generator": required,
        "approved_api_name": approved_api_name or None,
        "route_unavailable_reason": route_unavailable_reason or None,
        "route_guard_status": "passed",
        "route_guard_rule": (
            "Codex=image_gen only; ChatGPT web=Create Image / ChatGPT Images 2.0 only; other runtimes require a named approved "
            "image-generation API; programmatic/local renderer outputs are invalid even when saved as PNG/JPG/WebP."
        ),
    }
