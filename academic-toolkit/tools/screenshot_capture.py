# -*- coding: utf-8 -*-
"""通用界面截图工具 — 用 Electron 内嵌 Chromium 给运行中的网页截图。

供 dev-report(报告界面截图)、软著/专利材料等场景复用。契约稳定：
输入 URL/HTML + 输出 PNG 路径，输出真实界面截图（离线，不下载浏览器）。

用法:
  # 探测能力（Electron 是否可用）。可用退出 0，不可用退出 2（调用方据此降级为占位符）
  python screenshot_capture.py --check

  # 单张截图(PNG)
  python screenshot_capture.py --url http://127.0.0.1:19001/ --out figures/shot_home.png

  # 单张出「矢量 PDF」(HTML 流程图 → 论文 \\includegraphics 直接引)：out 用 .pdf 即自动走 pdf，
  # 也可显式 --format pdf。等效 drawio --crop：单页、无白边、真矢量文字。
  python screenshot_capture.py --file figures/fig_roadmap.html --out figures/fig_roadmap.pdf --format pdf

  # 元素级几何自检（只测量不出图，供 HTML 流程图自修复循环用）：
  #   量 .fig 内文字块，报「文字溢出被裁 / 越出画布边界 / 文字块重叠」。退出码 0=干净 1=有问题 2=无法检查。
  python screenshot_capture.py --geom-check figures/fig_flow_q1.html            # 无公式的图
  python screenshot_capture.py --geom-check figures/fig_flow_q1.html --render-math  # 含公式的图

  # 批量（推荐）：--config 指向一个 JSON
  python screenshot_capture.py --config shots.json

shots.json 结构:
  {
    "viewport": {"width": 1280, "height": 800},
    "targets": [
      {"url": "http://127.0.0.1:19001/",          "out": "figures/shot_home.png", "waitMs": 1200},
      {"url": "http://127.0.0.1:19001/login",      "out": "figures/shot_login.png", "waitForSelector": ".login-form"},
      {"file": "D:/proj/code/frontend/index.html", "out": "figures/shot_index.png", "fullPage": true},
      {"file": "D:/proj/figures/fig_flow.html",    "out": "figures/fig_flow.pdf",   "format": "pdf"},
      {"file": "D:/proj/figures/fig_algo.html",    "out": "figures/fig_algo.pdf",   "format": "pdf", "renderMath": true}
    ]
  }

renderMath:true → 截图前注入 KaTeX，把 HTML 里的 \\(...\\)/\\[...\\]/$$ 渲染成真公式（含公式的
流程/算法/架构图用）。素材缺失时自动降级（图仍出，公式不渲染），不阻断。

⛔ format:"pdf"（或 out 以 .pdf 结尾）→ Electron 原生 printToPDF 出矢量 PDF：量内容真实像素，
   页面尺寸设成刚好等于内容，单页无白边、文字可选可搜、无限放大不糊。fullPage 仅对 png 有意义。

退出码: 0=全部成功  1=部分/全部截图失败  2=Electron 不可用(应降级)  3=参数/致命错误

⛔ 全标准库实现，与项目其它 tools 一致，不引第三方。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 本文件是 academic-toolkit/tools/screenshot_capture.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'

_TOTAL_TIMEOUT = 180


def _resolve_electron():
    """返回 (exe, main_script_or_None)。找不到返回 (None, None)。

    优先用后端 config 的 RUNTIME_ELECTRON_*；失败再看环境变量 MH_ELECTRON_EXE/MAIN。
    """
    exe = None
    main = None
    try:
        _backend = Path(__file__).resolve().parent.parent / 'web' / 'backend'
        if str(_backend) not in sys.path:
            sys.path.insert(0, str(_backend))
        import config as _cfg
        exe = getattr(_cfg, 'RUNTIME_ELECTRON_EXE', None)
        main = getattr(_cfg, 'RUNTIME_ELECTRON_MAIN', None)
    except Exception:
        pass
    if not exe:
        exe = os.environ.get('MH_ELECTRON_EXE') or None
        main = os.environ.get('MH_ELECTRON_MAIN') or None
    if exe and Path(exe).exists():
        if main and not Path(main).exists():
            main = None
        return (exe, main)
    return (None, None)


def _capture_dir():
    """capture.js 所在目录（与 electron main.js 同级 desktop/，或打包后 app 内）。

    独立跑 capture.js 时需要它的路径；打包后主 exe 自带，不需要。
    """
    dev = Path(__file__).resolve().parent.parent / 'desktop' / 'capture.js'
    return str(dev) if dev.exists() else None


def run_capture(targets, viewport=None, timeout=_TOTAL_TIMEOUT):
    """执行截图/出图。targets: [{url|file, out, format?, waitMs?, waitForSelector?, fullPage?}]。

    format="pdf"(或 out 以 .pdf 结尾) → 矢量 PDF；否则 PNG。字段整体透传给 capture.js。
    返回 dict: {"ok": bool, "results": [...], "reason": str}
    """
    exe, main = _resolve_electron()
    if not exe:
        return {'ok': False, 'results': [], 'reason': 'electron_unavailable'}

    norm_targets = []
    for t in targets:
        t2 = dict(t)
        if t2.get('out'):
            t2['out'] = str(Path(t2['out']).resolve())
        if t2.get('file'):
            t2['file'] = str(Path(t2['file']).resolve())
        norm_targets.append(t2)

    tmp = Path(tempfile.mkdtemp(prefix='mh_capture_'))
    cfg_path = tmp / 'cfg.json'
    result_path = tmp / 'result.json'
    cfg = {
        'viewport': viewport or {'width': 1280, 'height': 800},
        'resultPath': str(result_path),
        'targets': norm_targets,
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')

    cap_js = _capture_dir()
    cmd = [exe]
    if main is not None:
        if cap_js:
            cmd.append(cap_js)
        else:
            cmd.append(main)
    cmd += ['--mh-capture', str(cfg_path)]

    env = dict(os.environ)
    env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = '1'
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding='utf-8', errors='replace', env=env)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'results': [], 'reason': 'timeout'}
    except Exception as e:
        return {'ok': False, 'results': [], 'reason': 'spawn_failed: %s' % e}

    results = []
    if result_path.exists():
        try:
            results = json.loads(result_path.read_text(encoding='utf-8')).get('results', [])
        except Exception:
            pass
    if not results:
        for t in norm_targets:
            out = t.get('out')
            ok = bool(out) and Path(out).exists() and Path(out).stat().st_size > 1000
            results.append({'ok': ok, 'out': out, 'url': t.get('url') or t.get('file')})

    ok_all = bool(results) and all(r.get('ok') for r in results)
    return {
        'ok': ok_all,
        'results': results,
        'reason': '' if ok_all else 'some_or_all_failed',
        'stderr_tail': (proc.stderr or '')[-500:],
    }


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    ap = argparse.ArgumentParser(prog=PROG, description='通用界面截图工具(Electron capturePage)')
    ap.add_argument('--check', action='store_true', help='仅探测 Electron 是否可用')
    ap.add_argument('--config', help='批量截图配置 JSON 路径')
    ap.add_argument('--url', help='单张：页面 URL')
    ap.add_argument('--file', help='单张：本地 HTML 文件路径')
    ap.add_argument('--out', help='单张：输出路径(.png 截图 / .pdf 矢量)')
    ap.add_argument('--format', choices=['png', 'pdf'], help='单张：输出格式(缺省按 out 后缀推断)')
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=800)
    ap.add_argument('--wait-ms', type=int, default=1000)
    ap.add_argument('--full-page', action='store_true')
    ap.add_argument('--render-math', action='store_true',
                    help='截图前注入 KaTeX 渲染 HTML 里的 \\(...\\)/$$ 公式（含公式的流程/架构图用）')
    ap.add_argument('--geom-check', metavar='HTML',
                    help='元素级几何自检：量 HTML 里 .fig 内文字块，报文字溢出/越界裁切/块重叠。只测量不出图。'
                         '退出码 0=干净 1=有问题 2=无法检查。含公式的图配 --render-math。')
    args = ap.parse_args()

    if args.geom_check:
        one = {'file': args.geom_check, 'geomCheck': True, 'waitMs': args.wait_ms}
        if args.render_math:
            one['renderMath'] = True
        res = run_capture([one], {'width': args.width, 'height': args.height})
        if res.get('reason') == 'electron_unavailable':
            print('electron unavailable — 无法几何自检，跳过（不阻塞）')
            sys.exit(2)
        results = res.get('results') or []
        geom = (results[0].get('geom') if results else None) or {}
        if not geom or geom.get('error'):
            print('⚠ 几何自检无法进行: %s' % (geom.get('error') if geom else '无 .fig 或探针无返回'))
            sys.exit(2)
        overflow = geom.get('overflow') or []
        clip = geom.get('clip') or []
        overlap = geom.get('overlap') or []
        fig = geom.get('fig') or {}
        n = len(overflow) + len(clip) + len(overlap)
        print('=== 几何自检: %s ===' % args.geom_check)
        print(f"画布 {fig.get('w', '?')!s}x{fig.get('h', '?')!s} px, "
              f"文字块 {geom.get('blocks', '?')!s} 个")
        if n == 0:
            print('✅ PASS — 无文字溢出 / 越界 / 重叠')
            sys.exit(0)
        if overflow:
            print('❌ 文字溢出被裁 %d 处（盒子太窄/太矮，文字被切）：' % len(overflow))
            for o in overflow[:12]:
                print(f"   · 「{o.get('txt')!s}」 实宽{o.get('sw')!s}>盒宽{o.get('cw')!s}"
                      f" 实高{o.get('sh')!s}>盒高{o.get('ch')!s}")
        if clip:
            print('❌ 越出 .fig 边界 %d 处（会被论文页面裁掉）：' % len(clip))
            for c in clip[:12]:
                sides = []
                for k, name in (('left', '左'), ('top', '上'), ('right', '右'), ('bottom', '下')):
                    if c.get(k, 0) > 0:
                        sides.append(f'{name!s}越{c[k]!s}px')
                print(f"   · 「{c.get('txt')!s}」 {' '.join(sides)!s}")
        if overlap:
            print('❌ 文字块重叠 %d 对（内容互相压盖）：' % len(overlap))
            for v in overlap[:12]:
                print(f"   · 「{v.get('a')!s}」 ×「{v.get('b')!s}」 交叠面积{v.get('area')!s}px²")
        print('⛔ 共 %d 处几何问题 — 读 HTML 针对性改 CSS 后重检。' % n)
        sys.exit(1)

    if args.check:
        exe, main_js = _resolve_electron()
        if exe:
            print(f'OK electron available: {exe!s}' + (' (+main.js)' if main_js else ''))
            sys.exit(0)
        print('electron unavailable — 截图能力不可用，调用方应降级为占位符')
        sys.exit(2)

    if args.config:
        try:
            cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
        except Exception as e:
            print('配置读取失败: %s' % e)
            sys.exit(3)
        targets = cfg.get('targets') or []
        viewport = cfg.get('viewport')
    else:
        if (args.url or args.file) and args.out:
            one = {'out': args.out, 'waitMs': args.wait_ms}
            if args.url:
                one['url'] = args.url
            else:
                one['file'] = args.file
            if args.format:
                one['format'] = args.format
            if args.full_page:
                one['fullPage'] = True
            if args.render_math:
                one['renderMath'] = True
            targets = [one]
            viewport = {'width': args.width, 'height': args.height}
        else:
            print('需要 --config，或 (--url|--file) + --out')
            sys.exit(3)

    if not targets:
        print('没有截图目标')
        sys.exit(3)

    res = run_capture(targets, viewport)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res['reason'] == 'electron_unavailable':
        sys.exit(2)
    sys.exit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
