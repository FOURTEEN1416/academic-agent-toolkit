"""运行时适配器测试（独立系统，不依赖原软件）"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.runtime_adapter import RuntimePaths


def make_fake_runtime(root: Path) -> None:
    for relative in (
        "texlive/bin/xelatex.exe",
        "draw.io/draw.io.exe",
        "node/node.exe",
        "node/npm.cmd",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


def test_suite_runtime_wins_over_path(tmp_path, monkeypatch):
    make_fake_runtime(tmp_path / "runtime")
    monkeypatch.setattr("engine.runtime_adapter.shutil.which", lambda name: f"C:/system/{name}")

    runtime = RuntimePaths.discover(tmp_path)

    assert runtime.source == "suite_runtime"
    assert runtime.command("xelatex") == tmp_path / "runtime/texlive/bin/xelatex.exe"
    assert runtime.command("drawio") == tmp_path / "runtime/draw.io/draw.io.exe"
    assert runtime.command("node") == tmp_path / "runtime/node/node.exe"
    assert runtime.command("npm") == tmp_path / "runtime/node/npm.cmd"


def test_path_is_used_when_suite_runtime_is_missing(tmp_path, monkeypatch):
    fake_path = tmp_path / "fake-bin"
    fake_path.mkdir()
    (fake_path / "xelatex.exe").write_bytes(b"")
    monkeypatch.setattr("engine.runtime_adapter.shutil.which", lambda name: str(fake_path / f"{name}.exe") if name == "xelatex" else None)

    runtime = RuntimePaths.discover(tmp_path)

    assert runtime.source == "PATH"
    assert runtime.command("xelatex") == fake_path / "xelatex.exe"


def test_missing_runtime_reports_capability_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.runtime_adapter.shutil.which", lambda name: None)

    caps = RuntimePaths.discover(tmp_path).capabilities()

    assert caps["suite_runtime"] is False
    assert caps["source"] == "PATH"
    assert caps["commands"]["xelatex"] is False
