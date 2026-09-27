# -*- coding: utf-8 -*-
r"""claim_code_check 合同解析（_parse_contract）竖线分割回归测试。

2026-09-25 huawei2026d 赛时实锤：_parse_contract 用 line.split("|") 分割
METHOD_CLAIMS_MACHINE 合同行，会把 forbid 正则里的裸交替 `(dist|hypot)` 从
中间截断——M4 行被切成 4 段，首段变成字面量 `(dist`（永不匹配任何代码），
造成假 HARD FAIL。修复为 re.split(r'\s+\|\s+', line)：只有两侧带空白的竖线
才是列分隔符，正则内部的裸 `|` 不再被当作分隔符。

本文件三条钉：
  (i)  含裸交替的 forbid 正则必须解析成单条完整 pattern（假 FAIL 根因）；
  (ii) 正常 spaced-pipe 合同行的解析结果不得回归；
  (iii)反向测试——真含降级签名的代码在修复后仍必须被打中（防把门禁修哑）。
"""
import subprocess
import sys
from pathlib import Path

UTILS = Path(__file__).resolve().parent.parent / "skills" / "_utils"
sys.path.insert(0, str(UTILS))
from claim_code_check import _parse_contract  # noqa: E402

SCRIPT = UTILS / "claim_code_check.py"


def _contract(text: str):
    rows = _parse_contract("<!-- METHOD_CLAIMS_MACHINE\n" + text + "\n-->")
    assert len(rows) == 1, f"应解析出 1 条合同，实际 {len(rows)}: {rows}"
    return rows[0]


def test_bare_pipe_alternation_forbid_parsed_as_single_pattern():
    # 实锤原文（huawei2026d M4 行）：forbid 首项正则自带交替裸竖线。
    # 修复前 split("|") → forbid 首项被截成字面量 "(dist"（永不匹配 → 假 FAIL）；
    # 修复后必须是完整的一条 pattern，且 | 两侧无空格的正则原样保留。
    row = _contract(
        r"M4 | must: map_coordinates, interpolate, line_of_sight, los "
        r"| forbid: (dist|hypot)\s*\(.*\)\s*<=\s*R, 固定半径圆"
    )
    assert row["id"] == "M4"
    assert len(row["must"]) == 4
    assert len(row["forbid"]) == 2, f"forbid 应恰好 2 条，实际: {row['forbid']}"
    assert row["forbid"][0] == r"(dist|hypot)\s*\(.*\)\s*<=\s*R"
    assert row["forbid"][1] == "固定半径圆"
    # 截断残留不得出现（防回归到 split("|") 口径）
    assert "(dist" not in row["forbid"]
    assert hypot_tail_not_leaked(row)


def hypot_tail_not_leaked(row) -> bool:
    # split("|") 的另一种截断产物：`\s*\(.*\)\s*<=\s*R` 会作为独立段混进来
    return not any(p.startswith(r"\s*\(") for p in row["forbid"])


def test_normal_spaced_pipe_contract_no_regression():
    # 不含裸竖线的常规行（M2 形态）：语义列/must/forbid 逗号列表解析与修复前一致
    row = _contract(
        "M2 | must: CpModel, AddElement, model\\.Add, BoolVar "
        "| forbid: first_fit_only, FFD.*==.*optimal"
    )
    assert row["id"] == "M2"
    assert row["must"] == [r"CpModel", r"AddElement", r"model\.Add", r"BoolVar"]
    assert row["forbid"] == ["first_fit_only", "FFD.*==.*optimal"]
    # must 与 forbid 同时缺位的行不入库（与修复前一致）
    assert _parse_contract("<!-- METHOD_CLAIMS_MACHINE\nM9 | notes: 无签名\n-->") == []


