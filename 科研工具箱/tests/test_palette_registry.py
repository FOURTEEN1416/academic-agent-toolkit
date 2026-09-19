"""多场景配色注册表回归（P2 统一配色方案，2026-09-19 建立）。

守护四件事：
  1. 真仓注册表全过体检（`palette_kit.py registry-verify`）；
  2. 注册表与本地色板真源（`assets/palette_v6.json`）的色值一致性——防双源漂移；
  3. 体检器的判定逻辑（七类硬 FAIL 各有一例负例，防止门禁退化成永远 PASS）；
  4. 禁用清单与场景映射的完整性（禁用色板不得被任何场景引用）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "paper-figure-palette"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SKILL / "scripts"))

import palette_kit as pk  # noqa: E402

REGISTRY = SKILL / "assets" / "palette_registry.json"
V6 = SKILL / "assets" / "palette_v6.json"

VALID = ["#E69F00", "#56B4E9", "#009E73", "#F0E442"]


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _base(scenario_override: dict | None = None) -> dict:
    scenario = {"id": "s", "categorical": "cat", "sequential": "seq", "diverging": "div"}
    scenario.update(scenario_override or {})
    return {
        "schema_version": 1,
        "meta": {"checks": {"cvd_min_deltaE": 25.0, "cvd_fail_deltaE": 12.0,
                            "sequential_max_backstep": 0.5}},
        "scenarios": [scenario],
        "palettes": {
            "cat": {"kind": "categorical", "cvd_mode": "direct", "colors": VALID},
            "seq": {"kind": "sequential", "monotonic": True,
                    "stops": ["#FFFFFF", "#9FE698", "#19667F"]},
            "div": {"kind": "diverging",
                    "stops": ["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B"]},
        },
        "forbidden": [{"id": "jet", "aliases": ["rainbow"], "reason": "x"}],
        "rules": [{"id": "R1", "text": "x"}],
    }


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ---------- 真仓机检 ----------

def test_real_registry_passes_verification(capsys) -> None:
    """真仓注册表必须全过（含色值/单调性/CVD 契约/场景交叉一致）。"""
    assert pk.registry_verify(str(REGISTRY)) is True


def test_real_registry_structure() -> None:
    reg = _registry()
    assert reg["schema_version"] == 1
    assert len(reg["scenarios"]) >= 5
    assert len(reg["palettes"]) >= 8
    assert reg["forbidden"], "禁用清单不得为空"
    assert len(reg["rules"]) >= 8


def test_forbidden_includes_the_classic_traps() -> None:
    """jet/rainbow、RdGn、RdYlGn 必须登记为禁用（配色事故的高频来源）。"""
    ids = {str(i.get("id", "")).lower() for i in _registry()["forbidden"]}
    aliases = {a.lower() for i in _registry()["forbidden"] for a in (i.get("aliases") or [])}
    assert "jet" in ids
    assert ids & {"rdgn", "rdylgn"}
    assert "rainbow" in aliases


def test_every_scenario_references_existing_palettes() -> None:
    reg = _registry()
    palettes = reg["palettes"]
    for sc in reg["scenarios"]:
        for key in ("categorical", "categorical_alt", "sequential", "sequential_alt", "diverging"):
            ref = sc.get(key)
            if ref:
                assert ref in palettes, f"{sc['id']}.{key}={ref} 未在 palettes 中登记"


def test_grayscale_scenarios_use_monotonic_ramps() -> None:
    """要求灰度可分的场景，其顺序色带必须声明 monotonic。"""
    reg = _registry()
    for sc in reg["scenarios"]:
        if not sc.get("grayscale_required"):
            continue
        pal = reg["palettes"].get(sc.get("sequential") or "", {})
        assert pal.get("monotonic") is True, f"{sc['id']} 的顺序色带未声明单调"


# ---------- 与本地色板真源一致性 ----------

def test_local_palette_matches_v6_source() -> None:
    """注册表里的本地 8 色板色值必须与 palette_v6.json 真源一致（防双源漂移）。"""
    reg = _registry()
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    source = [c["hex"].upper() for c in v6["warm_family"]["colors"]]
    source += [c["hex"].upper() for c in v6["cool_family"]["colors"] if c["hex"].startswith("#")]
    registered = [c.upper() for c in reg["palettes"]["summer-beach-v6"]["colors"]]
    for hexc in source:
        assert hexc in registered, f"v6 真源色 {hexc} 未登记进注册表"


def test_local_palette_ink_map_covers_registered_colors() -> None:
    """墨色映射必须覆盖注册表中所有被它使用的基色（线条/描边取色来源）。"""
    reg = _registry()
    pal = reg["palettes"]["summer-beach-v6"]
    ink_map = {k.upper() for k in pal["ink_map"]}
    for hexc in pal["colors"]:
        if hexc.upper() in {"#90D9CB"}:   # M3 为 LAB 插值补位，无独立墨色（用族锚墨色）
            continue
        assert hexc.upper() in ink_map, f"{hexc} 缺墨色映射"


# ---------- 体检器判定逻辑（负例） ----------

def test_invalid_hex_is_flagged(tmp_path: Path) -> None:
    data = _base()
    data["palettes"]["cat"]["colors"] = ["#E69F00", "#GGGGGG"]
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_duplicate_colors_are_flagged(tmp_path: Path) -> None:
    data = _base()
    data["palettes"]["cat"]["colors"] = ["#E69F00", "#E69F00", "#56B4E9"]
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_non_monotonic_sequential_is_flagged(tmp_path: Path) -> None:
    """顺序色带明度来回跳（假亮带）必须拦下。"""
    data = _base()
    data["palettes"]["seq"]["stops"] = ["#FFFFFF", "#440154", "#FDE725", "#2A788E"]
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_diverging_without_extreme_center_is_flagged(tmp_path: Path) -> None:
    """发散色带中点不是明度极值（零点不突出）必须拦下。"""
    data = _base()
    data["palettes"]["div"]["stops"] = ["#2166AC", "#F7F7F7", "#92C5DE", "#F4A582", "#B2182B"]
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_direct_cvd_mode_with_poor_separation_is_flagged(tmp_path: Path) -> None:
    """声明"可直用"但实测分不开 = 合规声明与实际能力不符，必须拦下。"""
    data = _base()
    data["palettes"]["cat"]["colors"] = ["#FEBDAA", "#FEB8B5", "#FEE6A9"]  # 本地填充型三色
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_secondary_encoding_without_declaration_is_flagged(tmp_path: Path) -> None:
    """填充型色板必须显式声明依赖第二编码，否则会被误当作可直用。"""
    data = _base()
    data["palettes"]["cat"] = {"kind": "categorical", "cvd_mode": "secondary_encoding",
                               "colors": VALID}
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_secondary_encoding_with_declaration_passes(tmp_path: Path) -> None:
    data = _base()
    data["palettes"]["cat"] = {"kind": "categorical", "cvd_mode": "secondary_encoding",
                               "requires_secondary_encoding": True, "colors": VALID}
    assert pk.registry_verify(str(_write(tmp_path, data))) is True


def test_scenario_referencing_missing_palette_is_flagged(tmp_path: Path) -> None:
    data = _base({"sequential": "does-not-exist"})
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_scenario_referencing_forbidden_palette_is_flagged(tmp_path: Path) -> None:
    """禁用色板被场景引用（哪怕换了名字写）必须拦下。"""
    data = _base({"diverging": "rainbow-ramp"})
    data["palettes"]["rainbow-ramp"] = {"kind": "sequential", "monotonic": True,
                                        "stops": ["#FFFFFF", "#9FE698", "#19667F"]}
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_direct_required_policy_mapping_fill_palette_is_flagged(tmp_path: Path) -> None:
    """场景声明"要求直用可分"却映射填充型色板 = 假合规，必须拦下。"""
    data = _base({"cvd_policy": "direct_required"})
    data["palettes"]["cat"] = {"kind": "categorical", "cvd_mode": "secondary_encoding",
                               "requires_secondary_encoding": True, "colors": VALID}
    assert pk.registry_verify(str(_write(tmp_path, data))) is False


def test_missing_registry_file_returns_false(tmp_path: Path) -> None:
    assert pk.registry_verify(str(tmp_path / "nope.json")) is False
