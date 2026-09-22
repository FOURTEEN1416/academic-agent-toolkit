"""G2 棘轮：S14 后申报/打包环节两族口径（2026-09-22）。

before：comp-cumcm-package（打包沙演 + submission_checklist）与 comp-cumcm-disclosure
（AI 申报）只有国赛专属口径——华为杯链走到 S14 后按国赛清单组包会把"承诺书必含、
正文 ≤50 页、官方 docx 封面模板"这套 GMCM 要求整个做反。
after：打包脚本 `--compliance-profile` 数据驱动分支（真源 engine/modex-core/comp_rules.json，
与 G1 对 comp-final-audit 的做法同构）；SKILL/清单按族分节；申报机制标注两族通用。
本文件钉死：承诺书方向不得回退为国赛专属、华为杯文档要素不得丢失、国赛默认口径不得被改动。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "comp-cumcm-package" / "scripts" / "pack_submission.py"
SKILL_MD = (ROOT / "skills" / "comp-cumcm-package" / "SKILL.md").read_text(encoding="utf-8")
CHECKLIST = (ROOT / "skills" / "comp-cumcm-package" / "references"
             / "submission_checklist.md").read_text(encoding="utf-8")
COMP_RULES = json.loads(
    (ROOT / "engine" / "modex-core" / "comp_rules.json").read_text(encoding="utf-8"))

try:
    import fitz  # noqa: F401
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False


def _load_script():
    spec = importlib.util.spec_from_file_location("pack_submission_g2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(workspace: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workspace", str(workspace), *extra],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT))


def _mk_ws(tmp_path: Path, page1_text: str, name: str = "ws") -> Path:
    ws = tmp_path / name
    (ws / "paper").mkdir(parents=True)
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((72, 100), page1_text, fontname="china-s")
    doc.save(ws / "paper" / "main.pdf")
    doc.close()
    return ws


def test_g2_script_profile_loader_matches_rules_source():
    """脚本口径加载器与 comp_rules.json 真源一致；未知族返回 None（不伪造口径）。"""
    mod = _load_script()
    hw = mod.load_compliance("comp_huawei")
    cm = mod.load_compliance("comp_cumcm")
    assert hw == COMP_RULES["comp_huawei"]["compliance"]
    assert cm == COMP_RULES["comp_cumcm"]["compliance"]
    assert mod.load_compliance("comp_nobody") is None
    # 承诺书方向纯函数：同一份"首页含承诺书"文本，国赛 FAIL、华为杯 PASS（禁止同向回退）
    pages = ["研究生数学建模竞赛 参赛承诺书 …", "封面", "摘要"]
    assert mod.pledge_verdict(pages, hw)[0] == "PASS"
    assert mod.pledge_verdict(pages, cm)[0] == "FAIL"
    pages2 = ["摘要", "问题重述", "正文"]
    assert mod.pledge_verdict(pages2, hw)[0] == "FAIL"   # 缺承诺书是华为杯红线
    assert mod.pledge_verdict(pages2, cm)[0] == "PASS"


def test_g2_pack_pledge_direction_end_to_end(tmp_path):
    """CLI 端到端四象限：承诺书页 PDF 在华为杯口径 exit 0、国赛口径 exit 1；
    摘要页 PDF 反之。回退成国赛专属会直接打破本测试。"""
    if not HAVE_FITZ:
        import pytest
        pytest.skip("PyMuPDF 不可用，无法构造 PDF 夹具")
    pledge_ws = _mk_ws(tmp_path, "华为杯研究生数学建模竞赛 参赛承诺书", "ws-pledge")
    assert _run(pledge_ws, "--compliance-profile", "comp_huawei").returncode == 0
    cm = _run(pledge_ws)  # 默认国赛：含承诺书 = 硬失败（旧口径保持）
    assert cm.returncode == 1
    assert "承诺书" in cm.stdout
    abstract_ws = _mk_ws(tmp_path, "摘 要 本文针对问题一", "ws-abstract")
    assert _run(abstract_ws).returncode == 0
    hw2 = _run(abstract_ws, "--compliance-profile", "comp_huawei")
    assert hw2.returncode == 1 and "承诺书" in hw2.stdout


def test_g2_json_report_carries_profile_and_default_unchanged(tmp_path):
    """--json 回执 compliance_profile；默认（无旗标）行为与 G2 之前一致：
    国赛首页摘要硬检查文案原样、20MB 体积线不变。"""
    if not HAVE_FITZ:
        import pytest
        pytest.skip("PyMuPDF 不可用，无法构造 PDF 夹具")
    ws = _mk_ws(tmp_path, "正文第一页没有任何判据标记")
    rep = json.loads(_run(ws, "--json").stdout)
    assert rep["compliance_profile"] == "comp_cumcm"
    assert "摘要专用页" in rep["paper"]["hard_fail"]      # 国赛专属文案不得漂走
    assert rep["paper"]["pledge_check"]["verdict"] == "PASS"
    rep2 = json.loads(_run(ws, "--compliance-profile", "comp_huawei", "--json").stdout)
    assert rep2["compliance_profile"] == "comp_huawei"
    assert rep2["paper"]["pledge_check"]["mode"] == "required"
    assert "摘要专用页" not in str(rep2["paper"].get("hard_fail", ""))  # 国赛首页判据不反套


def test_g2_skill_doc_and_checklist_branch_per_family():
    """文档棘轮：SKILL.md 有 compliance_profile 分支表与官方 docx 模板指针；
    清单 §五 华为杯分节含承诺书必含 + 50 页 + 当届章程为准，且明示禁止套用国赛要素。"""
    for token in ("--compliance-profile comp_huawei", "comp_rules.json",
                  "pledge_page: required", "official_docx", "≤50"):
        assert token in SKILL_MD, f"SKILL.md 缺两族分支要素: {token}"
    section = CHECKLIST.split("## 五、")[1] if "## 五、" in CHECKLIST else ""
    assert section, "submission_checklist.md 缺 §五 华为杯（GMCM）差异清单"
    for token in ("必须含参赛承诺书", "≤50 页", "30-46", "当届", "official_docx"):
        assert token in section, f"§五 缺华为杯口径要素: {token}"
    assert "9/13" not in section, "§五 不得把国赛时间节点当作华为杯口径"


def test_g2_catalog_and_map_no_longer_cumcm_only_for_package():
    """catalog 与地图对打包技能的登记不再国赛专属（触发词与口径注记在位）。"""
    catalog = json.loads((ROOT.parent / "capabilities" / "catalog.json")
                         .read_text(encoding="utf-8"))
    entry = next(it for it in catalog["math_modeling_competition"]
                 if it["capability_id"] == "comp-cumcm-package")
    assert "华为杯" in entry["description"] and "--compliance-profile" in entry["description"]
    map_text = (ROOT / "CONTEST_SKILL_MAP.md").read_text(encoding="utf-8")
    line = next(l for l in map_text.splitlines() if "comp-cumcm-package`（" in l)
    assert "comp_huawei" in line, "地图 §三 打包条目缺华为杯口径注记"
