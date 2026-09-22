"""A7-F2 回归测试：pyc_loader 子进程参数相对路径转绝对路径。

敌意审计 A7 实测：run_pyc_native 以 tools/ 为子进程 cwd（payload 数据文件依赖），
调用方按文档用相对路径传图片参数（comp-visual-review Step4.5、paper-figure Step4.5、
paper-figure-drawio Step5.7 均为 `figures/xxx.png` 形态）→ File not found → exit 2，
被管线语义误判为"视觉审核通道不可用"而静默跳过。修复：调用方 cwd 下真实存在的
相对路径参数先转绝对路径再启动子进程；不存在的参数原样保留（保持原报错语义）。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("pyc_loader_under_test", ROOT / "tools" / "pyc_loader.py")
pyc_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pyc_loader)


def test_relative_path_existing_in_caller_cwd_is_absolutized(tmp_path, monkeypatch):
    (tmp_path / "figures").mkdir()
    fig = tmp_path / "figures" / "fig_q1.png"
    fig.write_bytes(b"png")
    monkeypatch.chdir(tmp_path)

    result = pyc_loader.absolutize_caller_paths(["figures/fig_q1.png", "--review"])
    assert result[0] == str(fig), "调用方 cwd 下真实存在的相对路径必须转绝对路径"
    assert result[1] == "--review", "选项参数必须原样保留"


def test_relative_path_missing_stays_verbatim(tmp_path, monkeypatch):
    """不存在的相对路径原样传——保持工具按自身 cwd 报 File not found 的原语义。"""
    monkeypatch.chdir(tmp_path)
    result = pyc_loader.absolutize_caller_paths(["figures/ghost.png"])
    assert result == ["figures/ghost.png"]


def test_absolute_and_flags_pass_through(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    absolute = str(tmp_path / "a.png")
    result = pyc_loader.absolutize_caller_paths([absolute, "--review", "-q", ""])
    assert result[:1] == [absolute]
    assert "--review" in result and "-q" in result


def test_none_and_empty_argv_tolerated():
    assert pyc_loader.absolutize_caller_paths(None) == []
    assert pyc_loader.absolutize_caller_paths([]) == []


def test_drive_anchored_path_pass_through():
    # Windows 盘符锚定路径（如 C:foo）不是绝对路径语义但也不能拼 cwd
    result = pyc_loader.absolutize_caller_paths(["C:foo.png"], caller_cwd="D:/any")
    assert result == ["C:foo.png"]


def test_explicit_caller_cwd_used_without_chdir(tmp_path):
    (tmp_path / "fig.png").write_bytes(b"png")
    other = tmp_path / "other"
    other.mkdir()
    result = pyc_loader.absolutize_caller_paths(["fig.png"], caller_cwd=other)
    assert result == ["fig.png"], "caller_cwd 下不存在的相对路径应原样保留"

    result2 = pyc_loader.absolutize_caller_paths(["fig.png"], caller_cwd=tmp_path)
    assert result2 == [str(tmp_path / "fig.png")]


def test_run_pyc_native_absolutizes_args_and_keeps_tools_cwd(tmp_path, monkeypatch):
    """run_pyc_native：参数转绝对、子进程 cwd 保留为 pyc 所在目录（payload 数据依赖）。"""
    (tmp_path / "fig.png").write_bytes(b"png")
    monkeypatch.chdir(tmp_path)

    pyc = tmp_path / "tools" / "fake_tool.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"fake")

    captured = {}

    def fake_run(cmd, cwd=None, env=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(pyc_loader, "find_py311_venv", lambda: "python311-exe")
    monkeypatch.setattr(subprocess, "run", fake_run)

    import pytest
    with pytest.raises(SystemExit) as exc_info:
        pyc_loader.run_pyc_native(pyc, ["fig.png", "--review"])
    assert exc_info.value.code == 0
    assert captured["cmd"][1] == str(pyc)
    assert captured["cmd"][2] == str(tmp_path / "fig.png"), "存在的相对路径参数必须以绝对路径下发给子进程"
    assert captured["cmd"][3] == "--review"
    assert Path(captured["cwd"]) == pyc.parent, "子进程 cwd 必须保留 tools/（payload 数据文件依赖）"
