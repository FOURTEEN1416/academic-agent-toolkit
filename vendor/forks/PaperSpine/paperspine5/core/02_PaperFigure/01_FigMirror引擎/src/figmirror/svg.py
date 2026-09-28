"""Semantic SVG renderer and editability/security auditor."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

ALLOWED_ELEMENT_TYPES = {"rect", "ellipse", "circle", "line", "arrow", "polyline", "path", "text"}
STYLE_ATTRIBUTES = {
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-dasharray",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "font-family",
    "font-size",
    "font-weight",
    "text-anchor",
    "dominant-baseline",
    "letter-spacing",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass
class SvgAudit:
    status: str
    path: str
    element_count: int = 0
    text_count: int = 0
    group_count: int = 0
    named_group_count: int = 0
    connector_count: int = 0
    connector_metadata_count: int = 0
    raster_image_count: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_svg(
    path: str | Path,
    *,
    allow_raster: bool = False,
    require_text: bool = False,
    require_named_groups: bool = False,
    require_connector_metadata: bool = False,
) -> SvgAudit:
    svg_path = Path(path)
    audit = SvgAudit(status="PASS", path=str(svg_path.resolve()))
    if not svg_path.is_file():
        audit.failures.append("SVG file does not exist")
        audit.status = "FAIL"
        return audit
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as exc:
        audit.failures.append(f"invalid XML: {exc}")
        audit.status = "FAIL"
        return audit
    if _local_name(root.tag) != "svg":
        audit.failures.append("root element is not <svg>")
    if not root.get("viewBox"):
        audit.failures.append("SVG has no viewBox")

    ids: set[str] = set()
    for element in root.iter():
        name = _local_name(element.tag)
        audit.element_count += 1
        if name == "text":
            audit.text_count += 1
        elif name == "g":
            audit.group_count += 1
            if element.get("id"):
                audit.named_group_count += 1
        elif name == "image":
            audit.raster_image_count += 1
        if element.get("marker-end") or element.get("data-connector") == "true":
            audit.connector_count += 1
            if element.get("data-source") and element.get("data-target"):
                audit.connector_metadata_count += 1
        if name in {"script", "foreignObject"}:
            audit.failures.append(f"unsafe or non-portable <{name}> element")
        element_id = element.get("id")
        if element_id:
            if element_id in ids:
                audit.failures.append(f"duplicate id: {element_id}")
            ids.add(element_id)
        for attr, value in element.attrib.items():
            attr_name = _local_name(attr)
            embedded_raster = (
                allow_raster
                and name == "image"
                and attr_name in {"href", "src"}
                and value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,"))
            )
            if attr_name in {"href", "src"} and value and not value.startswith("#") and not embedded_raster:
                audit.failures.append(f"external or unsupported embedded resource is not allowed: {value[:80]}")
            if attr_name.startswith("on"):
                audit.failures.append(f"event handler attribute is not allowed: {attr_name}")
    if audit.raster_image_count and not allow_raster:
        audit.failures.append("SVG contains raster <image>; it is not fully editable")
    if require_text and audit.text_count == 0:
        audit.failures.append("SVG contains no editable <text> elements")
    if audit.group_count == 0:
        audit.warnings.append("SVG contains no named groups/layers")
    elif audit.named_group_count == 0:
        audit.warnings.append("SVG groups have no stable ids")
    if require_named_groups and audit.named_group_count == 0:
        audit.failures.append("SVG contains no groups with stable ids")
    if require_connector_metadata:
        if audit.connector_count == 0:
            audit.failures.append("SVG contains no arrow connectors")
        elif audit.connector_metadata_count != audit.connector_count:
            audit.failures.append("one or more arrow connectors lack data-source/data-target metadata")
    if audit.failures:
        audit.status = "FAIL"
    return audit


def _safe_id(value: Any, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")
    return cleaned or fallback


def _attributes(element: dict[str, Any], keys: tuple[str, ...]) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key in keys:
        if key in element:
            attrs[key.replace("_", "-")] = str(element[key])
    style = element.get("style", {})
    if isinstance(style, dict):
        for key, value in style.items():
            css_key = key.replace("_", "-")
            if css_key in STYLE_ATTRIBUTES:
                attrs[css_key] = str(value)
    return attrs


def _add_element(parent: ET.Element, element: dict[str, Any], index: int) -> None:
    element_type = str(element.get("type") or "").strip()
    if element_type not in ALLOWED_ELEMENT_TYPES:
        raise ValueError(f"unsupported scene element type: {element_type!r}")
    element_id = _safe_id(element.get("id"), f"element-{index}")
    common = {"id": element_id, "data-editable": "true"}
    if element_type == "arrow":
        attrs = _attributes(element, ("x1", "y1", "x2", "y2"))
        attrs.setdefault("fill", "none")
        attrs.setdefault("stroke", "#24313a")
        attrs.setdefault("stroke-width", "2")
        attrs["marker-end"] = "url(#figmirror-arrow)"
        ET.SubElement(parent, f"{{{SVG_NS}}}line", {**common, **attrs})
        return
    if element_type == "text":
        attrs = _attributes(element, ("x", "y", "dx", "dy", "transform"))
        attrs.setdefault("fill", "#172027")
        attrs.setdefault("font-family", "Segoe UI, Microsoft YaHei UI, sans-serif")
        attrs.setdefault("font-size", "18")
        node = ET.SubElement(parent, f"{{{SVG_NS}}}text", {**common, **attrs})
        node.text = str(element.get("text") or "")
        return
    keys_by_type = {
        "rect": ("x", "y", "width", "height", "rx", "ry", "transform"),
        "ellipse": ("cx", "cy", "rx", "ry", "transform"),
        "circle": ("cx", "cy", "r", "transform"),
        "line": ("x1", "y1", "x2", "y2", "transform"),
        "polyline": ("points", "transform"),
        "path": ("d", "transform"),
    }
    attrs = _attributes(element, keys_by_type[element_type])
    attrs.setdefault("fill", "none" if element_type in {"line", "polyline", "path"} else "#ffffff")
    attrs.setdefault("stroke", "#24313a")
    attrs.setdefault("stroke-width", "2")
    ET.SubElement(parent, f"{{{SVG_NS}}}{element_type}", {**common, **attrs})


def render_scene(scene: dict[str, Any], output: str | Path) -> Path:
    """Render a semantic scene JSON object to a grouped, editable SVG."""

    width = int(scene.get("width", 1200))
    height = int(scene.get("height", 720))
    if width <= 0 or height <= 0:
        raise ValueError("scene width and height must be positive")
    layers = scene.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("scene must contain at least one layer")
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "viewBox": f"0 0 {width} {height}",
            "width": str(width),
            "height": str(height),
            "role": "img",
            "data-figmirror-format": "semantic-svg-v1",
        },
    )
    title = ET.SubElement(root, f"{{{SVG_NS}}}title", {"id": "figure-title"})
    title.text = str(scene.get("title") or "FigMirror schematic")
    description = ET.SubElement(root, f"{{{SVG_NS}}}desc", {"id": "figure-description"})
    description.text = str(scene.get("description") or "Editable semantic schematic generated by FigMirror")
    metadata = ET.SubElement(root, f"{{{SVG_NS}}}metadata")
    metadata.text = str(scene.get("provenance") or "FigMirror semantic scene; consult manifest for full provenance")
    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    marker = ET.SubElement(
        defs,
        f"{{{SVG_NS}}}marker",
        {
            "id": "figmirror-arrow",
            "viewBox": "0 0 10 10",
            "refX": "9",
            "refY": "5",
            "markerWidth": "7",
            "markerHeight": "7",
            "orient": "auto-start-reverse",
        },
    )
    ET.SubElement(marker, f"{{{SVG_NS}}}path", {"d": "M 0 0 L 10 5 L 0 10 z", "fill": "context-stroke"})
    root.set("aria-labelledby", "figure-title figure-description")

    element_index = 0
    used_layers: set[str] = set()
    for layer_index, layer in enumerate(layers, start=1):
        if not isinstance(layer, dict):
            raise ValueError("each scene layer must be an object")
        layer_id = _safe_id(layer.get("id"), f"layer-{layer_index}")
        if layer_id in used_layers:
            raise ValueError(f"duplicate scene layer id: {layer_id}")
        used_layers.add(layer_id)
        group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": layer_id, "data-layer-name": str(layer.get("name") or layer_id)})
        elements = layer.get("elements", [])
        if not isinstance(elements, list):
            raise ValueError(f"layer {layer_id} elements must be a list")
        for element in elements:
            if not isinstance(element, dict):
                raise ValueError(f"layer {layer_id} contains a non-object element")
            element_index += 1
            _add_element(group, element, element_index)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    audit = audit_svg(output_path, allow_raster=False)
    if audit.status != "PASS":
        raise ValueError(f"rendered SVG failed audit: {audit.failures}")
    return output_path
