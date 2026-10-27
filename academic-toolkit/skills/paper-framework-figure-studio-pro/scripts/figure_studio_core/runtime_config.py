"""Runtime environment capability and hard image-generation route policy.

This module is intentionally paper-agnostic.  It validates only *how* target
paper images are produced, never *what* a particular paper should show.
"""

from __future__ import annotations

from typing import Any

from .constants import IMAGE_GENERATION_ROUTE_ALIASES, RUNTIME_ENVIRONMENT_ALIASES
from .errors import StateError

CANONICAL_BUILTIN_GENERATOR = "image_gen"
CANONICAL_WEB_CHAT_GENERATOR = "create-image"
CANONICAL_APPROVED_API_GENERATOR = "approved-image-api"

# Legacy generator labels are accepted only to normalize older state/CLI
# vocabulary into the canonical generator names used by the route guard.
GENERATOR_ALIASES = {
    "imagegen": CANONICAL_BUILTIN_GENERATOR,
    "image-gen": CANONICAL_BUILTIN_GENERATOR,
    "image_gen": CANONICAL_BUILTIN_GENERATOR,
    "create-image": CANONICAL_WEB_CHAT_GENERATOR,
    "create_image": CANONICAL_WEB_CHAT_GENERATOR,
    "approved-image-api": CANONICAL_APPROVED_API_GENERATOR,
    "approved_image_api": CANONICAL_APPROVED_API_GENERATOR,
}

# Legacy generator labels may carry an environment prefix; match the generic
# route token so old state normalizes without hard-coding vendor names.
LEGACY_GENERATOR_TOKENS = (
    ("imagegen", CANONICAL_BUILTIN_GENERATOR),
    ("image-gen", CANONICAL_BUILTIN_GENERATOR),
    ("image_gen", CANONICAL_BUILTIN_GENERATOR),
    ("create-image", CANONICAL_WEB_CHAT_GENERATOR),
    ("create_image", CANONICAL_WEB_CHAT_GENERATOR),
    ("approved-image", CANONICAL_APPROVED_API_GENERATOR),
    ("approved_image", CANONICAL_APPROVED_API_GENERATOR),
)

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

# Legacy route labels are accepted only for migrating existing state; new state
# writes capability values.
ROUTE_ALIASES = {
    **IMAGE_GENERATION_ROUTE_ALIASES,
    "image_gen": "builtin_image_gen",
    "imagegen": "builtin_image_gen",
    "image-gen": "builtin_image_gen",
    "create-image": "web_image_chat",
    "create_image": "web_image_chat",
    "approved-image-api": "approved_api",
}


def normalize_runtime_environment(environment: str | None) -> str:
    """Return the canonical capability value for a runtime environment label."""
    value = (environment or "unknown").strip().lower() or "unknown"
    return RUNTIME_ENVIRONMENT_ALIASES.get(value, value)


def canonicalize_generator(generator: str | None) -> str:
    """Return the canonical target-image generator name or raise on denied routes."""
    value = (generator or "").strip()
    if not value:
        raise StateError("target-paper image generation must record a generator")
    key = value.lower().replace(" ", "-")
    key = key.replace("/", "-")
    if key in PROGRAMMATIC_GENERATOR_DENYLIST:
        raise StateError(
            f"forbidden target-image generator route: {generator!r}; use the built-in image route (image_gen), "
            "the web chat image route (create-image), or a named approved image-generation API only in an "
            "environment where those routes are unavailable"
        )
    if key in GENERATOR_ALIASES:
        return GENERATOR_ALIASES[key]
    for token, target in LEGACY_GENERATOR_TOKENS:
        if token in key:
            return target
    raise StateError(
        f"unknown target-image generator route: {generator!r}; allowed canonical values are "
        f"{CANONICAL_BUILTIN_GENERATOR}, {CANONICAL_WEB_CHAT_GENERATOR}, or {CANONICAL_APPROVED_API_GENERATOR}"
    )


def infer_image_generation_route(environment: str, explicit_route: str | None) -> str:
    env = normalize_runtime_environment(environment)
    if explicit_route:
        route = explicit_route.strip().lower()
        return ROUTE_ALIASES.get(route, route)
    if env == "builtin_image_gen":
        return "builtin_image_gen"
    if env == "web_image_chat":
        return "web_image_chat"
    if env == "approved_api":
        return "approved_api"
    return "unknown"


