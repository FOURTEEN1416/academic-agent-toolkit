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
    """.pyc 直调禁令（2026-09-09 独立审计转化；2026-09-23 v2.0 收尾升级为整仓退役）。

    历史两阶段：①.pyc 作为分发件时，文档不得教学 `python tools/*.pyc` 直调；
    ②v2.0 收尾（Decompyle++ 反编译重建 14 工具真源码 + 行为等价验证后）pyc 整体
    退役——tools/ 下不再允许任何 .pyc 存在（防字节码死灰复燃）。本测试守两道：
    文档不教学直调 + tools/ 零 pyc。"""
    import re
    bad = []
    targets = [ROOT / "AGENTS.md"]
    targets += list((ROOT / "skills").glob("*/SKILL.md"))
    for f in targets:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"python3?\s+[\w/\.-]*?([\w-]+)\.pyc", text):
            bad.append(f"{f.relative_to(ROOT)}: python …{m.group(0)[:60]}")
    assert not bad, "文档教学了 .pyc 直调:\n  " + "\n  ".join(bad)
    # v2.0 收尾：tools/ 下不允许任何 .pyc（真源码已全部重建为 .py）
    leftover = [p.name for p in (ROOT / "tools").glob("*.pyc")
                if "__pycache__" not in p.parts]
    assert not leftover, f"tools/ 下存在 .pyc（已于 v2.0 收尾退役，真源码为同名 .py）: {leftover}"