def test_gate_still_fires_on_real_violation(tmp_path):
    # 反向测试：构造真命中降级签名 (dist|hypot)...<=R 的假代码，修复后闸必须仍 FAIL。
    # 若本条也"通过"，说明门禁被修哑（例如把 forbid 整体吞掉）。
    md = tmp_path / "MODELING_REPORT.md"
    md.write_text(
        "# report\n"
        "<!-- METHOD_CLAIMS_MACHINE\n"
        "M4 | must: map_coordinates, interpolate "
        "| forbid: (dist|hypot)\\s*\\(.*\\)\\s*<=\\s*R, 固定半径圆\n"
        "-->\n",
        encoding="utf-8",
    )
    code = tmp_path / "code"
    code.mkdir()
    (code / "fake_solver.py").write_text(
        "import numpy as np\n"
        "R = 300.0\n"
        "visible = [hypot(x - cx, y - cy) <= R for x, y in points]\n"  # 正是合同禁止的"固定半径圆"降级
        "interpolate = None\n",       # 满足 must，确保 FAIL 只来自 forbid
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--modeling", str(md), "--codedir", str(code)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 1, f"真降级代码必须被拦截，exit={r.returncode}\n{r.stdout}"
    assert "M4" in r.stdout and "forbid" in r.stdout
    # 报出的必须是完整 pattern，而不是截断残段
    assert "(dist|hypot)" in r.stdout
    assert "'(dist'" not in r.stdout


def test_gate_passes_on_compliant_code(tmp_path):
    # 同合同的忠实实现（DEM 视线采样，无固定半径圆）→ exit 0，
    # 钉住"修复只去掉截断假 FAIL，不引入新误报"。
    md = tmp_path / "MODELING_REPORT.md"
    md.write_text(
        "# report\n"
        "<!-- METHOD_CLAIMS_MACHINE\n"
        "M4 | must: map_coordinates, interpolate "
        "| forbid: (dist|hypot)\\s*\\(.*\\)\\s*<=\\s*R, 固定半径圆\n"
        "-->\n",
        encoding="utf-8",
    )
    code = tmp_path / "code"
    code.mkdir()
    (code / "los.py").write_text(
        "from scipy.ndimage import map_coordinates\n"
        "blocked = sample_elevations(path) < los_line\n"
        "interpolate = map_coordinates\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--modeling", str(md), "--codedir", str(code)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, f"忠实实现不应被拦，exit={r.returncode}\n{r.stdout}"


def _m7_run(tmp_path, files: dict):
    """M7 形态合同（forbid: mean\\(）+ 指定 code/ 文件布局，跑 CLI 返回 (exit, stdout)。"""
    md = tmp_path / "MODELING_REPORT.md"
    md.write_text(
        "# report\n"
        "<!-- METHOD_CLAIMS_MACHINE\n"
        "M7 | must: event, sweep, peak | forbid: mean\\(, average_util\n"
        "-->\n",
        encoding="utf-8",
    )
    code = tmp_path / "code"
    for rel, body in files.items():
        p = code / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--modeling", str(md), "--codedir", str(code)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout


def test_scratch_dir_forbid_hit_does_not_fire(tmp_path):
    # 2026-09-25 huawei2026d M7 实锤：forbid `mean\(` 的两处命中全在 code/_tmp/
    # （w4_full_solve.py 等 scratch 分析脚本，非产品实现），_load_code 无排除导致假 FAIL。
    # 修复：codedir 下任一路径段以 `_` 开头（_tmp/、__pycache__/、_x.py，不写死名字）跳过。
    exitcode, out = _m7_run(tmp_path, {
        "main.py": "events = replay()\npeak = concurrency(events)\nsweep(line)\n",
        "_tmp/w4_full_solve.py": "util = data.mean(axis=0)\nprint(util)\n",
        "__pycache__/cached.py": "x = arr.mean()\n",
        "_scratch.py": "y = arr.mean()\n",       # 文件名段同样按 `_` 前缀排除
    })
    assert exitcode == 0, f"scratch 命中不得冒充实现体假 FAIL\n{out}"


def test_scratch_exclusion_does_not_swallow_real_hit(tmp_path):
    # 反向钉：同样的 mean( 出现在非 scratch 正式件里仍必须 FAIL
    # （防把排除逻辑写成 rglob 全盘失效/把门禁修哑）。
    exitcode, out = _m7_run(tmp_path, {
        "main.py": "util = traffic.mean(axis=0)\npeak = util\n",
        "_tmp/w4_full_solve.py": "events = []\n",
    })
    assert exitcode == 1, f"正式件降级签名必须仍被拦截，exit={exitcode}\n{out}"
    assert "M7" in out and "forbid" in out

