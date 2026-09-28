# -*- coding: utf-8 -*-
"""公众号审美批次 2026-09-11 批处理：
1. 读取 raw/NN_raw.md，提取 mmbiz.qpic.cn 图片 URL（按出现顺序去重）
2. 清洗 URL（去 watermark/wx_lazy/webp/碎片，路径 /640 -> /0 优先拿原图）
3. 下载到各文章目录 images/，生成 article.md（本地引用 + 来源映射表）
"""
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"D:\Desktop\参考图\公众号审美批次2026-09-11")
RAW = BASE / "raw"

META = {
    "01": {
        "folder": "01_顶刊配色LPH",
        "title": "顶刊科研绘图配色24——LPH",
        "account": "（配色分享系列号，抓取件未署名）",
        "date": "约 2026-09-10",
        "url": "https://mp.weixin.qq.com/s/5ZI2TRymW1RwjBSyXgwtwA",
    },
    "02": {
        "folder": "02_Codex科研绘图skill方法论",
        "title": "Codex让我的科研绘图提升好几个档次，这个skill神助攻了",
        "account": "AIPaperWrite AI论文写作（作者 Anan0729）",
        "date": "2026-09-01",
        "url": "https://mp.weixin.qq.com/s/HgyVcMlO2X4jONU6UsEE9w",
    },
    "03": {
        "folder": "03_渐变色质感图形",
        "title": "巧用渐变色，打造更有质感的图形",
        "account": "R语言数据分析指南",
        "date": "2026-07-25",
        "url": "https://mp.weixin.qq.com/s/YuKh_Xpnu2w4dea06ZgTrA",
    },
    "04": {
        "folder": "04_Origin顶刊模板图库",
        "title": "Origin这几百个顶刊模板，我直接看傻了...",
        "account": "材料电化学电催化",
        "date": "2026-07-23",
        "url": "https://mp.weixin.qq.com/s/L8umr3VkQfBCQlgwBrdkaw",
    },
    "05": {
        "folder": "05_圆形树状网络图复现",
        "title": "如何轻松绘制漂亮的树状网络图？",
        "account": "SCIPainter（作者 莫北）",
        "date": "2026-09-04",
        "url": "https://mp.weixin.qq.com/s/RX8kDQXO038s4fbp8GEshw",
    },
    "06": {
        "folder": "06_Origin400模板图库",
        "title": "Origin竟然自带400个绘图模板，我以前怕是用了个假软件...",
        "account": "电化学与电催化",
        "date": "2026-07-26",
        "url": "https://mp.weixin.qq.com/s/1vZAQjGorXDLFVyLKpwZiA",
    },
}

IMG_RE = re.compile(r"!\[[^\]]*\]\((https?://mmbiz\.qpic\.cn[^)\s]+)\)")

STRIP_PARAMS = ("watermark", "wx_lazy", "tp", "usePicPrefetch", "wxfrom", "from")


def clean_url(url: str) -> str:
    """去 fragment 与噪声参数；保留 wx_fmt。/640 结尾路径改 /0 以取原图。"""
    url = url.split("#", 1)[0]
    scheme, rest = url.split("://", 1)
    host, path_query = rest.split("/", 1)
    path, _, query = path_query.partition("?")
    path = re.sub(r"/640$", "/0", path)
    if query:
        keep = []
        for kv in query.split("&"):
            key = kv.split("=", 1)[0]
            if key == "wx_fmt" or (key not in STRIP_PARAMS):
                keep.append(kv)
        # 保留 wx_fmt；from=appmsg 也保留（无害）
        query = "&".join(keep)
    return f"{scheme}://{host}/{path}" + (f"?{query}" if query else "")


def ext_of(url: str) -> str:
    m = re.search(r"wx_fmt=(\w+)", url)
    return (m.group(1) if m else "png").lower()


def download(url: str, dest: Path) -> bool:
    variants = []
    if "/0?" in url or url.endswith("/0"):
        variants.append(url)  # 已是 /0
    else:
        variants.append(url)
    # 回退：/0 失败则试回 /640 原样
    fallback = url.replace("/0?", "/640?")
    if fallback != url:
        variants.append(fallback)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }
    for attempt_url in variants:
        for referer in (None, "https://mp.weixin.qq.com/"):
            for _ in range(2):
                try:
                    req = urllib.request.Request(attempt_url)
                    for k, v in headers.items():
                        req.add_header(k, v)
                    if referer:
                        req.add_header("Referer", referer)
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = resp.read()
                    if len(data) > 500:
                        dest.write_bytes(data)
                        return True
                except Exception:
                    time.sleep(1)
    return False


def main():
    report = []
    for num, meta in META.items():
        raw_path = RAW / f"{num}_raw.md"
        text = raw_path.read_text(encoding="utf-8")
        urls = IMG_RE.findall(text)
        seen, ordered = set(), []
        for u in urls:
            cu = clean_url(u)
            if cu not in seen:
                seen.add(cu)
                ordered.append(cu)

        folder = BASE / meta["folder"]
        img_dir = folder / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        mapping, ok, fail = [], 0, []
        for i, cu in enumerate(ordered, 1):
            ext = ext_of(cu)
            fname = f"{i:02d}.{ext}"
            dest = img_dir / fname
            if dest.exists() and dest.stat().st_size > 500:
                success = True
            else:
                success = download(cu, dest)
            if success:
                ok += 1
            else:
                fail.append(cu)
            mapping.append((fname, cu))

        # 重写 markdown：URL -> 本地相对路径
        body = text
        for fname, cu in mapping:
            body = body.replace(f"]({cu})", f"](images/{fname})")
            # 未清洗形态的也兜底替换
            body = re.sub(
                r"\]\(" + re.escape(cu).replace(re.escape("?"), r"\?") + r"[^)]*\)",
                f"](images/{fname})",
                body,
            )

        table = ["| 文件 | 原始 URL |", "|---|---|"]
        table += [f"| images/{f} | {u} |" for f, u in mapping]
        header = (
            f"# {meta['title']}\n\n"
            f"- 公众号：{meta['account']}\n- 发布时间：{meta['date']}\n"
            f"- 原文链接：{meta['url']}\n- 抓取日期：2026-09-11（firecrawl，图片已本地化）\n\n"
            f"配图 {len(ordered)} 张（去重后），下载成功 {ok}，失败 {len(fail)}。\n\n---\n\n"
        )
        footer = "\n\n---\n\n## 图片来源映射\n\n" + "\n".join(table) + "\n"
        (folder / "article.md").write_text(header + body + footer, encoding="utf-8")
        report.append(f"{num} {meta['folder']}: {ok}/{len(ordered)} ok, fail={len(fail)}")
        for f in fail:
            report.append(f"    FAIL {f}")

    print("\n".join(report))
    (BASE / "download_report.txt").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
