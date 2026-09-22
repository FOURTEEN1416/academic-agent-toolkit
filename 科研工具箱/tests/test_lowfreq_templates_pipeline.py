"""三族低频模板（apmcm_zh/mathorcup/wuyi）资产断链修复回归（2026-09-22，G4 批）。

P2 批（c59ffb4）已把 13 套竞赛模板收编进 skills/comp-paper-zh/_templates/，
但 comp-paper-zh SKILL.md 相应分支仍 `cp _templates/<族>/* 2>/dev/null`（吞错静默），
且三族模板 S7 论文步资产指针为空。本文件钉死"资产在位/指针不断链/分支不吞错"，
缩减须显式改本测试（棘轮口径同 test_huawei_pipeline.py）。
"""
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TEMPLATES = json.loads(
    (ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))

FAMILIES = {  # 模板 key -> (_templates 目录名, 期望 documentclass)
    "comp_apmcm_zh": ("apmcm_zh", "MathorCupmodeling"),
    "comp_mathorcup": ("mathorcup", "MathorCupmodeling"),
    "comp_wuyi": ("wuyi", "cumcmthesis"),
}

SKILL_MD = (ROOT / "skills" / "comp-paper-zh" / "SKILL.md").read_text(encoding="utf-8")


def _paper_step(fam):
    return next(s for s in TEMPLATES[fam]["sub_steps"]
                if s["skill_name"] == "comp-paper-zh")


def test_lowfreq_pipeline_keeps_8_steps():
    """三族管线步数与技能链钉死（8 步低频链；缩减须显式改本测试）。"""
    expected = ["comp-prob-analysis", "comp-modeling", "comp-code", "paper-figure",
                "paper-figure-drawio", "comp-review", "comp-paper-zh", "comp-compile-zh"]
    for fam in FAMILIES:
        chain = [s["skill_name"] for s in TEMPLATES[fam]["sub_steps"]]
        assert chain == expected, f"{fam}: {chain}"


def test_lowfreq_paper_step_asset_points_to_vendored_template():
    """S7 论文步资产指针指向在位 _templates 骨架（对齐 huawei 做法）。"""
    for fam, (d, _cls) in FAMILIES.items():
        assets = _paper_step(fam)["metadata"].get("assets") or []
        paths = [a.get("path", "") for a in assets]
        assert any(p.endswith(f"_templates/{d}/main.tex") for p in paths), \
            f"{fam} S7 缺 _templates/{d}/main.tex 资产指针: {paths}"
        for a in assets:
            assert a.get("name") and a.get("path"), f"{fam} 资产缺 name/path: {a}"


def test_lowfreq_template_files_exist():
    """三族 _templates 目录实存 cls+骨架，documentclass 与文档口径一致。"""
    base = ROOT / "skills" / "comp-paper-zh" / "_templates"
    for _fam, (d, cls) in FAMILIES.items():
        assert (base / d).is_dir(), f"缺目录 _templates/{d}/"
        assert any((base / d).glob("*.cls")), f"_templates/{d}/ 缺 .cls"
        main_tex = (base / d / "main.tex").read_text(encoding="utf-8")
        assert r"\documentclass" in main_tex and cls in main_tex, f"{d}/main.tex 非 {cls}"
    assert (base / "wuyi" / "image2.png").is_file(), "五一杯封面图缺位"


def test_lowfreq_assets_all_exist():
    """三族全部资产指针在位（check_template_assets 口径，仓库根相对）。"""
    import check_asset_utilization as cau
    tpl = {f: TEMPLATES[f] for f in FAMILIES}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fp:
        json.dump(tpl, fp, ensure_ascii=False)
        tmp = fp.name
    res = cau.check_template_assets(Path(tmp), ROOT.parent)
    assert res.get("error") is None, res
    assert res["missing"] == [], f"三族失联资产指针: {res['missing']}"


def test_skill_md_branch_fail_fast_no_silent_cp():
    """SKILL.md 三族分支：cp 前显式目录断言，cp 行不再 2>/dev/null 吞错。"""
    for _fam, (d, _cls) in FAMILIES.items():
        cp_re = re.compile(r'^[ \t]*cp "\$TMPL_BASE/' + re.escape(d)
                           + r'/"\* paper/( \|\| \{ [^\n]*exit 1; \})?[ \t]*$', re.M)
        m = cp_re.search(SKILL_MD)
        assert m, f"未找到无吞错的 cp _templates/{d}/ 行（可能仍是 2>/dev/null 式静默）"
        guard = SKILL_MD[max(0, m.start() - 400):m.start()]
        assert f'[ -d "$TMPL_BASE/{d}" ]' in guard, f"{d} 分支缺目录存在性断言"


def test_skill_md_doc_no_stale_missing_claim():
    """文档"尚未入库"段不得再把三族列为缺件（P2 批已收编，2026-09-22 G4 校正）。"""
    for line in SKILL_MD.splitlines():
        if "尚未入库" in line:
            for fam in ("mathorcup", "apmcm_zh", "wuyi"):
                assert fam not in line, f"过时断言仍称 {fam} 未入库: {line.strip()[:80]}"