def required_generator_for_environment(environment: str) -> str | None:
    env = normalize_runtime_environment(environment)
    if env == "builtin_image_gen":
        return CANONICAL_BUILTIN_GENERATOR
    if env == "web_image_chat":
        return CANONICAL_WEB_CHAT_GENERATOR
    if env == "approved_api":
        return CANONICAL_APPROVED_API_GENERATOR
    return None


def default_image_generation_note(environment: str) -> str:
    env = normalize_runtime_environment(environment)
    if env == "builtin_image_gen":
        return (
            "The built-in image-generation tool must be used through the image_gen route for every target-paper "
            "sketch and formal candidate. Generate each image separately. "
            "Python/PIL/Matplotlib/Graphviz/TikZ/Mermaid/canvas screenshots/SVG-to-PNG/PPT-rendered/programmatic "
            "raster PNGs are invalid substitutes."
        )
    if env == "web_image_chat":
        return (
            "The web chat image-generation surface must be used through the create-image route for every "
            "target-paper sketch and formal candidate. Generate each image separately. "
            "Do not satisfy an image unit by writing SVG/HTML/Mermaid/canvas/PPT/PDF or by rendering any local "
            "raster file."
        )
    if env == "approved_api":
        return (
            "Use a named approved image-generation API only when neither the built-in route nor the web chat "
            "route is available; record the API name and unavailability reason. Programmatic drawing or renderer "
            "output is never an approved image API."
        )
    return (
        "Resolve runtime capability before image steps: builtin_image_gen => image_gen only; "
        "web_image_chat => create-image only; approved_api => named approved image-generation API. "
        "Do not generate target images with code, SVG, screenshots, or local renderers."
    )


def runtime_environment_note(environment: str) -> str:
    return (
        "Use text replies plus direct Markdown image embeds for saved atlas boards; "
        "generated web pages are not produced."
    )


def validate_image_generation_route(
    *,
    environment: str | None,
    generator: str | None,
    approved_api_name: str | None = None,
    route_unavailable_reason: str | None = None,
) -> dict[str, Any]:
    """Validate the capability-locked generator for a target-paper image unit.

    Returns a small provenance payload that can be stored in state. The function
    rejects all programmatic/local renderer routes even when they produce a PNG.
    """
    raw_env = (environment or "unknown").strip() or "unknown"
    env = normalize_runtime_environment(raw_env)
    canonical = canonicalize_generator(generator)
    if env == "none":
        raise StateError(
            "runtime_environment.environment=none blocks target-paper IMAGE_* units; configure "
            "builtin_image_gen, web_image_chat, or approved_api before recording image generation"
        )
    required = required_generator_for_environment(env)
    if required is None:
        raise StateError(
            "runtime_environment.environment must be configured before target-paper IMAGE_* units; "
            "set it to builtin_image_gen, web_image_chat, or approved_api before recording image generation"
        )
    if env == "builtin_image_gen" and canonical != CANONICAL_BUILTIN_GENERATOR:
        raise StateError(
            "builtin_image_gen target-paper image units must call image_gen. Do not use create-image, SVG, "
            "Python/PIL, Matplotlib, Graphviz, TikZ, Mermaid, canvas, PPT/PDF, screenshots, or local raster renderers."
        )
    if env == "web_image_chat" and canonical != CANONICAL_WEB_CHAT_GENERATOR:
        raise StateError(
            "web_image_chat target-paper image units must use create-image. Do not output SVG, HTML, Mermaid, "
            "canvas, PPT/PDF, Python/PIL, Matplotlib, or any locally rendered raster substitute."
        )
    if env == "approved_api":
        if canonical != CANONICAL_APPROVED_API_GENERATOR:
            raise StateError(
                f"environment={env} must use a named approved image-generation API for target images; "
                "programmatic renderers and route aliases from another capability are invalid."
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
            "builtin_image_gen=image_gen only; web_image_chat=create-image only; approved_api=approved-image-api only; "
            "programmatic/local renderer outputs are invalid even when saved as PNG/JPG/WebP."
        ),
    }
