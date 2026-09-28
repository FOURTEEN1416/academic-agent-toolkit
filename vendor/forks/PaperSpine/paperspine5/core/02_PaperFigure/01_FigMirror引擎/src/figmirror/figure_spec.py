"""Constraint-based FigureSpec layout, routing, rendering, and visual QA.

The module deliberately knows nothing about a specific paper or scientific
domain.  Agents describe a scientific story as semantic nodes, lanes, ports,
and edges.  FigMirror owns coordinates, compact layout, unambiguous routing,
editable SVG rendering, and measurable layout gates.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import unicodedata
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .svg import SVG_NS, audit_svg


FIGURE_SPEC_VERSION = "0.1"
NODE_KINDS = {"input", "process", "mechanism", "branch", "join", "output", "evidence", "illustration"}
EDGE_KINDS = {"primary", "support", "feedback", "association"}
PORTS = {"N", "E", "S", "W"}

KIND_STYLE = {
    "input": ("#E7F3F1", "#0F766E"),
    "process": ("#EDF2F7", "#40546A"),
    "mechanism": ("#FFF1E8", "#B4532A"),
    "branch": ("#F0EAF7", "#7A4E9D"),
    "join": ("#F0EAF7", "#7A4E9D"),
    "output": ("#E7F0FA", "#356DA5"),
    "evidence": ("#EEF6EC", "#4E8A55"),
    "illustration": ("#FFF7DD", "#A46B00"),
}
EDGE_STYLE = {
    "primary": ("#26343D", "3.0", None),
    "support": ("#66818C", "2.0", "7 5"),
    "feedback": ("#B4532A", "2.2", "8 5"),
    "association": ("#6B7280", "1.8", "3 5"),
}


@dataclass
class LayoutAudit:
    status: str
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float | int] = field(default_factory=dict)
    node_boxes: dict[str, list[float]] = field(default_factory=dict)
    lane_boxes: dict[str, list[float]] = field(default_factory=dict)
    edge_routes: dict[str, list[list[float]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return result


def _integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _identifier(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not result or any(char.isspace() for char in result):
        raise ValueError(f"{name} must be a non-empty identifier without spaces")
    return result


def _optional_color(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        return ""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", result):
        raise ValueError(f"{name} must be a six-digit hex color")
    return result.upper()


def _boolean(value: Any, name: str, *, default: bool) -> bool:
    """Accept only real JSON booleans so strings such as ``"false"`` do not flip truthiness."""

    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def validate_figure_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the general-purpose semantic figure contract."""

    if not isinstance(raw, dict):
        raise ValueError("FigureSpec root must be an object")
    spec = dict(raw)
    spec.setdefault("schema_version", FIGURE_SPEC_VERSION)
    if str(spec["schema_version"]) != FIGURE_SPEC_VERSION:
        raise ValueError(f"unsupported FigureSpec schema_version: {spec['schema_version']!r}")
    title = str(spec.get("title") or "").strip()
    if len(title) < 3:
        raise ValueError("FigureSpec title must contain at least 3 characters")
    spec["title"] = title
    spec["width"] = int(_number(spec.get("width", 1400), "width", minimum=640, maximum=4000))
    spec["height"] = int(_number(spec.get("height", 640), "height", minimum=360, maximum=3000))

    story = spec.get("story")
    if not isinstance(story, dict):
        raise ValueError("FigureSpec requires a story object")
    story = dict(story)
    claim = str(story.get("claim") or "").strip()
    if len(claim) < 12:
        raise ValueError("story.claim must contain at least 12 characters")
    story["claim"] = claim

    raw_lanes = spec.get("lanes")
    if not isinstance(raw_lanes, list) or not 1 <= len(raw_lanes) <= 4:
        raise ValueError("FigureSpec requires 1–4 lanes")
    lanes: list[dict[str, Any]] = []
    lane_ids: set[str] = set()
    for index, raw_lane in enumerate(raw_lanes):
        if not isinstance(raw_lane, dict):
            raise ValueError(f"lanes[{index}] must be an object")
        lane = dict(raw_lane)
        lane_id = _identifier(lane.get("id"), f"lanes[{index}].id")
        if lane_id in lane_ids:
            raise ValueError(f"duplicate lane id: {lane_id}")
        lane_ids.add(lane_id)
        lane["id"] = lane_id
        lane["label"] = str(lane.get("label") or lane_id)
        lane["role"] = str(lane.get("role") or ("main" if index == 0 else "support"))
        lane["order"] = int(lane.get("order", index))
        lane["show_frame"] = _boolean(lane.get("show_frame"), f"lane {lane_id} show_frame", default=True)
        lane["show_label"] = _boolean(lane.get("show_label"), f"lane {lane_id} show_label", default=True)
        lanes.append(lane)
    lanes.sort(key=lambda item: (int(item["order"]), item["id"]))
    spec["lanes"] = lanes

    raw_assets = spec.get("assets", [])
    if not isinstance(raw_assets, list) or len(raw_assets) > 30:
        raise ValueError("FigureSpec assets must be a list with at most 30 visual assets")
    assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    for index, raw_asset in enumerate(raw_assets):
        if not isinstance(raw_asset, dict):
            raise ValueError(f"assets[{index}] must be an object")
        asset_id = _identifier(raw_asset.get("id"), f"assets[{index}].id")
        path = str(raw_asset.get("path") or "").strip()
        asset_kind = str(raw_asset.get("kind") or raw_asset.get("type") or "vector").strip().lower()
        if asset_kind not in {"vector", "raster"}:
            raise ValueError(f"asset {asset_id} kind must be vector or raster")
        if asset_id in asset_ids or not path:
            raise ValueError("visual asset ids must be unique and each asset requires a path")
        asset_ids.add(asset_id)
        assets.append(
            {
                "id": asset_id,
                "path": path,
                "label": str(raw_asset.get("label") or asset_id),
                "kind": asset_kind,
                "role": str(raw_asset.get("role") or "scientific-illustration"),
            }
        )
    spec["assets"] = assets

    raw_nodes = spec.get("nodes")
    if not isinstance(raw_nodes, list) or not 2 <= len(raw_nodes) <= 40:
        raise ValueError("FigureSpec requires 2–40 nodes")
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            raise ValueError(f"nodes[{index}] must be an object")
        node = dict(raw_node)
        node_id = _identifier(node.get("id"), f"nodes[{index}].id")
        if node_id in node_ids:
            raise ValueError(f"duplicate node id: {node_id}")
        node_ids.add(node_id)
        lane_id = _identifier(node.get("lane"), f"nodes[{index}].lane")
        if lane_id not in lane_ids:
            raise ValueError(f"node {node_id} references unknown lane {lane_id}")
        kind = str(node.get("kind") or "process")
        if kind not in NODE_KINDS:
            raise ValueError(f"node {node_id} has unsupported kind {kind!r}")
        rank = node.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
            raise ValueError(f"node {node_id} rank must be a non-negative integer")
        label = str(node.get("label") or "").strip()
        if not label:
            raise ValueError(f"node {node_id} requires a label")
        visual_asset_repeat = _integer(node.get("visual_asset_repeat", 1), f"node {node_id} visual_asset_repeat", minimum=1, maximum=4)
        visual_asset_repeat_layout = str(node.get("visual_asset_repeat_layout") or "row").strip().lower()
        if visual_asset_repeat_layout not in {"row", "grid"}:
            raise ValueError(f"node {node_id} visual_asset_repeat_layout must be row or grid")
        raw_repeat_labels = node.get("visual_asset_repeat_labels", [])
        if not isinstance(raw_repeat_labels, list) or any(not isinstance(item, str) or not item.strip() for item in raw_repeat_labels):
            raise ValueError(f"node {node_id} visual_asset_repeat_labels must be a list of non-empty strings")
        if raw_repeat_labels and len(raw_repeat_labels) != visual_asset_repeat:
            raise ValueError(f"node {node_id} visual_asset_repeat_labels must match visual_asset_repeat")
        repeat_labels = [item.strip()[:40] for item in raw_repeat_labels]
        raw_overlays = node.get("visual_asset_overlays", [])
        if not isinstance(raw_overlays, list) or len(raw_overlays) > 8:
            raise ValueError(f"node {node_id} visual_asset_overlays must be a list with at most 8 items")
        overlays: list[dict[str, Any]] = []
        for overlay_index, raw_overlay in enumerate(raw_overlays):
            if not isinstance(raw_overlay, dict):
                raise ValueError(f"node {node_id} visual_asset_overlays[{overlay_index}] must be an object")
            overlay_x = _number(raw_overlay.get("x"), f"node {node_id} overlay {overlay_index} x", minimum=0, maximum=1)
            overlay_y = _number(raw_overlay.get("y"), f"node {node_id} overlay {overlay_index} y", minimum=0, maximum=1)
            overlay_width = _number(raw_overlay.get("width"), f"node {node_id} overlay {overlay_index} width", minimum=0.01, maximum=1)
            overlay_height = _number(raw_overlay.get("height"), f"node {node_id} overlay {overlay_index} height", minimum=0.01, maximum=1)
            if overlay_x + overlay_width > 1.000001 or overlay_y + overlay_height > 1.000001:
                raise ValueError(f"node {node_id} overlay {overlay_index} must stay inside the visual asset")
            raw_repeat_index = raw_overlay.get("repeat_index")
            repeat_index = None if raw_repeat_index is None else _integer(
                raw_repeat_index,
                f"node {node_id} overlay {overlay_index} repeat_index",
                minimum=0,
                maximum=visual_asset_repeat - 1,
            )
            overlays.append(
                {
                    "x": overlay_x,
                    "y": overlay_y,
                    "width": overlay_width,
                    "height": overlay_height,
                    "stroke": _optional_color(raw_overlay.get("stroke"), f"node {node_id} overlay {overlay_index} stroke") or "#E23D3D",
                    "stroke_width": _number(raw_overlay.get("stroke_width", 3), f"node {node_id} overlay {overlay_index} stroke_width", minimum=0.5, maximum=12),
                    "repeat_index": repeat_index,
                }
            )
        node.update(
            {
                "id": node_id,
                "lane": lane_id,
                "kind": kind,
                "rank": rank,
                "stack_order": _integer(node.get("stack_order", 0), f"node {node_id} stack_order", minimum=-100, maximum=100),
                "label": label,
                "detail": str(node.get("detail") or "").strip(),
                "label_max_lines": _integer(node.get("label_max_lines", 3), f"node {node_id} label_max_lines", minimum=1, maximum=12),
                "detail_max_lines": _integer(node.get("detail_max_lines", 3), f"node {node_id} detail_max_lines", minimum=1, maximum=12),
                "text_offset_y": _number(
                    node.get("text_offset_y", 0),
                    f"node {node_id} text_offset_y",
                    minimum=-200,
                    maximum=200,
                ),
                "width": _number(node.get("width", 156), f"node {node_id} width", minimum=80, maximum=900),
                "height": _number(node.get("height", 82), f"node {node_id} height", minimum=48, maximum=720),
                "x": (
                    _number(node.get("x"), f"node {node_id} x", minimum=0, maximum=float(spec["width"]))
                    if node.get("x") is not None
                    else None
                ),
                "y": (
                    _number(node.get("y"), f"node {node_id} y", minimum=0, maximum=float(spec["height"]))
                    if node.get("y") is not None
                    else None
                ),
                "emphasis": str(node.get("emphasis") or "normal"),
                "visual_asset": str(node.get("visual_asset") or "").strip(),
                "visual_asset_fraction": _number(
                    node.get("visual_asset_fraction", 0.42),
                    f"node {node_id} visual_asset_fraction",
                    minimum=0.2,
                    maximum=0.8,
                ),
                "visual_asset_padding": _number(
                    node.get("visual_asset_padding", 9),
                    f"node {node_id} visual_asset_padding",
                    minimum=0,
                    maximum=32,
                ),
                "visual_asset_position": str(node.get("visual_asset_position") or "left").strip().lower(),
                "visual_asset_repeat": visual_asset_repeat,
                "visual_asset_repeat_layout": visual_asset_repeat_layout,
                "visual_asset_repeat_labels": repeat_labels,
                "visual_asset_overlays": overlays,
                "show_frame": _boolean(node.get("show_frame"), f"node {node_id} show_frame", default=True),
                "show_glyph": _boolean(node.get("show_glyph"), f"node {node_id} show_glyph", default=True),
                "panel_letter": str(node.get("panel_letter") or "").strip(),
                "label_weight": int(_number(node.get("label_weight", 700 if str(node.get("emphasis") or "normal") == "hero" else 600), f"node {node_id} label_weight", minimum=300, maximum=800)),
                "fill": _optional_color(node.get("fill"), f"node {node_id} fill"),
                "stroke": _optional_color(node.get("stroke"), f"node {node_id} stroke"),
            }
        )
        if node["visual_asset_position"] not in {"left", "top", "bottom"}:
            raise ValueError(f"node {node_id} visual_asset_position must be left, top, or bottom")
        if len(node["panel_letter"]) > 3:
            raise ValueError(f"node {node_id} panel_letter must contain at most three characters")
        if node["visual_asset"] and node["visual_asset"] not in asset_ids:
            raise ValueError(f"node {node_id} references unknown visual_asset {node['visual_asset']}")
        if node["visual_asset_overlays"] and not node["visual_asset"]:
            raise ValueError(f"node {node_id} visual_asset_overlays require visual_asset")
        nodes.append(node)
    spec["nodes"] = nodes

    raw_columns = spec.get("columns", [])
    if not isinstance(raw_columns, list) or len(raw_columns) > 6:
        raise ValueError("FigureSpec columns must be a list with at most 6 items")
    known_ranks = {int(node["rank"]) for node in nodes}
    columns: list[dict[str, Any]] = []
    column_ids: set[str] = set()
    for index, raw_column in enumerate(raw_columns):
        if not isinstance(raw_column, dict):
            raise ValueError(f"columns[{index}] must be an object")
        column_id = _identifier(raw_column.get("id"), f"columns[{index}].id")
        if column_id in column_ids:
            raise ValueError(f"duplicate column id: {column_id}")
        raw_ranks = raw_column.get("ranks")
        if not isinstance(raw_ranks, list) or not raw_ranks:
            raise ValueError(f"column {column_id} requires a non-empty ranks list")
        ranks = [_integer(rank, f"column {column_id} rank", minimum=0, maximum=100) for rank in raw_ranks]
        if len(ranks) != len(set(ranks)) or any(rank not in known_ranks for rank in ranks):
            raise ValueError(f"column {column_id} ranks must be unique existing ranks")
        line_style = str(raw_column.get("line_style") or "dotted").strip().lower()
        if line_style not in {"solid", "dashed", "dotted"}:
            raise ValueError(f"column {column_id} line_style must be solid, dashed, or dotted")
        column_ids.add(column_id)
        columns.append(
            {
                "id": column_id,
                "label": str(raw_column.get("label") or column_id).strip(),
                "ranks": ranks,
                "padding": _number(raw_column.get("padding", 18), f"column {column_id} padding", minimum=0, maximum=80),
                "fill": _optional_color(raw_column.get("fill"), f"column {column_id} fill"),
                "stroke": _optional_color(raw_column.get("stroke"), f"column {column_id} stroke") or "#1F2933",
                "line_style": line_style,
                "show_frame": _boolean(raw_column.get("show_frame"), f"column {column_id} show_frame", default=True),
                "show_label": _boolean(raw_column.get("show_label"), f"column {column_id} show_label", default=True),
            }
        )
    spec["columns"] = columns

    hero_node = _identifier(story.get("hero_node"), "story.hero_node")
    if hero_node not in node_ids:
        raise ValueError("story.hero_node must reference an existing node")
    story["hero_node"] = hero_node
    reading_order = story.get("reading_order")
    if not isinstance(reading_order, list) or not reading_order:
        raise ValueError("story.reading_order must be a non-empty node-id list")
    reading_order = [_identifier(item, "story.reading_order item") for item in reading_order]
    if len(reading_order) != len(set(reading_order)) or any(item not in node_ids for item in reading_order):
        raise ValueError("story.reading_order must contain unique existing node ids")
    story["reading_order"] = reading_order
    spec["story"] = story

    raw_edges = spec.get("edges")
    if not isinstance(raw_edges, list) or not raw_edges:
        raise ValueError("FigureSpec requires at least one edge")
    edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()
    for index, raw_edge in enumerate(raw_edges):
        if not isinstance(raw_edge, dict):
            raise ValueError(f"edges[{index}] must be an object")
        edge = dict(raw_edge)
        edge_id = _identifier(edge.get("id") or f"edge-{index + 1}", f"edges[{index}].id")
        if edge_id in edge_ids:
            raise ValueError(f"duplicate edge id: {edge_id}")
        edge_ids.add(edge_id)
        source = _identifier(edge.get("source"), f"edge {edge_id} source")
        target_edge = str(edge.get("target_edge") or "").strip()
        target = "" if target_edge else _identifier(edge.get("target"), f"edge {edge_id} target")
        if source not in node_ids or (target and target not in node_ids) or (target and source == target):
            raise ValueError(f"edge {edge_id} must connect an existing source node to a different node or edge")
        kind = str(edge.get("kind") or "primary")
        if kind not in EDGE_KINDS:
            raise ValueError(f"edge {edge_id} has unsupported kind {kind!r}")
        source_port = str(edge.get("source_port") or "").upper()
        target_port = str(edge.get("target_port") or "").upper()
        if source_port and source_port not in PORTS:
            raise ValueError(f"edge {edge_id} has invalid source_port")
        if target_port and target_port not in PORTS:
            raise ValueError(f"edge {edge_id} has invalid target_port")
        edge.update(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "target_edge": target_edge,
                "kind": kind,
                "source_port": source_port,
                "target_port": target_port,
                "label": str(edge.get("label") or "").strip(),
                "color": _optional_color(edge.get("color"), f"edge {edge_id} color"),
                "stroke_width": _number(
                    edge.get("stroke_width", float(EDGE_STYLE[kind][1])),
                    f"edge {edge_id} stroke_width",
                    minimum=0.5,
                    maximum=8,
                ),
                "line_style": str(edge.get("line_style") or "auto").strip().lower(),
                "arrow_style": str(edge.get("arrow_style") or "line").strip().lower(),
                "target_edge_gap": _number(edge.get("target_edge_gap", 0), f"edge {edge_id} target_edge_gap", minimum=0, maximum=120),
                "label_offset_y": _number(edge.get("label_offset_y", -8), f"edge {edge_id} label_offset_y", minimum=-100, maximum=100),
                "label_size": _number(edge.get("label_size", 10.5), f"edge {edge_id} label_size", minimum=8, maximum=28),
            }
        )
        if edge["line_style"] not in {"auto", "solid", "dashed"}:
            raise ValueError(f"edge {edge_id} line_style must be auto, solid, or dashed")
        if edge["arrow_style"] not in {"line", "block"}:
            raise ValueError(f"edge {edge_id} arrow_style must be line or block")
        edges.append(edge)
    edge_by_id = {edge["id"]: edge for edge in edges}
    for edge in edges:
        target_edge = edge["target_edge"]
        if not target_edge:
            continue
        if edge["kind"] not in {"support", "association"}:
            raise ValueError(f"edge {edge['id']} may target another edge only as support or association")
        if target_edge == edge["id"] or target_edge not in edge_by_id:
            raise ValueError(f"edge {edge['id']} target_edge must reference a different existing edge")
        if edge_by_id[target_edge]["target_edge"]:
            raise ValueError(f"edge {edge['id']} cannot target another edge-targeting edge")
    spec["edges"] = edges

    layout = dict(spec.get("layout") or {})
    layout_mode = str(layout.get("mode") or "auto").strip().lower()
    if layout_mode not in {"auto", "fixed"}:
        raise ValueError("FigureSpec layout.mode must be auto or fixed")
    if str(layout.get("direction") or "LR").upper() != "LR":
        raise ValueError("FigureSpec 0.1 currently supports left-to-right layout only")
    layout.update(
        {
            "mode": layout_mode,
            "direction": "LR",
            "margin": _number(layout.get("margin", 42), "layout.margin", minimum=20, maximum=160),
            "header_height": _number(layout.get("header_height", 92), "layout.header_height", minimum=56, maximum=180),
            "rank_gap": _number(layout.get("rank_gap", 48), "layout.rank_gap", minimum=18, maximum=160),
            "max_rank_gap": _number(layout.get("max_rank_gap", 88), "layout.max_rank_gap", minimum=30, maximum=220),
            "node_gap": _number(layout.get("node_gap", 22), "layout.node_gap", minimum=8, maximum=100),
            "lane_gap": _number(layout.get("lane_gap", 24), "layout.lane_gap", minimum=8, maximum=120),
            "lane_padding": _number(layout.get("lane_padding", 24), "layout.lane_padding", minimum=12, maximum=80),
            "min_extent_occupancy": _number(layout.get("min_extent_occupancy", 0.38), "layout.min_extent_occupancy", minimum=0.1, maximum=0.95),
            "min_packing_ratio": _number(layout.get("min_packing_ratio", 0.12), "layout.min_packing_ratio", minimum=0.03, maximum=0.8),
            "max_edge_crossings": int(_number(layout.get("max_edge_crossings", 0), "layout.max_edge_crossings", minimum=0, maximum=50)),
            "font_size": _number(layout.get("font_size", 15), "layout.font_size", minimum=9, maximum=28),
            "show_header": _boolean(layout.get("show_header"), "layout.show_header", default=True),
        }
    )
    spec["layout"] = layout

    panels = spec.get("panels", [])
    if panels:
        if not isinstance(panels, list) or not 2 <= len(panels) <= 4:
            raise ValueError("FigureSpec panels must declare 2–4 export regions")
        seen_panels: set[str] = set()
        normalized_panels: list[dict[str, Any]] = []
        for index, raw_panel in enumerate(panels):
            if not isinstance(raw_panel, dict):
                raise ValueError(f"panels[{index}] must be an object")
            panel = dict(raw_panel)
            panel_id = _identifier(panel.get("panel_id"), f"panels[{index}].panel_id")
            panel_lanes = panel.get("lanes")
            panel_columns = panel.get("columns")
            has_lanes = isinstance(panel_lanes, list) and bool(panel_lanes)
            has_columns = isinstance(panel_columns, list) and bool(panel_columns)
            if panel_id in seen_panels or has_lanes == has_columns:
                raise ValueError("panel ids must be unique and each panel must contain either lanes or columns")
            seen_panels.add(panel_id)
            normalized_panel = {"panel_id": panel_id, "label": str(panel.get("label") or panel_id)}
            if has_lanes:
                if any(str(item) not in lane_ids for item in panel_lanes):
                    raise ValueError(f"panel {panel_id} references an unknown lane")
                normalized_panel["lanes"] = [str(item) for item in panel_lanes]
            else:
                if any(str(item) not in column_ids for item in panel_columns):
                    raise ValueError(f"panel {panel_id} references an unknown column")
                normalized_panel["columns"] = [str(item) for item in panel_columns]
            normalized_panels.append(normalized_panel)
        spec["panels"] = normalized_panels
    else:
        spec["panels"] = []
    return spec


