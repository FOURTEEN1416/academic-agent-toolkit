import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.runtime_adapter import RuntimePaths


def load_tool(name: str):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_arxiv_offline_fallback_reads_suite_data(monkeypatch, tmp_path):
    module = load_tool("arxiv_miner.py")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "case_patterns.md").write_text("- graph optimization method\n", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(tmp_path / "tools" / "arxiv_miner.py"))

    assert module.offline_fallback("graph") == [{
        "source": "offline_patterns",
        "title": "graph optimization method",
        "summary": "- graph optimization method",
        "url": "data/case_patterns.md",
    }]


def test_arxiv_search_uses_https(monkeypatch):
    module = load_tool("arxiv_miner.py")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" />'

    def urlopen(request, timeout):
        captured["url"] = request.full_url
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    assert module.search_arxiv("test") == []
    assert captured["url"].startswith("https://")


def test_bibtex_checker_scans_each_entry_independently():
    module = load_tool("citation_checker.py")
    content = (
        "@article{first,\n  title={First},\n  author={A},\n  year={2024}\n}\n"
        "@article{second,\n  title={Second},\n  author={B},\n  year={2025}\n}\n"
        "@article{third,\n  author={C},\n  year={2026}\n}\n"
    )

    issues = module.check_bibtex(content)

    assert any("条目 third: 缺 title" in issue["msg"] for issue in issues)


def test_runtime_discovery_combines_suite_and_path_commands(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime" / "texlive" / "bin"
    runtime.mkdir(parents=True)
    suite_xelatex = runtime / "xelatex.exe"
    suite_xelatex.write_text("", encoding="utf-8")
    path_node = tmp_path / "node.exe"
    path_node.write_text("", encoding="utf-8")

    monkeypatch.setattr("engine.runtime_adapter.shutil.which", lambda name: str(path_node) if name == "node" else None)
    discovered = RuntimePaths.discover(tmp_path)

    assert discovered.commands["xelatex"] == suite_xelatex
    assert discovered.commands["node"] == path_node


def test_pyc_not_taught_as_invocation_entry(tmp_path):
    """2026-09-09 独立审计（未验证②转化）：.pyc 是 3.11 编译的字节码分发件，
    版本锁定（本机 3.12 直跑报 Bad magic number）。文档/技能一律不得教学
    `python tools/*.pyc` 直调——真源是同名 .py。本测试防该口径回潮。"""
    import re
    bad = []
    targets = [ROOT / "AGENTS.md", ROOT / "skills" / "CLAUDE.md"]
    targets += list((ROOT / "skills").glob("*/SKILL.md"))
    for f in targets:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"python3?\s+[\w/\.-]*?([\w-]+)\.pyc", text):
            bad.append(f"{f.relative_to(ROOT)}: python …{m.group(0)[:60]}")
    assert not bad, "文档教学了 .pyc 直调（应改为同名 .py 真源）:\n  " + "\n  ".join(bad)
    # 每个 .pyc 必须有同名 .py 真源
    orphans = [p.name for p in (ROOT / "tools").glob("*.pyc")
               if not p.with_suffix(".py").is_file() and "__pycache__" not in p.parts]
    assert not orphans, f"存在无 .py 真源的孤儿 .pyc: {orphans}"
