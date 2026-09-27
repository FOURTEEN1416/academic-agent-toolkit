"""G2 棘轮：S14 后申报/打包环节两族口径（2026-09-22；2026-09-25 承诺书口径勘误）。

before：comp-cumcm-package（打包沙演 + submission_checklist）与 comp-cumcm-disclosure
（AI 申报）只有国赛专属口径——华为杯链走到 S14 后按国赛清单组包会把"首页判据、
正文 ≤50 页、官方 docx 封面模板"这套 GMCM 要求整个做反。
after：打包脚本 `--compliance-profile` 数据驱动分支（真源 engine/modex-core/comp_rules.json，
与 G1 对 comp-final-audit 的做法同构）；SKILL/清单按族分节；申报机制标注两族通用。
2026-09-25 勘误：官方开赛公告证实华为杯论文模板全无承诺书页（首页为封皮不可删除、
4 logo 不能替换，第二页起为摘要/正文；承诺书为校级材料不入论文）——旧口径
pledge_page=required 系误引不存在的 third_party 覆盖档，已改为 absent_in_official_template。
本文件钉死：承诺书禁含方向不得回退、华为杯文档要素不得丢失、国赛默认口径不得被改动。
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


def _json_of(stdout: str) -> dict:
    """容忍库噪声前缀（如 CI 新版 PyMuPDF 的 fitz deprecation warning 打到 stdout），
    只解析第一段 JSON 文档。"""
    return json.loads(stdout[stdout.index("{"):])


def test_g2_script_profile_loader_matches_rules_source():
    """脚本口径加载器与 comp_rules.json 真源一致；未知键显式报错（不默认、不伪造口径）。

    2026-09-27 收口迁移：加载器收敛为 contest_profile.load_entry（唯一加载器，
    消 profiles 选择路径），旧 mod.load_compliance 名随之废除。"""
    mod = _load_script()
    cp_mod, hw_entry, hw_err = mod.load_entry("comp_huawei")
    _, cm_entry, cm_err = mod.load_entry("comp_cumcm")
    assert hw_err is None and cm_err is None, f"加载器不得对已知键报错: {hw_err} {cm_err}"
    # v2：条目无顶层 compliance 块（口径在 profiles 维度），脚本路径不选档即无视图
    assert not isinstance(hw_entry.get("compliance"), dict)
    assert not isinstance(cm_entry.get("compliance"), dict)
    assert isinstance(hw_entry.get("migration_evidence"), list), "华为历史口径留痕在 migration_evidence"
    _, nobody, nobody_err = mod.load_entry("comp_nobody")
    assert nobody is None and "comp_nobody" in (nobody_err or ""), \
        "未知赛事键必须显式报错，不默认任何赛事"
    assert cp_mod is not None, "加载器必须经 contest_profile 唯一消费路径"
    # 承诺书方向纯函数（v2）：华为 hw-pledge=unknown → SKIP 双向（不冒充任一方向）；
    # 国赛电子版经 resolve_profile 选档后 forbidden → FAIL/PASS 照常
    hw_view = cp_mod.resolve_profile(
        "comp_huawei", {"contest": {"edition": "2026", "submission_form": "electronic"}}).compliance
    cm_view = cp_mod.resolve_profile(
        "comp_cumcm", {"contest": {"edition": "2026", "submission_form": "electronic"}}).compliance
    assert hw_view == {}, "华为 unknown 约束不构造 compliance 视图（不冒充方向）"
    assert cm_view["pledge_page"] == "forbidden_in_electronic"
    pages = ["研究生数学建模竞赛 参赛承诺书 …", "封面", "摘要"]
    assert mod.pledge_verdict(pages, hw_view)[0] == "SKIP"   # 华为杯：unknown 不硬执行任一方向
    assert mod.pledge_verdict(pages, cm_view)[0] == "FAIL"   # 国赛：电子版含承诺书 = 硬失败
    pages2 = ["摘要", "问题重述", "正文"]
    assert mod.pledge_verdict(pages2, hw_view)[0] == "SKIP"
    assert mod.pledge_verdict(pages2, cm_view)[0] == "PASS"


def test_g2_pack_pledge_direction_end_to_end(tmp_path):
    """CLI 端到端（v2 生产 + B 第八轮 pack 修复口径）：
    无 --compliance-profile → 参数错误非零退出（旧默认国赛已删除，不静默按国赛跑）；
    脚本路径不选 profiles 档 → 承诺书/首页判据无口径，显式 SKIP + 人工确认文案，
    回执不冒充 PASS/FAIL——含承诺书页不再 exit 1 硬失败，改钉显式 SKIP；
    回退成"无口径硬判/无旗标默认国赛"的旧口径都会直接打破本测试。"""
    if not HAVE_FITZ:
        import pytest
        pytest.skip("PyMuPDF 不可用，无法构造 PDF 夹具")
    pledge_ws = _mk_ws(tmp_path, "华为杯研究生数学建模竞赛 参赛承诺书", "ws-pledge")
    no_flag = _run(pledge_ws)
    assert no_flag.returncode != 0, "无旗标必须失败（--compliance-profile 已必填）"
    assert "--compliance-profile" in no_flag.stderr + no_flag.stdout
    for prof in ("comp_cumcm", "comp_huawei"):
        rep = _json_of(_run(pledge_ws, "--compliance-profile", prof, "--json").stdout)
        check = rep["paper"]["pledge_check"]
        assert check["verdict"] == "SKIP", f"{prof} 无口径不得冒充判定: {check}"
        assert "人工确认" in check["detail"], check
        assert check["mode"] == "", "未选档不得伪造方向口径"
    abstract_ws = _mk_ws(tmp_path, "摘 要 本文针对问题一", "ws-abstract")
    for prof in ("comp_cumcm", "comp_huawei"):
        rep = _json_of(_run(abstract_ws, "--compliance-profile", prof, "--json").stdout)
        assert rep["paper"]["pledge_check"]["verdict"] == "SKIP"
        assert "形态" in rep["paper"]["page1_abstract_note"], "首页判据未选档须如实不机检"


def test_g2_json_report_carries_explicit_profile(tmp_path):
    """--json 回执 compliance_profile（口径必须显式选择，默认已删除；v2：脚本路径
    未选 profiles 档 → 判据不机检，无 hard_fail 键、不冒充通过；事实陈述照常）。"""
    if not HAVE_FITZ:
        import pytest
        pytest.skip("PyMuPDF 不可用，无法构造 PDF 夹具")
    ws = _mk_ws(tmp_path, "正文第一页没有任何判据标记")
    for prof in ("comp_cumcm", "comp_huawei"):
        rep = _json_of(_run(ws, "--compliance-profile", prof, "--json").stdout)
        assert rep["compliance_profile"] == prof
        assert "hard_fail" not in rep["paper"], rep["paper"]
        assert rep["paper"]["pledge_check"]["verdict"] == "SKIP"
        assert rep["paper"]["page1_has_abstract"] is False  # 事实陈述照常，判读留人工
        assert "形态" in rep["paper"]["page1_abstract_note"]


def test_g2_skill_doc_and_checklist_branch_per_family():
    """文档棘轮：SKILL.md 有口径必填显式语义与两族分支表、官方 docx 模板指针；
    清单 §五 华为杯分节含承诺书方向与当届口径要素，且明示禁止套用国赛要素。

    2026-09-27 收口迁移：SKILL"≤50"断言按新契约废除并加负向棘轮——华为页限
    出全局走任务覆盖通道（v2 候选：官方页限 unknown + migration_evidence 留痕），
    文档不得再钉死页数旧值；清单数字口径的文档修订归 C 窗（IR-E-C1 同批）。"""
    for token in ("--compliance-profile comp_huawei", "comp_rules.json",
                  "口径必须显式选择", "pledge_page: absent_in_official_template",
                  "official_docx"):
        assert token in SKILL_MD, f"SKILL.md 缺两族分支要素: {token}"
    assert "≤50" not in SKILL_MD, "SKILL.md 不得再钉死 50 页旧口径（80 出全局走任务覆盖通道）"
    section = CHECKLIST.split("## 五、")[1] if "## 五、" in CHECKLIST else ""
    assert section, "submission_checklist.md 缺 §五 华为杯（GMCM）差异清单"
    for token in ("全文不含承诺书页", "30-46", "当届", "official_docx"):
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