def _port(box: list[float], name: str) -> tuple[float, float]:
    x, y, width, height = box
    return {
        "N": (x + width / 2, y),
        "E": (x + width, y + height / 2),
        "S": (x + width / 2, y + height),
        "W": (x, y + height / 2),
    }[name]


def _path_length(points: list[tuple[float, float]]) -> float:
    return sum(abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in zip(points, points[1:]))


def _path_midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return the Manhattan-length midpoint of an orthogonal routed edge."""

    total = _path_length(points)
    if total <= 0:
        return points[0]
    remaining = total / 2
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        segment = abs(x2 - x1) + abs(y2 - y1)
        if remaining <= segment:
            ratio = remaining / segment if segment else 0
            return (x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)
        remaining -= segment
    return points[-1]


def _segment_hits_box(start: tuple[float, float], end: tuple[float, float], box: list[float], padding: float = 6) -> bool:
    x, y, width, height = box
    left, right = x - padding, x + width + padding
    top, bottom = y - padding, y + height + padding
    x1, y1 = start
    x2, y2 = end
    if math.isclose(y1, y2, abs_tol=1e-6):
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
    if math.isclose(x1, x2, abs_tol=1e-6):
        return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
    return False


def _route_hits(points: list[tuple[float, float]], boxes: dict[str, list[float]], excluded: set[str]) -> int:
    return sum(
        1
        for node_id, box in boxes.items()
        if node_id not in excluded and any(_segment_hits_box(start, end, box) for start, end in zip(points, points[1:]))
    )


def _compact_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    compact: list[tuple[float, float]] = []
    for point in points:
        if not compact or point != compact[-1]:
            compact.append(point)
    changed = True
    while changed and len(compact) > 2:
        changed = False
        result = [compact[0]]
        for index in range(1, len(compact) - 1):
            before, current, after = result[-1], compact[index], compact[index + 1]
            if (math.isclose(before[0], current[0]) and math.isclose(current[0], after[0])) or (
                math.isclose(before[1], current[1]) and math.isclose(current[1], after[1])
            ):
                changed = True
                continue
            result.append(current)
        result.append(compact[-1])
        compact = result
    return compact


def _route_edge(edge: dict[str, Any], boxes: dict[str, list[float]], content_box: list[float]) -> list[tuple[float, float]]:
    source_box, target_box = boxes[edge["source"]], boxes[edge["target"]]
    source_cx = source_box[0] + source_box[2] / 2
    target_cx = target_box[0] + target_box[2] / 2
    source_port = edge["source_port"] or ("E" if target_cx >= source_cx else "W")
    target_port = edge["target_port"] or ("W" if target_cx >= source_cx else "E")
    start, end = _port(source_box, source_port), _port(target_box, target_port)
    sx, sy = start
    tx, ty = end
    pad = 18.0
    left, top, width, height = content_box
    corridor_top = max(top + 10, min(source_box[1], target_box[1]) - 28)
    corridor_bottom = min(top + height - 10, max(source_box[1] + source_box[3], target_box[1] + target_box[3]) + 28)
    midpoint = (sx + tx) / 2

    if edge["kind"] == "feedback":
        candidates = [[start, (sx, corridor_bottom), (tx, corridor_bottom), end]]
    elif source_port in {"N", "S"} or target_port in {"N", "S"}:
        mid_y = (sy + ty) / 2
        candidates = [
            [start, (sx, mid_y), (tx, mid_y), end],
            [start, (sx, corridor_top), (tx, corridor_top), end],
            [start, (sx, corridor_bottom), (tx, corridor_bottom), end],
        ]
    elif math.isclose(sy, ty, abs_tol=1.0):
        candidates = [[start, end], [start, (sx + pad, sy), (sx + pad, corridor_top), (tx - pad, corridor_top), (tx - pad, ty), end]]
    else:
        candidates = [
            [start, (midpoint, sy), (midpoint, ty), end],
            [start, (sx + pad, sy), (sx + pad, corridor_top), (tx - pad, corridor_top), (tx - pad, ty), end],
            [start, (sx + pad, sy), (sx + pad, corridor_bottom), (tx - pad, corridor_bottom), (tx - pad, ty), end],
        ]
    excluded = {edge["source"], edge["target"]}
    best = min(candidates, key=lambda points: (_route_hits(points, boxes, excluded), _path_length(points)))
    return _compact_points(best)


def _route_edge_to_edge(edge: dict[str, Any], boxes: dict[str, list[float]], routes: dict[str, list[tuple[float, float]]]) -> list[tuple[float, float]]:
    source_box = boxes[edge["source"]]
    source_port = edge["source_port"] or "S"
    start = _port(source_box, source_port)
    target_x, target_y = _path_midpoint(routes[edge["target_edge"]])
    direction = 1 if target_y >= start[1] else -1
    end = (target_x, target_y - direction * float(edge["target_edge_gap"]))
    if math.isclose(start[0], end[0], abs_tol=1.0):
        return [start, end]
    mid_y = (start[1] + end[1]) / 2
    return _compact_points([start, (start[0], mid_y), (end[0], mid_y), end])


def _segments(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(points, points[1:]))


def _segments_cross(first: tuple[tuple[float, float], tuple[float, float]], second: tuple[tuple[float, float], tuple[float, float]]) -> bool:
    (x1, y1), (x2, y2) = first
    (x3, y3), (x4, y4) = second
    if any(math.isclose(xa, xb) and math.isclose(ya, yb) for xa, ya in first for xb, yb in second):
        return False
    first_horizontal = math.isclose(y1, y2)
    second_horizontal = math.isclose(y3, y4)
    if first_horizontal == second_horizontal:
        return False
    horizontal, vertical = (first, second) if first_horizontal else (second, first)
    (hx1, hy), (hx2, _) = horizontal
    (vx, vy1), (_, vy2) = vertical
    return min(hx1, hx2) < vx < max(hx1, hx2) and min(vy1, vy2) < hy < max(vy1, vy2)


def layout_figure_spec(raw: dict[str, Any]) -> tuple[dict[str, Any], LayoutAudit]:
    """Resolve ranks and lanes into compact node boxes and routed edges."""

    spec = validate_figure_spec(raw)
    layout = spec["layout"]
    margin = float(layout["margin"])
    header = float(layout["header_height"]) if layout["show_header"] else margin
    content_box = [margin, header, spec["width"] - 2 * margin, spec["height"] - header - margin]
    if layout["mode"] == "fixed":
        missing = [node["id"] for node in spec["nodes"] if node["x"] is None or node["y"] is None]
        if missing:
            raise ValueError(f"fixed FigureSpec layout requires node x/y coordinates: {missing}")
        boxes = {
            node["id"]: [float(node["x"]), float(node["y"]), float(node["width"]), float(node["height"])]
            for node in spec["nodes"]
        }
        lane_boxes: dict[str, list[float]] = {}
        for lane in spec["lanes"]:
            lane_node_boxes = [boxes[node["id"]] for node in spec["nodes"] if node["lane"] == lane["id"]]
            if not lane_node_boxes:
                lane_boxes[lane["id"]] = list(content_box)
                continue
            padding = float(layout["lane_padding"])
            left = max(content_box[0], min(box[0] for box in lane_node_boxes) - padding)
            top = max(content_box[1], min(box[1] for box in lane_node_boxes) - padding)
            right = min(content_box[0] + content_box[2], max(box[0] + box[2] for box in lane_node_boxes) + padding)
            bottom = min(content_box[1] + content_box[3], max(box[1] + box[3] for box in lane_node_boxes) + padding)
            lane_boxes[lane["id"]] = [left, top, max(1.0, right - left), max(1.0, bottom - top)]
        routes = {edge["id"]: _route_edge(edge, boxes, content_box) for edge in spec["edges"] if not edge["target_edge"]}
        for edge in spec["edges"]:
            if edge["target_edge"]:
                routes[edge["id"]] = _route_edge_to_edge(edge, boxes, routes)
        audit = _audit_layout(spec, boxes, lane_boxes, routes, content_box)
        resolved = {
            "spec": spec,
            "content_box": content_box,
            "node_boxes": boxes,
            "lane_boxes": lane_boxes,
            "edge_routes": routes,
        }
        return resolved, audit
    ranks = sorted({int(node["rank"]) for node in spec["nodes"]})
    rank_nodes = {rank: [node for node in spec["nodes"] if int(node["rank"]) == rank] for rank in ranks}
    rank_widths = {rank: max(float(node["width"]) for node in rank_nodes[rank]) for rank in ranks}
    available_width = content_box[2]
    gaps = max(0, len(ranks) - 1)
    desired = sum(rank_widths.values()) + gaps * float(layout["rank_gap"])
    scale = min(1.0, available_width / desired) if desired else 1.0
    if scale < 0.72:
        raise ValueError("FigureSpec is too wide for the requested canvas; reduce node widths or ranks")
    if scale < 1:
        for node in spec["nodes"]:
            node["width"] = max(80.0, float(node["width"]) * scale)
            node["height"] = max(48.0, float(node["height"]) * scale)
        rank_widths = {rank: max(float(node["width"]) for node in rank_nodes[rank]) for rank in ranks}
    total_node_width = sum(rank_widths.values())
    rank_gap = float(layout["rank_gap"])
    if gaps:
        available_gap = max(0.0, (available_width - total_node_width) / gaps)
        # When the requested ranks needed slight down-scaling, preserving the
        # original gap can still push the first and last columns outside the
        # canvas by a few pixels.  The available gap is the hard constraint;
        # the requested gap is only a preference.
        rank_gap = min(float(layout["max_rank_gap"]), available_gap)
    used_width = total_node_width + rank_gap * gaps
    x_cursor = content_box[0] + max(0, (available_width - used_width) / 2)
    rank_centers: dict[int, float] = {}
    for rank in ranks:
        rank_centers[rank] = x_cursor + rank_widths[rank] / 2
        x_cursor += rank_widths[rank] + rank_gap

    lane_nodes = {lane["id"]: [node for node in spec["nodes"] if node["lane"] == lane["id"]] for lane in spec["lanes"]}
    lane_heights: dict[str, float] = {}
    for lane in spec["lanes"]:
        by_rank: dict[int, list[dict[str, Any]]] = {}
        for node in lane_nodes[lane["id"]]:
            by_rank.setdefault(int(node["rank"]), []).append(node)
        stack_height = max(
            (sum(float(node["height"]) for node in items) + float(layout["node_gap"]) * max(0, len(items) - 1) for items in by_rank.values()),
            default=60.0,
        )
        label_band = 28 if lane["show_label"] else 0
        lane_heights[lane["id"]] = stack_height + 2 * float(layout["lane_padding"]) + label_band
    lane_total = sum(lane_heights.values()) + float(layout["lane_gap"]) * max(0, len(spec["lanes"]) - 1)
    if lane_total > content_box[3]:
        raise ValueError("FigureSpec lanes are too tall for the requested canvas")
    lane_y = content_box[1] + max(0, (content_box[3] - lane_total) / 2)
    lane_boxes: dict[str, list[float]] = {}
    for lane in spec["lanes"]:
        lane_boxes[lane["id"]] = [content_box[0], lane_y, content_box[2], lane_heights[lane["id"]]]
        lane_y += lane_heights[lane["id"]] + float(layout["lane_gap"])

    boxes: dict[str, list[float]] = {}
    for lane in spec["lanes"]:
        lane_box = lane_boxes[lane["id"]]
        label_band = 28 if lane["show_label"] else 0
        for rank in ranks:
            items = sorted(
                (node for node in lane_nodes[lane["id"]] if int(node["rank"]) == rank),
                key=lambda node: (int(node["stack_order"]), node["id"]),
            )
            if not items:
                continue
            stack_height = sum(float(node["height"]) for node in items) + float(layout["node_gap"]) * max(0, len(items) - 1)
            y_cursor = lane_box[1] + label_band + (lane_box[3] - label_band - stack_height) / 2
            for node in items:
                width, height = float(node["width"]), float(node["height"])
                boxes[node["id"]] = [rank_centers[rank] - width / 2, y_cursor, width, height]
                y_cursor += height + float(layout["node_gap"])

    routes = {edge["id"]: _route_edge(edge, boxes, content_box) for edge in spec["edges"] if not edge["target_edge"]}
    for edge in spec["edges"]:
        if edge["target_edge"]:
            routes[edge["id"]] = _route_edge_to_edge(edge, boxes, routes)
    audit = _audit_layout(spec, boxes, lane_boxes, routes, content_box)
    resolved = {"spec": spec, "content_box": content_box, "node_boxes": boxes, "lane_boxes": lane_boxes, "edge_routes": routes}
    return resolved, audit


def _audit_layout(
    spec: dict[str, Any],
    boxes: dict[str, list[float]],
    lane_boxes: dict[str, list[float]],
    routes: dict[str, list[tuple[float, float]]],
    content_box: list[float],
) -> LayoutAudit:
    failures: list[str] = []
    warnings: list[str] = []
    node_items = list(boxes.items())
    overlaps = 0
    for index, (first_id, first) in enumerate(node_items):
        for second_id, second in node_items[index + 1 :]:
            if max(first[0], second[0]) < min(first[0] + first[2], second[0] + second[2]) and max(first[1], second[1]) < min(first[1] + first[3], second[1] + second[3]):
                overlaps += 1
                failures.append(f"nodes overlap: {first_id} and {second_id}")
    left, top, width, height = content_box
    bounds_epsilon = 1e-6
    out_of_bounds = sum(
        1
        for node_id, (x, y, node_width, node_height) in boxes.items()
        if x < left - bounds_epsilon
        or y < top - bounds_epsilon
        or x + node_width > left + width + bounds_epsilon
        or y + node_height > top + height + bounds_epsilon
    )
    if out_of_bounds:
        failures.append(f"{out_of_bounds} node(s) extend outside the content area")

    edge_node_hits = 0
    for edge in spec["edges"]:
        hits = _route_hits(routes[edge["id"]], boxes, {item for item in (edge["source"], edge["target"]) if item})
        if hits:
            edge_node_hits += hits
            failures.append(f"edge {edge['id']} crosses {hits} unrelated node(s)")
    crossings = 0
    for index, first_edge in enumerate(spec["edges"]):
        for second_edge in spec["edges"][index + 1 :]:
            first_nodes = {item for item in (first_edge["source"], first_edge["target"]) if item}
            second_nodes = {item for item in (second_edge["source"], second_edge["target"]) if item}
            if first_nodes & second_nodes:
                continue
            crossings += sum(
                1
                for first_segment in _segments(routes[first_edge["id"]])
                for second_segment in _segments(routes[second_edge["id"]])
                if _segments_cross(first_segment, second_segment)
            )
    if crossings > int(spec["layout"]["max_edge_crossings"]):
        warnings.append(f"edge crossing count {crossings} exceeds target {spec['layout']['max_edge_crossings']}")

    node_area = sum(box[2] * box[3] for box in boxes.values())
    min_x = min(box[0] for box in boxes.values())
    min_y = min(box[1] for box in boxes.values())
    max_x = max(box[0] + box[2] for box in boxes.values())
    max_y = max(box[1] + box[3] for box in boxes.values())
    extent_area = max(1.0, (max_x - min_x) * (max_y - min_y))
    extent_occupancy = extent_area / max(1.0, width * height)
    packing_ratio = node_area / extent_area
    if extent_occupancy < float(spec["layout"]["min_extent_occupancy"]):
        warnings.append(f"content extent occupancy {extent_occupancy:.2f} is too low")
    if packing_ratio < float(spec["layout"]["min_packing_ratio"]):
        warnings.append(f"node packing ratio {packing_ratio:.2f} is too low")

    ranks = {node["id"]: int(node["rank"]) for node in spec["nodes"]}
    reversed_primary = sum(1 for edge in spec["edges"] if edge["kind"] == "primary" and ranks[edge["target"]] <= ranks[edge["source"]])
    if reversed_primary:
        failures.append(f"{reversed_primary} primary edge(s) do not follow the left-to-right reading order")
    total_edge_length = sum(_path_length(points) for points in routes.values())
    direct_distance = sum(
        abs(points[-1][0] - points[0][0]) + abs(points[-1][1] - points[0][1]) for points in routes.values()
    )
    route_efficiency = direct_distance / max(1.0, total_edge_length)
    score = max(0.0, 100.0 - overlaps * 25 - edge_node_hits * 20 - crossings * 5 - out_of_bounds * 25 - reversed_primary * 25)
    score -= max(0.0, float(spec["layout"]["min_extent_occupancy"]) - extent_occupancy) * 35
    score -= max(0.0, float(spec["layout"]["min_packing_ratio"]) - packing_ratio) * 60
    metrics: dict[str, float | int] = {
        "node_count": len(boxes),
        "edge_count": len(routes),
        "node_overlap_count": overlaps,
        "edge_node_intersection_count": edge_node_hits,
        "edge_crossing_count": crossings,
        "out_of_bounds_count": out_of_bounds,
        "reversed_primary_edge_count": reversed_primary,
        "extent_occupancy": round(extent_occupancy, 4),
        "packing_ratio": round(packing_ratio, 4),
        "route_efficiency": round(route_efficiency, 4),
        "computed_layout_score": round(max(0.0, score), 2),
        "minimum_font_size": float(spec["layout"]["font_size"]),
    }
    return LayoutAudit(
        status="FAIL" if failures else "PASS",
        failures=failures,
        warnings=warnings,
        metrics=metrics,
        node_boxes={key: [round(value, 3) for value in box] for key, box in boxes.items()},
        lane_boxes={key: [round(value, 3) for value in box] for key, box in lane_boxes.items()},
        edge_routes={key: [[round(x, 3), round(y, 3)] for x, y in points] for key, points in routes.items()},
    )


def _svg(tag: str, attributes: dict[str, Any] | None = None) -> ET.Element:
    return ET.Element(f"{{{SVG_NS}}}{tag}", {key: str(value) for key, value in (attributes or {}).items() if value is not None})


def _wrap_text(text: str, *, width: int, max_lines: int) -> list[str]:
    """Wrap mixed Latin/CJK copy using approximate rendered-width units."""

    requested_width = max(1.0, float(width))
    remaining = str(text).strip()
    lines: list[str] = []
    while remaining and len(lines) < max_lines:
        rendered_units = 0.0
        cut_at = len(remaining)
        for index, character in enumerate(remaining):
            if character.isspace():
                rendered_units += 0.55
            elif unicodedata.east_asian_width(character) in {"W", "F"}:
                rendered_units += 1.8
            elif character in "()[]{}.,;:%/=-+":
                rendered_units += 0.72
            else:
                rendered_units += 1.0
            if rendered_units > requested_width:
                cut_at = max(1, index)
                break
        if cut_at >= len(remaining):
            lines.append(remaining)
            break
        search_start = max(1, int(cut_at * 0.58))
        break_at = max(
            (remaining.rfind(mark, search_start, cut_at + 1) for mark in " ；，、：;,:"),
            default=-1,
        )
        if break_at >= search_start:
            cut_at = break_at + (0 if remaining[break_at].isspace() else 1)
        lines.append(remaining[:cut_at].rstrip())
        remaining = remaining[cut_at:].lstrip()
    if not lines:
        lines.append(str(text))
    return lines[:max_lines]


def _add_text(parent: ET.Element, x: float, y: float, text: str, *, size: float, weight: int = 600, anchor: str = "middle", fill: str = "#23313A", max_chars: int = 24, max_lines: int = 3) -> None:
    node = ET.SubElement(
        parent,
        f"{{{SVG_NS}}}text",
        {"x": str(x), "y": str(y), "text-anchor": anchor, "font-family": "Microsoft YaHei, Noto Sans CJK SC, Arial, Helvetica, sans-serif", "font-size": str(size), "font-weight": str(weight), "fill": fill, "data-editable": "true"},
    )
    lines = _wrap_text(text, width=max_chars, max_lines=max_lines)
    line_height = size * 1.12
    start = y - line_height * (len(lines) - 1) / 2
    for index, line in enumerate(lines):
        span = ET.SubElement(node, f"{{{SVG_NS}}}tspan", {"x": str(x), "y": str(start + index * line_height)})
        span.text = line


def _node_glyph(parent: ET.Element, kind: str, x: float, y: float, color: str) -> None:
    if kind == "input":
        ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": f"M {x-9} {y} L {x+9} {y} M {x+3} {y-6} L {x+9} {y} L {x+3} {y+6}", "fill": "none", "stroke": color, "stroke-width": "2"})
    elif kind == "output":
        ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": f"M {x-9} {y+6} L {x-2} {y-3} L {x+3} {y+2} L {x+10} {y-8}", "fill": "none", "stroke": color, "stroke-width": "2.2", "stroke-linecap": "round"})
    elif kind in {"branch", "join"}:
        for dx, dy in ((-8, 0), (7, -7), (7, 7)):
            ET.SubElement(parent, f"{{{SVG_NS}}}circle", {"cx": str(x + dx), "cy": str(y + dy), "r": "3.5", "fill": color})
        ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": f"M {x-5} {y} L {x+3} {y} M {x+3} {y} L {x+5} {y-7} M {x+3} {y} L {x+5} {y+7}", "fill": "none", "stroke": color, "stroke-width": "1.8"})
    elif kind == "evidence":
        for index, height in enumerate((6, 12, 9)):
            ET.SubElement(parent, f"{{{SVG_NS}}}rect", {"x": str(x - 10 + index * 7), "y": str(y + 7 - height), "width": "4.5", "height": str(height), "rx": "1", "fill": color})
    elif kind == "illustration":
        ET.SubElement(parent, f"{{{SVG_NS}}}circle", {"cx": str(x), "cy": str(y), "r": "9", "fill": "none", "stroke": color, "stroke-width": "1.8"})
        ET.SubElement(parent, f"{{{SVG_NS}}}circle", {"cx": str(x - 3), "cy": str(y - 1), "r": "2.5", "fill": color})
    else:
        ET.SubElement(parent, f"{{{SVG_NS}}}rect", {"x": str(x - 9), "y": str(y - 8), "width": "18", "height": "16", "rx": "3", "fill": "none", "stroke": color, "stroke-width": "1.8"})


def _prefix_asset_ids(root: ET.Element, prefix: str) -> None:
    mapping: dict[str, str] = {}
    for element in root.iter():
        element_id = element.get("id")
        if element_id:
            mapping[element_id] = f"{prefix}-{element_id}"
    for element in root.iter():
        element_id = element.get("id")
        if element_id in mapping:
            element.set("id", mapping[element_id])
        for key, value in list(element.attrib.items()):
            for old, new in mapping.items():
                value = value.replace(f"url(#{old})", f"url(#{new})")
                if value == f"#{old}":
                    value = f"#{new}"
            element.set(key, value)


def _inline_vector_assets(defs: ET.Element, spec: dict[str, Any], asset_root: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for asset in spec["assets"]:
        if asset["kind"] != "vector":
            continue
        path = Path(asset["path"])
        if not path.is_absolute():
            path = asset_root / path
        path = path.resolve()
        asset_audit = audit_svg(path, allow_raster=False, require_text=False)
        if asset_audit.status != "PASS":
            raise ValueError(f"vector asset {asset['id']} failed SVG audit: {asset_audit.failures}")
        asset_root_element = ET.parse(path).getroot()
        viewbox = asset_root_element.get("viewBox")
        if not viewbox:
            raise ValueError(f"vector asset {asset['id']} has no viewBox")
        symbol = ET.SubElement(defs, f"{{{SVG_NS}}}symbol", {"id": f"vector-asset-{asset['id']}", "viewBox": viewbox, "preserveAspectRatio": "xMidYMid meet"})
        copied_root = deepcopy(asset_root_element)
        _prefix_asset_ids(copied_root, f"asset-{asset['id']}")
        for child in list(copied_root):
            if child.tag.rsplit("}", 1)[-1] not in {"metadata", "title", "desc"}:
                symbol.append(child)
        records[asset["id"]] = str(path)
    return records


def _load_raster_assets(
    spec: dict[str, Any],
    asset_root: Path,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    records: dict[str, str] = {}
    payloads: dict[str, dict[str, str]] = {}
    signatures = {
        ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
        ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
        ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    }
    for asset in spec["assets"]:
        if asset["kind"] != "raster":
            continue
        path = Path(asset["path"])
        if not path.is_absolute():
            path = asset_root / path
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"raster asset {asset['id']} does not exist: {path}")
        suffix = path.suffix.lower()
        if suffix not in signatures:
            raise ValueError(f"raster asset {asset['id']} must be PNG or JPEG")
        mime, signature = signatures[suffix]
        content = path.read_bytes()
        if not content.startswith(signature):
            raise ValueError(f"raster asset {asset['id']} content does not match {suffix}")
        records[asset["id"]] = str(path)
        payloads[asset["id"]] = {
            "href": f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}",
            "mime": mime,
            "sha256": hashlib.sha256(content).hexdigest(),
            "role": asset["role"],
        }
    return records, payloads


def panel_manifest_from_layout(spec: dict[str, Any], audit: LayoutAudit) -> dict[str, Any] | None:
    if not spec.get("panels"):
        return None
    records: list[dict[str, Any]] = []
    for panel in spec["panels"]:
        if panel.get("lanes"):
            boxes = [audit.lane_boxes[lane_id] for lane_id in panel["lanes"]]
        else:
            column_map = {column["id"]: column for column in spec["columns"]}
            ranks = {
                rank
                for column_id in panel["columns"]
                for rank in column_map[column_id]["ranks"]
            }
            boxes = [
                audit.node_boxes[node["id"]]
                for node in spec["nodes"]
                if int(node["rank"]) in ranks
            ]
        x = min(box[0] for box in boxes)
        y = min(box[1] for box in boxes)
        right = max(box[0] + box[2] for box in boxes)
        bottom = max(box[1] + box[3] for box in boxes)
        pad = 8
        records.append({"panel_id": panel["panel_id"], "label": panel["label"], "bbox": [max(0, x - pad), max(0, y - pad), right - x + 2 * pad, bottom - y + 2 * pad]})
    return {"schema_version": FIGURE_SPEC_VERSION, "panels": records}


def render_figure_spec(
    raw: dict[str, Any],
    output: str | Path,
    *,
    layout_report: str | Path | None = None,
    panel_manifest: str | Path | None = None,
    asset_root: str | Path | None = None,
    allow_raster: bool = False,
) -> dict[str, Any]:
    """Layout and render a FigureSpec as grouped, editable SVG."""

    resolved, audit = layout_figure_spec(raw)
    if audit.status != "PASS":
        raise ValueError(f"FigureSpec layout failed: {audit.failures}")
    spec = resolved["spec"]
    root = _svg(
        "svg",
        {
            "viewBox": f"0 0 {spec['width']} {spec['height']}",
            "width": spec["width"],
            "height": spec["height"],
            "role": "img",
            "data-figmirror-format": "figure-spec-v1",
            "aria-labelledby": "figure-title figure-description",
        },
    )
    title = ET.SubElement(root, f"{{{SVG_NS}}}title", {"id": "figure-title"})
    title.text = spec["title"]
    description = ET.SubElement(root, f"{{{SVG_NS}}}desc", {"id": "figure-description"})
    description.text = spec["story"]["claim"]
    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    marker = ET.SubElement(defs, f"{{{SVG_NS}}}marker", {"id": "figure-spec-arrow", "viewBox": "0 0 10 10", "refX": "9", "refY": "5", "markerWidth": "7", "markerHeight": "7", "orient": "auto-start-reverse"})
    ET.SubElement(marker, f"{{{SVG_NS}}}path", {"d": "M 0 0 L 10 5 L 0 10 z", "fill": "context-stroke"})
    resolved_asset_root = Path(asset_root) if asset_root else Path(output).parent
    vector_assets = _inline_vector_assets(defs, spec, resolved_asset_root)
    raster_assets, raster_payloads = _load_raster_assets(spec, resolved_asset_root)
    if raster_assets and not allow_raster:
        raise ValueError("FigureSpec contains raster assets but allow_raster is false")
    asset_map = {asset["id"]: asset for asset in spec["assets"]}
    ET.SubElement(root, f"{{{SVG_NS}}}rect", {"width": str(spec["width"]), "height": str(spec["height"]), "fill": "#FFFFFF"})
    header_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "figure-header", "data-layer-name": "Header"})
    if spec["layout"]["show_header"]:
        _add_text(header_group, spec["width"] / 2, 32, spec["title"], size=24, weight=700, max_chars=72)
        _add_text(header_group, spec["width"] / 2, 61, spec["story"]["claim"], size=13, weight=400, fill="#5B6972", max_chars=110)

    column_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "figure-columns", "data-layer-name": "Reference grammar columns"})
    content_left, content_top, content_width, content_height = resolved["content_box"]
    for column in spec["columns"]:
        column_node_boxes = [
            resolved["node_boxes"][node["id"]]
            for node in spec["nodes"]
            if int(node["rank"]) in column["ranks"]
        ]
        padding = float(column["padding"])
        column_left = max(content_left, min(box[0] for box in column_node_boxes) - padding)
        column_right = min(content_left + content_width, max(box[0] + box[2] for box in column_node_boxes) + padding)
        attributes = {
            "x": str(column_left),
            "y": str(content_top),
            "width": str(column_right - column_left),
            "height": str(content_height),
            "rx": "10",
            "fill": column["fill"] or "none",
            "stroke": column["stroke"],
            "stroke-width": "1.6",
            "data-column-id": column["id"],
            "data-column-ranks": ",".join(str(rank) for rank in column["ranks"]),
        }
        if column["line_style"] == "dotted":
            attributes["stroke-dasharray"] = "2 7"
            attributes["stroke-linecap"] = "round"
        elif column["line_style"] == "dashed":
            attributes["stroke-dasharray"] = "8 6"
        if column["show_frame"]:
            ET.SubElement(column_group, f"{{{SVG_NS}}}rect", attributes)
        if column["show_label"]:
            _add_text(column_group, (column_left + column_right) / 2, content_top + 25, column["label"], size=16, weight=700, fill="#111820", max_chars=34)

    lane_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "figure-lanes", "data-layer-name": "Lanes"})
    lane_map = {lane["id"]: lane for lane in spec["lanes"]}
    for lane_id, box in resolved["lane_boxes"].items():
        x, y, width, height = box
        lane = lane_map[lane_id]
        fill = "#FBFCFD" if lane["role"] == "main" else "#F8FAF8"
        if lane["show_frame"]:
            ET.SubElement(lane_group, f"{{{SVG_NS}}}rect", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "rx": "16", "fill": fill, "stroke": "#D9E1E5", "stroke-width": "1.5", "data-lane-id": lane_id})
        if lane["show_label"]:
            _add_text(lane_group, x + 18, y + 20, lane["label"], size=12, weight=700, anchor="start", fill="#55636B", max_chars=40)

    edge_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "figure-edges", "data-layer-name": "Semantic edges"})
    edge_map = {edge["id"]: edge for edge in spec["edges"]}
    edge_marker_ids: set[str] = set()
    for edge_id, points in resolved["edge_routes"].items():
        edge = edge_map[edge_id]
        default_color, _, dash = EDGE_STYLE[edge["kind"]]
        color = edge["color"] or default_color
        stroke_width = str(edge["stroke_width"])
        marker_id = f"figure-spec-arrow-{color[1:].lower()}"
        if marker_id not in edge_marker_ids:
            edge_marker = ET.SubElement(
                defs,
                f"{{{SVG_NS}}}marker",
                {
                    "id": marker_id,
                    "viewBox": "0 0 10 10",
                    "refX": "9",
                    "refY": "5",
                    "markerWidth": "7",
                    "markerHeight": "7",
                    "orient": "auto-start-reverse",
                },
            )
            ET.SubElement(
                edge_marker,
                f"{{{SVG_NS}}}path",
                {"d": "M 0 0 L 10 5 L 0 10 z", "fill": color},
            )
            edge_marker_ids.add(marker_id)
        if edge["arrow_style"] == "block" and len(points) == 2 and math.isclose(points[0][0], points[1][0], abs_tol=1.0):
            arrow_x = points[0][0]
            start_y, end_y = points[0][1], points[1][1]
            direction = 1 if end_y >= start_y else -1
            shaft_half, head_half, head_height = 24.0, 46.0, 34.0
            head_base_y = end_y - direction * head_height
            polygon = [
                (arrow_x - shaft_half, start_y),
                (arrow_x + shaft_half, start_y),
                (arrow_x + shaft_half, head_base_y),
                (arrow_x + head_half, head_base_y),
                (arrow_x, end_y),
                (arrow_x - head_half, head_base_y),
                (arrow_x - shaft_half, head_base_y),
            ]
            path_data = "M " + " L ".join(f"{px:.3f} {py:.3f}" for px, py in polygon) + " Z"
            attributes = {"id": edge_id, "d": path_data, "fill": color, "stroke": "#5B6165", "stroke-width": "1.8", "stroke-linejoin": "miter", "data-edge-kind": edge["kind"], "data-source": edge["source"], "data-target": edge["target"] or f"edge:{edge['target_edge']}", "data-arrow-style": "block", "data-connector": "true"}
        else:
            path_data = " ".join(("M" if index == 0 else "L") + f" {x:.3f} {y:.3f}" for index, (x, y) in enumerate(points))
            attributes = {"id": edge_id, "d": path_data, "fill": "none", "stroke": color, "stroke-width": stroke_width, "stroke-linejoin": "round", "stroke-linecap": "round", "marker-end": f"url(#{marker_id})", "data-edge-kind": edge["kind"], "data-source": edge["source"], "data-target": edge["target"] or f"edge:{edge['target_edge']}", "data-arrow-style": "line"}
            if edge["line_style"] == "solid":
                dash = None
            elif edge["line_style"] == "dashed":
                dash = "7 5"
            if dash:
                attributes["stroke-dasharray"] = dash
        ET.SubElement(edge_group, f"{{{SVG_NS}}}path", attributes)
        if edge["label"]:
            middle = _path_midpoint(points)
            _add_text(edge_group, middle[0], middle[1] + float(edge["label_offset_y"]), edge["label"], size=float(edge["label_size"]), weight=500, fill=color, max_chars=22)

    node_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "figure-nodes", "data-layer-name": "Semantic nodes"})
    node_map = {node["id"]: node for node in spec["nodes"]}
    for node_id, box in resolved["node_boxes"].items():
        node = node_map[node_id]
        x, y, width, height = box
        default_fill, default_stroke = KIND_STYLE[node["kind"]]
        fill = node["fill"] or default_fill
        stroke = node["stroke"] or default_stroke
        group = ET.SubElement(node_group, f"{{{SVG_NS}}}g", {"id": node_id, "data-node-kind": node["kind"], "data-lane": node["lane"], "data-rank": str(node["rank"])})
        hero = node_id == spec["story"]["hero_node"] or node["emphasis"] == "hero"
        if node["show_frame"]:
            ET.SubElement(group, f"{{{SVG_NS}}}rect", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "rx": "13", "fill": fill, "stroke": stroke, "stroke-width": "3" if hero else "1.7"})
        glyph_x = x + 24
        if node["panel_letter"]:
            _add_text(group, x - 9, y + 20, node["panel_letter"], size=18, weight=700, anchor="end", fill="#111111", max_chars=3)
        text_region_top = y
        text_region_height = height
        if node["visual_asset"]:
            asset = asset_map[node["visual_asset"]]
            asset_padding = float(node["visual_asset_padding"])
            if node["visual_asset_position"] == "top":
                asset_width = width - 2 * asset_padding
                asset_height = min(height * float(node["visual_asset_fraction"]), height - 2 * asset_padding - 42)
                asset_x = x + asset_padding
                asset_y = y + asset_padding
                text_start = x + 12
                text_region_top = asset_y + asset_height + 3
                text_region_height = max(36.0, y + height - text_region_top)
            elif node["visual_asset_position"] == "bottom":
                asset_width = width - 2 * asset_padding
                asset_height = min(height * float(node["visual_asset_fraction"]), height - 2 * asset_padding - 42)
                asset_x = x + asset_padding
                asset_y = y + height - asset_padding - asset_height
                text_start = x + 12
                text_region_height = max(36.0, asset_y - y - 3)
            else:
                asset_width = min(width * float(node["visual_asset_fraction"]), height - 2 * asset_padding)
                asset_height = height - 2 * asset_padding
                asset_x = x + asset_padding
                asset_y = y + asset_padding
                text_start = x + asset_padding + asset_width + 5
            repeat = int(node["visual_asset_repeat"])
            repeat_gap = min(10.0, min(asset_width, asset_height) * 0.04) if repeat > 1 else 0.0
            slot_boxes: list[list[float]] = []
            if node["visual_asset_repeat_layout"] == "grid" and repeat > 1:
                columns = 2
                rows = math.ceil(repeat / columns)
                repeated_width = (asset_width - repeat_gap * (columns - 1)) / columns
                repeated_height = (asset_height - repeat_gap * (rows - 1)) / rows
                for repeat_index in range(repeat):
                    column_index = repeat_index % columns
                    row_index = repeat_index // columns
                    slot_boxes.append(
                        [
                            asset_x + column_index * (repeated_width + repeat_gap),
                            asset_y + row_index * (repeated_height + repeat_gap),
                            repeated_width,
                            repeated_height,
                        ]
                    )
            else:
                repeated_width = (asset_width - repeat_gap * (repeat - 1)) / repeat
                slot_boxes = [
                    [asset_x + repeat_index * (repeated_width + repeat_gap), asset_y, repeated_width, asset_height]
                    for repeat_index in range(repeat)
                ]
            image_boxes: list[list[float]] = []
            for repeat_index, (slot_x, slot_y, slot_width, slot_height) in enumerate(slot_boxes):
                label_band = min(18.0, max(12.0, slot_height * 0.18)) if node["visual_asset_repeat_labels"] else 0.0
                if node["visual_asset_repeat_labels"]:
                    _add_text(
                        group,
                        slot_x + slot_width / 2,
                        slot_y + label_band * 0.68,
                        node["visual_asset_repeat_labels"][repeat_index],
                        size=max(9.0, float(spec["layout"]["font_size"]) - 6),
                        weight=600,
                        fill="#26343D",
                        max_chars=24,
                    )
                image_x = slot_x
                image_y = slot_y + label_band
                image_width = slot_width
                image_height = max(1.0, slot_height - label_band)
                image_boxes.append([image_x, image_y, image_width, image_height])
                if asset["kind"] == "vector":
                    ET.SubElement(
                        group,
                        f"{{{SVG_NS}}}use",
                        {
                            "href": f"#vector-asset-{node['visual_asset']}",
                            "x": str(image_x),
                            "y": str(image_y),
                            "width": str(image_width),
                            "height": str(image_height),
                            "data-vector-asset": node["visual_asset"],
                            "data-asset-repeat-index": str(repeat_index),
                            "data-asset-repeat-layout": node["visual_asset_repeat_layout"],
                        },
                    )
                else:
                    payload = raster_payloads[node["visual_asset"]]
                    ET.SubElement(
                        group,
                        f"{{{SVG_NS}}}image",
                        {
                            "href": payload["href"],
                            "x": str(image_x),
                            "y": str(image_y),
                            "width": str(image_width),
                            "height": str(image_height),
                            "preserveAspectRatio": "xMidYMid meet",
                            "data-raster-asset": node["visual_asset"],
                            "data-raster-role": payload["role"],
                            "data-raster-sha256": payload["sha256"],
                            "data-asset-repeat-index": str(repeat_index),
                            "data-asset-repeat-layout": node["visual_asset_repeat_layout"],
                        },
                    )
            for overlay_index, overlay in enumerate(node["visual_asset_overlays"]):
                overlay_box = (
                    image_boxes[int(overlay["repeat_index"])]
                    if overlay["repeat_index"] is not None
                    else [asset_x, asset_y, asset_width, asset_height]
                )
                ET.SubElement(
                    group,
                    f"{{{SVG_NS}}}rect",
                    {
                        "x": str(overlay_box[0] + overlay_box[2] * float(overlay["x"])),
                        "y": str(overlay_box[1] + overlay_box[3] * float(overlay["y"])),
                        "width": str(overlay_box[2] * float(overlay["width"])),
                        "height": str(overlay_box[3] * float(overlay["height"])),
                        "fill": "none",
                        "stroke": overlay["stroke"],
                        "stroke-width": str(overlay["stroke_width"]),
                        "data-vector-overlay": "roi",
                        "data-overlay-index": str(overlay_index),
                        "data-overlay-repeat-index": "all" if overlay["repeat_index"] is None else str(overlay["repeat_index"]),
                    },
                )
        else:
            if node["show_glyph"]:
                _node_glyph(group, node["kind"], glyph_x, y + height / 2, stroke)
                text_start = x + 44
            else:
                text_start = x + 12
        text_x = text_start + (x + width - text_start) / 2
        label_size = float(spec["layout"]["font_size"]) + (1 if hero else 0)
        text_region_width = max(54.0, x + width - text_start - 12)
        label_chars = max(8, int(text_region_width / max(6.0, label_size * 0.56)))
        label_lines = _wrap_text(node["label"], width=label_chars, max_lines=node["label_max_lines"])
        if node["detail"]:
            detail_size = max(9.0, float(spec["layout"]["font_size"]) - 3)
            detail_chars = max(9, int(text_region_width / max(5.0, detail_size * 0.54)))
            detail_lines = _wrap_text(node["detail"], width=detail_chars, max_lines=node["detail_max_lines"])
            label_block = len(label_lines) * label_size * 1.12
            detail_block = len(detail_lines) * detail_size * 1.12
            total_block = label_block + detail_block + 6
            block_top = text_region_top + text_region_height / 2 - total_block / 2 + float(node["text_offset_y"])
            label_y = block_top + label_block / 2
            detail_y = block_top + label_block + 6 + detail_block / 2
            _add_text(group, text_x, label_y, node["label"], size=label_size, weight=node["label_weight"], max_chars=label_chars, max_lines=node["label_max_lines"])
            _add_text(group, text_x, detail_y, node["detail"], size=detail_size, weight=400, fill="#5B6972", max_chars=detail_chars, max_lines=node["detail_max_lines"])
        else:
            _add_text(
                group,
                text_x,
                text_region_top + text_region_height / 2 + float(node["text_offset_y"]),
                node["label"],
                size=label_size,
                weight=node["label_weight"],
                max_chars=label_chars,
                max_lines=node["label_max_lines"],
            )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    svg_audit = audit_svg(
        output_path,
        allow_raster=allow_raster,
        require_text=True,
        require_named_groups=True,
        require_connector_metadata=True,
    )
    if svg_audit.status != "PASS":
        raise ValueError(f"rendered FigureSpec SVG failed audit: {svg_audit.failures}")
    report_path = Path(layout_report) if layout_report else output_path.with_name("layout_report.json")
    report_path.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    panel_payload = panel_manifest_from_layout(spec, audit)
    panel_path: Path | None = None
    if panel_payload is not None:
        panel_path = Path(panel_manifest) if panel_manifest else output_path.with_name("panel_manifest.json")
        panel_path.write_text(json.dumps(panel_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": FIGURE_SPEC_VERSION,
        "status": "PASS",
        "output": str(output_path.resolve()),
        "layout_report": str(report_path.resolve()),
        "panel_manifest": str(panel_path.resolve()) if panel_path else None,
        "vector_assets": vector_assets,
        "raster_assets": raster_assets,
        "rendering_mode": "hybrid-raster-vector" if raster_assets else "vector",
        "layout_audit": audit.to_dict(),
        "svg_audit": svg_audit.to_dict(),
    }
