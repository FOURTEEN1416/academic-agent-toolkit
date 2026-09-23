"""Skill 触发条件与能力边界审计回归（P3 技能覆盖度件，2026-09-19 建立）。

守护四件事：
  1. 判定逻辑：frontmatter 缺失/name 不匹配/描述超长/near-长描述/无触发信号 逐类可判；
  2. 路由歧义：高重叠 + 无判别说明 → ERROR；有判别说明（互指或双向判别词）→ 放行；
  3. 真仓零缺口：全库 261 技能 frontmatter 合规、无未声明的路由歧义、
     能力目录与技能地图零漏网；
  4. 阈值可调：min_jaccard / min_shared 生效（防"把阈值调到永远通过"）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import skill_trigger_audit as sta  # noqa: E402


def _skill(root: Path, name: str, description: str, fm_name: str | None = None) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {fm_name or name}\ndescription: \"{description}\"\n---\n\n# {name}\n",
        encoding="utf-8",
    )


# ---------- frontmatter / 触发信号 ----------

def test_missing_frontmatter_is_error(tmp_path: Path) -> None:
    d = tmp_path / "bad"
    d.mkdir()
    (d / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    res = sta.audit_skills(tmp_path)
    assert any(e["kind"] == "no_frontmatter" for e in res["errors"])


def test_name_mismatch_is_error(tmp_path: Path) -> None:
    _skill(tmp_path, "alpha", "一个用于审计的技能，当用户要求审计时使用。", fm_name="beta")
    res = sta.audit_skills(tmp_path)
    assert any(e["kind"] == "name_mismatch" for e in res["errors"])


def test_too_long_description_is_error(tmp_path: Path) -> None:
    _skill(tmp_path, "alpha", "x" * 1030 + " 当用户使用时")
    res = sta.audit_skills(tmp_path)
    assert any(e["kind"] == "description_too_long" for e in res["errors"])


def test_short_description_is_warn(tmp_path: Path) -> None:
    _skill(tmp_path, "alpha", "写论文时使用")
    res = sta.audit_skills(tmp_path)
    assert any(w["kind"] == "description_too_short" for w in res["warns"])


def test_missing_trigger_signal_is_warn(tmp_path: Path) -> None:
    _skill(tmp_path, "alpha", "这是一个用于处理各类文档格式转换与批量导出任务的技能集合，覆盖多种输入输出格式。")
    res = sta.audit_skills(tmp_path)
    assert any(w["kind"] == "no_trigger_signal" for w in res["warns"])


def test_trigger_signal_recognised(tmp_path: Path) -> None:
    _skill(tmp_path, "alpha", "文档格式转换。当用户要求批量转换格式时使用。触发词：格式转换。")
    res = sta.audit_skills(tmp_path)
    assert not any(w["kind"] == "no_trigger_signal" for w in res["warns"])


# ---------- 路由歧义 ----------

_OVERLAP_A = ("中文论文写作与排版输出。当用户要求写中文论文、生成 latex 内容、导出 docx 时使用。"
              "覆盖 论文 写作 latex docx export format markdown draft academic content generate")
_OVERLAP_B = ("中文论文写作与排版输出。当用户要求写中文论文、生成 latex 内容、导出 pdf 时使用。"
              "覆盖 论文 写作 latex docx export format markdown draft academic content generate")


def test_undiscriminated_overlap_is_error(tmp_path: Path) -> None:
    _skill(tmp_path, "paper-alpha-zh", _OVERLAP_A)
    _skill(tmp_path, "paper-beta-zh", _OVERLAP_B)
    res = sta.audit_overlaps(sta.audit_skills(tmp_path)["records"], 0.30, 6)
    assert res["candidates"], "高重叠对未被识别"
    assert res["undiscriminated"], "缺判别说明的对未被拦截"


def test_mutual_reference_clears_overlap(tmp_path: Path) -> None:
    _skill(tmp_path, "paper-alpha-zh", _OVERLAP_A + " 需要 pdf 交付时改用 paper-beta-zh。")
    _skill(tmp_path, "paper-beta-zh", _OVERLAP_B + " 区别于 paper-alpha-zh：本技能只出 pdf。")
    res = sta.audit_overlaps(sta.audit_skills(tmp_path)["records"], 0.30, 6)
    assert res["candidates"]
    assert not res["undiscriminated"], res["undiscriminated"]


def test_bidirectional_discriminator_clears_overlap(tmp_path: Path) -> None:
    """双方各自写出"只用于/改用"也算判别成立（不需要互指名字）。"""
    _skill(tmp_path, "x-one", _OVERLAP_A + " 只用于 docx 交付；需 PDF 时换另一技能。")
    _skill(tmp_path, "x-two", _OVERLAP_B + " 只用于 PDF 交付；需 docx 时换另一技能。")
    res = sta.audit_overlaps(sta.audit_skills(tmp_path)["records"], 0.30, 6)
    assert not res["undiscriminated"]


def test_thresholds_are_effective(tmp_path: Path) -> None:
    """阈值提高后原先命中的对必须不再命中（防"阈值形同虚设"）。"""
    _skill(tmp_path, "paper-alpha-zh", _OVERLAP_A)
    _skill(tmp_path, "paper-beta-zh", _OVERLAP_B)
    records = sta.audit_skills(tmp_path)["records"]
    assert sta.audit_overlaps(records, 0.30, 6)["candidates"]
    assert not sta.audit_overlaps(records, 0.99, 6)["candidates"]
    assert not sta.audit_overlaps(records, 0.30, 999)["candidates"]


# ---------- 真仓机检 ----------

def test_real_repo_passes_strict() -> None:
    """真仓必须零 ERROR：frontmatter 合规 + 无未声明歧义 + 目录/地图零漏网。"""
    res = sta.run()
    assert res["ok"], res["errors"]


def test_real_repo_skill_count_matches_map() -> None:
    """技能数与地图/catalog 登记必须一致。

    下限取公开交付口径 255（2026-09-23 v2.0 W3f 合并后本机 255），不硬编码本机数
    （少 5 个无 License 上游技能，被根 .gitignore 有意隔离）——写死 261 等于把
    "完整本地仓"当成交付前提，CI 必红。一致性由下面两条对账保证：
    零漏网 + 零未登记 ⟹ 技能集合 ⊆ 地图 ∩ catalog。
    """
    res = sta.run()
    reg = res["registry"]
    assert reg["skills_total"] >= 255, reg["skills_total"]
    assert reg["missing_in_catalog"] == []
    assert reg["missing_in_map"] == []


def test_real_overlap_candidates_all_discriminated() -> None:
    """真仓里所有高重叠对都必须已声明判别说明。"""
    res = sta.run()
    undiscriminated = [f"{i['a']}×{i['b']}" for i in res["overlap_candidates"] if not i["discriminated"]]
    assert undiscriminated == [], undiscriminated


def test_non_skill_dirs_are_excluded() -> None:
    """_utils / shared-scripts 不是技能（无 SKILL.md 的共享目录），必须排除。"""
    names = sta.iter_skill_names()
    assert "_utils" not in names
    assert "shared-scripts" not in names
