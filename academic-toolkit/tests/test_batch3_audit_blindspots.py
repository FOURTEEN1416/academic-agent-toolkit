"""批次三 B3-6：断链棘轮四类盲区的行为锁。

① INNER_REF 覆盖 data/ 前缀；② broken_ref 文件级（父目录存在不放行）+ 登记册豁免；
③ 上游版式路径（shared/ docs/ ~/.claude/）显式登记不静默；④ 登记册目录条目有过期台账。
audit() 的 ROOT 指向 tmp 仓库骨架，不触真实 skills/。
"""
import json
import sys
from pathlib import Path


TOOLBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLBOX))

from tools import skill_library_audit as sla  # noqa: E402

FRONTMATTER = "---\nname: {name}\ndescription: audit blindspot fixture\n---\n\n"
# too_small 门禁要求 SKILL.md ≥ 200B，fixture 正文统一补足
PADDING = "本技能为机检行为锁的固定装置，正文补足体积门槛，不参与断链判定。\n\n" * 3


def _make_repo(tmp_path, body: str, name: str = "demo-skill"):
    """搭最小仓库骨架：一个技能 + 空 templates.json。"""
    root = tmp_path / "repo"
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(FRONTMATTER.format(name=name) + PADDING + body, encoding="utf-8")
    tpl = root / "engine" / "modex-core"
    tpl.mkdir(parents=True)
    (tpl / "templates.json").write_text("{}", encoding="utf-8")
    return root, skill


def _audit(root, monkeypatch):
    monkeypatch.setattr(sla, "ROOT", root)
    monkeypatch.setattr(sla, "_load_gap_register", lambda: {})
    return sla.audit()


def test_inner_ref_covers_data_prefix(tmp_path, monkeypatch):
    """① data/ 前缀入机检：技能内缺失 → FAIL；实存 → 放行。"""
    root, skill = _make_repo(
        tmp_path,
        "读 data/exists.json 与 data/missing.json 后综合。\n",
    )
    (skill / "data").mkdir()
    (skill / "data" / "exists.json").write_text("{}", encoding="utf-8")

    rep = _audit(root, monkeypatch)

    broken = rep["failures"].get("broken_inner_ref", [])
    assert any("data/missing.json" in x for x in broken), broken
    assert not any("data/exists.json" in x for x in broken)


def test_broken_ref_is_file_level_with_register_escape(tmp_path, monkeypatch):
    """② REF 通道文件级：父目录存在但文件缺失 → FAIL（旧行为放行）；登记册可豁免。"""
    root, _skill = _make_repo(
        tmp_path,
        "使用 tools/missing_tool.py 处理（tools/ 目录本身存在）。\n",
    )
    (root / "tools").mkdir()
    (root / "tools" / "real_tool.py").write_text("print('x')\n", encoding="utf-8")

    rep = _audit(root, monkeypatch)
    assert any("tools/missing_tool.py" in x for x in rep["failures"].get("broken_ref", []))

    # 登记册存量豁免（B3-6 ②接通登记册）
    monkeypatch.setattr(
        sla, "_load_gap_register",
        lambda: {"demo-skill": ["tools/missing_tool.py"]})
    rep2 = sla.audit()
    assert not rep2["failures"].get("broken_ref"), rep2["failures"]
    assert any("登记册棘轮存量" in x for x in rep2["acknowledged_inner_refs"])


def test_upstream_refs_are_registered_not_failed(tmp_path, monkeypatch):
    """③ 上游版式路径显式登记：shared/ docs/ ~/.claude/ 缺失目标进 upstream_refs，不计 FAIL。"""
    root, _skill = _make_repo(
        tmp_path,
        "遵循 shared/style_canon.md、docs/design/legacy.md 与 ~/.claude/skills/ 约定；"
        "docs/real.md 在仓内实存。\n",
    )
    (root / "docs").mkdir()
    (root / "docs" / "real.md").write_text("x", encoding="utf-8")

    rep = _audit(root, monkeypatch)

    upstream = rep.get("upstream_refs", [])
    assert any("shared/style_canon.md" in x for x in upstream)
    assert any("docs/design/legacy.md" in x for x in upstream)
    assert any("~/.claude/skills/" in x for x in upstream)
    assert not any("docs/real.md" in x for x in upstream), "仓内实存路径不该登记"
    assert rep["ok"] is True, "上游登记不得计入 FAIL"


def test_gap_register_dir_entries_have_expiry_ledger():
    """④ 登记册中目录形态条目必须在 _meta.dir_entry_expiry.expires 有过期台账。"""
    reg = json.loads(
        (TOOLBOX / "tools" / "asset_gap_register.json").read_text(encoding="utf-8"))
    expires = reg["_meta"].get("dir_entry_expiry", {}).get("expires", {})

    def is_dir_entry(e: str) -> bool:
        return e.endswith("/") or "." not in e.rstrip("/").rsplit("/", 1)[-1]

    unledgered = []
    for skill, entries in reg["gaps"].items():
        for e in entries:
            if is_dir_entry(e) and e not in expires.get(skill, {}):
                unledgered.append(f"{skill}: {e}")
    assert not unledgered, f"目录条目缺过期台账: {unledgered}"
